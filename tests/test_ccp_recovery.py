import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ccp_recovery as recovery


def test_inherited_auth_cannot_select_another_account(monkeypatch, tmp_path):
    (tmp_path / "team").mkdir()
    monkeypatch.setenv("CLAUDE_PROFILES", str(tmp_path))
    for key in ("CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"):
        monkeypatch.setenv(key, "unrelated-account")
    default = recovery.profile_env("default")
    assert "CLAUDE_CONFIG_DIR" not in default
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in default
    assert "ANTHROPIC_API_KEY" not in default
    assert "ANTHROPIC_BASE_URL" not in default
    assert recovery.profile_env("team")["CLAUDE_CONFIG_DIR"] == str(tmp_path / "team")


def test_same_email_wrong_organization_is_not_success():
    result = dict(state="local_oauth_present", email="user@example.com", orgId="personal")
    assert not recovery.matches(result, "user@example.com", "team")
    assert recovery.matches(result, "user@example.com", "personal")


def test_failure_is_not_reported_as_logout_and_raw_output_is_not_exposed(monkeypatch):
    monkeypatch.setattr(recovery, "claude_bin", lambda: "claude")
    result = recovery.inspect("default", lambda *a, **k: SimpleNamespace(stdout="private-error", returncode=2))
    assert result == dict(profile="default", state="check_failed")


def test_api_key_is_not_oauth_success(monkeypatch):
    monkeypatch.setattr(recovery, "claude_bin", lambda: "claude")
    data = dict(loggedIn=True, authMethod="api_key", secret="must-not-print")
    result = recovery.inspect("default", lambda *a, **k: SimpleNamespace(stdout=json.dumps(data), returncode=0))
    assert result["state"] == "oauth_unavailable"
    assert "secret" not in result


def test_rejects_profile_path_escape(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PROFILES", str(tmp_path))
    for name in ("..", "../default", "/tmp", "missing"):
        try:
            recovery.profile_dir(name)
        except ValueError:
            pass
        else:
            raise AssertionError("Unsafe or missing profile accepted")


def test_keychain_locked_context_never_runs_claude(monkeypatch):
    monkeypatch.setattr(recovery, "keychain_locked", lambda: True)

    def runner(*a, **k):
        raise AssertionError("claude must not run while the keychain is locked")
    result = recovery.inspect("default", runner)
    assert result == dict(profile="default", state="keychain_locked")


def test_status_skips_lock_and_hidden_dirs(monkeypatch, tmp_path):
    for name in ("team", "team.lock", ".tmp"):
        (tmp_path / name).mkdir()
    monkeypatch.setenv("CLAUDE_PROFILES", str(tmp_path))
    assert recovery.profile_names() == ["default", "team"]
