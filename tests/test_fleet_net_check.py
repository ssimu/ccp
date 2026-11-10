from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

_path = str(Path(__file__).resolve().parents[1] / "fleet" / "fleet-net-check")
_loader = SourceFileLoader("fleet_net_check", _path)
nc = module_from_spec(spec_from_loader("fleet_net_check", _loader))
_loader.exec_module(nc)


def test_healthy_mac_is_quiet():
    assert nc.judge("26.3", 10.0, 40, True) == []


def test_macmini_on_2026_11_11_flags_all_three():
    w = nc.judge("26.3", 55.3, 35493, False)
    assert len(w) == 3
    assert any("나가는 연결" in x for x in w)
    assert any("TIME_WAIT 35493" in x for x in w)
    assert any("재부팅 필요" in x and "결함 구간" in x for x in w)


def test_warns_a_week_before_the_bug():
    w = nc.judge("26.3", 43.0, 100, True)
    assert len(w) == 1 and "결함까지 6.7일" in w[0]


def test_old_macos_long_uptime_not_flagged():
    # wooui 15.7 은 164일째에도 멀쩡했다 — 결함은 26 이상에서만
    assert nc.judge("15.7", 164.0, 29, True) == []


def test_unknown_values_do_not_crash():
    assert nc.judge("", None, None, True) == []
