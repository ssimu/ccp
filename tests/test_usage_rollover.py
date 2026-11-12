"""합성 사용량만으로 독립 리셋과 소비자 일관성을 검증한다."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import ccp_usage as u

NOW = dt.datetime(2026, 12, 31, 23, 0).timestamp()
ROOT = Path(__file__).resolve().parents[1]


def row(w=120, s=30, m=None):
    r = ['61', str(w), '81', str(s), 'Fable', '100', 'ok', '', '', '10080', '300', '']
    if m is not None:
        r[11] = 'ccp:v1:' + json.dumps({'resets': {'model': NOW + m * 60}})
    return r


@pytest.mark.parametrize('model_reset,expected', [
    ('Jan 1 at 1am', 120), ('Jan 2 at 1am', 1560), ('', 120)])
def test_model_reset_parse_and_legacy_fallback(model_reset, expected):
    text = 'Current week (all models): 61% used · resets Jan 1 at 1am\nCurrent week (Fable): 100% used'
    if model_reset:
        text += ' · resets ' + model_reset
    r = u.parse(text, dt.datetime.fromtimestamp(NOW)).split('\t')
    assert len(r) == 12
    assert u.model_reset(r, now=NOW)[0] == expected


@pytest.mark.parametrize('w,s,m,expected', [
    (-60, 30, 120, ('0', '81', '100', '10020', '30', 120)),
    (120, -1, 60, ('61', '0', '100', '120', '299', 60)),
    (120, 30, -60, ('61', '81', '0', '120', '30', 10020)),
    (-20161, -601, None, ('0', '0', '0', '10079', '299', 10079)),
    (0, 0, 0, ('0', '0', '0', '10080', '300', 10080)),
])
def test_independent_windows_and_multiple_rollovers(w, s, m, expected):
    r = u.normalize(row(w, s, m), now=NOW)
    assert (r[0], r[2], r[5], r[1], r[3], u.model_reset(r, now=NOW)[0]) == expected
    assert '추정' in u.display_note(r, lang='ko')
    assert r[6] == 'stale'
    assert u.normalize(r, now=NOW) == r


def test_legacy_cache_uses_mtime_and_rolls_across_year(monkeypatch, tmp_path):
    monkeypatch.setenv('CCP_CONFIG_DIR', str(tmp_path))
    monkeypatch.setattr(u.time, 'time', lambda: NOW + 3 * 3600)
    u.write_cache('', '\t'.join(row()))
    os.utime(u.cache_path(''), (NOW, NOW))
    r, age = u.read_cache('')
    assert (r[0], r[2], r[5]) == ('0', '0', '0')
    assert r[7] == '01/08 01:00' and r[8] == '01/01 04:30'
    assert age == 10800


def test_native_model_reset_is_independent(monkeypatch, tmp_path):
    monkeypatch.setattr(u.time, 'time', lambda: NOW)
    (tmp_path / '.claude.json').write_text(json.dumps({
        'oauthAccount': {'accountUuid': 'synthetic'},
        'cachedUsageUtilization': {'accountUuid': 'synthetic', 'fetchedAtMs': NOW * 1000,
            'utilization': {'limits': [
                {'kind': 'weekly_all', 'percent': 61, 'resets_at': dt.datetime.fromtimestamp(NOW + 7200, dt.timezone.utc).isoformat()},
                {'kind': 'weekly_scoped', 'percent': 100, 'resets_at': dt.datetime.fromtimestamp(NOW - 3600, dt.timezone.utc).isoformat(),
                 'scope': {'model': {'display_name': 'Fable'}}}]}}}))
    r, _ = u.native_cache(str(tmp_path))
    assert (r[0], r[5]) == ('61', '0')
    assert u.model_reset(r, now=NOW)[0] == 10020


@pytest.mark.parametrize('lang,word', [('ko', '추정'), ('en', 'estimated'), ('ja', '推定'), ('zh', '估算')])
@pytest.mark.parametrize('view', ['graph', 'table'])
def test_renderer_estimates_visible_and_metadata_hidden(tmp_path, lang, word, view):
    now = u.time.time()
    r = u.normalize(row(-60, 30), now=now)
    (tmp_path / '0').write_text('\t'.join(r))
    (tmp_path / 'view').write_text(view)
    env = dict(os.environ, HOME=str(tmp_path), CCP_CONFIG_DIR=str(tmp_path), CCP_LANG=lang)
    result = subprocess.run([sys.executable, str(ROOT / 'ccp_render.py'), str(tmp_path), '-', '', 'claude:sample'],
                            env=env, text=True, capture_output=True, check=True)
    assert word in result.stdout and '100%' in result.stdout
    assert 'ccp:v1:' not in result.stdout


def test_saving_snapshot_fallback_does_not_refresh_observation_age(monkeypatch, tmp_path):
    monkeypatch.setenv('CCP_CONFIG_DIR', str(tmp_path))
    monkeypatch.setattr(u.time, 'time', lambda: NOW)
    r = u.normalize(row(), age=7200, now=NOW)
    u.save('', '\t'.join(r))
    cached, age = u.read_cache('')
    assert age == 7200 and cached[6] == 'stale'


def test_menu_normalizes_newer_disk_cache_without_losing_model_reset(monkeypatch, tmp_path):
    monkeypatch.setenv('CCP_CONFIG_DIR', str(tmp_path))
    monkeypatch.setattr(u.time, 'time', lambda: NOW)
    monkeypatch.setattr(u, 'logged_in', lambda d: True)
    monkeypatch.setattr(u, 'keychain_locked', lambda: False)
    monkeypatch.setattr(u, 'native_cache', lambda d: (None, None))
    monkeypatch.setattr(u, 'start_refresh', lambda d: None)
    r = row(-60, 30, 120)
    u.write_cache('', '\t'.join(r))
    os.utime(u.cache_path(''), (NOW, NOW))
    result = u.menu('').split('\t')
    assert result[0] == '0' and result[5] == '100'
    assert u.model_reset(result, now=NOW)[0] == 120
    assert '추정' in u.display_note(result, lang='ko')


def test_model_cache_survives_newer_snapshot_without_scoped_limit(monkeypatch, tmp_path):
    monkeypatch.setenv('CCP_CONFIG_DIR', str(tmp_path))
    monkeypatch.setattr(u.time, 'time', lambda: NOW)
    u.write_cache('', '\t'.join(row()))
    os.utime(u.cache_path(''), (NOW - 30, NOW - 30))
    snapshot = row(); snapshot[4] = snapshot[5] = ''
    monkeypatch.setattr(u, 'native_cache', lambda d: (snapshot, 1))
    selected, age = u.best_cache('', model_only=True)
    assert selected[4:6] == ['Fable', '100'] and age == 30


@pytest.mark.parametrize('independent_model', [False, True])
def test_stale_table_fits_six_accounts_in_80_by_24(monkeypatch, tmp_path, independent_model):
    import contextlib
    import io
    import runpy
    import shutil
    import unicodedata
    import re
    class Terminal(io.StringIO):
        def isatty(self):
            return True
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('CCP_CONFIG_DIR', str(tmp_path))
    monkeypatch.setenv('CCP_LANG', 'ko')
    monkeypatch.setattr(shutil, 'get_terminal_size', lambda *a: os.terminal_size((80, 24)))
    for i in range(6):
        raw = row()
        if independent_model:
            raw[11] = 'ccp:v1:' + json.dumps({'resets': {'model': u.time.time() + 3600}})
        r = u.normalize(raw, age=7200)
        (tmp_path / str(i)).write_text('\t'.join(r))
    monkeypatch.setattr(sys, 'argv', [str(ROOT / 'ccp_render.py'), str(tmp_path), '-', ''] + [f'claude:sample{i}' for i in range(6)])
    out = Terminal()
    with contextlib.redirect_stdout(out), pytest.raises(SystemExit):
        runpy.run_path(str(ROOT / 'ccp_render.py'), run_name='__main__')
    lines = re.sub(r'\033\[[0-9;]*m', '', out.getvalue()).splitlines()
    assert len(lines) <= 24
    assert all(sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in line) < 80 for line in lines)
    assert out.getvalue().count('cache ') == 6
    assert '\033[2m100%\033[0m' in out.getvalue()


def test_yearless_previous_december_rolls_forward_in_january():
    now = dt.datetime(2027, 1, 1, 1, 0)
    r = u.parse('Current week (all models): 61% used · resets Dec 31 at 11pm\nCurrent week (Fable): 100% used · resets Jan 2 at 1am', now).split('\t')
    assert r[0] == '0' and r[7] == '01/07 23:00' and r[1] == '9960'
    assert r[5] == '100' and u.model_reset(r, now=now.timestamp())[0] == 1440


def test_recommendation_prefers_measured_value_over_estimated_full_window(tmp_path):
    now = u.time.time()
    for i, raw in enumerate((row(-60, -60), row(120, 30))):
        if i == 1:
            raw[0], raw[5] = '80', '80'
        (tmp_path / str(i)).write_text('\t'.join(u.normalize(raw, now=now)))
    env = dict(os.environ, HOME=str(tmp_path), CCP_CONFIG_DIR=str(tmp_path), CCP_LANG='ko')
    subprocess.run([sys.executable, str(ROOT / 'ccp_render.py'), str(tmp_path), '-', '', 'claude:estimated', 'claude:measured'],
                   env=env, text=True, capture_output=True, check=True)
    assert 'rec\t1' in (tmp_path / '_meta').read_text()
