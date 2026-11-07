#!/usr/bin/env python3
"""함대 경보 — 조용히 끝나는 감시. 출력이 있을 때만 Telegram 으로 간다.
기준: 로그아웃된 프로필(imok 제외), 주간 남은 양 20% 미만, 모델(Fable) 한도 소진, 관문 접속 실패."""
import json, os, subprocess, sys
EXCLUDE = {"imok"}
try:
    out = subprocess.run(["bash", os.path.expanduser("~/.hermes/scripts/fleet_report.sh")], capture_output=True, text=True, timeout=420).stdout
    d = json.loads(out)
except Exception as e:
    print("⚠️ 함대 관문(FLEET_GATEWAY, 2026-11-08 부터 macmini) 접속 실패: " + type(e).__name__); sys.exit(0)
alerts = []
for h in d.get("hosts", []):
    if isinstance(h, dict) and h.get("profiles") is not None:
        for p in h["profiles"]:
            if p["profile"] in EXCLUDE:
                continue
            if p["state"] != "local_oauth_present":
                alerts.append("%s/%s: %s" % (h["host"], p["profile"], p["state"]))
def pct(x):
    try:
        return int(x)
    except Exception:
        return None
for u in d.get("usage", {}).get("claude", []):
    w = pct(u.get("weekly_pct")); m = pct(u.get("model_pct"))
    if w is not None and 100 - w < 20:
        alerts.append("Claude %s: 주간 %d%% 남음 (리셋 %s)" % (u["profile"], 100 - w, u.get("weekly_reset") or "?"))
    if m is not None and m >= 100:
        alerts.append("Claude %s: %s 한도 소진 (리셋 %s)" % (u["profile"], u.get("model") or "모델", u.get("weekly_reset") or "?"))
for u in d.get("usage", {}).get("codex", []):
    w = pct(u.get("weekly_pct"))
    if w is not None and 100 - w < 20:
        alerts.append("Codex %s: 주간 %d%% 남음 (리셋 %s)" % (u["profile"], 100 - w, u.get("weekly_reset") or "?"))
if alerts:
    print("🔔 ccp 함대 경보 (" + d.get("generated_at", "") + ")\n" + "\n".join("• " + a for a in alerts))
