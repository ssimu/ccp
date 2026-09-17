"""ccp_link — 워크트리 기록 연동 · 프로필 간 공유 이관 · 다른 프로필이 잡은 세션 찾기.

전부 임시 디렉터리에서 돈다. 실제 ~/.claude 는 건드리지 않는다.
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ccp_link  # noqa: E402


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


@pytest.fixture
def short():
    """짧은 임시 경로 — pytest 의 tmp_path 는 테스트 이름이 들어가 폴더 이름 64자 상한을 넘는다."""
    d = Path(tempfile.mkdtemp(prefix="ccp", dir="/tmp"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def repo(short):
    """메인 체크아웃 proj 와 linked worktree wt/feat (하위 폴더 sub 포함)."""
    tmp_path = short
    main = tmp_path / "proj"
    (main / "sub").mkdir(parents=True)
    (main / "sub" / "f.txt").write_text("x")
    git(main, "init", "-q")
    git(main, "add", "-A")
    git(main, "commit", "-qm", "init")
    wt = tmp_path / "wt" / "feat"
    wt.parent.mkdir()
    git(main, "worktree", "add", "-q", str(wt), "-b", "feat")
    return main.resolve(), wt.resolve()


@pytest.fixture
def homes(tmp_path):
    """기본 홈 .claude 와 프로필 둘(a, b). projects 는 공유 심링크."""
    base = tmp_path / "home" / ".claude"
    (base / "projects").mkdir(parents=True)
    profs = tmp_path / "home" / ".claude-profiles"
    for n in ("a", "b"):
        (profs / n).mkdir(parents=True)
        (profs / n / "projects").symlink_to(base / "projects")
    return base, profs


# ── 폴더 이름 ────────────────────────────────────────────────────────────
def test_이름은_영숫자_밖을_전부_대시로():
    assert ccp_link.encode("/Users/x/projects/hourse_bet") == "-Users-x-projects-hourse-bet"
    assert ccp_link.encode("/w/문서화") == "-w----"


def test_워크트리_루트는_메인_체크아웃_이름을_낸다(repo):
    main, wt = repo
    assert ccp_link.project_name(str(wt)) == ccp_link.encode(str(main))


def test_워크트리_하위_폴더는_메인의_같은_하위_폴더로(repo):
    main, wt = repo
    assert ccp_link.project_name(str(wt / "sub")) == ccp_link.encode(str(main / "sub"))


def test_메인_체크아웃과_git_밖에서는_아무것도_안_낸다(repo, tmp_path):
    main, _ = repo
    assert ccp_link.project_name(str(main)) is None
    assert ccp_link.project_name(str(tmp_path)) is None


def test_64자를_넘으면_포기한다(tmp_path):
    """Claude Code 가 이 환경변수에 ^[A-Za-z0-9_-]{1,64}$ 만 받는다 — 넘는 이름은 무시되므로 주지 않는다."""
    main = tmp_path / ("p" * 70)
    main.mkdir()
    (main / "f").write_text("x")
    git(main, "init", "-q"); git(main, "add", "-A"); git(main, "commit", "-qm", "i")
    wt = tmp_path / "w"
    git(main, "worktree", "add", "-q", str(wt), "-b", "b")
    assert ccp_link.project_name(str(wt)) is None


# ── 프로필 간 공유(file-history · paste-cache) ──────────────────────────
def test_프로필의_file_history를_기본_홈으로_합치고_심링크로_바꾼다(homes):
    base, profs = homes
    (base / "file-history" / "s0").mkdir(parents=True)
    (base / "file-history" / "s0" / "k@v1").write_text("base")
    (profs / "a" / "file-history" / "s0").mkdir(parents=True)
    (profs / "a" / "file-history" / "s0" / "k@v1").write_text("프로필 것 — 덮으면 안 된다")
    (profs / "a" / "file-history" / "s0" / "k@v2").write_text("v2")
    (profs / "a" / "file-history" / "s1").mkdir()
    (profs / "a" / "file-history" / "s1" / "z@v1").write_text("z")
    (profs / "a" / "paste-cache").mkdir()
    (profs / "a" / "paste-cache" / "h.txt").write_text("붙여넣기")

    rep = ccp_link.share_profiles(base, profs)

    for item in ("file-history", "paste-cache"):
        assert (profs / "a" / item).is_symlink() and (profs / "a" / item).resolve() == (base / item).resolve()
        assert (profs / "b" / item).is_symlink(), "디렉터리가 없던 프로필에도 링크를 만든다"
    assert (base / "file-history" / "s0" / "k@v1").read_text() == "base", "이미 있는 파일은 덮지 않는다"
    assert (base / "file-history" / "s0" / "k@v2").read_text() == "v2"
    assert (base / "file-history" / "s1" / "z@v1").read_text() == "z"
    assert (base / "paste-cache" / "h.txt").read_text() == "붙여넣기"
    assert rep["moved"] == 3 and rep["kept"] == 1


def test_공유_이관은_두_번_돌려도_같다(homes):
    base, profs = homes
    (profs / "a" / "file-history" / "s").mkdir(parents=True)
    (profs / "a" / "file-history" / "s" / "f").write_text("1")
    ccp_link.share_profiles(base, profs)
    rep = ccp_link.share_profiles(base, profs)
    assert rep["moved"] == 0 and rep["linked"] == 0
    assert (base / "file-history" / "s" / "f").read_text() == "1"


def test_dry_run은_아무것도_안_바꾼다(homes):
    base, profs = homes
    (profs / "a" / "file-history" / "s").mkdir(parents=True)
    (profs / "a" / "file-history" / "s" / "f").write_text("1")
    rep = ccp_link.share_profiles(base, profs, dry=True)
    assert rep["moved"] == 1
    assert not (profs / "a" / "file-history").is_symlink() and not (base / "file-history").exists()


# ── 워크트리 기록 이관 ───────────────────────────────────────────────────
def session(folder, sid, cwd):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{sid}.jsonl").write_text(
        json.dumps({"type": "mode"}) + "\n" + json.dumps({"type": "user", "cwd": cwd, "sessionId": sid}) + "\n")


def test_워크트리_폴더의_기록을_메인_폴더로_옮긴다(repo, homes):
    main, wt = repo
    base, profs = homes
    src = base / "projects" / ccp_link.encode(str(wt))
    session(src, "s1", str(wt))
    (src / "s1" / "subagents").mkdir(parents=True)
    (src / "s1" / "subagents" / "a.jsonl").write_text("{}")
    dst = base / "projects" / ccp_link.encode(str(main))
    session(dst, "m1", str(main))

    rep = ccp_link.migrate_projects(base, profs)

    assert (dst / "s1.jsonl").exists() and (dst / "s1" / "subagents" / "a.jsonl").exists()
    assert (dst / "m1.jsonl").exists()
    assert not src.exists(), "다 옮겼으면 빈 폴더를 남기지 않는다"
    assert rep["moved"] == 2 and rep["folders"] == 1


def test_같은_이름이_이미_있으면_옮기지_않고_남긴다(repo, homes):
    main, wt = repo
    base, profs = homes
    src = base / "projects" / ccp_link.encode(str(wt))
    session(src, "dup", str(wt))
    dst = base / "projects" / ccp_link.encode(str(main))
    session(dst, "dup", str(main))
    before = (dst / "dup.jsonl").read_text()
    rep = ccp_link.migrate_projects(base, profs)
    assert (dst / "dup.jsonl").read_text() == before and (src / "dup.jsonl").exists()
    assert rep["conflicts"] == 1


def test_메인_체크아웃_폴더와_사라진_경로는_건드리지_않는다(repo, homes):
    main, _ = repo
    base, profs = homes
    a = base / "projects" / ccp_link.encode(str(main))
    session(a, "m", str(main))
    b = base / "projects" / "-gone-wt"
    session(b, "g", "/gone/wt")
    rep = ccp_link.migrate_projects(base, profs)
    assert (a / "m.jsonl").exists() and (b / "g.jsonl").exists()
    assert rep["moved"] == 0 and rep["gone"] == ["-gone-wt"]


def test_지워진_워크트리의_기록은_사람이_짚어_주면_옮긴다(repo, homes):
    main, _ = repo
    base, profs = homes
    b = base / "projects" / "-gone-wt"
    session(b, "g", "/gone/wt")
    rep = ccp_link.migrate_projects(base, profs, maps={"-gone-wt": str(main)})
    assert (base / "projects" / ccp_link.encode(str(main)) / "g.jsonl").exists() and not b.exists()
    assert rep["gone"] == [] and rep["moved"] == 1


def live(cfg, pid, sid, cwd, kind="interactive", name="n"):
    (cfg / "sessions").mkdir(parents=True, exist_ok=True)
    (cfg / "sessions" / f"{pid}.json").write_text(
        json.dumps({"pid": pid, "sessionId": sid, "cwd": cwd, "kind": kind, "name": name}))


def test_살아_있는_세션이_있는_폴더는_옮기지_않는다(repo, homes):
    """도는 세션의 기록 파일을 옮기면 그 프로세스가 옛 자리에 새로 써서 대화가 둘로 갈린다."""
    main, wt = repo
    base, profs = homes
    src = base / "projects" / ccp_link.encode(str(wt))
    session(src, "s1", str(wt))
    live(profs / "a", os.getpid(), "s1", str(wt))
    rep = ccp_link.migrate_projects(base, profs)
    assert (src / "s1.jsonl").exists() and rep["busy"] == [src.name]


# ── 다른 프로필이 잡은 세션 ──────────────────────────────────────────────
def test_다른_프로필의_백그라운드_세션을_알려_준다(homes, tmp_path):
    base, profs = homes
    cwd = str(tmp_path)
    live(profs / "a", os.getpid(), "bg1", cwd, kind="bg", name="머지")
    got = ccp_link.owners(base, profs, cwd, me=str(profs / "b"))
    assert got == [("a", "bg", "bg1", "머지")]


def test_내_프로필_것과_죽은_프로세스와_남의_대화형은_빼_준다(homes, tmp_path):
    base, profs = homes
    cwd = str(tmp_path)
    live(profs / "b", os.getpid(), "mine", cwd, kind="bg")
    live(profs / "a", 2 ** 22 + 12345, "dead", cwd, kind="bg")          # 없는 pid
    live(base, os.getpid(), "inter", cwd, kind="interactive")          # 병행 세션은 평소 일이다
    assert ccp_link.owners(base, profs, cwd, me=str(profs / "b")) == []


def test_이어가려는_세션이_다른_프로필에서_살아_있으면_종류와_무관하게_알린다(homes, tmp_path):
    base, profs = homes
    live(base, os.getpid(), "abc-123", "/elsewhere", kind="interactive", name="x")
    got = ccp_link.owners(base, profs, str(tmp_path), me=str(profs / "b"), resume="abc-123")
    assert got == [("default", "interactive", "abc-123", "x")]
