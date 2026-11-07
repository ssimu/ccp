from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

import pytest

_path = str(Path(__file__).resolve().parents[1] / "fleet" / "fleet-jobs")
_loader = SourceFileLoader("fleet_jobs", _path)
fj = module_from_spec(spec_from_loader("fleet_jobs", _loader))
_loader.exec_module(fj)

CONF = {"default_cwd": "~/fleet-work", "machines": {"macmini": {"profile": "amc-team"}}}
PROJS = {"demo": {"machine": "macmini", "cwd": "~/projects/demo", "profile": "personal", "codex_profile": "bmc2"}}


def test_resolve_without_registry():
    r = fj.resolve(CONF, {}, on="macmini", project=None, profile=None, cwd=None, agent=None)
    assert r == {"machine": "macmini", "profile": "amc-team", "cwd": "~/fleet-work", "agent": "claude",
                 "codex_profile": "default", "project": None}


def test_unknown_project_rejected():
    with pytest.raises(ValueError) as e:
        fj.resolve(CONF, PROJS, on=None, project="nope", profile=None, cwd=None, agent=None)
    assert "demo" in str(e.value)


def test_project_fills_defaults():
    r = fj.resolve(CONF, PROJS, on=None, project="demo", profile=None, cwd=None, agent="codex")
    assert (r["machine"], r["cwd"], r["profile"], r["codex_profile"], r["agent"], r["project"]) == \
        ("macmini", "~/projects/demo", "personal", "bmc2", "codex", "demo")


def test_explicit_overrides_project():
    r = fj.resolve(CONF, PROJS, on="wooui", project="demo", profile="team", cwd="~/fleet-work/x", agent=None)
    assert (r["machine"], r["profile"], r["cwd"]) == ("wooui", "team", "~/fleet-work/x")


def test_codex_profile_default():
    r = fj.resolve(CONF, {}, on=None, project=None, profile=None, cwd=None, agent="codex")
    assert r["machine"] == "local" and r["codex_profile"] == "default"


def test_bad_agent_rejected():
    with pytest.raises(ValueError):
        fj.resolve(CONF, {}, on=None, project=None, profile=None, cwd=None, agent="gpt")


def test_finished_with_result_is_done():
    assert fj.classify("finished", None, 3, "고쳤다. 테스트 통과.") == "done"


def test_finished_without_result_is_exited():
    assert fj.classify("finished", None, 3, None) == "exited"


def test_question_result():
    assert fj.classify("running", "idle", 2, "질문: A 로 갈까 B 로 갈까") == "question"
    assert "question" in fj.TERMINAL


def test_states_without_result():
    assert fj.classify("running", "blocked", 1, None) == "blocked"
    assert fj.classify("running", "idle", 1, None) == "idle"
    assert fj.classify("running", None, 0, None) == "starting"
    assert fj.classify("running", "working", 1, None) == "running"


def test_projects_missing_or_broken(tmp_path, monkeypatch):
    monkeypatch.setattr(fj, "PROJECTS", str(tmp_path / "none.json"))
    assert fj.projects() == {}
    (tmp_path / "bad.json").write_text("{nope")
    monkeypatch.setattr(fj, "PROJECTS", str(tmp_path / "bad.json"))
    assert fj.projects() == {}


def _job(tmp_path, monkeypatch):
    monkeypatch.setattr(fj, "REG", str(tmp_path))
    return {"id": "j1", "machine": "macmini", "address": "macmini/t9", "result": "/x/j1.result.md", "task": "t",
            "profile": "p", "cwd": "~/fleet-work", "created_at": "2026-11-07T19:00:00+09:00", "phase": "running"}


def test_gone_terminal_with_result_is_done(tmp_path, monkeypatch):
    j = _job(tmp_path, monkeypatch)
    monkeypatch.setattr(fj, "hc_json", lambda *a, **k: {"error": {"code": "not_found"}, "rc": 1})
    monkeypatch.setattr(fj, "remote_read", lambda m, p: "고쳤다\n")
    assert fj.phase(j) == "done" and j["result_text"] == "고쳤다"


def test_gone_terminal_without_result_is_lost(tmp_path, monkeypatch):
    j = _job(tmp_path, monkeypatch)
    monkeypatch.setattr(fj, "hc_json", lambda *a, **k: {"error": {"code": "not_found"}, "rc": 1})
    monkeypatch.setattr(fj, "remote_read", lambda m, p: None)
    assert fj.phase(j) == "lost" and "not_found" in j["hc"]


def test_auto_profile_uses_pick():
    r0 = {"machine": "macmini", "profile": "auto", "agent": "claude", "codex_profile": "auto", "cwd": "~", "project": None}
    conf = {"machines": {"macmini": {"profile": "auto", "fallback_profile": "amc-team"}}}
    seen = []
    def pick(m, agent):
        seen.append((m, agent)); return {"profile": "ra00203", "weekly": "39"}
    r = fj.settle(r0, conf, pick)
    assert r["profile"] == "ra00203" and r["picked"] == "자동 · 주간 39%" and seen == [("macmini", "claude")]
    assert r["codex_profile"] == "auto"   # claude 작업이면 codex 쪽은 고르지 않는다


def test_auto_falls_back_when_nothing_fits():
    r0 = {"machine": "macmini", "profile": "auto", "agent": "claude", "codex_profile": "default", "cwd": "~", "project": None}
    conf = {"machines": {"macmini": {"fallback_profile": "amc-team"}}}
    r = fj.settle(r0, conf, lambda m, a: None)
    assert r["profile"] == "amc-team" and "대체" in r["picked"]


def test_codex_auto_and_explicit_untouched():
    r0 = {"machine": "wooui", "profile": "amc-team", "agent": "codex", "codex_profile": "auto", "cwd": "~", "project": None}
    r = fj.settle(r0, {}, lambda m, a: {"profile": "bmc2", "weekly": "0"})
    assert r["codex_profile"] == "bmc2" and r["profile"] == "amc-team"
    r0 = dict(r0, codex_profile="personal")
    r = fj.settle(r0, {}, lambda m, a: 1 / 0)
    assert r["codex_profile"] == "personal" and r.get("picked") is None


def test_resolve_reads_top_level_auto_defaults():
    conf = {"profile": "auto", "codex_profile": "auto", "machines": {}}
    r = fj.resolve(conf, {}, on="wooui", project=None, profile=None, cwd=None, agent="codex")
    assert r["profile"] == "auto" and r["codex_profile"] == "auto"
