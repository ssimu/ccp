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


def build_lines(rows, shown, hl, cols, ansi=False):
    """머리말 + 0) 새 대화 + 대화 줄들 + 키 안내. hl 줄에 ▶."""
    lines = [color(cut(t("z_pick_head") % shown, cols - 1), "1;36", ansi)]
    items = [None] + list(rows)
    for k, r in enumerate(items):
        mark = "▶" if k == hl else " "
        if r is None:
            body = f"{k}) {t('z_pick_new')}"
            tail = ""
        else:
            path, sid, when, branch, title, holder, hkind, cont = (r + [""] * 8)[:8]
            body = f"{k}) {sid[:8]}  {when}  {branch}  {title}" if branch else f"{k}) {sid[:8]}  {when}  {title}"
            tail = ""
            if holder:
                tail += " " + color(t("z_pick_held_mark") % holder_name(holder), "33", ansi)
            if cont:
                tail += " " + color(t("z_pick_cont_mark") % cont[:8], "2", ansi)
        head = f"  {mark} "
        room = cols - dw(head) - dw(strip_ansi(tail)) - 1
        if room < 12:                      # 좁은 터미널: 꼬리표를 버리고 본문만
            tail, room = "", cols - dw(head) - 1
        line = head + cut(body, room) + tail
        lines.append(color(line, "1", ansi) if k == hl and ansi else line)
    lines.append(color(cut("  " + t("z_pick_keys"), cols - 1), "2", ansi))
    return lines


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
