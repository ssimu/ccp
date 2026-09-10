"""Codex config.toml 에 [tui].status_line 을 넣는 병합 — 있는 건 건드리지 않고, 없는 곳에만."""
import os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ccp_codex_statusline as cs  # noqa: E402

ITEMS = '["model-with-reasoning", "five-hour-limit", "weekly-limit", "context-remaining", "current-dir", "git-branch"]'


def test_tui_섹션이_없으면_끝에_만든다():
    new, st = cs.merge('model = "gpt-5"\n\n[projects."/x"]\ntrust_level = "trusted"\n')
    assert st == "appended"
    assert new.endswith('[tui]\nstatus_line = ' + ITEMS + '   # ccp: 모델·5시간·주간 한도. 바꾸려면 codex 안에서 /statusline\nstatus_line_use_colors = true\n')
    assert new.startswith('model = "gpt-5"\n')                   # 앞부분은 그대로


def test_tui_섹션이_있으면_그_안에_넣는다():
    new, st = cs.merge('[tui]\n# 주석\ntheme = "dark"\n\n[other]\nx = 1\n')
    assert st == "inserted"
    assert new.index("[tui]") < new.index("status_line =") < new.index('theme = "dark"') < new.index("[other]")


def test_이미_있으면_그대로():
    text = '[tui]\nstatus_line = ["model"]\n'
    new, st = cs.merge(text)
    assert st == "kept" and new == text


def test_다른_섹션의_status_line_은_무시():
    new, st = cs.merge('[foo]\nstatus_line = ["x"]\n')
    assert st == "appended" and cs.current(new) == ITEMS


def test_빈_파일():
    new, st = cs.merge("")
    assert st == "appended" and new.startswith("[tui]\n")


def test_apply_는_백업을_남기고_심링크의_실파일을_고친다():
    with tempfile.TemporaryDirectory() as d:
        real = Path(d) / "real.toml"; real.write_text('a = 1\n')
        link = Path(d) / "config.toml"; link.symlink_to(real)
        assert cs.apply(str(link)) == "appended"
        assert link.is_symlink() and "status_line" in real.read_text()
        assert any(p.name.startswith("real.toml.bak-") or p.name.startswith("config.toml.bak-") for p in Path(d).iterdir())
        assert cs.apply(str(link)) == "kept"


def test_결과는_codex_가_읽을_수_있는_TOML():
    """python3.11+ 의 tomllib 이 있으면 파싱해 본다."""
    try:
        import tomllib
    except ImportError:
        import pytest; pytest.skip("tomllib 없음")
    new, _ = cs.merge('[tui]\ntheme = "dark"\n[projects."/x"]\ntrust_level = "trusted"\n')
    doc = tomllib.loads(new)
    assert doc["tui"]["status_line"][0] == "model-with-reasoning" and doc["tui"]["status_line_use_colors"] is True
