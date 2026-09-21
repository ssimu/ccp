#!/bin/zsh
# ccp.zsh 통합 테스트 — 가짜 HOME 과 가짜 claude/codex 실행파일로 돈다. 실제 계정·설정을 건드리지 않는다.
#   zsh tests/test_ccp_zsh.sh
set -u
REPO="${0:A:h:h}"
T="$(mktemp -d)"; W="$(mktemp -d /tmp/ccpw.XXXXXX)"; trap 'rm -rf "$T" "$W"' EXIT   # W = 짧은 경로(기록 폴더 이름 64자 상한)

export HOME="$T/home" XDG_CONFIG_HOME="$T/cfg" PATH="$T/bin:$PATH"
unset CCP_CONFIG_DIR CLAUDE_CONFIG_DIR CODEX_HOME CLAUDE_PROFILES CODEX_PROFILES
export CCP_LANG=ko   # 아래 기대 문구는 한국어. 언어 전환은 마지막 절에서 따로 본다
mkdir -p "$HOME/.claude/skills" "$HOME/.claude/plugins" "$HOME/.claude/commands" "$HOME/.claude/projects" \
         "$HOME/.codex/skills" "$T/bin" "$XDG_CONFIG_HOME/ccp"
echo '{}' > "$HOME/.claude/settings.json"; : > "$HOME/.codex/config.toml"
cat > "$T/bin/claude" <<'EOF'
#!/bin/sh
echo "claude CLAUDE_CONFIG_DIR=${CLAUDE_CONFIG_DIR-<unset>} args=$* pdn=${CLAUDE_CODE_PROJECT_DIR_NAME-<unset>}"
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

print "워크트리 기록 연동"
W="${W:A}"
git -C "$W" init -q main-co 2>/dev/null; MAIN="$W/main-co"
git -C "$MAIN" -c user.name=t -c user.email=t@t commit -q --allow-empty -m init
git -C "$MAIN" worktree add -q "$W/wt" -b feat 2>/dev/null
WANT="$(print -r -- "$MAIN" | sed 's/[^A-Za-z0-9]/-/g')"
out="$(run "cd '$W/wt' && ccp team")"
check "워크트리에서 띄우면 메인 체크아웃의 기록 폴더 이름을 준다" "$out" "pdn=$WANT"
out="$(run "cd '$MAIN' && CLAUDE_CODE_PROJECT_DIR_NAME=stale ccp team")"
check "메인 체크아웃에서는 주지 않는다 (물려받은 값도 지운다)" "$out" "pdn=<unset>"
out="$(run "cd '$W/wt' && ccp claude:default")"
check "기본 프로필에는 주지 않는다 (Claude Code 가 CLAUDE_CONFIG_DIR 없이는 안 받는다)" "$out" "pdn=<unset>"
printf 'CCP_LINK_WORKTREES=0\n' > "$XDG_CONFIG_HOME/ccp/config.zsh"
out="$(run "cd '$W/wt' && ccp team")"
check "CCP_LINK_WORKTREES=0 이면 끈다" "$out" "pdn=<unset>"
rm "$XDG_CONFIG_HOME/ccp/config.zsh"

print "다른 프로필이 잡은 세션"
mkdir -p "$HOME/.claude-profiles/personal/sessions"
printf '{"pid":%d,"sessionId":"11111111-2222-3333-4444-555555555555","cwd":"%s","kind":"bg","name":"머지"}' $$ "$W/wt" \
  > "$HOME/.claude-profiles/personal/sessions/$$.json"
out="$(run "cd '$W/wt' && ccp team")"
check "이 폴더의 백그라운드 세션을 다른 프로필이 잡고 있으면 알린다" "$out" "백그라운드 세션 11111111(머지)를 personal 프로필이 잡고 있다"
check "알리기만 하고 실행은 한다" "$out" "claude CLAUDE_CONFIG_DIR=$HOME/.claude-profiles/team"
out="$(run "cd '$W/wt' && ccp personal")"
checkno "자기 프로필 것은 알리지 않는다" "$out" "잡고 있다"
out="$(run "cd '$MAIN' && ccp team -r 11111111-2222-3333-4444-555555555555")"
check "-r 로 집은 세션이 다른 프로필에서 열려 있으면 경고" "$out" "세션 11111111 는 지금 personal 프로필에서 열려 있다"
rm -rf "$HOME/.claude-profiles/personal/sessions"

print "대화 가져오기 (--take · 선택 화면)"
PK="$W/pick"; mkdir -p "$PK"; PKF="$HOME/.claude/projects/$(print -r -- "${PK:A}" | sed 's/[^A-Za-z0-9]/-/g')"; mkdir -p "$PKF"
mkrec() {  # mkrec <세션ID> <제목> <mtime(초)> [continued-in]
  local f="$PKF/$1.jsonl"
  { printf '{"type":"ai-title","aiTitle":"%s","sessionId":"%s"}\n' "$2" "$1"
    printf '{"type":"user","parentUuid":null,"uuid":"u1","sessionId":"%s","gitBranch":"main","message":{"role":"user","content":"q"}}\n' "$1"
    [[ -n "${4:-}" ]] && printf '{"type":"continued-in","sessionId":"%s","continuedInSessionId":"%s"}\n' "$1" "$4"; } > "$f"
  touch -t "$3" "$f"
}
mkrec 11111111-2222-3333-4444-555555555555 "원본 대화" 202609211300
mkrec 11119999-2222-3333-4444-555555555555 "다른 대화" 202609211200
printf '{"type":"ai-title","aiTitle":"껍데기","sessionId":"22222222-0000-0000-0000-000000000000"}\n' > "$PKF/22222222-0000-0000-0000-000000000000.jsonl"
touch -t 202609211400 "$PKF/22222222-0000-0000-0000-000000000000.jsonl"
out="$(run "cd '$PK' && ccp team --take 11111111")"
check "--take <앞자리> → 그 기록을 --resume <경로> --fork-session 으로 연다" "$out" "args=--resume $PKF/11111111-2222-3333-4444-555555555555.jsonl --fork-session"
check "무엇을 가져오는지 알린다" "$out" "세션 11111111(원본 대화)를 team 계정으로 가져온다"
out="$(run "cd '$PK' && ccp team --take --foo")"
check "--take 만 주면 가장 최근 대화 (제목만 있는 껍데기는 건너뛴다)" "$out" "args=--resume $PKF/11111111-2222-3333-4444-555555555555.jsonl --fork-session --foo"
out="$(run "cd '$PK' && ccp team --take 1111")"
check "앞자리가 여럿과 맞으면 후보를 보이고 열지 않는다" "$out" "세션 ID '1111' 가 여러 개와 맞는다: 11111111 11119999"
checkno "여럿이면 claude 를 띄우지 않는다" "$out" "claude CLAUDE_CONFIG_DIR"
out="$(run "cd '$PK' && ccp team --take zzzz")"
check "없는 ID 는 안내" "$out" "가져올 대화가 없다: zzzz"
out="$(run "cd '$PK' && ccp codex:work --take")"
check "codex 에는 --take 가 없다" "$out" "claude 전용"
mkdir -p "$HOME/.claude-profiles/personal/sessions"
printf '{"pid":%d,"sessionId":"11111111-2222-3333-4444-555555555555","cwd":"%s","kind":"bg","name":"원본 대화"}' $$ "$PK" \
  > "$HOME/.claude-profiles/personal/sessions/$$.json"
out="$(run "cd '$PK' && ccp team --take 11111111")"
check "다른 프로필이 잡고 있어도 복사본이라 묻지 않고 열되, 정리 명령을 알린다" "$out" "원본은 personal 프로필이 아직 잡고 있다 — 정리: ccp personal 로 들어가 claude stop 11111111"
check "그래도 연다" "$out" "args=--resume $PKF/11111111-2222-3333-4444-555555555555.jsonl --fork-session"
checkno "'그래도 열까?' 는 묻지 않는다" "$out" "그래도 열까"
rm -rf "$HOME/.claude-profiles/personal/sessions"
out="$(run "cd '$PK' && ccp team")"
check "stdin 이 터미널이 아니면 선택 화면 없이 새 대화 (기존 동작)" "$out" "claude CLAUDE_CONFIG_DIR=$HOME/.claude-profiles/team args= "
out="$(printf '1\n' | CCP_PICK_SESSION=always zsh -c "source '$REPO/ccp.zsh'; cd '$PK' && ccp team" 2>&1)"
check "선택 화면: 대화 목록이 최근순으로 나온다" "$out" "1) 11111111"
check "선택 화면: 제목·브랜치가 보인다" "$out" "원본 대화"
checkno "선택 화면: 껍데기는 안 나온다" "$out" "22222222"
check "번호를 고르면 그 대화를 가져와 연다" "$out" "args=--resume $PKF/11111111-2222-3333-4444-555555555555.jsonl --fork-session"
out="$(printf '\n' | CCP_PICK_SESSION=always zsh -c "source '$REPO/ccp.zsh'; cd '$PK' && ccp team" 2>&1)"
check "Enter 는 새 대화" "$out" "args= "
checkno "Enter 면 resume 을 붙이지 않는다" "$out" "--resume"
out="$(printf 'q\n' | CCP_PICK_SESSION=always zsh -c "source '$REPO/ccp.zsh'; cd '$PK' && ccp team" 2>&1)"
checkno "q 는 취소 — 띄우지 않는다" "$out" "claude CLAUDE_CONFIG_DIR"
out="$(printf '1\n' | CCP_PICK_SESSION=always zsh -c "source '$REPO/ccp.zsh'; cd '$PK' && ccp team -c" 2>&1)"
check "-c/-r 을 직접 주면 선택 화면을 건너뛴다" "$out" "args=-c"
out="$(printf '1\n' | CCP_PICK_SESSION=0 zsh -c "source '$REPO/ccp.zsh'; cd '$PK' && ccp team" 2>&1)"
check "CCP_PICK_SESSION=0 이면 끈다" "$out" "args= "
mkrec 11111111-2222-3333-4444-555555555555 "원본 대화" 202609211300 33333333-0000-0000-0000-000000000000
out="$(printf '\n' | CCP_PICK_SESSION=always zsh -c "source '$REPO/ccp.zsh'; cd '$PK' && ccp team" 2>&1)"
check "다른 세션으로 이어진 대화는 그 표시가 붙되 목록에 남는다 (원본이 진짜 기록이다)" "$out" "33333333 로 이어짐"
rm -rf "$PKF"

print "ccp-migrate"
# 예전 ccp 가 만든 프로필 — file-history 가 심링크가 아니라 진짜 폴더다
LEG="$HOME/.claude-profiles/legacy"; mkdir -p "$LEG/file-history/s1"; echo v > "$LEG/file-history/s1/f@v1"
out="$(run 'ccp-migrate -n')"
check "-n 은 보기만" "$out" "미리 보기"
[[ ! -L "$LEG/file-history" ]] && check "-n 은 링크를 만들지 않는다" y y || check "-n 은 링크를 만들지 않는다" n y
out="$(run 'ccp-migrate')"
[[ -L "$LEG/file-history" && -f "$HOME/.claude/file-history/s1/f@v1" ]] \
  && check "file-history 를 기본 홈으로 합치고 심링크로 바꾼다" y y || check "file-history 를 기본 홈으로 합치고 심링크로 바꾼다" n y
rm -rf "$LEG"
out="$(run 'ccp-new linked >/dev/null; [[ -L $HOME/.claude-profiles/linked/file-history && -L $HOME/.claude-profiles/linked/paste-cache ]] && echo LINKED')"
check "새 프로필은 처음부터 file-history·paste-cache 를 공유한다" "$out" "LINKED"

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
