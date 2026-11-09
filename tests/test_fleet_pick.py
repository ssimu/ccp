from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

_path = str(Path(__file__).resolve().parents[1] / "fleet" / "fleet-pick")
_loader = SourceFileLoader("fleet_pick", _path)
fp = module_from_spec(spec_from_loader("fleet_pick", _loader))
_loader.exec_module(fp)


def R(profile, weekly, state="ok", session=""):
    return {"profile": profile, "weekly": weekly, "session": session, "state": state}


def test_lowest_weekly_wins():
    best, rows = fp.choose([R("a", "59"), R("b", "39"), R("c", "50")], exclude=[], max_pct=80)
    assert best["profile"] == "b"


def test_excluded_and_over_max_skipped():
    best, rows = fp.choose([R("imok", "1"), R("a", "85"), R("b", "70")], exclude=["imok"], max_pct=80)
    assert best["profile"] == "b"
    why = {r["profile"]: r["skip"] for r in rows}
    assert why["imok"] == "제외" and why["a"].startswith("주간")


def test_not_logged_in_or_unknown_skipped():
    best, _ = fp.choose([R("a", "", "nologin"), R("b", "", "ok"), R("c", "10", "fail")], exclude=[], max_pct=80)
    assert best is None


def test_stale_usable_but_fresh_preferred_on_tie():
    best, _ = fp.choose([R("a", "40", "stale"), R("b", "40", "ok")], exclude=[], max_pct=80)
    assert best["profile"] == "b"
    best, _ = fp.choose([R("a", "30", "stale"), R("b", "40", "ok")], exclude=[], max_pct=80)
    assert best["profile"] == "a"


def test_session_nearly_full_skipped():
    best, _ = fp.choose([R("a", "10", session="96"), R("b", "50", session="5")], exclude=[], max_pct=80)
    assert best["profile"] == "b"


def test_too_old_skipped():
    old = dict(R("a", "10", "stale"), age=7 * 3600)
    best, rows = fp.choose([old, dict(R("b", "60"), age=10)], exclude=[], max_pct=80)
    assert best["profile"] == "b" and rows[0]["skip"].startswith("사용량 낡음")


def test_switch_only_when_5pct_left():
    # 주간 94% 는 아직 쓴다, 95% 이상(남은 양 5% 이하)이면 넘긴다
    best, _ = fp.choose([R("a", "94"), R("b", "96")], exclude=[], max_pct=95)
    assert best["profile"] == "a"
    best, rows = fp.choose([R("a", "95")], exclude=[], max_pct=95)
    assert best is None and "95%" in rows[0]["skip"]


def M(profile, weekly, model, name="Fable", **kw):
    return dict(R(profile, weekly, **kw), model=model, model_name=name)


def test_model_limit_binds_choice():
    # 2026-11-09: 주간은 39% 남았는데 Fable 은 0% 남은 계정을 고르면 작업이 바로 막힌다 — 두 한도 중 빠듯한 쪽으로 견준다
    best, rows = fp.choose([M("team", "61", "100"), M("ra", "41", "77"), M("dr", "30", "93")], exclude=[], max_pct=95)
    assert best["profile"] == "ra"          # dr 는 주간이 더 남았지만 Fable 이 7% 뿐, ra 는 23%
    why = {r["profile"]: r["skip"] for r in rows}
    assert why["team"].startswith("Fable")


def test_all_model_exhausted_still_picks_by_weekly():
    # 모든 계정의 Fable 이 바닥이면 다른 모델은 쓸 수 있으니 주간으로 고르되 표시한다(대체 계정으로 떨어지지 않게)
    best, rows = fp.choose([M("a", "61", "100"), M("b", "40", "99")], exclude=[], max_pct=95)
    assert best["profile"] == "b" and "Fable" in best["note"]


def test_missing_model_value_means_weekly_only():
    best, _ = fp.choose([M("a", "50", ""), M("b", "40", "")], exclude=[], max_pct=95)
    assert best["profile"] == "b"
