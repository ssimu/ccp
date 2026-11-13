import base64
import hashlib
import json
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

_path = str(Path(__file__).resolve().parents[1] / "fleet" / "fleet-codex-check")
_loader = SourceFileLoader("fleet_codex_check", _path)
cc = module_from_spec(spec_from_loader("fleet_codex_check", _loader))
_loader.exec_module(cc)


def test_three_distinct_workspaces_are_quiet():
    rows = [{"profile": "default", "ws": "aaaa", "ok": True},
            {"profile": "bmc2", "ws": "bbbb", "ok": True},
            {"profile": "personal", "ws": "cccc", "ok": True}]
    assert cc.judge(rows) == []


def test_2026_11_13_default_duplicates_bmc2():
    rows = [{"profile": "default", "ws": "bbbb", "ok": True},
            {"profile": "bmc2", "ws": "bbbb", "ok": True},
            {"profile": "personal", "ws": "cccc", "ok": True}]
    w = cc.judge(rows)
    assert len(w) == 1 and "default·bmc2" in w[0] and "같은 워크스페이스" in w[0]


def test_revoked_token_is_flagged():
    w = cc.judge([{"profile": "default", "ws": "aaaa", "ok": False}])
    assert len(w) == 1 and "default" in w[0] and "로그인 확인 안 됨" in w[0]


def test_unknown_workspace_is_not_a_duplicate():
    assert cc.judge([{"profile": "a", "ws": None, "ok": True}, {"profile": "b", "ws": None, "ok": True}]) == []


def _jwt(claims):
    enc = lambda o: base64.urlsafe_b64encode(json.dumps(o).encode()).decode().rstrip("=")
    return enc({"alg": "none"}) + "." + enc(claims) + ".sig"


def test_workspace_hash_prefers_account_id_then_access_token(tmp_path):
    want = hashlib.sha256(b"acct-x").hexdigest()[:8]
    a = tmp_path / "a.json"
    a.write_text(json.dumps({"tokens": {"account_id": "acct-x", "access_token": _jwt({})}}))
    assert cc.workspace_hash(str(a)) == want
    b = tmp_path / "b.json"
    b.write_text(json.dumps({"tokens": {"access_token": _jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "acct-x"}})}}))
    assert cc.workspace_hash(str(b)) == want
    c = tmp_path / "c.json"
    c.write_text("{}")
    assert cc.workspace_hash(str(c)) is None
