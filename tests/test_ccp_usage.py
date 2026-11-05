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


def test_실패하면_한_번_더_시도하고_fail_은_캐시에_안_쓴다(monkeypatch, tmp_path):
    import ccp_usage
    monkeypatch.setenv("CCP_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(ccp_usage, "logged_in", lambda d: True)
    outs = iter(["", "Current session: 5% used\nCurrent week (all models): 7% used\n"])
    monkeypatch.setattr(ccp_usage, "fetch", lambda d: next(outs))
    line = ccp_usage.probe("/x/p")
    assert line.split("\t")[6] == "ok" and line.split("\t")[0] == "7"

    ccp_usage.save("/x/p", line)
    monkeypatch.setattr(ccp_usage, "fetch", lambda d: "")
    ccp_usage.save("/x/p", ccp_usage.probe("/x/p"))
    cached, _ = ccp_usage.read_cache("/x/p")
    assert cached[6] == "ok" and cached[0] == "7"


def test_프로브는_부가_트래픽을_끄지_않는다(monkeypatch, tmp_path):
    # CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC 가 켜지면 claude 는 사용량 API 응답을 받지 못하고,
    # 1시간 안에 남겨 둔 스냅숏(.claude.json 의 cachedUsageUtilization)이 있을 때만 한도 줄을 찍는다.
    # 최근에 직접 쓰지 않은 프로필은 줄이 통째로 빠져 fail 이 된다 — 부모 환경에 켜져 있어도 지운다.
    import subprocess
    seen = {}

    def fake_run(cmd, **kw):
        seen["env"] = kw["env"]
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setenv("CCP_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
    monkeypatch.setattr(ccp_usage.subprocess, "run", fake_run)
    ccp_usage.fetch("/x/p")
    assert "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC" not in seen["env"]
    assert seen["env"]["CLAUDE_CONFIG_DIR"] == "/x/p"


def native_snapshot(monkeypatch, tmp_path, age=10, account='a'):
    import json, time
    p = tmp_path / 'profile'
    p.mkdir()
    (p / '.claude.json').write_text(json.dumps({
        'oauthAccount': {'emailAddress': 'test@example.com', 'accountUuid': 'a'},
        'cachedUsageUtilization': {'accountUuid': account, 'fetchedAtMs': (time.time()-age)*1000,
          'utilization': {'limits': [
            {'kind': 'session', 'percent': 12, 'resets_at': '2099-01-01T00:00:00Z'},
            {'kind': 'weekly_all', 'percent': 83, 'resets_at': '2099-01-02T00:00:00Z'},
            {'kind': 'weekly_scoped', 'percent': 100, 'scope': {'model': {'display_name': 'Fable'}}}
          ]}}
    }))
    monkeypatch.setenv('CCP_CONFIG_DIR', str(tmp_path / 'config'))
    return str(p)


def test_menu_uses_native_snapshot_without_starting_claude(monkeypatch, tmp_path):
    p = native_snapshot(monkeypatch, tmp_path)
    monkeypatch.setattr(ccp_usage, 'fetch', lambda *a, **k: (_ for _ in ()).throw(AssertionError('must not block')))
    row = ccp_usage.menu(p).split('\t')
    assert (row[0], row[2], row[4], row[5], row[6]) == ('83', '12', 'Fable', '100', 'ok')
    assert row[11] == ''   # 신선한 스냅숏에는 메모가 없다 — stale 일 때만 'cache …'


def test_snapshot_from_other_account_is_rejected(monkeypatch, tmp_path):
    p = native_snapshot(monkeypatch, tmp_path, account='other')
    assert ccp_usage.native_cache(p) == (None, None)


def test_stale_snapshot_is_visible_but_not_recommended(monkeypatch, tmp_path):
    p = native_snapshot(monkeypatch, tmp_path, age=3600)
    monkeypatch.setattr(ccp_usage, 'start_refresh', lambda *a: None)
    row = ccp_usage.menu(p).split('\t')
    assert row[0] == '83' and row[6] == 'stale'
    assert 'cache' in row[11]


def test_cli_empty_output_can_still_update_native_snapshot(monkeypatch, tmp_path):
    p = native_snapshot(monkeypatch, tmp_path)
    monkeypatch.setattr(ccp_usage, 'fetch', lambda *a, **k: '')
    assert ccp_usage.probe(p).split('\t')[0] == '83'


def test_missing_login_does_not_launch_background_refresh(monkeypatch, tmp_path):
    monkeypatch.setattr(ccp_usage, 'start_refresh', lambda *a: (_ for _ in ()).throw(AssertionError('no login')))
    assert ccp_usage.menu(str(tmp_path / 'missing')).split('\t')[6] == 'nologin'


def test_refresh_is_throttled(monkeypatch, tmp_path):
    p = native_snapshot(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(ccp_usage, 'probe', lambda *a, **k: calls.append(a) or ccp_usage.parse(TEXT, NOW))
    ccp_usage.refresh(p)
    ccp_usage.refresh(p)
    assert len(calls) == 1


def test_expired_reset_is_stale_even_when_recent(monkeypatch, tmp_path):
    import json
    from pathlib import Path
    p = native_snapshot(monkeypatch, tmp_path)
    path = Path(p) / '.claude.json'
    data = json.loads(path.read_text())
    data['cachedUsageUtilization']['utilization']['limits'][0]['resets_at'] = '2000-01-01T00:00:00Z'
    path.write_text(json.dumps(data))
    assert ccp_usage.native_cache(p)[0][6] == 'stale'


def test_stale_renderer_keeps_usage_and_shows_when_it_was_fetched(tmp_path):
    # 낡은 값도 '쓸 수 있는 계정' 으로 그린다 — 주간 한도는 느리게 움직이고, 못 쓰는 계정으로 내려 보내면
    # 남은 양이 안 보인다(2026-11-06 실제로 전부 '확인 불가' 로 떠서 보고됨). 언제 값인지만 메모로 붙인다.
    import subprocess
    from pathlib import Path
    row = ['83', '120', '12', '30', 'Fable', '0', 'stale', '', '', '10080', '300', 'cache 11/06 00:17']
    (tmp_path / '0').write_text('\t'.join(row))
    renderer = Path(ccp_usage.__file__).with_name('ccp_render.py')
    result = subprocess.run([sys.executable, str(renderer), str(tmp_path), '-', '', 'claude:test'], capture_output=True, text=True, check=True)
    assert '83%' in result.stdout and 'cache 11/06 00:17' in result.stdout
    assert '로그인 필요' not in result.stdout and '조회 실패' not in result.stdout
    assert 'rec\t0' in (tmp_path / '_meta').read_text()        # 유일한 계정이면 추천도 된다


# ── 키체인 잠김 가드 ────────────────────────────────────────────────────────
# macOS 에서 로그인 키체인을 못 여는 맥락(SSH, 데스크톱 세션 밖 launchd)에서 claude 를 띄우면
# 키체인 대신 .credentials.json 에 토큰을 돌려 두 곳이 어긋나고, 결국 로그인이 끊긴다. 거기서는 claude 를 띄우지 않는다.
class _R:
    def __init__(self, rc, err=""): self.returncode, self.stderr, self.stdout = rc, err, ""


def _darwin(monkeypatch, tmp_path, rc, err=""):
    monkeypatch.setattr(ccp_usage.sys, "platform", "darwin")
    monkeypatch.setenv("HOME", str(tmp_path)); monkeypatch.delenv("CCP_SKIP_KEYCHAIN_CHECK", raising=False)
    (tmp_path / "Library/Keychains").mkdir(parents=True); (tmp_path / "Library/Keychains/login.keychain-db").write_text("")
    calls = []
    monkeypatch.setattr(ccp_usage.subprocess, "run", lambda cmd, **k: (calls.append(cmd), _R(rc, err))[1])
    return calls


def test_키체인_잠김은_security_의_interaction_not_allowed_로_판정(monkeypatch, tmp_path):
    _darwin(monkeypatch, tmp_path, 36, "security: SecKeychainCopySettings: User interaction is not allowed.")
    assert ccp_usage.keychain_locked() is True


def test_키체인이_열려_있으면_잠김_아님(monkeypatch, tmp_path):
    _darwin(monkeypatch, tmp_path, 0)
    assert ccp_usage.keychain_locked() is False


def test_다른_오류나_키체인_파일_없음은_잠김으로_보지_않는다(monkeypatch, tmp_path):
    _darwin(monkeypatch, tmp_path, 50, "could not be found")
    assert ccp_usage.keychain_locked() is False
    os.remove(tmp_path / "Library/Keychains/login.keychain-db")
    assert ccp_usage.keychain_locked() is False


def test_환경변수로_가드를_끌_수_있다(monkeypatch, tmp_path):
    _darwin(monkeypatch, tmp_path, 36, "User interaction is not allowed")
    monkeypatch.setenv("CCP_SKIP_KEYCHAIN_CHECK", "1")
    assert ccp_usage.keychain_locked() is False


def test_맥_아니면_검사하지_않는다(monkeypatch, tmp_path):
    calls = _darwin(monkeypatch, tmp_path, 36, "User interaction is not allowed")
    monkeypatch.setattr(ccp_usage.sys, "platform", "linux")
    assert ccp_usage.keychain_locked() is False and calls == []


def test_잠겨_있으면_menu_는_claude_를_띄우지_않고_이유를_적는다(monkeypatch, tmp_path):
    monkeypatch.setattr(ccp_usage, "keychain_locked", lambda: True)
    monkeypatch.setattr(ccp_usage, "logged_in", lambda d: True)
    monkeypatch.setattr(ccp_usage, "start_refresh", lambda d: (_ for _ in ()).throw(AssertionError("refresh 가 돌면 안 된다")))
    f = fields(ccp_usage.menu(""))
    assert f[6] == "fail" and f[11] == "keychain-locked" and len(f) == 12


def test_잠겨_있으면_refresh_도_조용히_건너뛴다(monkeypatch, tmp_path):
    monkeypatch.setattr(ccp_usage, "keychain_locked", lambda: True)
    monkeypatch.setattr(ccp_usage, "probe", lambda d, tries=1: (_ for _ in ()).throw(AssertionError("probe 가 돌면 안 된다")))
    monkeypatch.setenv("CCP_CONFIG_DIR", str(tmp_path))
    ccp_usage.refresh("")


def test_세션_창이_없으면_percent_가_null_인데_0_으로_본다(monkeypatch, tmp_path):
    # 최근 5시간 동안 안 쓴 프로필은 limits 의 session percent 가 null 로 온다. 비워 두면 메뉴에 '-' 로 떠서
    # 조회가 안 된 것처럼 보인다. 창이 아직 안 열린 것이니 0% 로 보인다(렌더러가 '새 창' 으로 적는다).
    import time, json as _j
    p = tmp_path / ".claude.json"
    p.write_text(_j.dumps({"oauthAccount": {"accountUuid": "a"},
                           "cachedUsageUtilization": {"accountUuid": "a", "fetchedAtMs": int(time.time() * 1000),
                                                      "utilization": {"limits": [
                                                          {"kind": "session", "percent": None, "resets_at": None},
                                                          {"kind": "weekly_all", "percent": 12, "resets_at": "2030-01-01T00:00:00Z"},
                                                          {"kind": "weekly_scoped", "percent": 0, "scope": {"model": {"display_name": "Fable"}}}]}}}))
    row, age = ccp_usage.native_cache(str(tmp_path))
    assert row[0] == "12" and row[2] == "0" and row[3] == "" and row[4] == "Fable" and row[5] == "0" and row[6] == "ok"


def test_세션_슬롯이_아예_없어도_주간이_있으면_세션은_0(monkeypatch, tmp_path):
    import time, json as _j
    p = tmp_path / ".claude.json"
    p.write_text(_j.dumps({"oauthAccount": {"accountUuid": "a"},
                           "cachedUsageUtilization": {"accountUuid": "a", "fetchedAtMs": int(time.time() * 1000),
                                                      "utilization": {"limits": [
                                                          {"kind": "weekly_all", "percent": 2, "resets_at": "2030-01-01T00:00:00Z"},
                                                          {"kind": "weekly_scoped", "percent": 0, "scope": {"model": {"display_name": "Fable"}}}]}}}))
    row, age = ccp_usage.native_cache(str(tmp_path))
    assert row[0] == "2" and row[2] == "0" and row[3] == "" and row[6] == "ok"


def test_신선한_스냅숏에는_cache_메모가_없고_낡으면_붙는다(monkeypatch, tmp_path):
    import time, json as _j
    def snap(age_s):
        (tmp_path / ".claude.json").write_text(_j.dumps({"oauthAccount": {"accountUuid": "a"},
            "cachedUsageUtilization": {"accountUuid": "a", "fetchedAtMs": int((time.time() - age_s) * 1000),
                                       "utilization": {"limits": [{"kind": "weekly_all", "percent": 5, "resets_at": "2030-01-01T00:00:00Z"}]}}}))
        return ccp_usage.native_cache(str(tmp_path))[0]
    assert snap(10)[11] == "" and snap(10)[6] == "ok"
    assert snap(600)[11] == "" and snap(600)[6] == "ok"      # 10분은 아직 신선 — 주간 한도는 느리게 움직인다
    assert snap(3600)[11].startswith("cache ") and snap(3600)[6] == "stale"


def test_menu_는_갱신_캐시_파일이_스냅숏보다_새로우면_그쪽을_쓴다(monkeypatch, tmp_path):
    import time, json as _j, os
    monkeypatch.setenv("CCP_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setattr(ccp_usage, "keychain_locked", lambda: False)
    monkeypatch.setattr(ccp_usage, "start_refresh", lambda d: None)
    prof = tmp_path / "p"; prof.mkdir()
    (prof / ".claude.json").write_text(_j.dumps({"oauthAccount": {"emailAddress": "x@example.com", "accountUuid": "a"},
        "cachedUsageUtilization": {"accountUuid": "a", "fetchedAtMs": int((time.time() - 3000) * 1000),
                                   "utilization": {"limits": [{"kind": "weekly_all", "percent": 50, "resets_at": "2030-01-01T00:00:00Z"}]}}}))
    ccp_usage.write_cache(str(prof), "\t".join(["12", "100", "3", "50", "Fable", "7", "ok", "01/01 00:00", "01/01 00:00", "10080", "300", ""]))
    f = fields(ccp_usage.menu(str(prof)))
    assert f[0] == "12" and f[6] == "ok" and f[11] == ""      # 스냅숏(50%, 50분 전)이 아니라 방금 쓴 캐시(12%)

