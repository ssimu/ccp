#!/usr/bin/env python3
"""claude 계정의 한도를 `/usage` 로 읽어 ccp 공용 TSV 한 줄로 낸다. 결과는 캐시에 남겨 상태줄이 같이 쓴다.

왜 /usage 인가: Claude Code 가 상태줄에 넘겨주는 rate_limits 에는 세션(5시간)·주간(전 모델)만 있고
**모델 전용 주간 한도(예: Fable)** 가 없다. 그건 /usage 출력에만 나온다. /usage 는 사용량 API 조회라
모델을 부르지 않는다(모델 턴 0 · 비용 0 — README 참조). 다만 3초쯤 걸리므로 상태줄은 매번 부르지 않고
캐시를 읽고, 오래됐으면 백그라운드에서 한 번 갱신한다.

TSV 12칸 (ccp_render.py · ccp_codex.py 와 같다):
  0 주간%  1 주간리셋(분)  2 세션%(API가 세션 한도를 안 주면 빈칸 = '미보고')  3 세션리셋(분)  4 모델명  5 모델%
  6 상태(ok/stale/nologin/fail)  7 주간리셋시각  8 세션리셋시각  9 주간창(분)  10 세션창(분)  11 메모

명령:
  ccp_usage.py menu [프로필디렉터리]         계정이 일치하는 스냅숏 즉시 표시 + 필요시 백그라운드 갱신
  ccp_usage.py probe [프로필디렉터리]        직접 조회 → stdout 한 줄 + 캐시 갱신 (진단용)
  ccp_usage.py refresh [프로필디렉터리]      조회 → 캐시만 갱신, 출력 없음 (상태줄이 백그라운드로 부른다)
  ccp_usage.py cache-path [프로필디렉터리]   그 프로필의 캐시 파일 경로
프로필 디렉터리를 비우면 기본 프로필(~/.claude.json).
"""
import datetime
import json
import os
import re
import subprocess
import sys
import time
import math
import fcntl
import tempfile

FIELDS = 12
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def config_dir():
    return os.environ.get("CCP_CONFIG_DIR") or os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "ccp")


def profile_name(profile_dir):
    return os.path.basename(profile_dir.rstrip("/")) if profile_dir else "default"


def cache_path(profile_dir):
    return os.path.join(config_dir(), "cache", f"usage-{profile_name(profile_dir)}.tsv")


def probe_dir():
    """/usage 프로브를 돌릴 전용 빈 디렉터리.

    Claude Code 는 실행된 cwd 마다 ~/.claude/projects/<cwd슬러그>/ 에 세션 기록을 남긴다.
    프로브를 홈에서 돌리면 그 기록이 홈의 프로젝트 디렉터리에 쌓인다 — 계정 수 × 10분마다
    한 개씩이라 수백 개가 된다. /resume 은 그걸 entrypoint=sdk-cli 로 걸러 보여주지는 않지만,
    목록을 열 때마다 전부 읽어야 해서 느려지고 디스크만 먹는다. 그래서 전용 폴더에서 돌린다.
    """
    d = os.path.join(config_dir(), "probe")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        return os.path.expanduser("~")
    return d


def auth_file(profile_dir):
    # 기본 프로필의 설정은 ~/.claude.json(홈 바로 아래)이다. CLAUDE_CONFIG_DIR=~/.claude 로 부르면 못 찾는다.
    return os.path.join(profile_dir, ".claude.json") if profile_dir else os.path.expanduser("~/.claude.json")


def keychain_locked():
    """macOS 에서 로그인 키체인을 열 수 없는 맥락인지 — SSH 세션, 데스크톱 세션 밖에서 띄운 launchd 작업 등.

    거기서 claude 를 띄우면 키체인 대신 <프로필>/.credentials.json 에 토큰을 돌린다. 그러면 파일과 키체인의
    refresh 토큰이 어긋나고, 다음에 어느 한쪽이 갱신을 시도할 때 서버가 토큰 묶음을 통째로 무효화해
    멀쩡하던 로그인까지 끊긴다(실제로 12시간마다 SSH 로 도는 점검이 이 길을 밟았다). 그래서 잠긴 맥락에서는
    claude 를 띄우지 않는다. `security` 가 "User interaction is not allowed" 를 낼 때만 잠김으로 본다 —
    키체인 파일이 없거나 다른 오류면 평소처럼 진행한다. 알고 하는 거면 CCP_SKIP_KEYCHAIN_CHECK=1.
    """
    if sys.platform != "darwin" or os.environ.get("CCP_SKIP_KEYCHAIN_CHECK") == "1":
        return False
    kc = os.path.join(os.environ.get("HOME") or os.path.expanduser("~"), "Library/Keychains/login.keychain-db")
    if not os.path.exists(kc):
        return False
    try:
        r = subprocess.run(["security", "show-keychain-info", kc], capture_output=True, text=True, timeout=5)
    except Exception:
        return False
    return r.returncode != 0 and "interaction is not allowed" in ((r.stderr or "") + (r.stdout or "")).lower()


def logged_in(profile_dir):
    try:
        return bool((json.load(open(auth_file(profile_dir))).get("oauthAccount") or {}).get("emailAddress"))
    except Exception:
        return False


def _parse_reset(text, now):
    # print 모드 형식: 'resets Sep 8 at 1:19am (Asia/Seoul)'
    #   정각이면 분 생략('11pm'), 연도가 바뀌면 'Jan 2, 2027 at 1:19am' 처럼 연도가 붙는다.
    m = re.search(r"resets ([A-Z][a-z]{2}) (\d+)(?:, (\d{4}))? at (\d+)(?::(\d+))?(am|pm)", text)
    if not m:
        return None
    mo, d, yr = MONTHS.get(m.group(1), 0), int(m.group(2)), m.group(3)
    h, mi, ap = int(m.group(4)), int(m.group(5) or 0), m.group(6)
    if ap == "pm" and h != 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    try:
        dt = datetime.datetime(int(yr) if yr else now.year, mo, d, h, mi)
    except ValueError:
        return None
    # 연도가 없을 때 과거로 나오면 내년으로 본다(연말 경계).
    if not yr and (now - dt).days > 180:
        dt = dt.replace(year=now.year + 1)
    return dt


def parse(text, now=None):
    """/usage 출력 → TSV 한 줄. 순수 함수 — 테스트 대상."""
    now = now or datetime.datetime.now()

    def row(pat):
        m = re.search(pat + r"([^\n]*)", text)
        if not m:
            return None, None
        line = m.group(1)
        pc = re.search(r"(\d+)% used", line)
        return (int(pc.group(1)) if pc else None), _parse_reset(line, now)

    w, wdt = row(r"Current week \(all models\):")
    s, sdt = row(r"Current session:")
    mm = re.search(r"Current week \((?!all models)([^)]+)\):([^\n]*)", text)
    mn = mp = None
    if mm:
        mn = mm.group(1)
        pc = re.search(r"(\d+)% used", mm.group(2))
        mp = int(pc.group(1)) if pc else None

    # 분은 반올림 — 버림이면 '1:19am 리셋'이 22:37에 2시간41분으로 나와 1분 어긋나 보인다.
    def mins(dt):
        return "" if dt is None else str(max(int(round((dt - now).total_seconds() / 60)), 0))

    def stamp(dt):
        return "" if dt is None else dt.strftime("%m/%d %H:%M")

    def num(v):
        return "" if v is None else str(v)

    if w is None and s is None:
        return "\t".join([""] * 6 + ["fail"] + [""] * 5)
    # claude 는 7일/5시간 창 고정. 뒤 세 칸은 codex 와 형식을 맞추려고 붙인다.
    # 세션 줄이 없으면 빈칸으로 둔다 = '미보고'. 2026-11-07: 쓰고 있는 계정(imok)에도 API 가 세션 항목을 아예 안 줬는데
    # 그걸 0% 로 꾸미니 "새 창 · 5시간 전부 남음" 으로 떠서 틀렸다. 렌더러가 '세션 미보고' 로 적는다(조회 실패와 다른 글).
    return "\t".join([num(w), mins(wdt), num(s), mins(sdt), mn or "", num(mp), "ok", stamp(wdt), stamp(sdt), "10080", "300", ""])


STALE_AFTER = 1800   # 초. 이 넘게 묵은 스냅숏만 '낡음' 표시 — 주간 한도는 느리게 움직이므로 5분은 너무 공격적이었다(전부 낡음으로 떠서 추천·그래프에서 빠짐)


def fetch(profile_dir, timeout=20):
    """claude -p /usage 를 돌려 원문을 돌려준다. 실패하면 ''."""
    env = dict(os.environ)
    for key in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
                "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
                "CLAUDE_CODE_USE_FOUNDRY", "CLAUDECODE"):
        env.pop(key, None)
    # 프로필 세션 안에서 부르면 CLAUDE_CONFIG_DIR 이 환경에 남아 자식이 물려받는다. 기본 프로필은 반드시 지운다.
    if profile_dir:
        env["CLAUDE_CONFIG_DIR"] = profile_dir
    else:
        env.pop("CLAUDE_CONFIG_DIR", None)
    # /usage 는 사용량 API 한 번이면 되는데, 그냥 부르면 MCP 서버·플러그인 동기화까지 전부 띄운다
    # (실측 4.6s, CPU 3.5s — 프로필 4개 병렬이면 CPU 18s). MCP 를 비우면 ~3s.
    # --bare 는 더 빠르지만 OAuth 를 안 읽어 구독 사용량이 안 나온다 — 쓰지 말 것.
    # CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC 도 쓰지 말 것(~1.5s 로 줄지만): 켜면 사용량 API 응답을 못 받고
    # 1시간 안에 남은 스냅숏(.claude.json 의 cachedUsageUtilization)이 있을 때만 한도 줄이 나온다 — 방금 쓴
    # 프로필에서만 되는 것처럼 보인다. 부모 환경에 켜져 있어도 지운다.
    env.pop("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", None)
    try:
        # stdin 을 끊는다 — 안 끊으면 백그라운드 claude 가 터미널 입력을 먹는다.
        # cwd 는 전용 프로브 폴더 — 세션 기록이 작업 중인 프로젝트에도, 홈에도 섞이지 않게(probe_dir 참조).
        r = subprocess.run(["claude", "-p", "/usage", "--max-turns", "1",
                            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                            "--no-session-persistence", "--no-chrome",
                            "--setting-sources", "", "--settings", '{"disableAllHooks":true}'], stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, timeout=timeout, env=env, cwd=probe_dir())
        return r.stdout
    except Exception:
        return ""


def probe(profile_dir, tries=2):
    if not logged_in(profile_dir):
        return "\t".join([""] * 6 + ["nologin"] + [""] * 5)
    # 사용량 API 가 가끔 실패한다. 그때 claude 는 오류 없이 한도 줄(Current session/week)만 빼고 출력하므로
    # parse 가 fail 을 낸다. 대개 곧바로 다시 부르면 된다 — 한 번 더 시도한다.
    for _ in range(tries):
        line = parse(fetch(profile_dir))
        if line.split("\t")[6] != "fail":
            break
        # Recent CLI builds can refresh this file without printing /usage.
        cached, age = native_cache(profile_dir)
        if cached is not None and age <= STALE_AFTER:
            return "\t".join(cached)
    return line


def native_cache(profile_dir):
    """Account-bound Claude snapshot, not a live network validity check."""
    try:
        with open(auth_file(profile_dir)) as fh:
            data = json.load(fh)
        account = (data.get("oauthAccount") or {}).get("accountUuid")
        cache = data.get("cachedUsageUtilization") or {}
        if not account or cache.get("accountUuid") != account:
            return None, None
        age = time.time() - float(cache["fetchedAtMs"]) / 1000
        if not math.isfinite(age) or age < -60:
            return None, None
        age = max(0, age)
        usage = cache.get("utilization") or {}
        limits = usage.get("limits")
        if not isinstance(limits, list):
            limits = [dict(kind=kind, percent=(usage.get(key) or {}).get("utilization"),
                           resets_at=(usage.get(key) or {}).get("resets_at"))
                      for key, kind in (("five_hour", "session"), ("seven_day", "weekly_all"))]
        row = [""] * FIELDS
        row[6], row[9], row[10] = "ok", "10080", "300"
        for slot in limits:
            kind, pct = slot.get("kind"), slot.get("percent")
            # percent 가 null 이면 모르는 값이다 — 0 으로 꾸미지 않는다(빈칸 = 미보고). API 가 0 을 주면 그때만 0(새 창).
            if not isinstance(pct, (int, float)) or isinstance(pct, bool) or not math.isfinite(pct) or not 0 <= pct <= 100:
                continue
            if kind in ("session", "weekly_all"):
                base = 2 if kind == "session" else 0
                row[base] = str(int(round(pct)))
                reset = slot.get("resets_at")
                if reset:
                    dt = datetime.datetime.fromisoformat(reset.replace("Z", "+00:00")).astimezone()
                    row[base + 1] = str(max(0, round((dt.timestamp() - time.time()) / 60)))
                    row[8 if base == 2 else 7] = dt.strftime("%m/%d %H:%M")
                    if dt.timestamp() <= time.time():
                        row[6] = "stale"
            elif kind == "weekly_scoped":
                model = ((slot.get("scope") or {}).get("model") or {}).get("display_name")
                if model and (not row[5] or pct > int(row[5])):
                    row[4], row[5] = model.replace("\t", " ").replace("\n", " "), str(int(round(pct)))
        if not row[0] and not row[2]:
            return None, None
        if age > STALE_AFTER:
            row[6] = "stale"
            # 낡은 값일 때만 언제 것인지 적는다 — 신선하면 카드가 깨끗해야 한다(옛 /usage 파싱 때와 같은 모양).
            row[11] = "cache " + datetime.datetime.fromtimestamp(cache["fetchedAtMs"] / 1000).strftime("%m/%d %H:%M")
        return row, age
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return None, None


def start_refresh(profile_dir):
    try:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "refresh", profile_dir],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def menu(profile_dir):
    """Never wait for Claude startup before displaying the account picker."""
    if not logged_in(profile_dir):
        return "\t".join([""] * 6 + ["nologin"] + [""] * 5)
    if keychain_locked():
        return "\t".join([""] * 6 + ["fail"] + [""] * 4 + ["keychain-locked"])
    row, age = native_cache(profile_dir)
    # 백그라운드 갱신(refresh)이 써 둔 캐시 파일이 Claude 의 스냅숏보다 새로우면 그쪽을 쓴다 —
    # 갱신이 끝나도 스냅숏만 보면 영원히 낡은 값이 떠 있었다.
    cached, cage = read_cache(profile_dir)
    if cached is not None and cached[6] == "ok" and (row is None or (age is not None and cage < age)):
        # /usage 글에는 세션 줄이 '0% 새 창' 일 때도 빠질 수 있어 글만으로는 '미보고' 와 구분이 안 된다 — 스냅숏에 세션 값이 있으면 그걸 가져온다
        if row is not None and not cached[2] and row[2]:
            cached = list(cached); cached[2], cached[3], cached[8] = row[2], row[3], row[8]
        row, age = cached, cage
        if age > STALE_AFTER:
            row = list(row); row[6] = "stale"
            row[11] = "cache " + datetime.datetime.fromtimestamp(time.time() - age).strftime("%m/%d %H:%M")
    if row is None or age > 60 or row[6] == "stale":
        start_refresh(profile_dir)
    if row is not None:
        return "\t".join(row)
    return "\t".join([""] * 6 + ["fail"] + [""] * 4 + ["refreshing"])


def refresh(profile_dir):
    """One bounded refresh per profile; repeated menu opens do not pile up CLIs."""
    if keychain_locked():
        return
    path = cache_path(profile_dir) + ".lock"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        lock.seek(0)
        try:
            last = float(lock.read())
        except ValueError:
            last = 0
        if time.time() - last < 60:
            return
        lock.seek(0)
        lock.truncate()
        lock.write(str(time.time()))
        lock.flush()
        save(profile_dir, probe(profile_dir, tries=1))


def save(profile_dir, line):
    # 조회 실패(fail)는 캐시에 덮어쓰지 않는다 — 잠깐의 네트워크 문제로 상태줄의 값이 사라지면 안 된다.
    if line.split("\t")[6] != "fail":
        write_cache(profile_dir, line)


def write_cache(profile_dir, line):
    p = cache_path(profile_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".usage-", dir=os.path.dirname(p))
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(line + "\n")
    os.replace(tmp, p)


def read_cache(profile_dir):
    """(12칸 리스트, 나이(초)) 또는 (None, None)."""
    p = cache_path(profile_dir)
    try:
        line = open(p, encoding="utf-8").read().strip("\n")
        age = max(0.0, __import__("time").time() - os.path.getmtime(p))
    except OSError:
        return None, None
    return (line.split("\t") + [""] * FIELDS)[:FIELDS], age


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "probe"
    pdir = sys.argv[2] if len(sys.argv) > 2 else ""
    if cmd == "cache-path":
        print(cache_path(pdir))
    elif cmd == "refresh":
        refresh(pdir)
    elif cmd == "menu":
        print(menu(pdir))
    elif cmd == "parse":                 # stdin 의 /usage 원문을 TSV 로 (디버깅용)
        print(parse(sys.stdin.read()))
    else:
        line = probe(pdir)
        save(pdir, line)
        print(line)
