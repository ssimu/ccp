#!/bin/bash
# fleet.sh <fleet-jobs 하위 명령과 인자…> — 관문 old-mbp 의 fleet-jobs 를 SSH 로 돌린다. 인자는 그대로(따옴표 안전하게) 전달한다.
#   bash ~/.hermes/scripts/fleet.sh dispatch --on macmini --name fix-x "작업문 …"
#   bash ~/.hermes/scripts/fleet.sh wait j261106-094318 --timeout 150
# 관문 주소는 ~/.hermes/fleet.env 의 FLEET_GATEWAY (예: FLEET_GATEWAY=user@100.x.y.z — Tailscale 주소). 저장소에는 적지 않는다.
[ -f "$HOME/.hermes/fleet.env" ] && . "$HOME/.hermes/fleet.env"
GW="${FLEET_GATEWAY:?set FLEET_GATEWAY=user@host in ~/.hermes/fleet.env}"
q=""; for a in "$@"; do q+=" $(printf '%q' "$a")"; done
exec ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new "$GW" "PATH=\$HOME/.local/bin:\$PATH fleet-jobs$q"
