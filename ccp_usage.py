#!/usr/bin/env python3
"""claude 계정의 한도를 `/usage` 로 읽어 ccp 공용 TSV 한 줄로 낸다. 결과는 캐시에 남겨 상태줄이 같이 쓴다.

왜 /usage 인가: Claude Code 가 상태줄에 넘겨주는 rate_limits 에는 세션(5시간)·주간(전 모델)만 있고
**모델 전용 주간 한도(예: Fable)** 가 없다. 그건 /usage 출력에만 나온다. /usage 는 사용량 API 조회라
모델을 부르지 않는다(모델 턴 0 · 비용 0 — README 참조). 다만 3초쯤 걸리므로 상태줄은 매번 부르지 않고
캐시를 읽고, 오래됐으면 백그라운드에서 한 번 갱신한다.

TSV 12칸 (ccp_render.py · ccp_codex.py 와 같다):
  0 주간%  1 주간리셋(분)  2 세션%  3 세션리셋(분)  4 모델명  5 모델%
  6 상태(ok/nologin/fail)  7 주간리셋시각  8 세션리셋시각  9 주간창(분)  10 세션창(분)  11 메모

명령:
  ccp_usage.py probe [프로필디렉터리]        조회 → stdout 한 줄 + 캐시 갱신 (ccp 메뉴가 부른다)
  ccp_usage.py refresh [프로필디렉터리]      조회 → 캐시만 갱신, 출력 없음 (상태줄이 백그라운드로 부른다)
  ccp_usage.py cached <초> [프로필디렉터리]  캐시가 <초> 안쪽이면 stdout 한 줄(남은 분 보정), 아니면 종료코드 1
                                            (ccp 메뉴가 probe 전에 부른다. 60초 넘은 캐시면 백그라운드 갱신도 건다)
  ccp_usage.py cache-path [프로필디렉터리]   그 프로필의 캐시 파일 경로
프로필 디렉터리를 비우면 기본 프로필(~/.claude.json).
"""
import datetime
import json
import os
import re
import subprocess
import sys

FIELDS = 12
FAIL_TTL = 300
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
    return "\t".join([num(w), mins(wdt), num(s), mins(sdt), mn or "", num(mp), "ok", stamp(wdt), stamp(sdt), "10080", "300", ""])


def fetch(profile_dir, timeout=40):
    """claude -p /usage 를 돌려 원문을 돌려준다. 실패하면 ''."""
    env = dict(os.environ)
    # 프로필 세션 안에서 부르면 CLAUDE_CONFIG_DIR 이 환경에 남아 자식이 물려받는다. 기본 프로필은 반드시 지운다.
    if profile_dir:
        env["CLAUDE_CONFIG_DIR"] = profile_dir
    else:
        env.pop("CLAUDE_CONFIG_DIR", None)
    # /usage 는 사용량 API 한 번이면 되는데, 그냥 부르면 MCP 서버·플러그인 동기화·부가 트래픽까지 전부 띄운다
    # (실측 4.6s, CPU 3.5s — 프로필 4개 병렬이면 CPU 18s). 그래서 MCP 는 비운다.
    # --bare 는 더 빠르지만 OAuth 를 안 읽어 구독 사용량이 안 나온다 — 쓰지 말 것.
    # CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC 도 쓰지 말 것 — 켜면 /api/oauth/usage 응답을 못 받는다
    # (claude 2.1.283~285 실측: 요청은 나가는데 200 이 안 온다). 그때 claude 는 마지막으로 저장해 둔 값을
    # 조용히 대신 보여서 "출력 동일"로 보이지만 낡은 %이고, 저장된 값이 없는 프로필은 한도 줄이 아예 없다.
    # 바깥 셸에서 물려받은 값도 지운다.
    env.pop("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", None)
    try:
        # stdin 을 끊는다 — 안 끊으면 백그라운드 claude 가 터미널 입력을 먹는다.
        # cwd 는 전용 프로브 폴더 — 세션 기록이 작업 중인 프로젝트에도, 홈에도 섞이지 않게(probe_dir 참조).
        r = subprocess.run(["claude", "-p", "/usage", "--max-turns", "1",
                            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                            "--no-session-persistence", "--no-chrome"], stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, timeout=timeout, env=env, cwd=probe_dir())
        return r.stdout
    except Exception:
        return ""


def probe(profile_dir):
    if not logged_in(profile_dir):
        return "\t".join([""] * 6 + ["nologin"] + [""] * 5)
    return parse(fetch(profile_dir))


def write_cache(profile_dir, line):
    p = cache_path(profile_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
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


def cached_line(profile_dir, ttl):
    """ttl(초) 안쪽의 정상 캐시를 지금 기준으로 고친 TSV 한 줄. 쓸 수 없으면 None.
    메뉴가 계정마다 claude 를 띄우지 않게(프로필당 수 초) 먼저 이것을 본다."""
    row, age = read_cache(profile_dir)
    if row is None or age > ttl:
        return None
    # 실패도 잠깐(5분)은 캐시로 보인다 — 안 그러면 늘 실패하는 계정 하나가 메뉴를 열 때마다 수십 초를 붙잡는다.
    if row[6] == "fail":
        return "\t".join(row) if age <= min(ttl, FAIL_TTL) else None
    if row[6] != "ok":
        return None
    # 1·3칸은 조회 시점 기준 '남은 분'이다. 지난 만큼 뺀다 — 그새 리셋이 지났으면 %가 틀리니 캐시를 버린다.
    gone = int(age // 60)
    for k in (1, 3):
        if row[k].isdigit():
            left = int(row[k]) - gone
            if left <= 0:
                return None
            row[k] = str(left)
    return "\t".join(row)


def settle(profile_dir, line):
    """조회 결과를 캐시에 반영하고 화면에 보일 줄을 돌려준다. probe·refresh 가 같이 쓴다.
    조회 실패(fail)는 성한 캐시를 덮지 않는다 — 사용량 API 는 붐빌 때 한도 줄 없이 끝나기도 하고, 기계가 바쁘면
    claude 가 시간 초과로 끝난다. 리셋 전의 예전 값이 있으면 fail 대신 그것을 보이고 캐시는 낡은 채로 둔다(다시 시도된다)."""
    if line.split("\t")[6] != "fail":
        write_cache(profile_dir, line)
        return line
    prev = cached_line(profile_dir, 7 * 86400)
    if prev is None or prev.split("\t")[6] == "fail":
        write_cache(profile_dir, line)      # 쓸 만한 예전 값이 없을 때만 — 상태줄은 ok 줄만 쓰니 영향 없다
        return line
    return prev


def refresh_in_background(profile_dir):
    """캐시만 떼어 놓고 갱신한다. 상태줄(ccp_statusline.py)과 같은 락을 써서 한 번만 돈다."""
    lock = os.path.join(config_dir(), "cache", f"refresh-{profile_name(profile_dir)}.lock")
    try:
        if os.path.exists(lock) and __import__("time").time() - os.path.getmtime(lock) < 120:
            return
        os.makedirs(os.path.dirname(lock), exist_ok=True)
        os.close(os.open(lock, os.O_CREAT | os.O_WRONLY | os.O_TRUNC))
        # 실패하면 락을 남긴다 — 캐시가 낡은 채라, 락이 없으면 부를 때마다 claude 를 다시 띄운다(2분 뒤 재시도).
        cmd = f'python3 "{os.path.abspath(__file__)}" refresh "{profile_dir}" && rm -f "{lock}"'
        subprocess.Popen(["bash", "-c", cmd], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True,
                         env=dict(os.environ, CCP_CONFIG_DIR=config_dir()))
    except Exception:
        pass


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "probe"
    pdir = sys.argv[2] if len(sys.argv) > 2 else ""
    if cmd == "cache-path":
        print(cache_path(pdir))
    elif cmd == "cached":
        ttl = float(sys.argv[2]) if len(sys.argv) > 2 else 600
        pdir = sys.argv[3] if len(sys.argv) > 3 else ""
        line = cached_line(pdir, ttl)
        if line is None:
            sys.exit(1)
        if read_cache(pdir)[1] > 60 and not os.environ.get("CCP_USAGE_NO_BG"):
            refresh_in_background(pdir)
        print(line)
    elif cmd == "refresh":
        # 실패면 종료코드 1 — 부른 쪽(상태줄·메뉴)이 락을 남겨 2분은 다시 안 띄운다.
        line = probe(pdir)
        settle(pdir, line)
        sys.exit(1 if line.split("\t")[6] == "fail" else 0)
    elif cmd == "parse":                 # stdin 의 /usage 원문을 TSV 로 (디버깅용)
        print(parse(sys.stdin.read()))
    else:
        print(settle(pdir, probe(pdir)))
