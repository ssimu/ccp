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


def _age(path, sec):
    t = __import__("time").time() - sec
    os.utime(path, (t, t))


def test_캐시_먼저_남은분_보정():
    with tempfile.TemporaryDirectory() as d:
        os.environ["CCP_CONFIG_DIR"] = d
        line = ccp_usage.parse(TEXT, NOW)
        ccp_usage.write_cache("/x/profiles/team", line)
        _age(ccp_usage.cache_path("/x/profiles/team"), 125)
        got = fields(ccp_usage.cached_line("/x/profiles/team", 600))
        want = fields(line)
        assert int(got[1]) == int(want[1]) - 2 and int(got[3]) == int(want[3]) - 2
        assert got[0] == want[0] and got[4] == "Fable"
        assert ccp_usage.cached_line("/x/profiles/team", 60) is None          # ttl 넘음
        assert ccp_usage.cached_line("/x/profiles/none", 600) is None


def test_캐시_리셋이_지났으면_버림():
    with tempfile.TemporaryDirectory() as d:
        os.environ["CCP_CONFIG_DIR"] = d
        line = fields(ccp_usage.parse(TEXT, NOW)); line[3] = "3"
        ccp_usage.write_cache("", "\t".join(line))
        _age(ccp_usage.cache_path(""), 300)
        assert ccp_usage.cached_line("", 600) is None


def test_조회_실패면_리셋_전_예전_캐시로(monkeypatch=None):
    with tempfile.TemporaryDirectory() as d:
        os.environ["CCP_CONFIG_DIR"] = d
        ccp_usage.write_cache("", ccp_usage.parse(TEXT, NOW))
        _age(ccp_usage.cache_path(""), 3 * 3600)
        assert ccp_usage.cached_line("", 600) is None
        assert fields(ccp_usage.cached_line("", 7 * 86400))[4] == "Fable"


def test_실패도_5분은_캐시():
    with tempfile.TemporaryDirectory() as d:
        os.environ["CCP_CONFIG_DIR"] = d
        fail = "\t".join([""] * 6 + ["fail"] + [""] * 5)
        ccp_usage.write_cache("", fail)
        assert fields(ccp_usage.cached_line("", 600))[6] == "fail"
        _age(ccp_usage.cache_path(""), 400)
        assert ccp_usage.cached_line("", 600) is None


def test_프로브는_부가트래픽_차단을_켜지_않는다():
    """CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC 이 켜지면 claude 가 /api/oauth/usage 응답을 못 받는다.
    그때 claude 는 마지막으로 저장해 둔 값을 조용히 보이고(낡은 %), 저장된 값이 없으면 한도 줄 없이 끝난다.
    ccp 가 직접 켜는 것도, 바깥 셸에서 물려받는 것도 안 된다."""
    seen = {}

    class R:
        stdout = TEXT

    def fake_run(cmd, **kw):
        seen["env"] = kw["env"]
        return R()

    real, had = ccp_usage.subprocess.run, os.environ.get("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC")
    ccp_usage.subprocess.run = fake_run
    os.environ["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"      # 물려받은 경우까지
    try:
        with tempfile.TemporaryDirectory() as d:
            os.environ["CCP_CONFIG_DIR"] = d
            assert ccp_usage.fetch("/x/profiles/team") == TEXT
    finally:
        ccp_usage.subprocess.run = real
        if had is None:
            os.environ.pop("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", None)
        else:
            os.environ["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = had
    leaked = "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC" in seen["env"]     # env 통째로 단언하면 실패 때 키까지 찍힌다
    assert not leaked
    assert seen["env"].get("CLAUDE_CONFIG_DIR") == "/x/profiles/team"


def test_갱신이_실패해도_성한_캐시를_덮지_않는다():
    """백그라운드 refresh 가 느린 날(claude 가 40초 넘게 걸려 시간 초과) fail 을 덮어쓰면
    메뉴는 5분간 '조회 실패', 상태줄은 모델 한도 조각이 사라진다. 성한 값이 있으면 그대로 둔다."""
    with tempfile.TemporaryDirectory() as d:
        os.environ["CCP_CONFIG_DIR"] = d
        fail = "\t".join([""] * 6 + ["fail"] + [""] * 5)
        ok = ccp_usage.parse(TEXT, NOW)
        ccp_usage.write_cache("", ok)
        _age(ccp_usage.cache_path(""), 900)
        shown = ccp_usage.settle("", fail)
        assert fields(shown)[6] == "ok" and fields(shown)[4] == "Fable"       # 화면엔 예전 값
        row, age = ccp_usage.read_cache("")
        assert row[6] == "ok" and age > 800                                   # 캐시는 손대지 않음(낡은 채로 — 다시 시도된다)
        # 성한 값이 없으면 fail 을 남긴다 — 그래야 메뉴가 5분은 다시 안 두드린다
        assert fields(ccp_usage.settle("/x/profiles/none", fail))[6] == "fail"
        assert ccp_usage.read_cache("/x/profiles/none")[0][6] == "fail"
        # 성공은 늘 덮어쓴다
        assert ccp_usage.settle("", ok) == ok and ccp_usage.read_cache("")[1] < 5
