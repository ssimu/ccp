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


# ── 대화형 터미널 질문(ask) ── 사람의 대화형 Claude 터미널에서 나온 질문을 작업판에 올린다(2026-11-08).

@pytest.fixture
def board(tmp_path, monkeypatch):
    monkeypatch.setattr(fj, "REG", str(tmp_path))
    state = {"status": "idle", "sent": [], "killed": []}

    def fake_hc_json(*args, timeout=60):
        if args[0] == "get":
            return {"address": args[1], "state": "live", "status": {"state": state["status"]}, "turn": 5,
                    "foreground": {"cwd": "/Users/swh/proj"}}
        return {}

    class P:
        returncode = 0; stdout = ""; stderr = ""

    def fake_hc(*args, timeout=60, check=False):
        if args[0] == "send":
            state["sent"].append((args[1], args[2]))
        if args[0] in ("kill", "rm"):
            state["killed"].append(args[1])
        return P()

    monkeypatch.setattr(fj, "hc_json", fake_hc_json)
    monkeypatch.setattr(fj, "hc", fake_hc)
    return state


def _ask(text="배포할까요?", on="mbp2", terminal="t13", project="picdock"):
    import argparse
    fj.cmd_ask(argparse.Namespace(on=on, terminal=terminal, project=project, name=None, question=text))
    return [j for j in fj.all_jobs() if j.get("kind") == "ask"]


def test_ask_creates_unreported_question(board):
    js = _ask()
    assert len(js) == 1
    j = js[0]
    assert j["address"] == "mbp2/t13" and j["phase"] == "question" and j["reported"] is False
    assert j["result_text"].startswith("질문:") and "배포할까요?" in j["result_text"]


def test_ask_same_terminal_updates_instead_of_duplicate(board):
    _ask("첫 질문")
    js = _ask("고친 질문")
    assert len(js) == 1 and "고친 질문" in js[0]["result_text"] and js[0]["reported"] is False


def test_ask_stays_question_while_terminal_idle(board):
    j = _ask()[0]
    assert fj.phase(j) == "question"


def test_ask_answered_at_computer_closes_itself(board):
    j = _ask()[0]
    board["status"] = "working"          # 사람이 그 터미널에 직접 답했다
    assert fj.phase(j) == "answered"
    assert j["reported"] is True and "컴퓨터" in j["answer"]


def test_send_to_open_ask_relays_and_closes(board):
    import argparse
    j = _ask()[0]
    fj.cmd_send(argparse.Namespace(id=j["id"], message="승인"))
    j = fj.load(j["id"])
    assert board["sent"] == [("mbp2/t13", "승인")]
    assert j["phase"] == "answered" and j["answer"] == "승인" and j["reported"] is True


def test_send_to_closed_ask_refuses(board):
    import argparse
    j = _ask()[0]
    board["status"] = "working"; fj.phase(j)
    with pytest.raises(SystemExit) as e:
        fj.cmd_send(argparse.Namespace(id=j["id"], message="승인"))
    assert "이미" in str(e.value) and board["sent"] == []


def test_stop_and_clean_never_kill_interactive_terminal(board):
    import argparse
    j = _ask()[0]
    fj.cmd_stop(argparse.Namespace(id=j["id"]))
    fj.cmd_clean(argparse.Namespace(age=0, quiet=True))
    assert board["killed"] == [] and fj.load(j["id"])["phase"] == "stopped"


def test_list_drops_ask_answered_at_computer_after_telegram(board, capsys):
    import argparse
    j = _ask()[0]
    j["reported"] = True; fj.save(j)          # 이미 Telegram 으로 알렸다
    fj.cmd_list(argparse.Namespace(all=False, project=None, json=False))
    assert "결정 필요" in capsys.readouterr().out
    board["status"] = "working"               # 그 뒤 컴퓨터에서 답했다
    fj.cmd_list(argparse.Namespace(all=False, project=None, json=False))
    assert "결정 필요" not in capsys.readouterr().out and fj.load(j["id"])["phase"] == "answered"


def test_ask_on_busy_terminal_waits_for_idle_before_auto_close(board):
    board["status"] = "working"               # 마스터가 다른 일을 시킨 직후 올렸다
    j = _ask()[0]
    assert j["armed"] is False
    assert fj.phase(j) == "question"          # 일하는 중이어도 닫히지 않는다
    board["status"] = "done"; assert fj.phase(j) == "question" and j["armed"] is True
    board["status"] = "working"; assert fj.phase(j) == "answered"   # 그 뒤 다시 일하면 사람이 답한 것


def test_gateway_self_alias_maps_to_local():
    conf = {"aliases": {"macmini": "local"}, "machines": {"local": {"fallback_profile": "amc-team"}}}
    projs = {"demo": {"machine": "macmini", "cwd": "~/fleet-work/demo"}}
    assert fj.resolve(conf, {}, on="macmini", project=None, profile=None, cwd=None, agent=None)["machine"] == "local"
    assert fj.resolve(conf, projs, on=None, project="demo", profile=None, cwd=None, agent=None)["machine"] == "local"
    assert fj.resolve(conf, {}, on="wooui", project=None, profile=None, cwd=None, agent=None)["machine"] == "wooui"


def test_moved_gateway_refuses(monkeypatch, capsys):
    monkeypatch.setattr(fj, "cfg", lambda: {"moved_to": "macmini"})
    monkeypatch.setattr(fj.sys, "argv", ["fleet-jobs", "list"])
    with pytest.raises(SystemExit) as e:
        fj.main()
    assert "macmini" in str(e.value)


def test_reask_on_busy_terminal_rearms(board):
    j = _ask("첫 질문")[0]
    assert j["armed"] is True
    board["status"] = "working"               # 마스터가 다른 지시를 보낸 직후 같은 질문을 다시 올렸다
    j = _ask("다시 올림")[0]
    assert j["armed"] is False and fj.phase(j) == "question"


def test_send_reads_stdin_dash(board, monkeypatch):
    import argparse, io
    j = _ask()[0]
    monkeypatch.setattr("sys.stdin", io.StringIO("긴 답\n둘째 줄\n"))
    fj.cmd_send(argparse.Namespace(id=j["id"], message="-"))
    assert board["sent"] == [("mbp2/t13", "긴 답\n둘째 줄")]


def test_two_asks_same_second_get_distinct_ids(board, monkeypatch):
    # 같은 초에 다른 터미널 두 곳에서 질문을 올리면 id 가 같아 첫 질문이 덮어써지던 것(2026-11-08 실측)
    import datetime
    t = datetime.datetime(2026, 11, 8, 14, 9, 21)
    monkeypatch.setattr(fj, "now", lambda: t)
    _ask("첫 질문", terminal="t60", project="boneage")
    js = _ask("둘째 질문", terminal="t5c", project="kbds")
    assert len(js) == 2 and len({j["id"] for j in js}) == 2
    assert {j["project"] for j in js} == {"boneage", "kbds"}


def test_ask_keep_survives_terminal_working(board):
    # 마스터가 작업자를 막지 않는 결정을 대신 올린 것(--keep)은 터미널이 다시 일해도 닫히지 않는다(2026-11-08:
    # 작업자가 다른 일로 바로 돌아가 boneage·kbds 질문이 '컴퓨터에서 답함'으로 저절로 닫혔다)
    import argparse
    fj.cmd_ask(argparse.Namespace(on="mbp2", terminal="t60", project="boneage", name=None, question="메일 보낼까?", keep=True))
    j = [x for x in fj.all_jobs() if x.get("kind") == "ask"][0]
    board["status"] = "done"; assert fj.phase(j) == "question"
    board["status"] = "working"; assert fj.phase(j) == "question"
    fj.cmd_send(argparse.Namespace(id=j["id"], text="보내", message="보내"))
    assert fj.load(j["id"])["phase"] != "question"


# ── 알림은 주요 이벤트만(2026-11-08 사용자: "Hermes 알림이 너무 많다") ──

def test_unreported_skips_closed_asks(board, capsys):
    # 질문이 닫힌 것(컴퓨터에서 답함·send 로 답함·터미널 사라짐)은 사람이 이미 아는 일 — 조용히 표시만 한다
    j = _ask("배포할까요?")[0]
    j["reported"] = True; fj.save(j)          # 처음 올린 질문은 이미 알림 나감
    board["status"] = "working"; fj.phase(j)   # 컴퓨터에서 답함 → answered
    capsys.readouterr()
    fj.cmd_unreported(None)
    assert capsys.readouterr().out == ""
    assert fj.load(j["id"])["reported"] is True


def test_reask_update_does_not_renotify_by_default(board):
    j = _ask("첫 질문")[0]
    j["reported"] = True; fj.save(j)
    js = _ask("고친 질문")
    assert js[0]["reported"] is True and "고친 질문" in js[0]["result_text"]


def test_reask_with_notify_renotifies(board):
    import argparse
    j = _ask("첫 질문")[0]
    j["reported"] = True; fj.save(j)
    fj.cmd_ask(argparse.Namespace(on="mbp2", terminal="t13", project="picdock", name=None, question="중요하게 바뀜", notify=True))
    assert fj.load(j["id"])["reported"] is False


def test_unreported_still_sends_new_question_and_done(board, capsys):
    _ask("새 질문")
    capsys.readouterr()
    fj.cmd_unreported(None)
    out = capsys.readouterr().out
    assert "결정 필요" in out and "새 질문" in out


def test_done_message_is_short_question_is_full():
    base = {"id": "j1", "machine": "macmini", "profile": "p", "task": "t", "cwd": "~/x", "created_at": "2026-11-08T10:00:00"}
    long = "\n".join(f"줄{i}" for i in range(40))
    done = fj.fmt({**base, "phase": "done", "result_text": long}, with_result=True)
    q = fj.fmt({**base, "phase": "question", "result_text": long}, with_result=True)
    assert "줄7" in done and "줄8" not in done and "fleet-jobs result j1" in done
    assert "줄29" in q
