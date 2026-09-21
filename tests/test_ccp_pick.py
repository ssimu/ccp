"""ccp_pick — 계정을 고른 뒤 뜨는 '이 폴더의 대화' 선택 화면. 그리기와 비대화형 입력만 본다(termios 는 터미널이 있어야 한다)."""
import io, os, sys
from pathlib import Path

os.environ["CCP_LANG"] = "ko"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ccp_pick  # noqa: E402

ROWS = [
    ["/p/f7745fb0-1.jsonl", "f7745fb0-c595-4ea1-a7dc-6df3fc6abc94", "09-21 13:27", "main", "H100 Gemma 긴 입력 처리", "", "", "ddc14aa5-38a1-4c1d-815f-6a3d21c951e3"],
    ["/p/76b78e19-1.jsonl", "76b78e19-0abb-4072-98d0-d536f5f1c1b8", "09-21 12:45", "feat/x", "Claude API로 정답 확장", "default", "bg", ""],
]


def test_첫_줄은_새_대화이고_대화는_1번부터():
    lines = ccp_pick.build_lines(ROWS, "ra00203", hl=0, cols=120)
    assert "ra00203" in lines[0]
    assert "0) 새 대화" in lines[1] and "▶" in lines[1]
    assert "1) f7745fb0" in lines[2] and "09-21 13:27" in lines[2] and "main" in lines[2] and "H100 Gemma" in lines[2]
    assert "2) 76b78e19" in lines[3] and "feat/x" in lines[3]


def test_잡은_프로필과_이어진_세션_표시():
    lines = ccp_pick.build_lines(ROWS, "ra00203", hl=0, cols=120)
    assert "ddc14aa5 로 이어짐" in lines[2]
    assert "기본 프로필이 잡고 있음" in lines[3]      # default 는 언어에 맞는 이름으로


def test_강조는_한_줄에만():
    lines = ccp_pick.build_lines(ROWS, "ra00203", hl=2, cols=120)
    assert sum("▶" in ln for ln in lines) == 1 and "▶" in lines[3]


def test_긴_제목은_터미널_폭에_맞춰_자른다():
    rows = [["/p/a.jsonl", "aaaaaaaa-1", "09-21 13:27", "main", "가" * 200, "", "", ""]]
    for ln in ccp_pick.build_lines(rows, "team", hl=0, cols=60):
        assert ccp_pick.dw(ccp_pick.strip_ansi(ln)) <= 60


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
