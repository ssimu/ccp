#!/usr/bin/env python3
"""대화 기록 연동 — 워크트리와 메인 체크아웃, 그리고 프로필과 프로필 사이.

Claude Code 는 기록을 `<설정 디렉터리>/projects/<실행 폴더 경로를 바꾼 이름>/` 에 둔다. 그래서 끊기는 곳이 둘이다.

  1) 폴더: 같은 저장소라도 linked worktree(예: Orca 가 만드는 ~/orca/workspaces/<repo>/<이름>)에서 띄우면
     다른 폴더에 쌓여 메인 체크아웃의 /resume 목록에 안 나온다.
     → CLAUDE_CODE_PROJECT_DIR_NAME 으로 메인 체크아웃의 폴더 이름을 준다. Claude Code(2.1.234+)는 이 변수를
       **CLAUDE_CONFIG_DIR 이 있을 때만**, 그리고 ^[A-Za-z0-9_-]{1,64}$ 일 때만 받는다(settings.json 의 env 로는 무시).
       그래서 ccp 프로필로 띄울 때만 되고 기본 프로필(~/.claude)에는 길이 없다.
  2) 프로필: projects 는 공유하지만 file-history(되감기용 파일 백업)·paste-cache(붙여넣은 원문)는 프로필마다
     따로라, 계정을 바꿔 이어가면 되감기가 죽는다. 둘 다 세션 ID·내용 해시가 이름이라 섞일 일이 없다 → 공유한다.
     sessions/·jobs/·daemon 은 **공유하지 않는다** — 백그라운드 데몬이 계정 인증에 묶여 있다. 대신 다른 프로필이
     잡고 있는 세션을 실행 전에 알려 준다(owners).

명령:
  ccp_link.py name [폴더]                         워크트리면 메인 체크아웃의 폴더 이름, 아니면 출력 없음
  ccp_link.py owners --me <설정디렉터리|''> [--resume <세션ID>] [폴더]
                                                 다른 프로필이 잡은 세션을 TSV(프로필·종류·세션ID·이름)로
  ccp_link.py migrate [-n]                        기존 프로필·기존 워크트리 기록을 한 번 옮긴다(-n 은 보기만)
  ccp_link.py migrate [-n] --map <기록폴더이름> <메인 체크아웃 경로>
                                                 이미 지워진 워크트리의 기록 — git 에 물을 수 없으니 어디로 합칠지 직접 알려 준다
"""
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ccp_i18n import t  # noqa: E402

SHARED = ("file-history", "paste-cache")           # 프로필 간에 공유해도 안전한 것
NAME_OK = re.compile(r"^[A-Za-z0-9_-]{1,64}$")      # Claude Code 가 받는 폴더 이름
RESERVED = re.compile(r"^(?:con|prn|aux|nul|com[0-9]|lpt[0-9])$", re.I)
OLD = ".ccp-old"                                    # 합치고 남은 것(이름이 겹쳐 못 옮긴 파일)을 두는 곳
DEFAULT = "default"


def base_dir():
    return os.path.join(os.path.expanduser("~"), ".claude")


def profiles_dir():
    return os.environ.get("CLAUDE_PROFILES") or os.path.join(os.path.expanduser("~"), ".claude-profiles")


def real(p):
    return unicodedata.normalize("NFC", os.path.realpath(str(p)))


def encode(path):
    """Claude Code 의 폴더 이름 규칙 — 영문·숫자가 아닌 글자는 전부 '-'. (한글 세 글자 폴더는 '---' 가 된다.)"""
    return re.sub(r"[^A-Za-z0-9]", "-", unicodedata.normalize("NFC", str(path)))


def project_name(cwd):
    """cwd 가 linked worktree 안이면 메인 체크아웃의 같은 위치가 쓸 폴더 이름. 그 밖에는 None."""
    cwd = real(cwd)
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir", "--show-toplevel"],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = r.stdout.splitlines()
    if r.returncode != 0 or len(lines) != 2:
        return None
    common, top = real(lines[0]), real(lines[1])
    if os.path.basename(common) != ".git":          # bare 저장소·서브모듈은 '메인 체크아웃'이 없다
        return None
    main = os.path.dirname(common)
    if main == top:                                 # 메인 체크아웃 자신
        return None
    rel = os.path.relpath(cwd, top)
    name = encode(main if rel == "." else os.path.join(main, rel))
    if not NAME_OK.match(name) or RESERVED.match(name):
        return None                                 # 넘겨도 Claude Code 가 무시한다 — 기록이 갈리느니 주지 않는다
    return name


# ── 옮기기 공통 ──────────────────────────────────────────────────────────
def merge(src, dst, dry=False):
    """src 안의 것을 dst 로 옮긴다. 이미 있는 이름은 덮지 않는다(둘 다 폴더면 안으로 들어간다). → (옮김, 남김)"""
    moved = kept = 0
    for name in sorted(os.listdir(src)):
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if not os.path.lexists(d):
            if not dry:
                os.makedirs(dst, exist_ok=True)
                shutil.move(s, d)
            moved += 1
        elif os.path.isdir(s) and not os.path.islink(s) and os.path.isdir(d):
            m, k = merge(s, d, dry)
            moved, kept = moved + m, kept + k
            if not dry and not os.listdir(s):
                os.rmdir(s)
        else:
            kept += 1
    return moved, kept


def profile_dirs(profs):
    if not os.path.isdir(profs):
        return []
    return [os.path.join(profs, n) for n in sorted(os.listdir(profs)) if os.path.isdir(os.path.join(profs, n))]


def share_profiles(base, profs, dry=False):
    """프로필마다 SHARED 를 기본 홈 것으로 합치고 심링크로 바꾼다. 멱등."""
    base, profs = str(base), str(profs)
    rep = {"moved": 0, "kept": 0, "linked": 0, "leftover": []}
    for p in profile_dirs(profs):
        for item in SHARED:
            target, link = os.path.join(base, item), os.path.join(p, item)
            if os.path.islink(link):
                continue
            had = os.path.isdir(link)
            old = link + OLD
            if not dry:
                os.makedirs(target, exist_ok=True)
                if had:
                    os.rename(link, old)            # 먼저 자리를 비우고 링크부터 세운다 — 도는 세션이 쓸 곳이 끊기는 틈을 줄인다
                os.symlink(target, link)
            rep["linked"] += 1
            if had:
                m, k = merge(link if dry else old, target, dry)
                rep["moved"] += m
                rep["kept"] += k
                if not dry:
                    if k:
                        rep["leftover"].append(old)
                    else:
                        shutil.rmtree(old)
    return rep


# ── 살아 있는 세션 ───────────────────────────────────────────────────────
def alive(pid):
    try:
        os.kill(int(pid), 0)
    except PermissionError:
        return True
    except (OSError, ValueError, TypeError, OverflowError):
        return False
    return True


def live_sessions(base, profs):
    """→ [(프로필이름, 설정디렉터리, 세션 dict)] — pid 가 살아 있는 것만."""
    out = []
    for label, cfg in [(DEFAULT, str(base))] + [(os.path.basename(p), p) for p in profile_dirs(str(profs))]:
        sdir = os.path.join(cfg, "sessions")
        if not os.path.isdir(sdir):
            continue
        for f in sorted(os.listdir(sdir)):
            if not f.endswith(".json"):
                continue
            try:
                with open(os.path.join(sdir, f), encoding="utf-8") as fh:
                    o = json.load(fh)
            except (OSError, ValueError):
                continue
            if isinstance(o, dict) and alive(o.get("pid")):
                out.append((label, cfg, o))
    return out


def owners(base, profs, cwd, me="", resume=None):
    """지금 띄우려는 프로필(me) 말고 다른 프로필이 잡고 있는 세션.

    알리는 것은 둘뿐이다: 이 폴더의 **백그라운드** 세션(데몬이 계속 쥐고 있다), 그리고 --resume 으로 집은 바로 그 세션.
    같은 폴더에서 남의 대화형 세션이 도는 것은 평소 일(병행 작업)이라 알리지 않는다.
    """
    me = real(me) if me else real(base)
    here = real(cwd)
    got = set()
    for label, cfg, o in live_sessions(base, profs):
        if real(cfg) == me:
            continue
        sid = o.get("sessionId") or ""
        if (resume and sid == resume) or (o.get("kind") == "bg" and o.get("cwd") and real(o["cwd"]) == here):
            got.add((label, o.get("kind") or "", sid, o.get("name") or ""))
    return sorted(got)


# ── 워크트리 기록 이관 ───────────────────────────────────────────────────
def folder_cwd(folder):
    """그 기록 폴더의 세션들이 처음 뜬 실행 폴더. 최근 파일부터 앞 200줄만 본다."""
    files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".jsonl")]
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh):
                    if i >= 200:
                        break
                    if '"cwd"' not in line:
                        continue
                    try:
                        c = json.loads(line).get("cwd")
                    except ValueError:
                        continue
                    if c:
                        return c
        except OSError:
            continue
    return None


def migrate_projects(base, profs, dry=False, maps=None):
    """워크트리 이름으로 쌓인 기록 폴더를 메인 체크아웃 폴더로 합친다. 멱등.

    maps = {기록폴더이름: 메인 체크아웃 경로} — 실행 폴더가 사라져 git 에 물을 수 없는 것을 사람이 짚어 준 것.
    """
    maps = {k: encode(real(v)) for k, v in (maps or {}).items()}
    base = str(base)
    root = os.path.join(base, "projects")
    rep = {"moved": 0, "conflicts": 0, "folders": 0, "busy": [], "gone": [], "plan": []}
    if not os.path.isdir(root):
        return rep
    lives = live_sessions(base, profs)
    busy_names = {encode(real(o["cwd"])) for _, _, o in lives if o.get("cwd")}
    busy_sids = {o.get("sessionId") for _, _, o in lives}
    for name in sorted(os.listdir(root)):
        folder = os.path.join(root, name)
        if os.path.islink(folder) or not os.path.isdir(folder):
            continue
        if name in maps:
            target = maps[name]
        else:
            cwd = folder_cwd(folder)
            if not cwd:
                continue
            if not os.path.isdir(cwd):
                rep["gone"].append(name)            # 워크트리였는지 git 에 물을 수 없다 — 옮기지 않고 알리기만 한다(--map)
                continue
            target = project_name(cwd)
        if not target or target == name:
            continue
        if name in busy_names or any(os.path.exists(os.path.join(folder, f"{s}.jsonl")) for s in busy_sids if s):
            rep["busy"].append(name)                # 도는 세션의 파일을 옮기면 옛 자리에 새로 써서 대화가 갈린다
            continue
        m, k = merge(folder, os.path.join(root, target), dry)
        rep["moved"] += m
        rep["conflicts"] += k
        rep["folders"] += 1
        rep["plan"].append((name, target, m, k))
        if not dry and not os.listdir(folder):
            os.rmdir(folder)
    return rep


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "name":
        n = project_name(rest[0] if rest else os.getcwd())
        if n:
            print(n)
        return 0
    if cmd == "owners":
        me, resume, cwd = "", None, os.getcwd()
        it = iter(rest)
        for a in it:
            if a == "--me":
                me = next(it, "")
            elif a == "--resume":
                resume = next(it, None)
            else:
                cwd = a
        for row in owners(base_dir(), profiles_dir(), cwd, me=me, resume=resume):
            print("\t".join(row))
        return 0
    if cmd == "migrate":
        dry = "-n" in rest or "--dry-run" in rest
        maps, it = {}, iter(rest)
        for a in it:
            if a == "--map":
                k, v = next(it, None), next(it, None)
                if not k or not v or not os.path.isdir(os.path.expanduser(v)):
                    print(t("ln_map_bad", name=k or "", path=v or ""), file=sys.stderr)
                    return 2
                maps[k.rstrip("/").split("/")[-1]] = os.path.expanduser(v)
        base, profs = base_dir(), profiles_dir()
        if dry:
            print(t("ln_dry"))
        s = share_profiles(base, profs, dry)
        print(t("ln_share", linked=s["linked"], moved=s["moved"], kept=s["kept"]))
        for p in s["leftover"]:
            print(t("ln_leftover", path=p))
        p = migrate_projects(base, profs, dry, maps)
        for src, dst, m, k in p["plan"]:
            print(t("ln_folder", src=src, dst=dst, moved=m, kept=k))
        print(t("ln_projects", folders=p["folders"], moved=p["moved"], kept=p["conflicts"]))
        for n in p["busy"]:
            print(t("ln_busy", name=n))
        if p["gone"]:
            print(t("ln_gone", n=len(p["gone"])))
            for n in p["gone"]:
                print("    " + n)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
