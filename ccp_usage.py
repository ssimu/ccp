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
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def config_dir():
    return os.environ.get("CCP_CONFIG_DIR") or os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "ccp")


def profile_name(profile_dir):
    return os.path.basename(profile_dir.rstrip("/")) if profile_dir else "default"


def cache_path(profile_dir):
    return os.path.join(config_dir(), "cache", f"usage-{profile_name(profile_dir)}.tsv")


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
    try:
        # stdin 을 끊는다 — 안 끊으면 백그라운드 claude 가 터미널 입력을 먹는다. cwd 는 홈으로 — 세션 기록이 작업 중인 프로젝트에 섞이지 않게.
        r = subprocess.run(["claude", "-p", "/usage", "--max-turns", "1"], stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, timeout=timeout, env=env, cwd=os.path.expanduser("~"))
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


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "probe"
    pdir = sys.argv[2] if len(sys.argv) > 2 else ""
    if cmd == "cache-path":
        print(cache_path(pdir))
    elif cmd == "refresh":
        write_cache(pdir, probe(pdir))
    elif cmd == "parse":                 # stdin 의 /usage 원문을 TSV 로 (디버깅용)
        print(parse(sys.stdin.read()))
    else:
        line = probe(pdir)
        # 조회 실패(fail)는 캐시에 덮어쓰지 않는다 — 잠깐의 네트워크 문제로 상태줄의 값이 사라지면 안 된다.
        if line.split("\t")[6] != "fail":
            write_cache(pdir, line)
        print(line)
