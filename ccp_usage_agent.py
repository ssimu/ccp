#!/usr/bin/env python3
"""install.sh 전용: 사용량 갱신 LaunchAgent를 데스크톱 GUI 도메인에 설치한다."""
import os
from pathlib import Path
import plistlib
import subprocess
import sys

from ccp_usage import config_dir

LABEL = 'local.ccp.usage-refresh'


def install_agent(enabled=True):
    cfg = Path(config_dir())
    cfg.mkdir(parents=True, exist_ok=True)
    disabled = cfg / 'usage-refresh.disabled'
    if not enabled:
        disabled.touch()
        print('  ✓ 주기 갱신 꺼짐 (usage-refresh.disabled)')
        return 0
    # 설치 재실행은 기존 opt-out을 존중한다. 재개는 사람이 marker를 옮긴 뒤 설치한다.
    if disabled.exists():
        print('  ✓ 주기 갱신 꺼짐 설정 유지')
        return 0
    if sys.platform != 'darwin':
        print('  ✓ macOS 외 환경: ccp-usage-refresh 수동 실행 가능')
        return 0
    repo = Path(__file__).resolve().parent
    target = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')
    target.parent.mkdir(parents=True, exist_ok=True)
    agent = {
        'Label': LABEL,
        'ProgramArguments': [sys.executable, str(repo / 'ccp-usage-refresh')],
        'StartInterval': 900,
        'RunAtLoad': True,
        'LimitLoadToSessionType': 'Aqua',
        'ProcessType': 'Background',
        'EnvironmentVariables': {
            'HOME': str(Path.home()),
            # launchd의 기본 PATH에는 Homebrew/사용자 설치 claude가 없을 수 있다.
            'PATH': os.environ.get('PATH', '/usr/bin:/bin:/usr/sbin:/sbin'),
            'CCP_CONFIG_DIR': str(cfg),
            'CLAUDE_PROFILES': os.environ.get('CLAUDE_PROFILES') or str(Path.home() / '.claude-profiles'),
        },
        'StandardOutPath': '/dev/null',
        'StandardErrorPath': '/dev/null',
    }
    content = plistlib.dumps(agent)
    changed = not target.exists() or target.read_bytes() != content
    if changed:
        target.write_bytes(content)
    if os.environ.get('SSH_CONNECTION') or os.environ.get('SSH_TTY'):
        print('  ! plist만 준비함 — 데스크톱 터미널에서 install.sh를 다시 실행할 것')
        return 0
    domain = f'gui/{os.getuid()}'
    try:
        loaded = subprocess.run(['launchctl', 'print', domain + '/' + LABEL], capture_output=True, timeout=5)
        if loaded.returncode == 0:
            print('  ✓ 사용량 갱신 LaunchAgent 이미 등록됨' + (' (경로/PATH 변경은 다음 데스크톱 로그인 때 반영)' if changed else ''))
            return 0
        result = subprocess.run(['launchctl', 'bootstrap', domain, str(target)], capture_output=True, timeout=5)
        if result.returncode:
            print('  ! GUI LaunchAgent 등록 실패 — 데스크톱 로그인 후 install.sh를 다시 실행할 것')
            return 1
    except (OSError, subprocess.TimeoutExpired):
        print('  ! launchctl 실행 실패 — 데스크톱 터미널에서 다시 설치할 것')
        return 1
    print('  ✓ 사용량 갱신 LaunchAgent: GUI 세션에서 15분마다')
    return 0


if __name__ == '__main__':
    raise SystemExit(install_agent(enabled='--disable' not in sys.argv[1:]))
