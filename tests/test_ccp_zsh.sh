#!/bin/zsh
# ccp.zsh 통합 테스트 — 가짜 HOME 과 가짜 claude/codex 실행파일로 돈다. 실제 계정·설정을 건드리지 않는다.
#   zsh tests/test_ccp_zsh.sh
set -u
REPO="${0:A:h:h}"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

export HOME="$T/home" XDG_CONFIG_HOME="$T/cfg" PATH="$T/bin:$PATH"
unset CCP_CONFIG_DIR CLAUDE_CONFIG_DIR CODEX_HOME CLAUDE_PROFILES CODEX_PROFILES
export CCP_LANG=ko   # 아래 기대 문구는 한국어. 언어 전환은 마지막 절에서 따로 본다
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
run()    { zsh -c "source '$REPO/ccp.zsh' 2>&1; $1" 2>&1 </dev/null }   # 케이스마다 새 zsh. stdin 은 닫는다 — 프롬프트(read)가 있으면 빈 답으로 지나간다
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
printf 'claude\tnoalias\t\t개인용 설명\n' >> "$TSV"
out="$(run 'alias 개인용 2>&1; alias | grep -c noalias')"
check "별칭이 비고 설명만 있으면 설명을 별칭으로 착각하지 않는다" "x${out}x" "x0x"
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

print "ccp-rm"
out="$(run 'ccp-rm -f extra')"
check "삭제 메시지" "$out" "삭제: claude:extra"
[[ ! -e "$HOME/.claude-profiles/extra" ]] && check "디렉터리가 사라진다" y y || check "디렉터리가 사라진다" n y
check "TSV 줄도 사라진다" "$(grep -c $'\textra\t' "$TSV")" "0"
check "다른 줄은 그대로" "$(grep -c $'^claude\tteam\t' "$TSV")" "1"
out="$(run 'ccp-rm -f claude:기본' 2>&1; run 'ccp-rm -f 기본')"
check "기본 프로필은 지울 수 없다" "$out" "기본 프로필(~/.claude, ~/.codex)은 지울 수 없다"
[[ -d "$HOME/.claude" ]] && check "~/.claude 는 무사" y y || check "~/.claude 는 무사" n y
out="$(run 'ccp-rm -f nope')"
check "없는 프로필은 안내" "$out" "없는 프로필: claude:nope"
out="$(run 'ccp-rm --codex -f second')"
check "codex 프로필 삭제" "$out" "삭제: codex:second"
out="$(printf 'n\n' | zsh -c "source '$REPO/ccp.zsh'; ccp-rm team" 2>&1)"
check "-f 없이는 확인을 묻고 n 이면 취소" "$out" "취소"
[[ -d "$HOME/.claude-profiles/team" ]] && check "취소하면 남아 있다" y y || check "취소하면 남아 있다" n y

print "ccp-edit"
out="$(run 'ccp-edit team team2 cc2')"
check "이름·별칭 변경 메시지" "$out" "수정: claude:team → claude:team2 (별칭 'cc2')"
[[ -d "$HOME/.claude-profiles/team2" && ! -e "$HOME/.claude-profiles/team" ]] && check "디렉터리가 옮겨진다(로그인 유지)" y y || check "디렉터리가 옮겨진다(로그인 유지)" n y
check "TSV 갱신" "$(cat "$TSV")" $'claude\tteam2\tcc2\t팀'
check "옛 줄 제거" "$(grep -c $'\tteam\t' "$TSV")" "0"
out="$(run 'alias cc2; alias cct 2>&1')"
check "새 별칭이 생기고 옛 별칭은 없다" "$out" "cc2='ccp claude:team2'"
checkno "옛 별칭은 없다" "$out" "cct='ccp"
out="$(run 'ccp-edit team2 team2 -')"
check "'-' 는 별칭 제거" "$(cat "$TSV")" $'claude\tteam2\t\t팀'
out="$(run 'ccp-edit team2 personal')"
check "이미 있는 이름으로는 못 바꾼다" "$out" "이미 있는 이름"
out="$(printf '\n\n' | zsh -c "source '$REPO/ccp.zsh'; ccp-edit team2" 2>&1)"
check "인자 없이 Enter 만 치면 그대로" "$out" "수정: claude:team2 → claude:team2 (별칭 '')"
run 'ccp-edit team2 team cct' >/dev/null   # 아래 테스트가 기대하는 상태로 되돌린다

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

print "언어"
out="$(CCP_LANG=en run 'ccp nope')"
check "CCP_LANG=en 이면 영어 메시지" "$out" "profile 'nope' not found"
out="$(CCP_LANG=ja run 'ccp nope')"
check "CCP_LANG=ja 이면 일본어 메시지" "$out" "プロファイル 'nope' がない"
out="$(CCP_LANG=zh run 'ccp-sync')"
check "CCP_LANG=zh 이면 중국어 메시지" "$out" "所有配置均已存在"
out="$(CCP_LANG=en run 'ccp claude:default')"
check "en 에서 기본 프로필 이름은 default" "$out" "CLAUDE_CONFIG_DIR=<unset>"
out="$(CCP_LANG=en run 'ccp claude:기본')"
check "언어가 en 이어도 '기본' 으로 기본 프로필을 부를 수 있다" "$out" "CLAUDE_CONFIG_DIR=<unset>"
out="$(CCP_LANG=ko run 'ccp claude:default')"
check "언어가 ko 여도 'default' 로 부를 수 있다" "$out" "CLAUDE_CONFIG_DIR=<unset>"
out="$(env -u CCP_LANG LANG=ja_JP.UTF-8 zsh -c "source '$REPO/ccp.zsh'; echo LANG=\$CCP_LANG")"
check "CCP_LANG 이 없으면 로케일에서 정한다 (ja_JP → ja)" "$out" "LANG=ja"
out="$(env -u CCP_LANG LANG=de_DE.UTF-8 zsh -c "source '$REPO/ccp.zsh'; echo LANG=\$CCP_LANG")"
check "모르는 로케일은 en" "$out" "LANG=en"

print "예전 3칸 TSV 호환"
printf 'old\tcco\t설명\n' > "$TSV"
out="$(run 'alias cco')"
check "도구 칸이 없으면 claude 로 본다" "$out" "cco='ccp claude:old'"

print "\n통과 $PASS · 실패 $FAIL"
(( FAIL == 0 ))
