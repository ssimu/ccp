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
  ccp_link.py sessions --me <설정디렉터리|''> [-n N] [--id <세션ID 앞자리>] [폴더]
                                                 이 폴더(와 같은 저장소의 다른 워크트리)에서 나눈 대화를 최근순 TSV 로:
                                                 경로·세션ID·시각·브랜치·제목·잡은 프로필·종류·이어진 세션·크기·내 계정에서 열림·수정 epoch.
                                                 --id 는 앞자리로 하나를 집는다(없으면 1, 여럿이면 2 로 끝나며 후보를 stderr 에)
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



# ── 이 폴더의 대화 목록 — 계정을 바꿔 가져오기(fork) 위해 ─────────────────────
HEAD_BYTES, TAIL_BYTES = 65536, 262144     # 기록은 수십 MB 까지 크다. 앞뒤만 읽어도 제목·브랜치·이어짐은 다 나온다
TITLE_LEN = 40


def session_folders(base, cwd):
    """cwd 의 대화가 쌓여 있을 수 있는 기록 폴더들 — 자기 폴더, 메인 체크아웃 폴더, 같은 저장소의 다른 워크트리 폴더.

    Orca 같은 도구는 브랜치마다 워크트리를 만들어 거기서 대화하므로, 메인에서 띄워도 그 대화들을 고를 수 있어야 한다.
    """
    cwd = real(cwd)
    names = [encode(cwd)]
    pn = project_name(cwd)
    if pn:
        names.append(pn)
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5)
        top = real(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None
        if top:
            rel = os.path.relpath(cwd, top)
            r = subprocess.run(["git", "-C", cwd, "worktree", "list", "--porcelain"], capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                if line.startswith("worktree "):
                    w = real(line[len("worktree "):])
                    names.append(encode(w if rel == "." else os.path.join(w, rel)))
    except (OSError, subprocess.SubprocessError):
        pass
    out, seen = [], set()
    for n in names:
        p = os.path.join(str(base), "projects", n)
        if n not in seen and os.path.isdir(p):
            seen.add(n)
            out.append(p)
    return out


def _ends(path):
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        head = fh.read(HEAD_BYTES)
        if size > HEAD_BYTES + TAIL_BYTES:
            fh.seek(size - TAIL_BYTES)
            tail = fh.read()
        else:
            tail = head + fh.read()
    return head.decode("utf-8", "replace"), tail.decode("utf-8", "replace")


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _one_line(s):
    return " ".join(str(s).split())[:TITLE_LEN]


def scan_session(path):
    """기록 파일 하나 → {sid, path, mtime, title, branch, continued_in}. 대화 행이 없는 껍데기면 None.

    껍데기: 세션을 백그라운드로 넘길 때 Claude Code 가 제목만 적어 둔 파일. 그걸 이어받으면 빈 대화가 열린다.
    """
    try:
        head, tail = _ends(path)
    except OSError:
        return None
    if '"parentUuid"' not in head and '"parentUuid"' not in tail:
        return None
    info = {"path": path, "sid": os.path.basename(path)[:-len(".jsonl")], "mtime": os.path.getmtime(path),
            "size": os.path.getsize(path), "title": "", "branch": "", "continued_in": "", "holder": "", "holder_kind": "", "open": ""}
    for line in reversed(tail.splitlines()):          # 마지막 줄부터 — 제목·브랜치는 최신 것이 맞다
        if not info["title"] and '"aiTitle"' in line:            # 키 이름으로 건다 — 콜론 뒤 공백 유무에 흔들리지 않게
            info["title"] = _one_line(_field(line, "aiTitle"))
        if not info["branch"] and '"gitBranch"' in line:
            info["branch"] = _one_line(_field(line, "gitBranch"))
        if not info["continued_in"] and '"continuedInSessionId"' in line:
            info["continued_in"] = _field(line, "continuedInSessionId")
        if info["title"] and info["branch"] and info["continued_in"]:
            break
    if not info["title"] or not info["branch"]:
        for line in head.splitlines():
            if not info["branch"] and '"gitBranch"' in line:
                info["branch"] = _one_line(_field(line, "gitBranch"))
            if not info["title"] and '"user"' in line:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if o.get("type") != "user" or o.get("isMeta") or o.get("isCompactSummary"):
                    continue
                txt = _text((o.get("message") or {}).get("content")).strip()
                if txt and not txt.startswith("<"):   # <local-command-…> 같은 내부 표식은 제목이 아니다
                    info["title"] = _one_line(txt)
            if info["title"] and info["branch"]:
                break
    return info


def _field(line, key):
    try:
        v = json.loads(line).get(key)
    except ValueError:
        return ""
    return v if isinstance(v, str) else ""


def sessions(base, profs, cwd, me="", limit=10):
    """이 폴더에서 나눈 대화, 최근순.

    holder = 지금 띄우려는 프로필(me) 말고 **다른** 프로필이 잡고 있으면 그 이름(정리 안내 대상).
    open   = me 자신이 지금 열어 둔 세션이면 그 프로필 이름(알림만 — 복사본으로 가져와도 엉키지 않는다).
    """
    me = real(me) if me else real(base)
    held, mine = {}, {}
    for label, cfg, o in live_sessions(base, profs):
        if not o.get("sessionId"):
            continue
        if real(cfg) != me:
            held[o["sessionId"]] = (label, o.get("kind") or "")
        else:
            mine[o["sessionId"]] = label
    files = []
    for folder in session_folders(base, cwd):
        for f in os.listdir(folder):
            if f.endswith(".jsonl"):
                p = os.path.join(folder, f)
                try:
                    files.append((os.path.getmtime(p), p))
                except OSError:
                    pass
    out = []
    for _, p in sorted(files, reverse=True):
        info = scan_session(p)
        if not info:
            continue
        info["holder"], info["holder_kind"] = held.get(info["sid"], ("", ""))
        info["open"] = mine.get(info["sid"], "")
        out.append(info)
        if limit and len(out) >= limit:
            break
    return out


def resolve_session(base, profs, cwd, prefix):
    """세션 ID(앞자리도 됨) → (기록 파일 경로, []) . 없으면 (None, []), 여럿이면 (None, [앞 8자…])."""
    hits = []
    for folder in session_folders(base, cwd):
        for f in os.listdir(folder):
            if f.endswith(".jsonl") and f[:-len(".jsonl")].startswith(prefix):
                hits.append(os.path.join(folder, f))
    exact = [h for h in hits if os.path.basename(h)[:-len(".jsonl")] == prefix]
    if exact:
        return exact[0], []
    if len(hits) == 1:
        return hits[0], []
    return None, [os.path.basename(h)[:8] for h in hits]


def session_row(info):
    import time
    when = time.strftime("%m-%d %H:%M", time.localtime(info["mtime"]))
    return "\t".join([info["path"], info["sid"], when, info["branch"], info["title"],
                      info["holder"], info["holder_kind"], info["continued_in"],
                      str(info.get("size", "")), info.get("open", ""), str(int(info["mtime"]))])


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
    if cmd == "sessions":
        me, n, sid, cwd = "", 10, None, os.getcwd()
        it = iter(rest)
        for a in it:
            if a == "--me":
                me = next(it, "")
            elif a == "-n":
                n = int(next(it, "10") or 10)
            elif a == "--id":
                sid = next(it, None)
            else:
                cwd = a
        base, profs = base_dir(), profiles_dir()
        if sid is not None:
            path, more = resolve_session(base, profs, cwd, sid)
            if path is None:
                if more:
                    print(" ".join(sorted(more)), file=sys.stderr)
                    return 2
                return 1
            info = scan_session(path)
            if not info:
                return 1
            me_r = real(me) if me else real(base)
            for label, cfg, o in live_sessions(base, profs):
                if o.get("sessionId") != info["sid"]:
                    continue
                if real(cfg) != me_r:
                    info["holder"], info["holder_kind"] = label, o.get("kind") or ""
                else:
                    info["open"] = label
            print(session_row(info))
            return 0
        for info in sessions(base, profs, cwd, me=me, limit=n):
            print(session_row(info))
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
