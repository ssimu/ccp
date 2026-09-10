#!/bin/bash
# ccp 설치 — 멱등. 몇 번 돌려도 같은 결과.
#
#   git clone https://github.com/ssimu/ccp.git ~/projects/ccp
#   ~/projects/ccp/install.sh                 # ccp + Claude Code 상태줄(현재 계정·남은 한도)
#   ~/projects/ccp/install.sh --no-statusline # 상태줄은 건드리지 않음
#
# 하는 일:
#   1. ~/.zshrc 에 ccp.zsh 를 source 하는 한 줄 (clone 한 위치를 그대로 쓴다)
#   2. ~/.config/ccp/{profiles.tsv,config.zsh,statusline.conf} 를 예시에서 복사 (이미 있으면 그대로 둠)
#   3. profiles.tsv 대로 프로필 디렉터리 생성 (ccp-sync)
#   4. ~/.claude/statusline-command.sh 링크 + settings.json 의 statusLine 설정 (--no-statusline 이면 건너뜀)
#      codex 가 있으면 ~/.codex/config.toml 의 [tui].status_line 에 모델·한도 항목도 넣는다(있으면 그대로)
# 로그인(/login)은 프로필마다 사람이 직접 한다 — 토큰은 어디에도 복사하지 않는다.
set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="${CCP_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/ccp}"
ZRC="${ZDOTDIR:-$HOME}/.zshrc"
CC="$HOME/.claude"
STATUSLINE=1
NOTES=()

for a in "$@"; do
    case "$a" in
        --statusline) STATUSLINE=1 ;;     # 기본값. 예전 호출과의 호환용
        --no-statusline) STATUSLINE=0 ;;
        -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
        *) printf '모르는 옵션: %s\n' "$a" >&2; exit 1 ;;
    esac
done

ok()   { printf '  ✓ %s\n' "$1"; }
note() { NOTES+=("$1"); }
step() { printf '\n▸ %s\n' "$1"; }

step "0/4  필요한 것"
for c in zsh python3 claude; do
    if command -v "$c" >/dev/null 2>&1; then ok "$c"
    else
        case "$c" in
            claude) note "claude 가 PATH 에 없다. ccp 는 claude CLI 를 감싸는 도구다 — 먼저 설치할 것: https://docs.anthropic.com/claude-code" ;;
            *)      note "$c 가 없다. ccp 는 zsh 함수이고 메뉴는 python3 로 그린다." ;;
        esac
    fi
done
command -v codex >/dev/null 2>&1 && ok "codex (선택 — 있으면 메뉴에 함께 뜬다)"

step "1/4  ~/.zshrc"
LINE="[ -f \"$DIR/ccp.zsh\" ] && source \"$DIR/ccp.zsh\""
if [ ! -f "$ZRC" ]; then
    printf '%s\n' "$LINE" > "$ZRC"
    ok "$ZRC 새로 만들고 source 한 줄 넣음"
elif grep -qF "$DIR/ccp.zsh" "$ZRC"; then
    ok "$ZRC (이미 배선됨)"
elif grep -qF "/ccp.zsh" "$ZRC"; then
    note "$ZRC 가 다른 위치의 ccp.zsh 를 source 하고 있다: $(grep -F '/ccp.zsh' "$ZRC" | head -1) — 이 clone($DIR)을 쓰려면 그 줄을 고칠 것. 이번엔 건드리지 않았다."
else
    cp "$ZRC" "$ZRC.bak-$(date +%Y%m%d%H%M%S)"
    printf '\n# ── ccp (Claude Code / Codex 계정 프로필 전환) ──\n%s\n' "$LINE" >> "$ZRC"
    ok "$ZRC 에 source 한 줄 추가 (백업 생성)"
fi

step "2/4  설정 $CFG"
mkdir -p "$CFG"
for f in profiles.tsv config.zsh statusline.conf; do
    if [ -f "$CFG/$f" ]; then ok "$f (그대로 둠)"
    else
        cp "$DIR/${f%.*}.example.${f##*.}" "$CFG/$f"
        ok "$f 생성 (예시 복사)"
        [ "$f" = profiles.tsv ] && note "$CFG/profiles.tsv 는 예시 그대로다(team/personal/work). 실제 계정에 맞게 고친 뒤 'ccp-sync' 를 돌릴 것. 안 쓰는 예시 프로필 디렉터리는 rm -rf ~/.claude-profiles/<이름> 으로 지운다."
    fi
done

step "3/4  프로필 디렉터리"
if command -v zsh >/dev/null 2>&1; then
    CCP_CONFIG_DIR="$CFG" zsh -c "source '$DIR/ccp.zsh'; ccp-sync" | sed 's/^/  /'
else
    note "zsh 가 없어 프로필 디렉터리를 만들지 못했다. zsh 설치 후 'ccp-sync'."
fi

step "4/4  statusline"
if [ "$STATUSLINE" = 1 ]; then
    mkdir -p "$CC"
    dst="$CC/statusline-command.sh"
    if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$DIR/statusline.sh" ]; then ok "statusline-command.sh (이미 연결됨)"
    else
        if [ -e "$dst" ] && [ ! -L "$dst" ]; then
            mv "$dst" "$dst.bak-$(date +%Y%m%d%H%M%S)"
            note "$dst 가 실제 파일이었다 → .bak 으로 옮기고 링크했다."
        else rm -f "$dst"; fi
        ln -s "$DIR/statusline.sh" "$dst"; ok "statusline-command.sh → $DIR/statusline.sh"
    fi
    # 명령은 'bash ~/.claude/statusline-command.sh' 로 고정한다 — 절대경로를 넣으면 머신마다 settings.json 이 달라진다.
    python3 - "$CC/settings.json" <<'PY'
import json, os, sys
p = sys.argv[1]
cur = json.load(open(p)) if os.path.exists(p) else {}
want = {"type": "command", "command": "bash ~/.claude/statusline-command.sh"}
prev = cur.get("statusLine")
if prev == want:
    print("  ✓ settings.json statusLine (이미 설정됨)")
else:
    cur["statusLine"] = want
    json.dump(cur, open(p, "w"), ensure_ascii=False, indent=2)
    print("  ✓ settings.json statusLine 설정" + (f" (이전 값: {json.dumps(prev, ensure_ascii=False)})" if prev else ""))
PY
else
    ok "건너뜀 (--no-statusline)"
fi
# Codex 는 외부 스크립트를 못 붙이지만 자기 상태줄 항목을 고를 수 있다 — 모델·5시간·주간 한도가 보이게 넣는다.
# 이미 status_line 이 있으면 손대지 않는다. Codex 안에서 /statusline 으로 바꿀 수 있다.
if [ "$STATUSLINE" = 1 ] && command -v codex >/dev/null 2>&1; then
    case "$(python3 "$DIR/ccp_codex_statusline.py" apply 2>/dev/null)" in
        kept)     ok "codex 상태줄 (이미 설정돼 있어 그대로 둠 — 바꾸려면 codex 에서 /statusline)" ;;
        inserted|appended) ok "codex 상태줄: 모델 · 5시간 한도 · 주간 한도 · 컨텍스트 · 디렉터리 · git (~/.codex/config.toml, 백업 남김)" ;;
        *)        note "codex 상태줄 설정을 못 넣었다. ~/.codex/config.toml 을 확인할 것: python3 $DIR/ccp_codex_statusline.py apply" ;;
    esac
fi

printf '\n─────────────────────────────────────────────\n'
if [ ${#NOTES[@]} -eq 0 ]; then printf '설치 완료.\n'
else
    printf '설치 완료. 확인할 것 %d건:\n\n' "${#NOTES[@]}"
    for n in "${NOTES[@]}"; do printf '  ! %s\n' "$n"; done
fi
cat <<EOT

다음 (사람이 직접):
  source ~/.zshrc
  \$EDITOR $CFG/profiles.tsv    계정 이름·별칭을 내 것으로 (한 줄 = 프로필 하나)
  ccp-sync                      고친 대로 디렉터리 생성
  ccp                           메뉴 → 프로필 골라 /login  (프로필마다 한 번)
EOT
