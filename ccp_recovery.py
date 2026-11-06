#!/usr/bin/env python3
"""Inspect isolated Claude OAuth profiles and start a verified, interactive login.

No scheduler, token copying, automatic logout, or browser automation is installed.
The operator completes the official browser/Gmail flow and any CAPTCHA.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ccp_usage import keychain_locked  # noqa: E402  (same rule as the menu: never start claude without the keychain)


def profile_dir(name):
    if name == "default":
        return None
    root = Path(os.environ.get("CLAUDE_PROFILES", str(Path.home() / ".claude-profiles")))
    if not name or name in (".", "..") or "/" in name or not (root / name).is_dir():
        raise ValueError("Unknown profile: " + name)
    return root / name


def profile_names():
    """default + 프로필 폴더들. 잠금(*.lock)·숨김 폴더는 프로필이 아니다."""
    root = Path(os.environ.get("CLAUDE_PROFILES", str(Path.home() / ".claude-profiles")))
    return ["default"] + sorted(p.name for p in root.glob("*")
                                if p.is_dir() and not p.name.startswith(".") and not p.name.endswith(".lock"))


def profile_env(name):
    env = dict(os.environ)
    # An inherited token/API provider can silently select a different account.
    for key in ("CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY",
                "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK",
                "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
                "CLAUDE_CODE_PROJECT_DIR_NAME", "CLAUDECODE"):
        env.pop(key, None)
    directory = profile_dir(name)
    if directory is not None:
        env["CLAUDE_CONFIG_DIR"] = str(directory)
    return env


def claude_bin():
    local = Path.home() / ".local/bin/claude"
    found = str(local) if local.is_file() else shutil.which("claude")
    if not found:
        raise ValueError("Claude Code executable not found")
    return found


def inspect(name, runner=subprocess.run):
    result = {"profile": name}
    if keychain_locked():
        # SSH or a non-desktop launchd context: claude would fall back to .credentials.json and desync the
        # keychain token. Report it as its own state; it is not a logout.
        result["state"] = "keychain_locked"
        return result
    try:
        proc = runner([claude_bin(), "auth", "status", "--json"], env=profile_env(name),
                      cwd=str(Path.home()), capture_output=True, text=True, timeout=40)
        data = json.loads(proc.stdout)
        if not isinstance(data, dict):
            raise ValueError("Unexpected status shape")
        # Whitelist fields; never print arbitrary CLI stderr or credentials.
        for key in ("loggedIn", "authMethod", "email", "orgId", "orgName", "subscriptionType"):
            if key in data:
                result[key] = data[key]
        result["state"] = ("local_oauth_present" if data.get("loggedIn") is True
                           and data.get("authMethod") == "claude.ai"
                           else "oauth_unavailable")
        if proc.returncode not in (0, 1) or (proc.returncode != 0 and data.get("loggedIn")):
            result["state"] = "check_failed"
    except (OSError, ValueError, subprocess.TimeoutExpired):
        result["state"] = "check_failed"
    return result


def matches(result, email, org_id):
    return (result.get("state") == "local_oauth_present"
            and result.get("email", "").casefold() == email.casefold()
            and result.get("orgId") == org_id)


def login(args):
    env = profile_env(args.profile)
    if args.manual_browser:
        env["BROWSER"] = "/usr/bin/true"
    locks = Path(os.environ.get("CCP_CONFIG_DIR", str(Path.home() / ".config/ccp"))) / "recovery-locks"
    locks.mkdir(parents=True, exist_ok=True)
    with (locks / (args.profile + ".lock")).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another recovery is already running for this profile.", file=sys.stderr)
            return 2
        print("Expected account: " + args.email + " | organization: " + args.org_id, flush=True)
        proc = subprocess.run([claude_bin(), "auth", "login", "--claudeai", "--email", args.email],
                              env=env, cwd=str(Path.home()))
        if proc.returncode:
            return proc.returncode
        result = inspect(args.profile)
        result["identity_verified"] = matches(result, args.email, args.org_id)
        print(json.dumps(result, ensure_ascii=False))
        if not result["identity_verified"]:
            print("Identity verification failed; recovery is NOT complete. No logout performed.", file=sys.stderr)
            return 3
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status", help="Local OAuth presence only; not server token validation. keychain_locked = run it from a desktop session (or an hc terminal of a desktop-started core)")
    status.add_argument("profile", nargs="?")
    auth = sub.add_parser("login", help="Interactive OAuth; verify email and organization afterwards")
    auth.add_argument("profile")
    auth.add_argument("--email", required=True)
    auth.add_argument("--org-id", required=True)
    auth.add_argument("--manual-browser", action="store_true", help="Print URL without launching remote browser")
    args = parser.parse_args()
    try:
        if args.command == "login":
            return login(args)
        names = [args.profile] if args.profile else profile_names()
        results = [inspect(name) for name in names]
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0 if all(r["state"] == "local_oauth_present" for r in results) else 1
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
