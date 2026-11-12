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

# 메모의 기계용 접미사. 12칸 계약은 유지하고 절대 시각(연도 포함)을 보존한다.
# observed는 파일을 다시 저장해도 실제 조회 시각이 새것으로 둔갑하지 않게 한다.
META = "ccp:v1:"


def note_parts(row):
    note, sep, raw = row[11].partition(META)
    try:
        meta = json.loads(raw) if sep else {}
        if not isinstance(meta, dict):
            meta = {}
    except (ValueError, TypeError):
        meta = {}
    return note.rstrip(" |"), meta


def set_metadata(row, meta):
    note, _ = note_parts(row)
    row[11] = (note + " | " if note else "") + META + json.dumps(meta, separators=(",", ":"), sort_keys=True)


def _number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def roll_window(used, reset, window_min, now=None):
    """지난 창은 0% 추정으로 넘긴다. 서버를 다시 조회한 값은 아니다."""
    now = time.time() if now is None else now
    reset = _number(reset)
    estimated = reset is not None and reset <= now
    if estimated:
        period = window_min * 60
        reset += (math.floor((now - reset) / period) + 1) * period
        if used is not None and used != "":
            used = 0
    return used, reset, estimated


def normalize(row, age=0, now=None):
    """Claude TSV의 유일한 시간 보정 경로. 입력은 바꾸지 않으며 반복 적용해도 같다.

    옛 캐시는 저장 시각 + 남은 분으로 절대 리셋을 복원한다. 모델 시각이 없으면
    보정 전 주간 시각을 사용한다. 관측되지 않은 세션(null)은 계속 빈칸이다.
    """
    now = time.time() if now is None else now
    row = list(row)
    if row[6] not in ("ok", "stale"):
        return row
    note, meta = note_parts(row)
    observed = _number(meta.get("observed"))
    if observed is None:
        observed = now - age
    resets = dict(meta.get("resets") or {})
    for name, index in (("weekly", 1), ("session", 3)):
        if _number(resets.get(name)) is None:
            minutes = _number(row[index])
            resets[name] = now - age + minutes * 60 if minutes is not None else None
    if _number(resets.get("model")) is None:
        resets["model"] = resets.get("weekly")
    estimated = set(meta.get("estimated") or [])
    for name, pct, minutes, stamp, window in (("weekly", 0, 1, 7, 10080), ("session", 2, 3, 8, 300), ("model", 5, None, None, 10080)):
        used, reset, rolled = roll_window(row[pct], resets.get(name), window, now)
        resets[name] = reset
        row[pct] = str(used)
        if rolled and row[pct]:
            estimated.add(name)
        if minutes is not None and reset is not None:
            row[minutes] = str(max(0, round((reset - now) / 60)))
            row[stamp] = datetime.datetime.fromtimestamp(reset).strftime("%m/%d %H:%M")
    if now - observed > STALE_AFTER or estimated:
        row[6] = "stale"
        if "cache " not in note:
            note = (note + " · " if note else "") + "cache " + datetime.datetime.fromtimestamp(observed).strftime("%m/%d %H:%M")
    row[11] = note
    meta.update(observed=observed, resets=resets, estimated=sorted(estimated))
    set_metadata(row, meta)
    return row


def model_reset(row, now=None):
    now = time.time() if now is None else now
    _, meta = note_parts(row)
    reset = _number((meta.get("resets") or {}).get("model"))
    if reset is None:
        return (int(row[1]) if row[1].lstrip("-").isdigit() else None), row[7]
    return max(0, round((reset - now) / 60)), datetime.datetime.fromtimestamp(reset).strftime("%m/%d %H:%M")


def display_note(row, lang=None):
    from ccp_i18n import t
    note, meta = note_parts(row)
    parts = []
    if meta.get("estimated"):
        parts.append(t("usage_estimated", lang))
    elif row[6] == "stale":
        parts.append(t("usage_stale", lang))
    if note:
        parts.append(note)
    return " · ".join(parts)


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


def keychain_locked(deadline=None):
    """macOS 에서 로그인 키체인을 열 수 없는 맥락인지 — SSH 세션, 데스크톱 세션 밖에서 띄운 launchd 작업 등.

    거기서 claude 를 띄우면 키체인 대신 <프로필>/.credentials.json 에 토큰을 돌린다. 그러면 파일과 키체인의
    refresh 토큰이 어긋나고, 다음에 어느 한쪽이 갱신을 시도할 때 서버가 토큰 묶음을 통째로 무효화해
    멀쩡하던 로그인까지 끊긴다(실제로 12시간마다 SSH 로 도는 점검이 이 길을 밟았다). 그래서 잠긴 맥락에서는
    claude 를 띄우지 않는다. `security` 가 "User interaction is not allowed" 를 낼 때만 잠김으로 본다 —
    키체인 파일이 없거나 다른 오류면 평소처럼 진행한다. 알고 하는 거면 CCP_SKIP_KEYCHAIN_CHECK=1.
    """
    timeout = 5 if deadline is None else min(5, deadline - time.monotonic())
    if timeout <= 0:
        return True  # 검사 예산도 없으면 Claude를 띄우지 않는다.
    if sys.platform != "darwin" or os.environ.get("CCP_SKIP_KEYCHAIN_CHECK") == "1":
        return False
    kc = os.path.join(os.environ.get("HOME") or os.path.expanduser("~"), "Library/Keychains/login.keychain-db")
    if not os.path.exists(kc):
        return False
    try:
        r = subprocess.run(["security", "show-keychain-info", kc], capture_output=True, text=True, timeout=timeout)
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
    # 연도 없는 7일/5시간 리셋은 현재와 가까운 연도로 본다(연말 양방향).
    if not yr and (now - dt).days > 180:
        dt = dt.replace(year=now.year + 1)
    elif not yr and (dt - now).days > 180:
        dt = dt.replace(year=now.year - 1)
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
    mn = mp = mdt = None
    if mm:
        mn = mm.group(1)
        pc = re.search(r"(\d+)% used", mm.group(2))
        mp = int(pc.group(1)) if pc else None
        mdt = _parse_reset(mm.group(2), now)

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
    result = [num(w), mins(wdt), num(s), mins(sdt), mn or "", num(mp), "ok", stamp(wdt), stamp(sdt), "10080", "300", ""]
    set_metadata(result, {"observed": now.timestamp(), "resets": {
        key: value.timestamp() if value else None
        for key, value in (("weekly", wdt), ("session", sdt), ("model", mdt or wdt))}})
    return "\t".join(normalize(result, now=now.timestamp()))


REFRESH_TIMEOUT = 90   # 초. 뒤 갱신은 사람이 기다리지 않는다 — 2026-11-09 wooui(부하 큰 Mac)에서 /usage 가 18~37초 걸려 20초 제한이면 매번 실패, 캐시가 하루 넘게 멈췄다
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


def probe(profile_dir, tries=2, timeout=None):
    if not logged_in(profile_dir):
        return "\t".join([""] * 6 + ["nologin"] + [""] * 5)
    # 사용량 API 가 가끔 실패한다. 그때 claude 는 오류 없이 한도 줄(Current session/week)만 빼고 출력하므로
    # parse 가 fail 을 낸다. 대개 곧바로 다시 부르면 된다 — 한 번 더 시도한다.
    for _ in range(tries):
        line = parse(fetch(profile_dir) if timeout is None else fetch(profile_dir, timeout=timeout))
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
        resets = {}
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
                    resets["session" if base == 2 else "weekly"] = dt.timestamp()
            elif kind == "weekly_scoped":
                model = ((slot.get("scope") or {}).get("model") or {}).get("display_name")
                if model and (not row[5] or pct > int(row[5])):
                    row[4], row[5] = model.replace("\t", " ").replace("\n", " "), str(int(round(pct)))
                    reset = slot.get("resets_at")
                    resets["model"] = datetime.datetime.fromisoformat(reset.replace("Z", "+00:00")).timestamp() if reset else None
        if not row[0] and not row[2]:
            return None, None
        if age > STALE_AFTER:
            row[6] = "stale"
            # 낡은 값일 때만 언제 것인지 적는다 — 신선하면 카드가 깨끗해야 한다(옛 /usage 파싱 때와 같은 모양).
            row[11] = "cache " + datetime.datetime.fromtimestamp(cache["fetchedAtMs"] / 1000).strftime("%m/%d %H:%M")
        set_metadata(row, {"observed": cache["fetchedAtMs"] / 1000, "resets": resets})
        return normalize(row, age), age
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return None, None


def start_refresh(profile_dir):
    # launchd가 소유한 작업은 hc 같은 짧은 부모의 자식 정리에 속하지 않는다.
    # -k는 쓰지 않는다: 이미 실행 중인 작업을 끊거나 중복 실행하지 않는다.
    agent = os.path.expanduser('~/Library/LaunchAgents/local.ccp.usage-refresh.plist')
    disabled = os.path.exists(os.path.join(config_dir(), 'usage-refresh.disabled'))
    if sys.platform == 'darwin' and os.path.exists(agent) and not disabled:
        try:
            result = subprocess.run(['launchctl', 'kickstart', f'gui/{os.getuid()}/local.ccp.usage-refresh'],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=1)
            if result.returncode == 0:
                return
        except (OSError, subprocess.TimeoutExpired):
            pass
    # 미설치/Linux 보조 경로. 관리 터미널의 자식 일괄 정리까지 피한다고 보장하지 않는다.
    try:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "refresh", profile_dir],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def best_cache(profile_dir, model_only=False):
    candidates = [(r, a) for r, a in (native_cache(profile_dir), read_cache(profile_dir))
                  if r is not None and r[6] in ('ok', 'stale') and (not model_only or (r[4] and r[5]))]
    return min(candidates, key=lambda item: item[1]) if candidates else (None, None)


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
    if cached is not None and cached[6] in ("ok", "stale") and (row is None or (age is not None and cage < age)):
        # /usage 글에는 세션 줄이 '0% 새 창' 일 때도 빠질 수 있어 글만으로는 '미보고' 와 구분이 안 된다 — 스냅숏에 세션 값이 있으면 그걸 가져온다
        if row is not None and not cached[2] and row[2]:
            cached = list(cached); cached[2], cached[3], cached[8] = row[2], row[3], row[8]
            _, meta = note_parts(cached)
            _, source = note_parts(row)
            meta['resets']['session'] = source['resets']['session']
            if 'session' in source.get('estimated', []):
                meta['estimated'] = sorted(set(meta.get('estimated', []) + ['session']))
            # 오래된 세션을 보충했다면 그 조회 시각도 숨기지 않는다.
            meta['observed'] = min(meta['observed'], source['observed'])
            set_metadata(cached, meta)
            cached = normalize(cached)
        row, age = cached, cage
    if row is None or age > 60 or row[6] == "stale":
        start_refresh(profile_dir)
    if row is not None:
        return "\t".join(row)
    return "\t".join([""] * 6 + ["fail"] + [""] * 4 + ["refreshing"])


def refresh(profile_dir, timeout=REFRESH_TIMEOUT, deadline=None, min_age=0):
    """One bounded refresh per profile; repeated menu opens do not pile up CLIs."""
    if (keychain_locked() if deadline is None else keychain_locked(deadline=deadline)):
        return
    path = cache_path(profile_dir) + ".lock"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        if min_age:
            cached, age = best_cache(profile_dir)
            if cached is not None and cached[6] == 'ok' and age < min_age:
                return
        lock.seek(0)
        try:
            last = float(lock.read())
        except ValueError:
            last = 0
        if time.time() - last < 60:
            return
        if deadline is not None:
            timeout = min(timeout, deadline - time.monotonic())
        if timeout <= 0:
            return
        lock.seek(0)
        lock.truncate()
        lock.write(str(time.time()))
        lock.flush()
        save(profile_dir, probe(profile_dir, tries=1, timeout=timeout))


def profile_dirs():
    """메뉴와 같이 기본 프로필 및 실제 프로필 디렉터리를 열거한다."""
    root = os.environ.get('CLAUDE_PROFILES') or os.path.expanduser('~/.claude-profiles')
    yield ''
    try:
        with os.scandir(root) as entries:
            dirs = sorted(e.path for e in entries if e.is_dir() and not e.name.startswith('.') and not e.name.endswith('.lock'))
    except OSError:
        dirs = []
    yield from dirs


def refresh_all(min_age=600, max_seconds=600):
    """15분 타이머용: 한 번에 하나씩, 최근 성공은 생략, 전체 작업은 최대 10분.

    전체 락과 기존 프로필 락을 함께 쓴다. 오래된 것부터 처리하므로 시간 상한에
    걸리더라도 뒤쪽 프로필이 매번 굶지 않는다. 실패는 기존 캐시를 보존한다.
    """
    deadline = time.monotonic() + max_seconds
    if os.path.exists(os.path.join(config_dir(), 'usage-refresh.disabled')) or keychain_locked(deadline=deadline):
        return
    path = os.path.join(config_dir(), 'cache', 'refresh-all.lock')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        pending = []
        for profile in profile_dirs():
            if time.monotonic() >= deadline:
                return
            if not logged_in(profile):
                continue
            row, age = best_cache(profile)
            if row is not None and row[6] == 'ok' and age < min_age:
                continue
            # 실패한 선두 프로필 때문에 시간 상한 뒤의 프로필이 매번 굶지 않게
            # 마지막 시도 시각도 순서에 반영한다(신선함 판정에는 절대 쓰지 않음).
            try:
                with open(cache_path(profile) + '.lock') as attempt:
                    last_attempt = _number(attempt.read()) or 0
            except OSError:
                last_attempt = 0
            observed = time.time() - age if age is not None else 0
            pending.append((max(observed, last_attempt), profile))
        for _, profile in sorted(pending):
            if time.monotonic() >= deadline:
                break
            refresh(profile, deadline=deadline, min_age=min_age)


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
    row = (line.split("\t") + [""] * FIELDS)[:FIELDS]
    row = normalize(row, age)
    _, meta = note_parts(row)
    observed = _number(meta.get('observed'))
    if observed is not None:
        age = max(0, time.time() - observed)
    return row, age


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
