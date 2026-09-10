#!/bin/zsh
# ccp.zsh 통합 테스트 — 가짜 HOME 과 가짜 claude/codex 실행파일로 돈다. 실제 계정·설정을 건드리지 않는다.
#   zsh tests/test_ccp_zsh.sh
set -u
REPO="${0:A:h:h}"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

export HOME="$T/home" XDG_CONFIG_HOME="$T/cfg" PATH="$T/bin:$PATH"
unset CCP_CONFIG_DIR CLAUDE_CONFIG_DIR CODEX_HOME CLAUDE_PROFILES CODEX_PROFILES
mkdir -p "$HOME/.claude/skills" "$HOME/.claude/plugins" "$HOME/.claude/commands" "$HOME/.claude/projects" \
         "$HOME/.codex/skills" "$T/bin" "$XDG_CONFIG_HOME/ccp"
echo '{}' > "$HOME/.claude/settings.json"; : > "$HOME/.codex/config.toml"
cat > "$T/bin/claude" <<'EOF'
#!/bin/sh
echo "claude CLAUDE_CONFIG_DIR=${CLAUDE_CONFIG_DIR-<unset>} args=$*"
EOF
cat > "$T/bin/codex" <<'EOF'
#!/bin/sh
echo "codex CODEX_HOME=${CODEX_HOME-<unset>} args=$*"
EOF
chmod +x "$T/bin/"*
TSV="$XDG_CONFIG_HOME/ccp/profiles.tsv"
printf 'claude\tteam\tcct\t팀\nclaude\tpersonal\t\t\ncodex\twork\tcxw\t\n' > "$TSV"

PASS=0; FAIL=0
run()    { zsh -c "source '$REPO/ccp.zsh' 2>&1; $1" 2>&1 }   # 케이스마다 새 zsh — 별칭·상태가 새지 않게
check()  { local name="$1" got="$2" want="$3"
           if [[ "$got" == *"$want"* ]]; then PASS=$((PASS+1)); print "  ok   $name"
           else FAIL=$((FAIL+1)); print "  FAIL $name\n       기대: ...$want...\n       실제: $got"; fi }
checkno(){ local name="$1" got="$2" bad="$3"
           if [[ "$got" != *"$bad"* ]]; then PASS=$((PASS+1)); print "  ok   $name"
           else FAIL=$((FAIL+1)); print "  FAIL $name\n       없어야: $bad\n       실제: $got"; fi }

print "별칭"
out="$(run 'alias cct; alias cxw; alias | grep -c personal')"
check "별칭 칸이 있는 줄은 alias 가 된다 (claude)" "$out" "cct='ccp claude:team'"
check "별칭 칸이 있는 줄은 alias 가 된다 (codex)"  "$out" "cxw='ccp codex:work'"
check "별칭 칸이 비면 alias 를 만들지 않는다"      "$out" $'\n0'
printf 'claude\tbad\tcp\t\n' >> "$TSV"
out="$(run 'whence -w cp')"
check "기존 명령과 겹치는 별칭은 거부하고 경고" "$out" "별칭 cp 은(는) 이미 있는 command"
check "겹치는 별칭을 덮어쓰지 않는다"          "$out" "cp: command"
printf 'claude\tteam\tcct\t팀\nclaude\tpersonal\t\t\ncodex\twork\tcxw\t\n' > "$TSV"

print "ccp-sync"
out="$(run 'ccp-sync')"
check "TSV 의 프로필을 만든다" "$out" "생성: claude team"
check "codex 프로필도 만든다"  "$out" "생성: codex work"
[[ -L "$HOME/.claude-profiles/team/settings.json" && -L "$HOME/.claude-profiles/team/projects" ]] \
  && check "claude: settings.json·projects 를 심링크로 공유" "y" "y" || check "claude: settings.json·projects 를 심링크로 공유" "n" "y"
[[ ! -e "$HOME/.claude-profiles/team/.claude.json" ]] \
  && check "claude: .claude.json 은 만들지도 링크하지도 않는다" "y" "y" || check "claude: .claude.json 은 만들지도 링크하지도 않는다" "n" "y"
[[ -L "$HOME/.codex-profiles/work/config.toml" && -L "$HOME/.codex-profiles/work/skills" ]] \
  && check "codex: config.toml·skills 를 심링크로 공유" "y" "y" || check "codex: config.toml·skills 를 심링크로 공유" "n" "y"
out="$(run 'ccp-sync')"
check "두 번 돌려도 안전 (멱등)" "$out" "프로필 전부 있음"

print "ccp-new"
out="$(run 'ccp-new extra ccx 설명글')"
check "디렉터리 생성" "$out" "생성: $HOME/.claude-profiles/extra"
check "TSV 에 기록"   "$(cat "$TSV")" $'claude\textra\tccx\t설명글'
out="$(run 'ccp-new extra')"
check "이미 있으면 거부" "$out" "이미 있음"
check "TSV 에 중복 기록하지 않는다" "$(grep -c $'\textra\t' "$TSV")" "1"
out="$(run 'ccp-new --codex second')"
check "codex 프로필 생성 안내" "$out" "CODEX_HOME=$HOME/.codex-profiles/second codex login"
check "codex 줄도 TSV 에"      "$(cat "$TSV")" $'codex\tsecond\t\t'

print "ccp 실행"
out="$(run 'ccp team --foo bar')"
check "이름으로 → CLAUDE_CONFIG_DIR 지정, 인자 전달" "$out" "claude CLAUDE_CONFIG_DIR=$HOME/.claude-profiles/team args=--foo bar"
checkno "기본은 --dangerously-skip-permissions 를 붙이지 않는다" "$out" "dangerously"
out="$(run 'ccp 0')"
check "0번 = 기본 프로필, CLAUDE_CONFIG_DIR 없이" "$out" "CLAUDE_CONFIG_DIR=<unset>"
out="$(CLAUDE_CONFIG_DIR="$HOME/.claude-profiles/team" run 'ccp claude:기본')"
check "프로필 세션 안에서 기본을 골라도 현재 프로필이 새지 않는다" "$out" "CLAUDE_CONFIG_DIR=<unset>"
out="$(run 'ccp codex:work -q')"
check "codex 프로필 → CODEX_HOME 지정" "$out" "codex CODEX_HOME=$HOME/.codex-profiles/work args=-q"
out="$(run 'ccp codex:기본')"
check "codex 기본 → CODEX_HOME 없이" "$out" "CODEX_HOME=<unset>"
out="$(run 'ccp nope')"
check "없는 이름은 안내" "$out" "프로필 'nope' 없음"

print "config.zsh"
printf 'CCP_CLAUDE_ARGS=(--dangerously-skip-permissions --model opus)\n' > "$XDG_CONFIG_HOME/ccp/config.zsh"
out="$(run 'ccp team')"
check "CCP_CLAUDE_ARGS 가 claude 인자 앞에 붙는다" "$out" "args=--dangerously-skip-permissions --model opus"
rm "$XDG_CONFIG_HOME/ccp/config.zsh"

print "예전 3칸 TSV 호환"
printf 'old\tcco\t설명\n' > "$TSV"
out="$(run 'alias cco')"
check "도구 칸이 없으면 claude 로 본다" "$out" "cco='ccp claude:old'"

print "\n통과 $PASS · 실패 $FAIL"
(( FAIL == 0 ))
