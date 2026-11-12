"""로그인/키체인/launchd는 합성 환경, /usage는 가짜 실행파일만 사용한다."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
import ccp_usage as u

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('CCP_CONFIG_DIR', str(tmp_path / 'cfg'))
    monkeypatch.setenv('CLAUDE_PROFILES', str(tmp_path / 'profiles'))
    monkeypatch.delenv('CLAUDE_CONFIG_DIR', raising=False)
    monkeypatch.setattr(u, 'keychain_locked', lambda **kw: False)
    for p in [tmp_path, tmp_path / 'profiles' / 'alpha', tmp_path / 'profiles' / 'beta']:
        p.mkdir(parents=True, exist_ok=True)
        (p / '.claude.json').write_text(json.dumps({'oauthAccount': {'emailAddress': 'test@example.com'}}))
    b = tmp_path / 'bin'; b.mkdir()
    fake = b / 'claude'
    fake.write_text('#!/bin/sh\nprintf "%s\\n" "${CLAUDE_CONFIG_DIR:-default}" >> "$HOME/calls"\nprintf "Current week (all models): 19%% used\\n"\n')
    fake.chmod(0o755)
    monkeypatch.setenv('PATH', str(b) + os.pathsep + os.environ['PATH'])
    return tmp_path


def test_all_profiles_sequential_and_fresh_skip(home):
    u.refresh_all(min_age=600)
    assert (home / 'calls').read_text().splitlines() == ['default', str(home / 'profiles/alpha'), str(home / 'profiles/beta')]
    for p in ['', str(home / 'profiles/alpha'), str(home / 'profiles/beta')]:
        assert u.read_cache(p)[0][0] == '19'
    u.refresh_all(min_age=600)
    assert len((home / 'calls').read_text().splitlines()) == 3


def test_locked_context_no_probe_or_cache(home, monkeypatch):
    # SSH/非GUI launchd가 내는 security 오류를 실제 keychain_locked 판정으로 통과시킨다.
    monkeypatch.undo()
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('CCP_CONFIG_DIR', str(home / 'cfg'))
    monkeypatch.setattr(u.sys, 'platform', 'darwin')
    monkeypatch.delenv('CCP_SKIP_KEYCHAIN_CHECK', raising=False)
    kc = home / 'Library/Keychains'; kc.mkdir(parents=True)
    (kc / 'login.keychain-db').write_text('')
    monkeypatch.setattr(u.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a, 36, '', 'User interaction is not allowed.'))
    u.refresh_all()
    assert not (home / 'calls').exists() and not (home / 'cfg').exists()


def test_batch_and_profile_locks_prevent_overlap(home):
    path = home / 'cfg/cache'; path.mkdir(parents=True)
    with (path / 'refresh-all.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        u.refresh_all()
        assert not (home / 'calls').exists()
    with Path(u.cache_path('') + '.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        u.refresh_all()
    assert 'default' not in (home / 'calls').read_text().splitlines()
    assert len((home / 'calls').read_text().splitlines()) == 2


def test_total_deadline_caps_each_fetch_and_stops_next_profile(home, monkeypatch):
    # 가짜 시계로 시간 상한을 넘긴다. 프로세스를 죽이는 시험은 하지 않는다.
    clock = [100.0]
    monkeypatch.setattr(u.time, 'monotonic', lambda: clock[0])
    timeouts = []
    def fetch(profile, timeout=20):
        timeouts.append(timeout)
        clock[0] += 7
        return 'Current week (all models): 23% used\n'
    monkeypatch.setattr(u, 'fetch', fetch)
    u.refresh_all(max_seconds=5)
    assert timeouts == [5]
    assert u.read_cache('')[0][0] == '23'
    assert u.read_cache(str(home / 'profiles/alpha'))[0] is None


def test_disabled_and_no_login_do_not_probe(home):
    (home / 'cfg').mkdir()
    (home / 'cfg/usage-refresh.disabled').touch()
    u.refresh_all()
    assert not (home / 'calls').exists()


def test_missing_login_is_skipped(home):
    (home / '.claude.json').write_text('{}')
    u.refresh_all()
    assert 'default' not in (home / 'calls').read_text().splitlines()


def test_short_parent_requests_launchd_without_starting_child(home, monkeypatch):
    monkeypatch.setattr(u.sys, 'platform', 'darwin')
    agent = home / 'Library/LaunchAgents/local.ccp.usage-refresh.plist'
    agent.parent.mkdir(parents=True); agent.write_text('synthetic')
    calls = []
    def run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, '', '')
    monkeypatch.setattr(u.subprocess, 'run', run)
    monkeypatch.setattr(u.subprocess, 'Popen', lambda *a, **kw: pytest.fail('launchd must own the worker'))
    u.start_refresh('')
    assert calls == [['launchctl', 'kickstart', f'gui/{os.getuid()}/local.ccp.usage-refresh']]


def test_installer_gui_agent_and_opt_out(home, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location('usage_agent', ROOT / 'ccp_usage_agent.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.sys, 'platform', 'darwin')
    fake = home / 'bin/launchctl'
    fake.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$HOME/launchcalls"\n[ "$1" != print ]\n')
    fake.chmod(0o755)
    assert module.install_agent() == 0
    import plistlib
    path = home / 'Library/LaunchAgents/local.ccp.usage-refresh.plist'
    agent = plistlib.loads(path.read_bytes())
    assert agent['StartInterval'] == 900 and agent['RunAtLoad'] is True
    assert agent['LimitLoadToSessionType'] == 'Aqua'
    assert agent['ProgramArguments'] == [sys.executable, str(ROOT / 'ccp-usage-refresh')]
    assert agent['EnvironmentVariables']['HOME'] == str(home)
    assert set(agent['EnvironmentVariables']) == {'HOME', 'PATH', 'CCP_CONFIG_DIR', 'CLAUDE_PROFILES'}
    assert f'bootstrap gui/{os.getuid()} {path}' in (home / 'launchcalls').read_text()
    before = (home / 'launchcalls').read_text()
    assert module.install_agent(enabled=False) == 0
    assert (home / 'cfg/usage-refresh.disabled').exists()
    assert (home / 'launchcalls').read_text() == before
    u.refresh_all()
    assert not (home / 'calls').exists()


def test_installer_does_not_load_from_ssh(home, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location('usage_agent', ROOT / 'ccp_usage_agent.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.sys, 'platform', 'darwin')
    monkeypatch.setenv('SSH_CONNECTION', 'synthetic')
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: pytest.fail('must not bootstrap in SSH'))
    assert module.install_agent() == 0
    assert (home / 'Library/LaunchAgents/local.ccp.usage-refresh.plist').exists()


def test_two_cli_runs_share_batch_lock(home):
    fake = home / 'bin/claude'
    fake.write_text('#!/bin/sh\nprintf "called\\n" >> "$HOME/calls"\nsleep 0.1\nprintf "Current week (all models): 19%% used\\n"\n')
    env = dict(os.environ)
    commands = [subprocess.Popen([sys.executable, str(ROOT / 'ccp-usage-refresh')], env=env) for _ in range(2)]
    assert all(p.wait(timeout=10) == 0 for p in commands)
    assert len((home / 'calls').read_text().splitlines()) == 3


def test_install_shell_wires_refresh_command_in_fake_home(home, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(home / '.config'))
    monkeypatch.setenv('ZDOTDIR', str(home))
    monkeypatch.delenv('SSH_CONNECTION', raising=False)
    monkeypatch.delenv('SSH_TTY', raising=False)
    fake = home / 'bin/launchctl'
    fake.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$HOME/launchcalls"\n[ "$1" != print ]\n')
    fake.chmod(0o755)
    result = subprocess.run(['bash', str(ROOT / 'install.sh'), '--no-statusline'], capture_output=True, text=True, env=dict(os.environ))
    assert result.returncode == 0, result.stderr
    command = home / '.local/bin/ccp-usage-refresh'
    assert command.is_symlink() and command.resolve() == ROOT / 'ccp-usage-refresh'
    if sys.platform == 'darwin':
        import plistlib
        agent = plistlib.loads((home / 'Library/LaunchAgents/local.ccp.usage-refresh.plist').read_bytes())
        assert agent['EnvironmentVariables']['CLAUDE_PROFILES'] == str(home / 'profiles')
        assert f'bootstrap gui/{os.getuid()}' in (home / 'launchcalls').read_text()
    result = subprocess.run(['bash', str(ROOT / 'install.sh'), '--no-statusline', '--no-usage-refresh'], capture_output=True, text=True, env=dict(os.environ))
    assert result.returncode == 0 and (home / 'cfg/usage-refresh.disabled').exists()


def test_failed_profile_does_not_starve_later_profiles(home, monkeypatch):
    clock = [100.0]
    wall = [100000.0]
    monkeypatch.setattr(u.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(u.time, 'time', lambda: wall[0])
    called = []
    def fetch(profile, timeout=20):
        called.append(profile)
        clock[0] += 5
        return ''
    monkeypatch.setattr(u, 'fetch', fetch)
    u.refresh_all(max_seconds=5)
    assert called == ['']
    wall[0] += 900
    u.refresh_all(max_seconds=5)
    assert called == ['', str(home / 'profiles/alpha')]


def test_keychain_check_respects_batch_deadline(home, monkeypatch):
    # 원래 함수로 security의 timeout까지 전체 예산에 포함되는지 확인한다.
    monkeypatch.undo()
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.delenv('CCP_SKIP_KEYCHAIN_CHECK', raising=False)
    monkeypatch.setattr(u.sys, 'platform', 'darwin')
    monkeypatch.setattr(u.time, 'monotonic', lambda: 100)
    directory = home / 'Library/Keychains'; directory.mkdir(parents=True)
    (directory / 'login.keychain-db').write_text('')
    seen = []
    def security(cmd, **kw):
        seen.append(kw['timeout'])
        return subprocess.CompletedProcess(cmd, 0, '', '')
    monkeypatch.setattr(u.subprocess, 'run', security)
    assert not u.keychain_locked(deadline=102)
    assert seen == [2]
    assert u.keychain_locked(deadline=99)
    assert seen == [2]
