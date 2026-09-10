#!/bin/bash
# Claude Code 상태줄 — 지금 어느 계정으로, 한도가 얼마나 남았는지를 항상 보인다.
#
#   amc-team:me@example.com │ 주간 ██░░░ 21% ↻3일22시간 │ 세션 █░░░░ 16% ↻4시간34분 │ Fable 5.1 │ ~/proj │ ctx 22% │ git main *2
#
# 여러 계정을 ccp 로 오가면 "지금 이 창이 어느 계정인지"가 늘 헷갈린다. 그래서 계정을 맨 앞에 둔다.
# 한도는 Claude Code 가 stdin JSON 의 rate_limits 로 직접 넘겨준다(five_hour / seven_day, 첫 응답 뒤부터).
#   → ccp 처럼 /usage 를 부르지 않으므로 렌더마다 비용이 없다.
# 계정 이메일은 rate_limits 에 없다. 프로필의 .claude.json(oauthAccount) 에서 읽는다.
#   프로필 세션이면 CLAUDE_CONFIG_DIR 이 잡혀 있고, 기본 세션이면 ~/.claude.json 이다.
# 색: 70% 노랑, 90% 빨강, 100% 굵은 빨강 — ccp 메뉴와 같은 기준.
# 의존: python3 (ccp 자체가 요구한다). jq 는 필요 없다.
exec python3 -c '
import json, os, sys, time, subprocess

try: d = json.load(sys.stdin)
except Exception: d = {}

def C(s, code): return f"\033[{code}m{s}\033[0m" if code else s
DIM = "2"

# ── 계정 ──────────────────────────────────────────────────────────────────
cfg = os.environ.get("CLAUDE_CONFIG_DIR")
if cfg:
    acct_file = os.path.join(cfg, ".claude.json"); profile = os.path.basename(cfg.rstrip("/"))
else:
    acct_file = os.path.expanduser("~/.claude.json"); profile = "기본"
email = ""
try:
    email = (json.load(open(acct_file)).get("oauthAccount") or {}).get("emailAddress") or ""
except Exception:
    pass
acct = f"{profile}:{email}" if email else f"{profile}:" + C("미로그인", "33")

# ── 한도 ──────────────────────────────────────────────────────────────────
def left(secs):
    m = max(0, int(round(secs / 60)))
    if m <= 0: return "곧"
    dd, hh, mm = m // 1440, (m % 1440) // 60, m % 60
    if dd: return f"{dd}일{hh}시간"
    if hh: return f"{hh}시간{mm}분"
    return f"{mm}분"
def col(p):
    if p is None: return DIM
    return "1;31" if p >= 100 else "31" if p >= 90 else "33" if p >= 70 else "32"
def bar(p, n=5):
    if p is None: return C("·" * n, DIM)
    f = max(0, min(n, int(round(p / 100 * n))))
    if p > 0 and f == 0: f = 1
    return C("█" * f, col(p)) + C("░" * (n - f), DIM)
def quota(label, w):
    if not w or w.get("used_percentage") is None: return None
    p = int(round(w["used_percentage"])); r = w.get("resets_at")
    s = f"{label} {bar(p)} " + C(f"{p}%", col(p))
    if r: s += C(f" ↻{left(r - time.time())}", DIM)
    return s
rl = d.get("rate_limits") or {}
parts = [acct]
q = [x for x in (quota("주간", rl.get("seven_day")), quota("세션", rl.get("five_hour"))) if x]
parts += q if q else [C("한도 조회 전", DIM)]   # 첫 응답 전이거나 API 키 사용자면 rate_limits 가 없다

# ── 모델 · 디렉터리 · 컨텍스트 ──────────────────────────────────────────────
model = (d.get("model") or {}).get("display_name") or ""
if model: parts.append(model)
cwd = (d.get("workspace") or {}).get("current_dir") or d.get("cwd") or ""
home = os.path.expanduser("~")
if cwd.startswith(home): cwd = "~" + cwd[len(home):]
if cwd: parts.append(cwd)
used = (d.get("context_window") or {}).get("used_percentage")
if used is not None: parts.append("ctx " + C(f"{int(round(used))}%", col(used)))

# ── git ────────────────────────────────────────────────────────────────────
real_cwd = (d.get("workspace") or {}).get("current_dir") or d.get("cwd") or ""
if real_cwd:
    try:
        env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
        br = subprocess.run(["git", "-C", real_cwd, "branch", "--show-current"], capture_output=True, text=True, timeout=1, env=env)
        if br.returncode == 0:
            branch = br.stdout.strip() or "detached"
            st = subprocess.run(["git", "-C", real_cwd, "status", "--porcelain"], capture_output=True, text=True, timeout=2, env=env).stdout.splitlines()
            mod = sum(1 for l in st if l.startswith(" M")); add = sum(1 for l in st if l.startswith("A")); unt = sum(1 for l in st if l.startswith("??"))
            ind = (f"*{mod}" if mod else "") + (f"+{add}" if add else "") + (f"?{unt}" if unt else "")
            parts.append("git " + branch + (f" [{ind}]" if ind else ""))
    except Exception:
        pass

sys.stdout.write(C(" │ ", DIM).join(parts))
'
