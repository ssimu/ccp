#!/usr/bin/env python3
"""가짜 HOME/합성 캐시로 HEAD와 작업트리 그래프·표를 비교한다. 네트워크 호출 없음."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.datetime(2026, 11, 13, 13, 0).timestamp()
OBSERVED = datetime.datetime(2026, 11, 9, 10, 0).timestamp()

# GUI/서브프로세스 대신 순수 캐시 메뉴를 호출한다. 기준 시각도 합성으로 고정한다.
WRAPPER = '''
import datetime, os, runpy, sys, time
class Fixed(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls.fromtimestamp(float(os.environ['PREVIEW_NOW']), tz)
datetime.datetime = Fixed
time.time = lambda: float(os.environ['PREVIEW_NOW'])
import ccp_usage
ccp_usage.keychain_locked = lambda: False
ccp_usage.start_refresh = lambda profile: None
for i in range(2):
    profile = os.path.join(os.environ['HOME'], 'profiles', 'sample-' + str(i))
    with open(os.path.join(os.environ['PREVIEW_ROWS'], str(i)), 'w') as fh:
        fh.write(ccp_usage.menu(profile))
sys.argv = ['ccp_render.py', os.environ['PREVIEW_ROWS'], '-', '', 'claude:sample-0', 'claude:sample-1']
runpy.run_path(os.path.join(os.environ['PREVIEW_CODE'], 'ccp_render.py'), run_name='__main__')
'''


def main():
    with tempfile.TemporaryDirectory(prefix='ccp-preview-') as temporary:
        base = Path(temporary)
        old = base / 'before'; old.mkdir()
        for name in ('ccp_usage.py', 'ccp_render.py', 'ccp_i18n.py'):
            content = subprocess.run(['git', 'show', 'HEAD:' + name], cwd=ROOT, capture_output=True, text=True, check=True).stdout
            (old / name).write_text(content)
        # 리셋이 지난 옛 12칸 TSV, 그리고 아직 리셋 전이지만 오래된 TSV.
        fixtures = [
            ['61', '780', '81', '30', 'Fable', '100', 'ok', '11/09 23:00', '11/09 10:30', '10080', '300', ''],
            ['41', '10080', '', '', 'Fable', '77', 'ok', '11/16 10:00', '', '10080', '300', ''],
        ]
        print('합성 기준: 2026-11-13 13:00, 관측: 2026-11-09 10:00. 숫자는 남은 양. 실제 계정 없음.\n')
        for title, code in [('변경 전 (HEAD)', old), ('변경 후', ROOT)]:
            home = base / ('old-home' if code == old else 'new-home'); home.mkdir()
            cfg = home / 'cfg'; cache = cfg / 'cache'; cache.mkdir(parents=True)
            rows = home / 'rows'; rows.mkdir()
            for i, values in enumerate(fixtures):
                profile = home / 'profiles' / f'sample-{i}'; profile.mkdir(parents=True)
                (profile / '.claude.json').write_text(json.dumps({'oauthAccount': {'emailAddress': 'sample@example.com'}}))
                path = cache / f'usage-sample-{i}.tsv'; path.write_text('\t'.join(values))
                os.utime(path, (OBSERVED, OBSERVED))
            for view in ('graph', 'table'):
                (cfg / 'view').write_text(view)
                env = dict(os.environ, HOME=str(home), CCP_CONFIG_DIR=str(cfg), CCP_LANG='ko',
                           PREVIEW_NOW=str(NOW), PREVIEW_ROWS=str(rows), PREVIEW_CODE=str(code), PYTHONPATH=str(code))
                result = subprocess.run([sys.executable, '-c', WRAPPER], cwd=home, env=env, capture_output=True, text=True, check=True)
                print(f'{title} — {view}\n\n```text\n{result.stdout.rstrip()}\n```\n')


if __name__ == '__main__':
    main()
