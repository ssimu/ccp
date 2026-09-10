#!/usr/bin/env python3
"""Claude Code 상태줄 — 현재 계정과 남은 한도를 항상 보인다. 무엇을 어떻게 보일지는 statusline.conf 로 정한다.

  team:me@example.com │ 주간 ██░░░ 21% ↻3일22시간 │ 세션 █░░░░ 16% ↻4시간34분 │ Fable 5.1 │ ~/proj │ ctx 22% │ git main [*2]

입력: Claude Code 가 stdin 으로 주는 JSON. 한도는 rate_limits(five_hour / seven_day, 첫 응답 뒤부터)에서 읽으므로
      /usage 를 따로 부르지 않는다 — 렌더마다 비용이 없다. 계정 이메일은 rate_limits 에 없어 프로필의 .claude.json 에서 읽는다.
설정: $CCP_CONFIG_DIR/statusline.conf (없으면 기본값). 항목 설명은 statusline.example.conf.
      $CCP_CONFIG_DIR/statusline.sh 가 있으면 이 파일 대신 그것을 실행한다 — 완전히 다른 상태줄을 쓰고 싶은 사람용.
문구: ccp_i18n.py (CCP_LANG).
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CFG_DIR = os.environ.get("CCP_CONFIG_DIR") or os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "ccp")

# ── 설정 ────────────────────────────────────────────────────────────────────
DEFAULTS = {
    "segments":   "account quota model dir ctx git",
    "format":     "",                 # 비어 있지 않으면 segments/separator 대신 이 틀을 쓴다
    "separator":  " │ ",
    "account":    "{profile}:{email}",
    "quota":      "weekly session model",   # model = Fable 같은 모델 전용 주간 한도 (ccp 캐시에서)
    "model_quota_ttl": "10",          # 캐시가 이보다 오래(분)됐으면 백그라운드로 다시 조회
    "model_quota_bg":  "yes",         # no 면 캐시만 읽고 조회는 ccp 메뉴에 맡긴다
    "percent":    "used",             # used | left
    "bar":        "5",                # 막대 칸 수. 0 = 막대 없음
    "bar_chars":  "█░",
    "show_reset": "yes",
    "thresholds": "70 90",            # 노랑 / 빨강 (사용률 기준)
    "color":      "yes",
    "dir":        "short",            # short(~/…) | name(마지막 폴더만) | full
    "ctx":        "ctx {pct}%",
    "git":        "git {branch}{changes}",
    "lang":       "",                 # 비우면 CCP_LANG / 로케일
}


def load_conf(path):
    conf = dict(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r"([A-Za-z_]+)\s*=\s*(.*)$", line)
                if not m:
                    continue
                k, v = m.group(1).lower(), m.group(2).strip()
                # 따옴표로 감싼 값은 닫는 따옴표까지, 아니면 # 앞까지. 그 뒤는 주석으로 버린다.
                if v[:1] in ("\"", "'"):
                    q = v[0]; end = v.find(q, 1)
                    v = v[1:end] if end > 0 else v[1:]
                else:
                    v = v.split("#", 1)[0].rstrip()
                if k in conf:
                    conf[k] = v
    except OSError:
        pass
    return conf


def yes(v):
    return str(v).strip().lower() in ("1", "yes", "y", "true", "on")


CONF = load_conf(os.path.join(CFG_DIR, "statusline.conf"))
if CONF["lang"]:
    os.environ["CCP_LANG"] = CONF["lang"]
elif not os.environ.get("CCP_LANG"):
    # Claude Code 를 ccp.zsh 를 거치지 않은 셸(IDE 등)에서 띄우면 CCP_LANG 이 없다. config.zsh 에 적힌 값을 읽는다.
    try:
        m = re.search(r"^\s*(?:export\s+)?CCP_LANG=[\"']?(\w+)", open(os.path.join(CFG_DIR, "config.zsh"), encoding="utf-8").read(), re.M)
        if m: os.environ["CCP_LANG"] = m.group(1)
    except OSError:
        pass

try:
    from ccp_i18n import t, left as i18n_left
except Exception:   # 사전을 못 찾아도 상태줄은 죽지 않아야 한다
    _F = {"default": "default", "nologin": "not logged in", "weekly": "weekly", "session": "session", "sl_no_limits": "quota not yet reported"}
    def t(k, lang=None, **kw): return _F.get(k, k)
    def i18n_left(m, lang=None):
        if m is None: return ""
        if m <= 0: return "soon"
        d, h, mm = m // 1440, (m % 1440) // 60, m % 60
        return f"{d}d{h}h" if d else f"{h}h{mm}m" if h else f"{mm}m"

COLOR = yes(CONF["color"])
try:
    TH_Y, TH_R = [int(x) for x in CONF["thresholds"].split()[:2]]
except Exception:
    TH_Y, TH_R = 70, 90
try:
    BARW = max(0, int(CONF["bar"]))
except Exception:
    BARW = 5
FULL, EMPTY = (CONF["bar_chars"] + "█░")[0], (CONF["bar_chars"] + "█░")[1]
DIM = "2"


def C(s, code):
    return f"\033[{code}m{s}\033[0m" if (COLOR and code) else s


def col(used):
    if used is None: return DIM
    return "1;31" if used >= 100 else "31" if used >= TH_R else "33" if used >= TH_Y else "32"


def bar(used):
    if BARW <= 0: return ""
    if used is None: return C("·" * BARW, DIM) + " "
    f = max(0, min(BARW, int(round(used / 100 * BARW))))
    if used > 0 and f == 0: f = 1
    return C(FULL * f, col(used)) + C(EMPTY * (BARW - f), DIM) + " "


# ── 입력 ────────────────────────────────────────────────────────────────────
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}

# ── 조각 ────────────────────────────────────────────────────────────────────
def seg_account():
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    if cfg:
        acct_file = os.path.join(cfg, ".claude.json"); profile = os.path.basename(cfg.rstrip("/"))
    else:
        acct_file = os.path.expanduser("~/.claude.json"); profile = t("default")
    email = ""
    try:
        email = (json.load(open(acct_file)).get("oauthAccount") or {}).get("emailAddress") or ""
    except Exception:
        pass
    if not email:
        return f"{profile}:" + C(t("nologin"), "33")
    return CONF["account"].format(profile=profile, email=email, user=email.split("@")[0], domain=email.split("@")[-1])


def quota_one(label, w):
    if not w or w.get("used_percentage") is None:
        return None
    used = int(round(w["used_percentage"]))
    shown = 100 - used if CONF["percent"].lower() == "left" else used
    s = f"{label} " + bar(used) + C(f"{shown}%", col(used))
    r = w.get("resets_at")
    if r and yes(CONF["show_reset"]):
        s += C(" ↻" + i18n_left(max(0, int(round((r - time.time()) / 60)))), DIM)
    return s


def seg_weekly():
    return quota_one(t("weekly"), (d.get("rate_limits") or {}).get("seven_day"))


def seg_session():
    return quota_one(t("session"), (d.get("rate_limits") or {}).get("five_hour"))


def _profile_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or ""


def _refresh_in_background():
    """캐시가 낡았을 때 ccp_usage.py refresh 를 떼어 놓고 돌린다. 락으로 한 번만."""
    lock = os.path.join(CFG_DIR, "cache", "refresh-" + (os.path.basename(_profile_dir().rstrip("/")) or "default") + ".lock")
    try:
        os.makedirs(os.path.dirname(lock), exist_ok=True)
        if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 120:
            return                                   # 이미 도는 중(2분 안)
        fd = os.open(lock, os.O_CREAT | os.O_WRONLY | os.O_TRUNC); os.close(fd)
        # 끝나면 락을 지우도록 셸로 감싼다. 상태줄 프로세스와 분리(start_new_session).
        cmd = f'python3 "{os.path.join(HERE, "ccp_usage.py")}" refresh "{_profile_dir()}"; rm -f "{lock}"'
        subprocess.Popen(["bash", "-c", cmd], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, env=dict(os.environ, CCP_CONFIG_DIR=CFG_DIR))
    except Exception:
        pass


def seg_model_quota():
    """Fable 같은 모델 전용 주간 한도. Claude Code 의 rate_limits 에는 없어 ccp 의 /usage 캐시에서 읽는다."""
    try:
        import ccp_usage
    except Exception:
        return None
    try:
        ttl = float(CONF["model_quota_ttl"]) * 60
    except Exception:
        ttl = 600
    row, age = ccp_usage.read_cache(_profile_dir())
    stale = row is None or age > ttl
    if stale and yes(CONF["model_quota_bg"]) and not os.environ.get("CCP_STATUSLINE_TEST_NO_BG"):
        _refresh_in_background()
    if row is None or row[6] != "ok" or not row[4] or not row[5].strip().lstrip("-").isdigit():
        return None
    used = int(row[5])
    shown = 100 - used if CONF["percent"].lower() == "left" else used
    s = f"{row[4]} " + bar(used) + C(f"{shown}%", col(used))
    if row[1].isdigit() and yes(CONF["show_reset"]):
        # 캐시 시점의 '남은 분'에서 지난 시간을 뺀다
        left_min = max(0, int(row[1]) - int(age // 60))
        s += C(" ↻" + i18n_left(left_min), DIM)
    if stale:
        s += C("~", DIM)                              # 낡은 값 표시. 다음 렌더쯤 갱신된다
    return s


def seg_quota():
    parts = []
    for w in CONF["quota"].split():
        f = {"weekly": seg_weekly, "session": seg_session, "model": seg_model_quota}.get(w)
        s = f() if f else None
        if s: parts.append(s)
    return CONF["separator"].join(parts) if parts else C(t("sl_no_limits"), DIM)


def seg_model():
    return (d.get("model") or {}).get("display_name") or None


def _cwd():
    return (d.get("workspace") or {}).get("current_dir") or d.get("cwd") or ""


def seg_dir():
    cwd = _cwd()
    if not cwd: return None
    mode = CONF["dir"].lower()
    if mode == "name": return os.path.basename(cwd.rstrip("/")) or cwd
    if mode == "full": return cwd
    home = os.path.expanduser("~")
    return "~" + cwd[len(home):] if cwd.startswith(home) else cwd


def seg_ctx():
    used = (d.get("context_window") or {}).get("used_percentage")
    if used is None: return None
    pct = int(round(used))
    return CONF["ctx"].format(pct=C(f"{pct}", col(used)))


def seg_git():
    cwd = _cwd()
    if not cwd: return None
    try:
        env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
        br = subprocess.run(["git", "-C", cwd, "branch", "--show-current"], capture_output=True, text=True, timeout=1, env=env)
        if br.returncode != 0: return None
        branch = br.stdout.strip() or "detached"
        st = subprocess.run(["git", "-C", cwd, "status", "--porcelain"], capture_output=True, text=True, timeout=2, env=env).stdout.splitlines()
        mod = sum(1 for l in st if l.startswith(" M")); add = sum(1 for l in st if l.startswith("A")); unt = sum(1 for l in st if l.startswith("??"))
        ind = (f"*{mod}" if mod else "") + (f"+{add}" if add else "") + (f"?{unt}" if unt else "")
        return CONF["git"].format(branch=branch, changes=f" [{ind}]" if ind else "")
    except Exception:
        return None


SEGS = {"account": seg_account, "quota": seg_quota, "weekly": seg_weekly, "session": seg_session, "model_quota": seg_model_quota,
        "model": seg_model, "dir": seg_dir, "ctx": seg_ctx, "git": seg_git}


def render():
    if CONF["format"]:
        vals = {k: (f() or "") for k, f in SEGS.items()}
        try:
            return CONF["format"].format(**vals)
        except (KeyError, IndexError, ValueError):
            return "statusline.conf: format 오류 / bad format — " + CONF["format"]
    out = []
    for name in CONF["segments"].split():
        f = SEGS.get(name)
        s = f() if f else None
        if s: out.append(s)
    return CONF["separator"].join(out)


if __name__ == "__main__":
    sys.stdout.write(render())
