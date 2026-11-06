#!/bin/zsh
# fleet/ccp-worker 통합 테스트 — 가짜 HOME 에서만 돈다. 실제 ~/.claude-profiles·키체인·claude 를 건드리지 않는다.
#   zsh tests/test_ccp_worker.sh
# 마지막 exec 단계(zsh -lic 'ccp ...')는 가짜 HOME 의 .zshrc 에 둔 ccp 스텁으로 간다 — 받은 인자와 CCP_PICK_SESSION 을 기록만 한다.
set -u
REPO="${0:A:h:h}"
WORKER="$REPO/fleet/ccp-worker"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

# PATH 는 최소로 — 진짜 claude(~/.local/bin 등)가 잡히지 않게. ZDOTDIR 도 가짜 HOME 으로 해 진짜 .zshrc(진짜 ccp)를 읽지 않는다.
export HOME="$T/home" ZDOTDIR="$T/home" PATH="$T/bin:/usr/bin:/bin"
unset CCP_WORKER_ALLOWED CLAUDE_CONFIG_DIR CCP_CONFIG_DIR XDG_CONFIG_HOME
mkdir -p "$HOME/projects/repo" "$HOME/fleet-work/job" "$HOME/.claude-profiles/team" "$T/bin" "$T/outside"
export CCP_WORKER_TEST_MARK="$T/claude-ran" CCP_WORKER_TEST_LOG="$T/ccp-called"
# exec 단계가 부르는 ccp 스텁 — 인자와 CCP_PICK_SESSION 을 기록하고 0 으로 끝난다. claude 는 부르지 않는다.
cat > "$ZDOTDIR/.zshrc" <<'EOS'
ccp() { echo "ccp args=$* pick=${CCP_PICK_SESSION-<unset>}" >> "$CCP_WORKER_TEST_LOG"; return 0 }
EOS
# 그래도 claude 가 불리면 표식 파일을 남긴다
cat > "$T/bin/claude" <<'EOS'
#!/bin/sh
echo "claude $*" >> "$CCP_WORKER_TEST_MARK"; exit 0
EOS
chmod +x "$T/bin/claude"

PASS=0; FAIL=0
check()  { local name="$1" got="$2" want="$3"
           if [[ "$got" == *"$want"* ]]; then PASS=$((PASS+1)); print "  ok   $name"
           else FAIL=$((FAIL+1)); print "  FAIL $name\n       기대: ...$want...\n       실제: $got"; fi }
checkno(){ local name="$1" got="$2" bad="$3"
           if [[ "$got" != *"$bad"* ]]; then PASS=$((PASS+1)); print "  ok   $name"
           else FAIL=$((FAIL+1)); print "  FAIL $name\n       없어야: $bad\n       실제: $got"; fi }
# run <폴더> <프로필> [환경=값 ...] → OUT(stdout+stderr), RC
run() { local dir="$1" prof="$2"; shift 2
        OUT="$(cd "$dir" && env "$@" zsh "$WORKER" "$prof" 2>&1 </dev/null)"; RC=$? }
# jget <.claude.json> <파이썬 식> — d 에 JSON 을 담아 식을 평가해 출력
jget() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))' "$1" "$2" 2>&1 }

print "허용 폴더"
run "$T/outside" team
check "허용 폴더 밖이면 exit 2"        "rc=$RC" "rc=2"
check "허용 폴더 밖이면 거부 문구"     "$OUT"   "허용 폴더"
[[ ! -e "$HOME/.claude-profiles/team/.claude.json" ]] \
  && check "거부하면 프로필 설정을 건드리지 않는다" y y || check "거부하면 프로필 설정을 건드리지 않는다" n y

print "프로필"
run "$HOME/projects/repo" nope
check "허용 폴더 안이지만 없는 프로필이면 exit 2" "rc=$RC" "rc=2"
check "없는 프로필 문구"                           "$OUT"   "프로필 없음"
[[ ! -e "$HOME/.claude-profiles/nope" ]] && check "없는 프로필을 만들지 않는다" y y || check "없는 프로필을 만들지 않는다" n y

print "신뢰·권한 수락 미리 기록"
CFG="$HOME/.claude-profiles/team/.claude.json"
run "$HOME/projects/repo" team
checkno "허용 폴더 검사·프로필 검사를 지나간다 (거부 문구 없음)" "$OUT" "거부"
checkno "프로필 없음 문구가 없다"                               "$OUT" "프로필 없음"
[[ -f "$CFG" ]] && check ".claude.json 이 생긴다" y y || check ".claude.json 이 생긴다" n y
KEY="${${HOME}:A}/projects/repo"   # ccp-worker 는 \${PWD:A} 로 심링크를 푼 경로를 쓴다
check "projects[<폴더>].hasTrustDialogAccepted = true" "$(jget "$CFG" "d['projects']['$KEY']['hasTrustDialogAccepted']")" "True"
check "bypassPermissionsModeAccepted = true"           "$(jget "$CFG" 'd["bypassPermissionsModeAccepted"]')" "True"
check "hasCompletedOnboarding = true"                  "$(jget "$CFG" 'd["hasCompletedOnboarding"]')" "True"
check "exec 단계가 ccp 스텁으로 간다 (exit 0)"              "rc=$RC" "rc=0"
check "ccp 에 프로필 이름을 넘기고 CCP_PICK_SESSION=0 으로"   "$(cat "$CCP_WORKER_TEST_LOG" 2>&1)" "ccp args=team pick=0"
[[ ! -e "$CCP_WORKER_TEST_MARK" ]] && check "실제 claude 는 뜨지 않는다" y y || check "실제 claude 는 뜨지 않는다" "n: $(cat "$CCP_WORKER_TEST_MARK")" y
rm -f "$CCP_WORKER_TEST_LOG"

# 이미 있는 설정은 보존하고, 다 적혀 있으면 다시 쓰지 않는다
python3 - "$CFG" <<'PY'
import json, sys
f = sys.argv[1]; d = json.load(open(f)); d["keep"] = "me"; d["theme"] = "light"
json.dump(d, open(f, "w"))
PY
run "$HOME/projects/repo" team
check "기존 키를 보존한다"              "$(jget "$CFG" 'd["keep"]')"  "me"
check "이미 있는 theme 은 덮지 않는다"  "$(jget "$CFG" 'd["theme"]')" "light"
check "두 번 돌려도 신뢰 기록은 그대로" "$(jget "$CFG" "d['projects']['$KEY']['hasTrustDialogAccepted']")" "True"
BEFORE="$(stat -f %m "$CFG")"; sleep 1
run "$HOME/projects/repo" team
check "바뀔 것이 없으면 파일을 다시 쓰지 않는다 (mtime 유지)" "$(stat -f %m "$CFG")" "$BEFORE"

print "다른 허용 폴더·기본 프로필"
run "$HOME/fleet-work/job" team
check "~/fleet-work 도 기본 허용 폴더 — 스텁까지 간다" "rc=$RC" "rc=0"
check "fleet-work 폴더도 신뢰 기록" "$(jget "$CFG" "d['projects']['${${HOME}:A}/fleet-work/job']['hasTrustDialogAccepted']")" "True"
rm -f "$CCP_WORKER_TEST_LOG"
run "$HOME/projects/repo" default
checkno "default 프로필은 디렉터리 검사 없이 통과" "$OUT" "프로필 없음"
check   "default 는 ~/.claude.json 에 적는다" "$(jget "$HOME/.claude.json" 'd["bypassPermissionsModeAccepted"]')" "True"
check   "default 는 ccp 에 0 을 넘긴다"       "$(cat "$CCP_WORKER_TEST_LOG" 2>&1)" "ccp args=0 pick=0"

print "CCP_WORKER_ALLOWED"
run "$T/outside" team CCP_WORKER_ALLOWED="$T/outside"
checkno "CCP_WORKER_ALLOWED 로 준 폴더는 허용된다" "$OUT" "허용 폴더"
check   "허용된 폴더는 신뢰 기록까지 간다" "$(jget "$CFG" "d['projects']['${${T}:A}/outside']['hasTrustDialogAccepted']")" "True"
run "$T/outside" team CCP_WORKER_ALLOWED="$T/elsewhere:$T/outside"
checkno "콜론으로 여러 폴더를 줄 수 있다" "$OUT" "허용 폴더"
run "$HOME/projects/repo" team CCP_WORKER_ALLOWED="$T/outside"
check "CCP_WORKER_ALLOWED 를 주면 기본 허용 폴더는 빠진다" "rc=$RC" "rc=2"
check "거부 문구에 허용 목록이 보인다 (준 그대로)" "$OUT" "허용 폴더($T/outside)"
[[ ! -e "$CCP_WORKER_TEST_MARK" ]] && check "끝까지 실제 claude 는 뜨지 않았다" y y || check "끝까지 실제 claude 는 뜨지 않았다" "n: $(cat "$CCP_WORKER_TEST_MARK")" y
check "거부된 경우에는 ccp 스텁을 부르지 않았다 (통과한 3건만 기록)" "$(grep -c '^ccp ' "$CCP_WORKER_TEST_LOG")" "3"

print "\n통과 $PASS · 실패 $FAIL"
(( FAIL == 0 ))
