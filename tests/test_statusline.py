"""상태줄(ccp_statusline.py) — statusline.conf 의 항목이 실제 출력에 반영되는지."""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOW = time.time()
PAYLOAD = json.dumps({"model": {"display_name": "Opus"}, "workspace": {"current_dir": str(Path.home() / "proj")},
                      "context_window": {"used_percentage": 12},
                      "rate_limits": {"seven_day": {"used_percentage": 38, "resets_at": NOW + 2 * 86400 + 3 * 3600},
                                      "five_hour": {"used_percentage": 12, "resets_at": NOW + 100 * 60}}})


def run(conf=None, payload=PAYLOAD, lang="ko", extra_env=None, custom_script=None):
    with tempfile.TemporaryDirectory() as cfg:
        if conf is not None:
            (Path(cfg) / "statusline.conf").write_text(conf)
        if custom_script is not None:
            p = Path(cfg) / "statusline.sh"; p.write_text(custom_script); p.chmod(0o755)
        env = dict(os.environ, CCP_CONFIG_DIR=cfg, CCP_LANG=lang, CLAUDE_CONFIG_DIR="/nonexistent")
        env.update(extra_env or {})
        r = subprocess.run(["bash", str(ROOT / "statusline.sh")], input=payload, capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr
        return r.stdout


def plain(s):
    import re
    return re.sub(r"\033\[[0-9;]*m", "", s)


def test_기본값():
    out = plain(run())
    assert out.startswith("nonexistent:미로그인 │ 주간 ██░░░ 38% ↻2일3시간 │ 세션 █░░░░ 12% ↻1시간40분 │ Opus │ ~/proj │ ctx 12%")


def test_segments_순서와_선택():
    out = plain(run("segments = model account\n"))
    assert out == "Opus │ nonexistent:미로그인"


def test_separator():
    assert " ~ " in plain(run("segments = model dir\nseparator = ' ~ '\n"))


def test_막대_없이_숫자만():
    out = plain(run("segments = weekly\nbar = 0\nshow_reset = no\n"))
    assert out == "주간 38%"


def test_막대_글자와_폭():
    out = plain(run("segments = weekly\nbar = 10\nbar_chars = '#-'\nshow_reset = no\n"))
    assert out == "주간 ####------ 38%"


def test_남은_비율():
    out = plain(run("segments = weekly session\npercent = left\nbar = 0\nshow_reset = no\n"))
    assert out == "주간 62% │ 세션 88%"


def test_계정_형식():
    payload = json.loads(PAYLOAD)
    with tempfile.TemporaryDirectory() as prof:
        (Path(prof) / ".claude.json").write_text(json.dumps({"oauthAccount": {"emailAddress": "me@example.com"}}))
        out = plain(run('segments = account\naccount = "{profile} <{user}@…>"\n', json.dumps(payload),
                        extra_env={"CLAUDE_CONFIG_DIR": prof}))
        assert out == f"{Path(prof).name} <me@…>"


def test_format_틀():
    out = plain(run('format = "[{model}] {weekly} / {ctx}"\nbar = 0\nshow_reset = no\n'))
    assert out == "[Opus] 주간 38% / ctx 12%"


def test_format_틀_오류는_죽지_않고_알려준다():
    out = plain(run('format = "{nope}"\n'))
    assert "format" in out


def test_색_기준():
    out = run("segments = weekly\nthresholds = 30 35\nbar = 0\nshow_reset = no\n")
    assert "\033[31m38%" in out            # 38% ≥ 35 → 빨강
    out = run("segments = weekly\nthresholds = 30 50\nbar = 0\nshow_reset = no\n")
    assert "\033[33m38%" in out            # 30 ≤ 38 < 50 → 노랑
    out = run("segments = weekly\ncolor = no\nbar = 0\nshow_reset = no\n")
    assert "\033[" not in out


def test_dir_모드():
    assert plain(run("segments = dir\ndir = name\n")) == "proj"
    assert plain(run("segments = dir\ndir = full\n")) == str(Path.home() / "proj")


def test_언어를_설정에서만_바꾼다():
    out = plain(run("segments = weekly\nlang = en\nbar = 0\nshow_reset = no\n", lang="ko"))
    assert out == "weekly 38%"


def test_rate_limits_없으면_안내():
    p = json.loads(PAYLOAD); del p["rate_limits"]
    assert "한도 조회 전" in plain(run("segments = quota\n", json.dumps(p)))


def test_사용자_스크립트가_있으면_그것을_실행():
    out = run(custom_script="#!/bin/bash\ncat >/dev/null; printf 'MINE'\n")
    assert out == "MINE"


def test_따옴표_값_뒤의_주석은_버린다():
    out = plain(run('segments = git\ngit = "git {branch}"      # 주석 / comment\n'))
    assert "#" not in out and "주석" not in out


def test_CCP_LANG_이_없으면_config_zsh_에서_읽는다():
    with tempfile.TemporaryDirectory() as cfg:
        (Path(cfg) / "config.zsh").write_text("CCP_CLAUDE_ARGS=()\nCCP_LANG=ja\n")
        (Path(cfg) / "statusline.conf").write_text("segments = weekly\nbar = 0\nshow_reset = no\n")
        env = {k: v for k, v in os.environ.items() if k != "CCP_LANG"}
        env.update(CCP_CONFIG_DIR=cfg, CLAUDE_CONFIG_DIR="/nonexistent", LANG="en_US.UTF-8")
        r = subprocess.run(["bash", str(ROOT / "statusline.sh")], input=PAYLOAD, capture_output=True, text=True, env=env)
        assert plain(r.stdout) == "週間 38%", r.stdout


def test_설정_파일이_없어도_기본으로_돈다():
    assert "주간" in plain(run(None))
