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
