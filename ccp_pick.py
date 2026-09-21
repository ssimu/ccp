#!/usr/bin/env python3
"""계정을 고른 뒤 뜨는 '이 폴더에서 나눈 대화' 선택 화면.

ccp_render.py(계정 메뉴)와 같은 조작: ↑↓/j k 이동 · 숫자 = 그 번호 · Enter 선택 · Esc/q 취소.
0번은 항상 "새 대화". 화면은 먼저 지운다 — 계정 메뉴가 남긴 한도 표 위에 겹쳐 그리지 않도록.

  argv: <tmpdir> <보이는 프로필 이름>
  입력: <tmpdir>/rows.tsv — ccp_link.py sessions 의 출력(경로·세션ID·시각·브랜치·제목·잡은 프로필·종류·이어진 세션)
  결과: <tmpdir>/_meta 에 'sel\\tN' — N: 1부터 = 그 줄, 0 = 새 대화, -1 = 취소, -2 = 잘못된 입력
터미널이 아니면(파이프·테스트) 목록을 찍고 stdin 에서 한 줄을 읽는다.
"""
import os
import re
import shutil
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ccp_i18n import t  # noqa: E402

ANSI = re.compile(r"\033\[[0-9;?]*[A-Za-z]")


def dw(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def strip_ansi(s):
    return ANSI.sub("", s)


def cut(s, n):
    """표시 폭 n 에 맞춰 자른다(넘치면 … 붙임)."""
    if dw(s) <= n:
        return s
    out, w = "", 0
    for c in s:
        cw = 2 if unicodedata.east_asian_width(c) in "WF" else 1
        if w + cw > max(0, n - 1):
            break
        out += c
        w += cw
    return out + "…"


def color(s, code, on=True):
    return f"\033[{code}m{s}\033[0m" if (on and code) else s


def holder_name(h):
    return t("default") if h == "default" else h


def size_text(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    mb = n / 1048576
    if mb >= 10:
        return f"{mb:.0f}MB"
    if mb >= 1:
        return f"{mb:.1f}MB"
    if n >= 1024:
        return f"{n / 1024:.0f}KB"
    return f"{n}B"


def _day(ts):
    lt = time.localtime(ts)
    return (lt.tm_year, lt.tm_yday)


def _days_ago(ts, now):
    return int((time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1)) -
                time.mktime(time.localtime(ts)[:3] + (0, 0, 0, 0, 0, -1))) // 86400)


def when_text(ts, now, fallback=""):
    """오늘은 시각만, 어제는 '어제 시각', 그 전은 월-일."""
    if ts is None:
        return fallback
    d = _days_ago(ts, now)
    if d <= 0:
        return time.strftime("%H:%M", time.localtime(ts))
    if d == 1:
        return t("z_pick_yesterday") + " " + time.strftime("%H:%M", time.localtime(ts))
    return time.strftime("%m-%d", time.localtime(ts))


def group_of(ts, now):
    if ts is None:
        return "older"
    d = _days_ago(ts, now)
    return "today" if d <= 0 else ("week" if d < 7 else "older")


GROUP_KEY = {"today": "z_pick_today", "week": "z_pick_week", "older": "z_pick_older"}
TIMEW, BRANCHW, SIZEW = 11, 9, 6


def _epoch(r):
    try:
        return float(r[10])
    except (IndexError, ValueError, TypeError):
        return None


def build_lines(rows, shown, hl, cols, ansi=False, now=None):
    """머리말 + 0) 새 대화 + (오늘/이번 주/이전 구분선 + 대화 줄들) + 키 안내. hl 항목은 ▶ 와 반전.

    rows 는 ccp_link.py sessions 의 TSV 열(예전 8열도 받는다). 색은 계정 메뉴와 같은 규약:
    선택 행 반전(7) · 보조 정보 흐림(2) · 브랜치 청록(36) · 오늘 초록(32) · 경고 노랑(33).
    """
    now = time.time() if now is None else now
    lines = [color(cut(t("z_pick_head") % shown, cols - 1), "1;36", ansi)]

    def item(k, body_segs, tail_segs):
        """body_segs/tail_segs = [(텍스트, 색코드)] — 폭을 맞춰 자른 뒤 색을 입힌다. 선택 행은 통째로 반전."""
        head = f"  {'▶' if k == hl else ' '} "
        tail_plain = "".join(x for x, _ in tail_segs)
        body_plain = "".join(x for x, _ in body_segs)
        room = cols - dw(head) - dw(tail_plain) - 1
        if room < 16:                                  # 좁으면 꼬리표부터 버린다
            tail_segs, tail_plain = [], ""
            room = cols - dw(head) - 1
        if dw(body_plain) > room:                      # 본문은 마지막 조각(제목)에서 자른다
            over = dw(body_plain) - room
            txt, code = body_segs[-1]
            body_segs = body_segs[:-1] + [(cut(txt, max(1, dw(txt) - over)), code)]
        if tail_segs:                                  # 꼬리표(크기·표시)는 오른쪽 끝에 맞춘다 — 줄마다 들쭉날쭉하지 않게
            body_plain = "".join(x for x, _ in body_segs)
            txt, code = body_segs[-1]
            body_segs = body_segs[:-1] + [(pad(txt, dw(txt) + room - dw(body_plain)), code)]
        if k == hl:
            plain_line = head + "".join(x for x, _ in body_segs) + tail_plain
            return color(plain_line, "7", ansi) if ansi else plain_line
        return head + "".join(color(x, c, ansi) for x, c in body_segs) + "".join(color(x, c, ansi) for x, c in tail_segs)

    lines.append(item(0, [(f"0) {t('z_pick_new')}", "1")], []))
    cur_group = None
    for k, r in enumerate(rows, start=1):
        r = (list(r) + [""] * 11)[:11]
        path, sid, when, branch, title, holder, hkind, cont, size, opened, _ = r
        ts = _epoch(r)
        g = group_of(ts, now)
        if g != cur_group:
            cur_group = g
            label = f"  ── {t(GROUP_KEY[g])} "
            lines.append(color(cut(label + "─" * max(0, cols - 1 - dw(label)), cols - 1), "2", ansi))
        wt = when_text(ts, now, fallback=when)
        tcol = "32" if g == "today" else ("" if g == "week" else "2")
        body = [(f"{k}) ", "1;36" if k < 10 else "1"), (f"{sid[:8]}  ", "2"),
                (pad(wt, TIMEW), tcol), (pad(cut(branch, BRANCHW - 1), BRANCHW), "36"),
                (title, "") if title else (t("z_pick_untitled"), "2")]
        tail = []
        st = size_text(size)
        if st:
            tail.append(("  " + rpad(st, SIZEW), "2"))
        if holder:
            tail.append((" " + t("z_pick_held_mark") % holder_name(holder), "33"))
        if opened:
            tail.append((" " + t("z_pick_open_mark"), "33"))
        if cont:
            tail.append((" " + t("z_pick_cont_mark") % cont[:8], "2"))
        lines.append(item(k, body, tail))
    lines.append(color(cut("  " + t("z_pick_keys"), cols - 1), "2", ansi))
    return lines


def pad(s, n):
    return s + " " * max(0, n - dw(s))


def rpad(s, n):
    return " " * max(0, n - dw(s)) + s


def read_rows(tmp):
    rows = []
    try:
        with open(os.path.join(tmp, "rows.tsv"), encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if line:
                    rows.append(line.split("\t"))
    except OSError:
        pass
    return rows


def write_meta(tmp, sel):
    with open(os.path.join(tmp, "_meta"), "w") as f:
        f.write(f"sel\t{sel}\n")


def plain(rows, shown, stdin, stdout):
    """터미널이 아닐 때: 목록을 찍고 한 줄을 읽는다. Enter = 새 대화."""
    cols = shutil.get_terminal_size((100, 24)).columns
    for ln in build_lines(rows, shown, hl=-1, cols=cols):
        stdout.write(ln + "\n")
    stdout.write(t("z_pick_prompt"))
    stdout.flush()
    ans = stdin.readline().strip()
    if ans == "":
        return 0
    if ans.lower() == "q":
        return -1
    if ans.isdigit() and 0 <= int(ans) <= len(rows):
        return int(ans)
    stdout.write(t("z_out_of_range") % ans + "\n")
    return -2


def interactive(rows, shown):
    import termios
    import tty as ttymod
    from ccp_keys import KeyReader
    cols = shutil.get_terminal_size((100, 24)).columns
    hl = 0
    out = sys.stdout
    fd = os.open("/dev/tty", os.O_RDWR)
    old = termios.tcgetattr(fd)
    sel = -1
    n = 0

    def draw(first):
        nonlocal n
        lines = build_lines(rows, shown, hl, cols, ansi=True)
        if not first:
            out.write(f"\033[{n}A")
        for ln in lines:
            out.write("\r\033[2K" + ln + "\n")
        out.flush()
        n = len(lines)

    try:
        ttymod.setcbreak(fd)
        out.write("\033[2J\033[H\033[?25l")     # 화면을 지우고 맨 위에서 — 계정 메뉴의 한도 표 위에 겹치지 않게
        draw(True)
        total = len(rows) + 1
        keys = KeyReader(fd)
        while True:
            k = keys.name(keys.next())
            if k in ("cancel", "eof"):
                break
            if k == "enter":
                sel = hl
                break
            if k == "up":
                hl = (hl - 1) % total
            elif k == "down":
                hl = (hl + 1) % total
            elif len(k) == 1 and k.isdigit() and int(k) < total:
                hl = int(k)
            else:
                continue
            draw(False)
    except KeyboardInterrupt:
        sel = -1
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        out.write("\033[?25h")
        out.flush()
        os.close(fd)
    return sel


def run(tmp, shown, stdin=None, stdout=None, force_plain=False):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    rows = read_rows(tmp)
    if not rows:
        write_meta(tmp, 0)
        return 0
    use_tty = not force_plain and sys.stdout.isatty() and os.path.exists("/dev/tty")
    sel = interactive(rows, shown) if use_tty else plain(rows, shown, stdin, stdout)
    write_meta(tmp, sel)
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1], sys.argv[2]))
