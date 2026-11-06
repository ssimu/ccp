#!/bin/zsh
# fleet/ccp-worker 통합 테스트 — 가짜 HOME 에서만 돈다. 실제 ~/.claude-profiles·키체인·claude 를 건드리지 않는다.
#   zsh tests/test_ccp_worker.sh
# 마지막 exec 단계(zsh -lic 'ccp ...')는 가짜 HOME 에 ccp 가 없어 실패한다 — 그 종료코드는 보지 않는다.
set -u
REPO="${0:A:h:h}"
WORKER="$REPO/fleet/ccp-worker"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

export HOME="$T/home" PATH="$T/bin:$PATH"
unset ZDOTDIR CCP_WORKER_ALLOWED CLAUDE_CONFIG_DIR CCP_CONFIG_DIR XDG_CONFIG_HOME
mkdir -p "$HOME/projects/repo" "$HOME/fleet-work/job" "$HOME/.claude-profiles/team" "$T/bin" "$T/outside"
# 실제 claude 가 뜨면 안 된다 — PATH 앞의 가짜 claude 가 호출되면 표식 파일을 남긴다
cat > "$T/bin/claude" <<'EOS'
#!/bin/sh
echo "claude $*" >> "$CCP_WORKER_TEST_MARK"; exit 0
EOS
chmod +x "$T/bin/claude"
export CCP_WORKER_TEST_MARK="$T/claude-ran"

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
[[ ! -e "$CCP_WORKER_TEST_MARK" ]] && check "실제 claude 는 뜨지 않는다" y y || check "실제 claude 는 뜨지 않는다" "n: $(cat "$CCP_WORKER_TEST_MARK")" y

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
checkno "~/fleet-work 도 기본 허용 폴더" "$OUT" "허용 폴더"   # 통과 뒤 exec 단계는 가짜 HOME 에 ccp 가 없어 실패한다 — 종료코드는 보지 않는다
check "fleet-work 폴더도 신뢰 기록" "$(jget "$CFG" "d['projects']['${${HOME}:A}/fleet-work/job']['hasTrustDialogAccepted']")" "True"
run "$HOME/projects/repo" default
checkno "default 프로필은 디렉터리 검사 없이 통과" "$OUT" "프로필 없음"
check   "default 는 ~/.claude.json 에 적는다" "$(jget "$HOME/.claude.json" 'd["bypassPermissionsModeAccepted"]')" "True"

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

print "\n통과 $PASS · 실패 $FAIL"
(( FAIL == 0 ))
