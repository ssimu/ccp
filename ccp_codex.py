#!/usr/bin/env python3
"""codex 계정의 사용량을 ccp 렌더러가 먹는 TSV 한 줄로 낸다.

codex 는 `$CODEX_HOME/auth.json` 에 계정을 딱 하나만 들고 있어서, 계정 전환은
프로필마다 CODEX_HOME 을 따로 두는 것 말고는 방법이 없다(ccp 의 CLAUDE_CONFIG_DIR 과 같은 구조).

사용량은 `codex app-server` 의 JSON-RPC(`account/read`, `account/rateLimits/read`)로 읽는다.
모델을 부르지 않으므로 토큰이 들지 않는다 — claude 쪽이 `/usage` 로 턴을 태우는 것과 다르다.

TSV 12칸 (ccp_render.py 와 공유):
  0 주간%  1 주간리셋(분)  2 세션%  3 세션리셋(분)  4 모델명  5 모델%
  6 상태(ok/nologin/fail)  7 주간리셋시각  8 세션리셋시각
  9 주간창(분)  10 세션창(분)  11 메모
"""
import datetime
import json
import os
import subprocess
import sys
import time

FIELDS = 12
SESSION_MAX_MINS = 1440   # 이 이하 창은 '세션', 넘으면 '주간'. primary/secondary 위치는 요금제마다 다르다.


def _slot(window):
    """한도 창 하나를 (퍼센트, 남은 분, 시각문자열, 창길이) 로."""
    if not window:
        return None
    pct = window.get("usedPercent")
    mins = window.get("windowDurationMins")
    resets = window.get("resetsAt")
    return (None if pct is None else int(round(pct)), mins, resets)


def to_tsv(account, ratelimits, now=None):
    """account/read 와 account/rateLimits/read 응답을 TSV 한 줄로. 순수 함수 — 테스트 대상."""
    now = time.time() if now is None else now
    out = [""] * FIELDS

    if not account:
        out[6] = "nologin"
        return "\t".join(out)
    out[6] = "ok"

    rl = (ratelimits or {}).get("rateLimits") or {}

    def put(slot, base):
        pct, window, resets = slot
        out[base] = "" if pct is None else str(pct)
        if resets:
            out[base + 1] = str(max(0, int(round((resets - now) / 60))))
            out[7 if base == 0 else 8] = datetime.datetime.fromtimestamp(resets).strftime("%m/%d %H:%M")
        if window:
            out[9 if base == 0 else 10] = str(int(window))

    for key in ("primary", "secondary"):
        slot = _slot(rl.get(key))
        if slot is None:
            continue
        _pct, window, _resets = slot
        weekly = window is None or window > SESSION_MAX_MINS
        put(slot, 0 if weekly else 2)

    # 메모: 왜 막혔는지 / 되살릴 수단이 있는지. 없으면 빈 칸이어야 한다(카드가 지저분해진다).
    # 프로필 이름만으론 어느 워크스페이스인지 알 수 없다 — 요금제를 앞에 붙인다.
    notes = [account.get("planType")] if account.get("planType") else []
    credits = rl.get("credits") or {}
    if (rl.get("rateLimitReachedType") or "").endswith("credits_depleted") and not credits.get("unlimited"):
        notes.append("크레딧 소진")
    if rl.get("spendControlReached"):
        notes.append("지출 한도")
    tickets = ((ratelimits or {}).get("rateLimitResetCredits") or {}).get("availableCount") or 0
    if tickets:
        notes.append(f"리셋권 {tickets}")
    out[11] = " · ".join(notes)
    return "\t".join(out)


def _rpc(codex_home, timeout=20.0):
    """app-server 를 띄워 계정과 한도를 읽는다. 실패하면 (None, None)."""
    env = dict(os.environ, CODEX_HOME=codex_home)
    env.pop("OPENAI_API_KEY", None)   # API 키가 환경에 있으면 ChatGPT 계정 대신 그걸 본다
    try:
        p = subprocess.Popen(["codex", "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True, bufsize=1, env=env)
    except Exception:
        return None, None

    def send(obj):
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()

    account = limits = None
    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"clientInfo": {"name": "ccp", "title": "ccp", "version": "1"}}})
        send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
        send({"jsonrpc": "2.0", "id": 2, "method": "account/read", "params": {}})
        send({"jsonrpc": "2.0", "id": 3, "method": "account/rateLimits/read", "params": {}})
        deadline = time.time() + timeout
        seen = set()
        while time.time() < deadline and seen != {2, 3}:
            line = p.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line)
            except Exception:
                continue
            if msg.get("id") == 2:
                seen.add(2)
                account = (msg.get("result") or {}).get("account")
            elif msg.get("id") == 3:
                seen.add(3)
                limits = msg.get("result")
    except Exception:
        pass
    finally:
        try:
            p.kill()
            p.wait(timeout=2)
        except Exception:
            pass
    return account, limits


def probe(codex_home):
    # 미로그인 프로필에 app-server 를 띄우는 건 낭비다 — auth.json 이 없으면 바로 끝낸다.
    if not os.path.exists(os.path.join(codex_home, "auth.json")):
        return to_tsv(None, None)
    account, limits = _rpc(codex_home)
    if account is None and limits is None:
        return "\t".join([""] * 6 + ["fail"] + [""] * 5)
    return to_tsv(account, limits)


def who(codex_home):
    """ccp-ls 용 한 줄: 이메일 + 요금제."""
    if not os.path.exists(os.path.join(codex_home, "auth.json")):
        return "(미로그인)"
    account, _ = _rpc(codex_home)
    if not account:
        return "(조회 실패)"
    return f"{account.get('email') or '?'}  {account.get('planType') or ''}".rstrip()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "probe"
    home = sys.argv[2]
    print(who(home) if cmd == "who" else probe(home))
