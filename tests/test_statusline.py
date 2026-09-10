"""상태줄(ccp_statusline.py) — statusline.conf 의 항목이 실제 출력에 반영되는지."""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOW = time.time()
PAYLOAD = json.dumps({"model": {"display_name": "Opus"}, "workspace": {"current_dir": str(Path.home() / "proj")},
                      "context_window": {"used_percentage": 12},
                      "rate_limits": {"seven_day": {"used_percentage": 38, "resets_at": NOW + 2 * 86400 + 3 * 3600},
                                      "five_hour": {"used_percentage": 12, "resets_at": NOW + 100 * 60}}})


NO_BG = "model_quota_bg = no\n"   # 테스트에서 실제 claude 를 띄우지 않도록


def run(conf=None, payload=PAYLOAD, lang="ko", extra_env=None, custom_script=None, cache=None, cache_age=0):
    with tempfile.TemporaryDirectory() as cfg:
        (Path(cfg) / "statusline.conf").write_text(NO_BG + (conf or ""))
        if cache is not None:
            c = Path(cfg) / "cache"; c.mkdir()
            f = c / "usage-default.tsv"; f.write_text(cache + "\n")
            os.utime(f, (time.time() - cache_age, time.time() - cache_age))
        if custom_script is not None:
            p = Path(cfg) / "statusline.sh"; p.write_text(custom_script); p.chmod(0o755)
        env = dict(os.environ, CCP_CONFIG_DIR=cfg, CCP_LANG=lang, CLAUDE_CONFIG_DIR="/nonexistent")
        env.update(extra_env or {})
        if cache is not None: env.pop("CLAUDE_CONFIG_DIR")      # 캐시는 기본 프로필(usage-default) 것
        r = subprocess.run(["bash", str(ROOT / "statusline.sh")], input=payload, capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr
        return r.stdout


def plain(s):
    import re
    return re.sub(r"\033\[[0-9;]*m", "", s)


def test_기본값():
    # 주간: 남은 2일3시간/7일 → 경과 0.69 → 눈금 6번째 칸. 사용 38% → 4칸 채움.  세션: 남은 100/300분 → 경과 0.67 → 6번째. 12% → 1칸.
    out = plain(run())
    assert out.startswith("nonexistent:미로그인 │ Opus │ 주간 ████░░┃░░░ 38% │ 세션 █░░░░░┃░░░ 12% │ ~/proj │ ctx 12%")


def test_리셋_시간은_켜면_보인다():
    out = plain(run("segments = weekly\nshow_reset = yes\n"))
    assert out.endswith("38% ↻2일3시간")


def test_눈금을_끄면_막대만():
    out = plain(run("segments = weekly\nbar_tick = no\n"))
    assert out == "주간 ████░░░░░░ 38%"


def test_눈금은_리셋_직전이면_오른쪽_끝():
    p = json.loads(PAYLOAD); p["rate_limits"]["seven_day"]["resets_at"] = NOW + 60
    out = plain(run("segments = weekly\n", json.dumps(p)))
    assert out == "주간 ████░░░░░┃ 38%"


CACHE = "25\t5580\t48\t190\tFable\t47\tok\t09/14 15:00\t09/10 21:10\t10080\t300\t"


def test_모델_전용_한도는_캐시에서():
    out = plain(run("segments = quota\nbar_tick = no\nshow_reset = yes\n", cache=CACHE))
    assert "Fable █████░░░░░ 47% ↻3일21시간" in out and not out.endswith("~")


def test_낡은_캐시는_물결표():
    out = plain(run("segments = model_quota\nmodel_quota_ttl = 1\n", cache=CACHE, cache_age=5 * 60))
    assert out.startswith("Fable ") and out.endswith("~")
    assert "↻" not in out                            # 낡은 캐시의 리셋 시각은 믿을 수 없어 생략


def test_신선한_캐시는_지난_시간을_빼고_리셋을_보인다():
    out = plain(run("segments = model_quota\nmodel_quota_ttl = 60\nshow_reset = yes\n", cache=CACHE, cache_age=5 * 60))
    assert "↻3일20시간" in out and not out.endswith("~")   # 5580분 − 5분


def test_캐시가_없으면_모델_조각은_빠진다():
    out = plain(run("segments = quota\n"))
    assert "Fable" not in out and out.startswith("주간")


def test_모델_한도가_없는_계정은_조각_없음():
    out = plain(run("segments = quota\n", cache="5\t100\t1\t10\t\t\tok\t\t\t10080\t300\t"))
    assert out.count("│") == 1


def test_segments_순서와_선택():
    out = plain(run("segments = model account\n"))
    assert out == "Opus │ nonexistent:미로그인"


def test_separator():
    assert " ~ " in plain(run("segments = model dir\nseparator = ' ~ '\n"))


def test_막대_없이_숫자만():
    out = plain(run("segments = weekly\nbar = 0\n"))
    assert out == "주간 38%"


def test_막대_글자와_폭():
    out = plain(run("segments = weekly\nbar = 5\nbar_chars = '#-'\nbar_tick = no\n"))
    assert out == "주간 ##--- 38%"


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
        (Path(cfg) / "statusline.conf").write_text(NO_BG + "segments = weekly\nbar = 0\nshow_reset = no\n")
        env = {k: v for k, v in os.environ.items() if k != "CCP_LANG"}
        env.update(CCP_CONFIG_DIR=cfg, CLAUDE_CONFIG_DIR="/nonexistent", LANG="en_US.UTF-8")
        r = subprocess.run(["bash", str(ROOT / "statusline.sh")], input=PAYLOAD, capture_output=True, text=True, env=env)
        assert plain(r.stdout) == "週間 38%", r.stdout


def test_설정_파일이_없어도_기본으로_돈다():
    with tempfile.TemporaryDirectory() as cfg:
        env = dict(os.environ, CCP_CONFIG_DIR=cfg, CCP_LANG="ko", CLAUDE_CONFIG_DIR="/nonexistent", CCP_STATUSLINE_TEST_NO_BG="1")
        r = subprocess.run(["bash", str(ROOT / "statusline.sh")], input=PAYLOAD, capture_output=True, text=True, env=env)
        assert "주간" in plain(r.stdout)
