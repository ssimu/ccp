#!/usr/bin/env python3
"""함대 경보 — 조용히 끝나는 감시. 출력이 있을 때만 Telegram 으로 간다.
기준: 로그아웃된 프로필(imok 제외), 주간 남은 양 5% 이하(이때 fleet-pick 이 다른 계정으로 넘긴다), 모델(Fable) 한도 소진, 관문 접속 실패, 나가는 연결 막힘·macOS 26 장기 가동(49.7일 TIME_WAIT 결함, fleet-net-check), Codex 로그인 풀림·워크스페이스 겹침(fleet-codex-check)."""
import json, os, subprocess, sys
EXCLUDE = {"imok"}
LEFT_MAX = 5   # 남은 양이 이 % 이하이면 알린다 — fleet-pick 의 전환 기준(주간 95%)과 같게
try:
    out = subprocess.run(["bash", os.path.expanduser("~/.hermes/scripts/fleet_report.sh")], capture_output=True, text=True, timeout=420).stdout
    d = json.loads(out)
except Exception as e:
    # 관문이 나가는 연결을 못 하면(macOS 26 의 49.7일 TIME_WAIT 결함) Tailscale 도 끊겨 SSH 조차 안 들어온다(2026-11-11).
    print("⚠️ 함대 관문(FLEET_GATEWAY, 2026-11-08 부터 macmini) 접속 실패: " + type(e).__name__ +
          "\n  전원·망이 멀쩡한데 이러면 macOS 26 장기 가동 결함일 수 있다 — LAN 에서 `fleet-net-check` 확인, 맞으면 `sudo fdesetup authrestart`"); sys.exit(0)
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
    if w is not None and 100 - w <= LEFT_MAX:
        alerts.append("Claude %s: 주간 %d%% 남음 (리셋 %s)" % (u["profile"], 100 - w, u.get("weekly_reset") or "?"))
    if m is not None and m >= 100:
        alerts.append("Claude %s: %s 한도 소진 (리셋 %s)" % (u["profile"], u.get("model") or "모델", u.get("model_reset") or u.get("weekly_reset") or "?"))
for u in d.get("usage", {}).get("codex", []):
    w = pct(u.get("weekly_pct"))
    if w is not None and 100 - w <= LEFT_MAX:
        alerts.append("Codex %s: 주간 %d%% 남음 (리셋 %s)" % (u["profile"], 100 - w, u.get("weekly_reset") or "?"))
for n in [x for k in ("net", "codex_login") if isinstance(d.get(k), list) for x in d[k]]:
    for w in n.get("warn", []):
        alerts.append("%s: %s" % (n.get("host", "?"), w))
if alerts:
    print("🔔 ccp 함대 경보 (" + d.get("generated_at", "") + ")\n" + "\n".join("• " + a for a in alerts))
