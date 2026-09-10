#!/bin/bash
# Claude Code 상태줄 진입점. ~/.claude/statusline-command.sh 가 이 파일을 가리킨다(install.sh 가 링크).
# 실제 그리기는 옆의 ccp_statusline.py. 이 파일은 심링크로 설치되므로 원본 디렉터리를 찾아 넘긴다.
# 사용자가 ~/.config/ccp/statusline.sh 를 두면 그것을 대신 실행한다 — 완전히 다른 상태줄을 쓰고 싶은 사람용.
_self="${BASH_SOURCE[0]}"; _target="$(readlink "$_self" 2>/dev/null || echo "$_self")"
export CCP_HOME_DIR="$(cd "$(dirname "$_target")" && pwd)"
export CCP_CONFIG_DIR="${CCP_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/ccp}"
if [ -x "$CCP_CONFIG_DIR/statusline.sh" ]; then exec "$CCP_CONFIG_DIR/statusline.sh"; fi
exec python3 "$CCP_HOME_DIR/ccp_statusline.py"
