"""ccp 의 codex 사용량 파서 — app-server 응답을 ccp 렌더러 TSV 로 옮기는 부분."""
import os, sys, time
from pathlib import Path

os.environ["CCP_LANG"] = "ko"   # 기대 문구가 한국어다. 언어별 문구는 test_i18n 이 본다

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ccp_codex  # noqa: E402

NOW = 1788826800.0  # 2026-09-08 09:20 KST


def fields(tsv):
    return tsv.split("\t")


def rl(primary=None, secondary=None, **kw):
    d = {"limitId": "codex", "primary": primary, "secondary": secondary,
         "credits": {"hasCredits": False, "unlimited": False, "balance": None},
         "spendControlReached": False, "rateLimitReachedType": None}
    d.update(kw)
    return {"rateLimits": d, "rateLimitResetCredits": {"availableCount": 0, "credits": []}}


def win(pct, mins, resets_in_hours):
    return {"usedPercent": pct, "windowDurationMins": mins,
            "resetsAt": int(NOW + resets_in_hours * 3600)}


def test_주간_한도만_있는_팀_계정():
    """primary 가 7일 창이면 주간 칸에 들어간다 (세션 칸은 비어야 한다)."""
    out = fields(ccp_codex.to_tsv({"planType": "team"}, rl(primary=win(100, 10080, 96)), NOW))
    assert out[0] == "100"          # 주간 %
    assert out[1] == str(96 * 60)   # 주간 리셋까지 분
    assert out[2] == "" and out[3] == ""   # 세션 없음
    assert out[6] == "ok"
    assert out[9] == "10080"        # 주간 창 길이


def test_5시간_창이_primary_여도_세션_칸으로_간다():
    """Plus/Pro 는 primary 가 5시간, secondary 가 주간이다. 위치가 아니라 창 길이로 나눈다."""
    out = fields(ccp_codex.to_tsv(
        {"planType": "plus"},
        rl(primary=win(42, 300, 3), secondary=win(12, 10080, 120)), NOW))
    assert out[2] == "42" and out[3] == str(3 * 60)      # 세션
    assert out[0] == "12" and out[1] == str(120 * 60)    # 주간
    assert out[9] == "10080" and out[10] == "300"        # 창 길이 둘 다


def test_모델별_한도는_없다():
    out = fields(ccp_codex.to_tsv({"planType": "team"}, rl(primary=win(10, 10080, 24)), NOW))
    assert out[4] == "" and out[5] == ""


def test_미로그인():
    out = fields(ccp_codex.to_tsv(None, None, NOW))
    assert out[6] == "nologin"


def test_한도정보가_아직_없는_새_계정():
    """로그인은 했지만 한 번도 안 쓴 계정은 rateLimits 가 비어 온다 — 실패가 아니다."""
    out = fields(ccp_codex.to_tsv({"planType": "plus"}, {"rateLimits": None}, NOW))
    assert out[6] == "ok"
    assert out[0] == "" and out[2] == ""


def test_크레딧_소진과_리셋권을_메모로_낸다():
    payload = rl(primary=win(100, 10080, 96),
                 rateLimitReachedType="workspace_owner_credits_depleted")
    payload["rateLimitResetCredits"]["availableCount"] = 3
    out = fields(ccp_codex.to_tsv({"planType": "team"}, payload, NOW))
    assert out[11].startswith("team")
    assert "크레딧 소진" in out[11]
    assert "리셋권 3" in out[11]


def test_메모는_요금제부터_보여준다():
    """프로필 이름('기본')만으론 어느 워크스페이스인지 모른다."""
    out = fields(ccp_codex.to_tsv({"planType": "plus"}, rl(primary=win(30, 10080, 96)), NOW))
    assert out[11] == "plus"


def test_무제한_크레딧이면_소진_경고를_달지_않는다():
    payload = rl(primary=win(30, 10080, 96), rateLimitReachedType="workspace_owner_credits_depleted")
    payload["rateLimits"]["credits"] = {"hasCredits": True, "unlimited": True, "balance": None}
    out = fields(ccp_codex.to_tsv({"planType": "team"}, payload, NOW))
    assert "크레딧 소진" not in out[11]


def test_리셋_시각은_렌더러_형식_그대로():
    out = fields(ccp_codex.to_tsv({"planType": "team"}, rl(primary=win(50, 10080, 4)), NOW))
    import datetime
    want = datetime.datetime.fromtimestamp(NOW + 4 * 3600).strftime("%m/%d %H:%M")
    assert out[7] == want


def test_이미_지난_리셋은_0분():
    out = fields(ccp_codex.to_tsv({"planType": "team"}, rl(primary=win(50, 10080, -2)), NOW))
    assert out[1] == "0"


def test_필드는_항상_12개():
    for a, r in ((None, None), ({"planType": "team"}, rl(primary=win(1, 10080, 1)))):
        assert len(fields(ccp_codex.to_tsv(a, r, NOW))) == 12
