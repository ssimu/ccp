#!/usr/bin/env python3
"""Codex CLI 하단 상태줄에 모델·5시간 한도·주간 한도가 보이게 ~/.codex/config.toml 의 [tui].status_line 을 넣는다.

Codex 는 Claude Code 처럼 외부 스크립트를 상태줄에 붙일 수 없다. 대신 자기 상태줄에 넣을 항목을
[tui].status_line 으로 고른다(Codex 안에서 /statusline 으로도 바꿀 수 있고 같은 파일에 저장된다).
ccp 의 codex 프로필들은 config.toml 을 ~/.codex 와 심링크로 공유하므로 여기 한 번 넣으면 전 프로필에 적용된다.

항목 이름(codex 0.153 기준): model, model-with-reasoning, five-hour-limit, weekly-limit, context-remaining,
context-used, current-dir, project-name, git-branch, thread-title, run-state, codex-version, used-tokens,
total-input-tokens, total-output-tokens, thread-id, thread-credits, estimated-thread-cost, task-progress
(요금제에 따라 daily-limit / monthly-limit / annual-limit / usage-limit 도 있다).
ccp 프로필(계정) 이름은 Codex 가 항목으로 지원하지 않아 넣을 수 없다 — 계정은 ccp 메뉴에서 확인한다.

규칙: 이미 status_line 이 있으면 손대지 않는다(사용자가 고른 것). 없으면 [tui] 에 넣는다. 원본은 .bak 으로 남긴다.
TOML 파서 없이 줄 단위로 다룬다 — 파일을 통째로 다시 쓰면 주석·순서가 사라지고, codex 가 다시 쓸 때 심링크가
실파일로 바뀌는 것과 같은 종류의 놀라움을 만들기 때문이다.

    ccp_codex_statusline.py apply [config.toml 경로]      기본값 넣기 (있으면 그대로)
    ccp_codex_statusline.py show  [config.toml 경로]      현재 값
"""
import os
import re
import shutil
import sys
import time

DEFAULT_ITEMS = ["model-with-reasoning", "five-hour-limit", "weekly-limit", "context-remaining", "current-dir", "git-branch"]


def default_path():
    return os.path.join(os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex"), "config.toml")


def _toml_list(items):
    return "[" + ", ".join(f'"{i}"' for i in items) + "]"


def current(text):
    """[tui] 섹션 안의 status_line 값(문자열) 또는 None."""
    in_tui = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            in_tui = (s == "[tui]")
            continue
        if in_tui:
            m = re.match(r"status_line\s*=\s*(\[[^\]]*\]|null|\S+)", s)   # 뒤에 붙은 주석은 뺀다
            if m:
                return m.group(1).strip()
    return None


def merge(text, items=DEFAULT_ITEMS):
    """(새 본문, 상태). 상태: 'kept'(이미 있음) | 'inserted'(기존 [tui] 에 추가) | 'appended'([tui] 새로 만듦)."""
    if current(text) is not None:
        return text, "kept"
    lines = text.splitlines()
    block = [f"status_line = {_toml_list(items)}   # ccp: 모델·5시간·주간 한도. 바꾸려면 codex 안에서 /statusline",
             "status_line_use_colors = true"]
    for i, line in enumerate(lines):
        if line.strip() == "[tui]":
            # [tui] 바로 아래, 그 섹션의 기존 키들 앞에 넣는다.
            j = i + 1
            while j < len(lines) and (lines[j].strip() == "" or lines[j].lstrip().startswith("#")):
                j += 1
            out = lines[:j] + block + lines[j:]
            return "\n".join(out) + ("\n" if text.endswith("\n") or not text else ""), "inserted"
    tail = ("" if not text or text.endswith("\n") else "\n") + ("\n" if text.strip() else "")
    return text + tail + "[tui]\n" + "\n".join(block) + "\n", "appended"


def apply(path, items=DEFAULT_ITEMS):
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    new, status = merge(text, items)
    if status != "kept":
        if os.path.exists(path):
            shutil.copy2(path, f"{path}.bak-{time.strftime('%Y%m%d%H%M%S')}")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # 심링크면 링크가 가리키는 실파일을 고친다(프로필 쪽에서 불려도 공유가 끊기지 않게).
        real = os.path.realpath(path)
        with open(real, "w", encoding="utf-8") as fh:
            fh.write(new)
    return status


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "apply"
    path = sys.argv[2] if len(sys.argv) > 2 else default_path()
    if cmd == "show":
        try:
            print(current(open(path, encoding="utf-8").read()) or "(없음)")
        except OSError:
            print("(config.toml 없음)")
    else:
        print(apply(path))
