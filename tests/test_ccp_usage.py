"""ccp_usage — /usage 원문 파서와 캐시."""
import datetime, os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ccp_usage  # noqa: E402

NOW = datetime.datetime(2026, 9, 10, 18, 0)
TEXT = """You are currently using your subscription to power your Claude Code usage
Current session: 48% used · resets Sep 10 at 9:10pm (Asia/Seoul)
Current week (all models): 25% used · resets Sep 14 at 3pm (Asia/Seoul)
Current week (Fable): 47% used · resets Sep 14 at 3pm (Asia/Seoul)
What's contributing to your limits usage?
"""


def fields(s): return s.split("\t")


def test_세션_주간_모델을_모두_읽는다():
    f = fields(ccp_usage.parse(TEXT, NOW))
    assert f[0] == "25" and f[2] == "48" and f[4] == "Fable" and f[5] == "47" and f[6] == "ok"
    assert f[3] == str(3 * 60 + 10)                  # 21:10 까지 190분
    assert f[1] == str((4 * 24 - 3) * 60)            # 9/14 15:00 까지
    assert f[7] == "09/14 15:00" and f[8] == "09/10 21:10"
    assert f[9] == "10080" and f[10] == "300"
    assert len(f) == 12


def test_정각은_분이_생략된다():
    f = fields(ccp_usage.parse("Current session: 1% used · resets Sep 10 at 11pm (Asia/Seoul)\n", NOW))
    assert f[3] == str(5 * 60)


def test_연도가_붙은_형식():
    f = fields(ccp_usage.parse("Current week (all models): 1% used · resets Jan 2, 2027 at 1:19am (Asia/Seoul)\n", NOW))
    assert f[7] == "01/02 01:19" and int(f[1]) > 100 * 1440


def test_연말_경계는_내년으로():
    f = fields(ccp_usage.parse("Current session: 1% used · resets Jan 3 at 1am (Asia/Seoul)\n", datetime.datetime(2026, 12, 31, 23, 0)))
    assert 0 < int(f[3]) < 4 * 1440


def test_모델_한도가_없는_계정():
    f = fields(ccp_usage.parse("Current session: 10% used · resets Sep 10 at 9pm (Asia/Seoul)\nCurrent week (all models): 5% used · resets Sep 14 at 3pm (Asia/Seoul)\n", NOW))
    assert f[4] == "" and f[5] == "" and f[6] == "ok"


def test_아무것도_못_읽으면_fail():
    f = fields(ccp_usage.parse("Not logged in\n", NOW))
    assert f[6] == "fail" and len(f) == 12


def test_캐시_쓰고_읽기():
    with tempfile.TemporaryDirectory() as d:
        os.environ["CCP_CONFIG_DIR"] = d
        line = ccp_usage.parse(TEXT, NOW)
        ccp_usage.write_cache("/x/profiles/team", line)
        assert ccp_usage.cache_path("/x/profiles/team") == os.path.join(d, "cache", "usage-team.tsv")
        assert ccp_usage.cache_path("") == os.path.join(d, "cache", "usage-default.tsv")
        row, age = ccp_usage.read_cache("/x/profiles/team")
        assert row[4] == "Fable" and age < 5
        assert ccp_usage.read_cache("/x/profiles/none") == (None, None)
