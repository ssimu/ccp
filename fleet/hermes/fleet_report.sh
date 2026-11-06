#!/bin/bash
# 집 Mac 함대(관문 Mac)의 Claude/Codex 로그인 상태와 한도를 JSON 으로 가져온다.
# 관문 주소는 ~/.hermes/fleet.env 의 FLEET_GATEWAY (예: FLEET_GATEWAY=user@100.x.y.z — Tailscale 주소). 저장소에는 적지 않는다.
[ -f "$HOME/.hermes/fleet.env" ] && . "$HOME/.hermes/fleet.env"
GW="${FLEET_GATEWAY:?set FLEET_GATEWAY=user@host in ~/.hermes/fleet.env}"
ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new "$GW" "~/.local/bin/fleet-report" 2>/dev/null
