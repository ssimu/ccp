"""ccp_pick — 계정을 고른 뒤 뜨는 '이 폴더의 대화' 선택 화면. 그리기와 비대화형 입력만 본다(termios 는 터미널이 있어야 한다)."""
import io, os, sys, time
from pathlib import Path

os.environ["CCP_LANG"] = "ko"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ccp_pick  # noqa: E402

NOW = time.mktime((2026, 9, 21, 15, 30, 0, 0, 0, -1))          # 2026-09-21(월) 15:30 현지
T = lambda y, mo, d, h, mi: str(int(time.mktime((y, mo, d, h, mi, 0, 0, 0, -1))))
# 열: 경로 · 세션ID · 시각 · 브랜치 · 제목 · 잡은 프로필 · 종류 · 이어진 세션 · 크기 · 내 계정에서 열림 · epoch
ROWS = [
    ["/p/f7745fb0-1.jsonl", "f7745fb0-c595-4ea1-a7dc-6df3fc6abc94", "09-21 13:27", "main", "H100 Gemma 긴 입력 처리", "", "", "ddc14aa5-38a1-4c1d-815f-6a3d21c951e3", "49079054", "", T(2026, 9, 21, 13, 27)],
    ["/p/76b78e19-1.jsonl", "76b78e19-0abb-4072-98d0-d536f5f1c1b8", "09-20 12:45", "feat/x", "Claude API로 정답 확장", "default", "bg", "", "1200000", "", T(2026, 9, 20, 12, 45)],
    ["/p/911acc43-1.jsonl", "911acc43-d9d4-4fdf-a0c9-53fd8f1cb7e4", "09-17 10:52", "main", "지금 보고 있는 대화", "", "", "", "3000", "ra00203", T(2026, 9, 17, 10, 52)],
    ["/p/5e9877ff-1.jsonl", "5e9877ff-4c92-468e-8489-bdc5d5397480", "09-01 10:52", "main", "옛 대화", "", "", "", "800", "", T(2026, 9, 1, 10, 52)],
]


def plain(lines):
    return [ccp_pick.strip_ansi(ln) for ln in lines]


def find(lines, needle):
    hits = [ln for ln in plain(lines) if needle in ln]
    assert hits, (needle, plain(lines))
    return hits[0]


def test_첫_줄은_새_대화이고_대화는_1번부터():
    lines = plain(ccp_pick.build_lines(ROWS, "ra00203", hl=0, cols=120, now=NOW))
    assert "ra00203" in lines[0]
    new = find(lines, "0) 새 대화"); assert "▶" in new
    r1 = find(lines, "1) f7745fb0"); assert "13:27" in r1 and "main" in r1 and "H100 Gemma" in r1
    r2 = find(lines, "2) 76b78e19"); assert "feat/x" in r2


def test_최근순_묶음_구분선_오늘_이번주_이전():
    lines = plain(ccp_pick.build_lines(ROWS, "ra00203", hl=0, cols=120, now=NOW))
    i_today, i_week, i_old = (next(i for i, ln in enumerate(lines) if k in ln) for k in ("오늘", "이번 주", "이전"))
    assert i_today < lines.index(find(lines, "1) f7745fb0")) < i_week < lines.index(find(lines, "2) 76b78e19"))
    assert i_week < lines.index(find(lines, "3) 911acc43")) < i_old < lines.index(find(lines, "4) 5e9877ff"))


def test_시각은_상대적으로_오늘은_시간만_어제는_어제_그_전은_날짜():
    lines = plain(ccp_pick.build_lines(ROWS, "ra00203", hl=0, cols=120, now=NOW))
    assert "13:27" in find(lines, "1) f7745fb0") and "09-21" not in find(lines, "1) f7745fb0")
    assert "어제 12:45" in find(lines, "2) 76b78e19")
    assert "09-17" in find(lines, "3) 911acc43")


def test_크기와_표시들():
    lines = plain(ccp_pick.build_lines(ROWS, "ra00203", hl=0, cols=120, now=NOW))
    assert "47MB" in find(lines, "1) f7745fb0") and "ddc14aa5 로 이어짐" in find(lines, "1) f7745fb0")
    assert "1.1MB" in find(lines, "2) 76b78e19") and "기본 프로필이 잡고 있음" in find(lines, "2) 76b78e19")
    assert "3KB" in find(lines, "3) 911acc43") and "이 계정에서 열려 있음" in find(lines, "3) 911acc43")


def test_강조는_한_줄에만_그리고_색_모드에서는_반전():
    lines = ccp_pick.build_lines(ROWS, "ra00203", hl=2, cols=120, now=NOW, ansi=True)
    marked = [ln for ln in lines if "▶" in ln]
    assert len(marked) == 1 and "2) 76b78e19" in ccp_pick.strip_ansi(marked[0]) and "\033[7m" in marked[0]


def test_긴_제목은_터미널_폭에_맞춰_자른다():
    rows = [["/p/a.jsonl", "aaaaaaaa-1", "09-21 13:27", "main", "가" * 200, "", "", "", "10", "", T(2026, 9, 21, 13, 0)]]
    for ln in ccp_pick.build_lines(rows, "team", hl=0, cols=60, now=NOW, ansi=True):
        assert ccp_pick.dw(ccp_pick.strip_ansi(ln)) <= 60


def test_예전_8열_행도_그려진다():
    rows = [r[:8] for r in ROWS]
    lines = plain(ccp_pick.build_lines(rows, "team", hl=0, cols=120, now=NOW))
    assert find(lines, "1) f7745fb0")


def test_비대화형은_번호를_읽어_meta_에_적는다(tmp_path):
    (tmp_path / "rows.tsv").write_text("\n".join("\t".join(r) for r in ROWS) + "\n")
    def run(answer):
        out = io.StringIO()
        ccp_pick.run(str(tmp_path), "team", stdin=io.StringIO(answer), stdout=out, force_plain=True)
        return (tmp_path / "_meta").read_text().strip(), out.getvalue()
    meta, out = run("2\n")
    assert meta == "sel\t2" and "1) f7745fb0" in out and "2) 76b78e19" in out
    assert run("\n")[0] == "sel\t0"          # Enter = 새 대화
    assert run("q\n")[0] == "sel\t-1"        # 취소
    meta, out = run("9\n")                   # 범위 밖
    assert meta == "sel\t-2" and "범위 밖: 9" in out


def test_크기와_표시는_오른쪽_끝에_맞춰_정렬된다():
    lines = ccp_pick.build_lines(ROWS, "ra00203", hl=0, cols=120, now=NOW)
    items = [ln for ln in plain(lines) if ") " in ln and "새 대화" not in ln]
    assert items and all(ccp_pick.dw(ln) == 119 for ln in items), [ccp_pick.dw(ln) for ln in items]
    assert items[0].rstrip().endswith("ddc14aa5 로 이어짐") and items[1].rstrip().endswith("기본 프로필이 잡고 있음")


def test_제목이_없으면_제목_없음_표시():
    rows = [["/p/a.jsonl", "aaaaaaaa-1", "09-21 13:27", "main", "", "", "", "", "10", "", T(2026, 9, 21, 13, 0)]]
    assert "(제목 없음)" in find(ccp_pick.build_lines(rows, "team", hl=0, cols=120, now=NOW), "1) aaaaaaaa")
