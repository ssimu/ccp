# ccp — Claude Code / Codex 계정 프로필 전환 (zsh)
#
#   ccp              메뉴에서 고른다 (claude·codex 계정을 한 화면에, 사용량·추천 함께 표시)
#                    ↑↓(j/k) 이동 · 숫자 키로 해당 번호 · Enter 실행 · v 그래프/표 전환 · Esc/q 취소
#                    엔터만 치면 추천 계정으로 바로 실행
#                    기본은 새 대화. -c/--continue, -r/--resume 을 직접 주면 그대로 전달
#   ccp 2            번호로 바로
#   ccp team         이름으로 (Tab 완성). 양쪽에 같은 이름이 있으면 codex:team 처럼 도구를 붙인다
#   ccp-ls           프로필 + 계정/조직
#   ccp-usage        프로필별 사용량만
#   ccp-new <이름>          claude 프로필 추가 (profiles.tsv 에도 기록)
#   ccp-new --codex <이름>  codex 프로필 추가
#   ccp-sync         profiles.tsv 에 있는데 디렉터리가 없는 프로필을 만든다
#   ccp-statusline   상태줄 미리보기 (statusline.conf 를 고치면서 확인)
#   claude           기본 프로필(~/.claude)
#
# 설정 (저장소에 없음 — 사람마다 다르다):
#   $CCP_CONFIG_DIR/profiles.tsv   도구<TAB>이름<TAB>별칭<TAB>설명. 계정 수·이름·별칭은 여기서 정한다.
#   $CCP_CONFIG_DIR/config.zsh     CCP_CLAUDE_ARGS 등 실행 옵션 (config.example.zsh 참조)
#   $CCP_CONFIG_DIR/statusline.conf 상태줄에 무엇을 어떻게 보일지 (statusline.example.conf 참조)
#   CCP_CONFIG_DIR 기본값은 ~/.config/ccp
#
# 원리(claude): CLAUDE_CONFIG_DIR 은 인증까지 분리한다(빈 디렉터리로 실행하면 Not logged in).
#   공유(심링크): settings.json skills plugins commands projects(대화 기록)
#   분리        : .claude.json(인증·MCP)
#   ⚠ .claude.json 은 절대 링크하지 말 것 — 링크하면 두 프로필이 같은 계정을 본다.
#
# 원리(codex): CODEX_HOME 을 프로필마다 따로 둔다. codex 는 auth.json 에 계정을 하나만 들고 있어서
#   이 방법 말고는 매번 logout/login 을 반복해야 한다. 같은 ChatGPT 로그인이라도 워크스페이스가
#   다르면 각각 로그인해야 한다(브라우저 승인 화면에서 워크스페이스를 고른다).
#   공유(심링크): config.toml skills plugins prompts rules AGENTS.md
#   분리        : auth.json, sessions/, 히스토리·상태 파일
#   사용량은 `codex app-server` 의 JSON-RPC 로 읽는다 — 모델을 부르지 않으므로 토큰이 안 든다.

# 이 파일이 있는 디렉터리(렌더러·codex 조회 스크립트가 옆에 있다)
_CCP_HOME="${${(%):-%x}:A:h}"

# 사용자 설정. 렌더러(보기 상태 파일)도 같은 디렉터리를 쓰므로 export 한다.
export CCP_CONFIG_DIR="${CCP_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/ccp}"
CCP_PROFILES_TSV="$CCP_CONFIG_DIR/profiles.tsv"

# claude 를 띄울 때 항상 붙일 인자. 기본은 없음. 예: CCP_CLAUDE_ARGS=(--dangerously-skip-permissions)
typeset -ga CCP_CLAUDE_ARGS
[ -f "$CCP_CONFIG_DIR/config.zsh" ] && source "$CCP_CONFIG_DIR/config.zsh"

# 표시 언어. config.zsh 의 CCP_LANG(ko/en/ja/zh)이 있으면 그것, 없으면 로케일(LC_ALL→LC_MESSAGES→LANG)에서.
# ko/ja/zh 가 아니면 en. python 자식(렌더러·statusline)도 같은 값을 쓰도록 export 한다.
_ccp_lang_detect() {
  local l="${CCP_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}"
  case "${l:l}" in ko*) print ko;; ja*) print ja;; zh*) print zh;; *) print en;; esac
}
export CCP_LANG="$(_ccp_lang_detect)"
source "$_CCP_HOME/ccp_i18n.zsh"          # 문구 사전(생성 파일). 원본은 ccp_i18n.py
_CCP_DEFAULT="$(_ccp_t default)"           # 기본 프로필(~/.claude, ~/.codex)의 표시 이름

CLAUDE_PROFILES="${CLAUDE_PROFILES:-$HOME/.claude-profiles}"
CODEX_PROFILES="${CODEX_PROFILES:-$HOME/.codex-profiles}"

# 프로필 이름 목록 (기본 프로필은 '기본' 으로 표기, 메뉴 0번)
_ccp_list() { print -l "$CLAUDE_PROFILES"/*(N/:t) }
_cxp_list() { print -l "$CODEX_PROFILES"/*(N/:t) }
_cxp_available() { command -v codex >/dev/null 2>&1 }

# 계정/조직 한 줄
_ccp_who() {
  python3 -c "
import json,sys
try: a=json.load(open(sys.argv[1])).get('oauthAccount') or {}
except Exception: print(sys.argv[2]); raise SystemExit
if not a.get('emailAddress'): print(sys.argv[2]); raise SystemExit
print(f\"{a['emailAddress']}  {(a.get('organizationName') or '')[:26]}\")
" "$1" "$(_ccp_t z_nologin)" 2>/dev/null || _ccp_tl z_nologin
}

# 로그인 여부만. 미로그인 프로필은 /usage 를 부를 필요가 없다(호출당 ~3.5s).
_ccp_logged_in() {
  python3 -c "
import json,sys
try: a=json.load(open(sys.argv[1])).get('oauthAccount') or {}
except Exception: sys.exit(1)
sys.exit(0 if a.get('emailAddress') else 1)
" "$1" 2>/dev/null
}

# ── /usage 출력 파서 ────────────────────────────────────────────────────────
# 한 줄 TSV 로 뱉는다: 주간% \t 주간리셋(분) \t 세션% \t 세션리셋(분) \t 모델명 \t 모델% \t 상태 \t 주간리셋시각 \t 세션리셋시각
# 표시는 전부 _ccp_render 가 맡는다 — 여기서는 숫자만 낸다.
_ccp_parse_script() { cat <<'PY'
import re,sys,datetime
t=sys.stdin.read()
M={m:i for i,m in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],1)}
now=datetime.datetime.now()
def parse(x):
    # print 모드 형식: 'resets Sep 8 at 1:19am (Asia/Seoul)'
    #   정각이면 분 생략('11pm'), 연도가 바뀌면 'Jan 2, 2027 at 1:19am' 처럼 연도가 붙는다.
    m=re.search(r'resets ([A-Z][a-z]{2}) (\d+)(?:, (\d{4}))? at (\d+)(?::(\d+))?(am|pm)',x)
    if not m: return None
    mo,d,yr=M.get(m.group(1),0),int(m.group(2)),m.group(3)
    h,mi,ap=int(m.group(4)),int(m.group(5) or 0),m.group(6)
    if ap=='pm' and h!=12: h+=12
    if ap=='am' and h==12: h=0
    try: dt=datetime.datetime(int(yr) if yr else now.year,mo,d,h,mi)
    except ValueError: return None
    # 연도가 없을 때 과거로 나오면 내년으로 본다(연말 경계).
    if not yr and (now-dt).days>180: dt=dt.replace(year=now.year+1)
    return dt
def row(pat):
    m=re.search(pat+r'([^\n]*)',t)
    if not m: return None,None
    line=m.group(1); pc=re.search(r'(\d+)% used',line)
    return (int(pc.group(1)) if pc else None), parse(line)
w,wdt=row(r'Current week \(all models\):')
s,sdt=row(r'Current session:')
mm=re.search(r'Current week \((?!all models)([^)]+)\):([^\n]*)',t)
mn=None; mp=None
if mm:
    mn=mm.group(1); pc=re.search(r'(\d+)% used',mm.group(2))
    mp=int(pc.group(1)) if pc else None
# 분은 반올림 — 버림이면 '1:19am 리셋'이 22:37에 2시간41분으로 나와 1분 어긋나 보인다.
def mins(dt):  return '' if dt is None else str(max(int(round((dt-now).total_seconds()/60)),0))
def stamp(dt): return '' if dt is None else dt.strftime('%m/%d %H:%M')
def num(v):    return '' if v is None else str(v)
# 뒤 세 칸(주간 창·세션 창·메모)은 codex 와 형식을 맞추려고 붙인다. claude 는 7일/5시간 고정.
if w is None and s is None:
    print('\t'.join(['']*6+['fail']+['']*5))
else:
    print('\t'.join([num(w),mins(wdt),num(s),mins(sdt),mn or '',num(mp),'ok',stamp(wdt),stamp(sdt),
                     '10080','300','']))
PY
}

# 사용량 한 줄. /usage 는 print 모드에서도 동작한다(모델 호출 아님).
# 인자가 비면 기본 프로필. 기본은 설정이 ~/.claude.json(홈 바로 아래)이라
# CLAUDE_CONFIG_DIR=~/.claude 로 부르면 ~/.claude/.claude.json 을 찾아 실패한다.
_ccp_usage_one() {
  local dir="${1:-}"
  local cfg="$HOME/.claude.json"
  [ -n "$dir" ] && cfg="$dir/.claude.json"
  _ccp_logged_in "$cfg" || { printf '\t\t\t\t\t\tnologin\n'; return 0; }
  # 프로필 세션 안에서 부르면 CLAUDE_CONFIG_DIR 이 환경에 남아 자식이 물려받는다.
  # 기본 프로필을 조회하려면 반드시 지워야 한다(안 그러면 현재 프로필이 조회된다).
  # stdin 을 끊는다 — 안 끊으면 백그라운드 claude 가 터미널 입력(메뉴에서 고르는 번호)을
  # 먹어 버려서 read 가 빈 값을 받는다.
  { if [ -n "$dir" ]; then CLAUDE_CONFIG_DIR="$dir" command claude -p "/usage" --max-turns 1 </dev/null
    else ( unset CLAUDE_CONFIG_DIR; command claude -p "/usage" --max-turns 1 </dev/null ); fi; } 2>/dev/null \
    | python3 -c "$(_ccp_parse_script)" 2>/dev/null || printf '\t\t\t\t\t\tfail\n'
}

# codex 사용량 한 줄. app-server 에 account/read + account/rateLimits/read 를 던진다(토큰 0, ~1s).
_cxp_usage_one() {
  python3 "$_CCP_HOME/ccp_codex.py" probe "${1:-$HOME/.codex}" 2>/dev/null \
    || printf '\t\t\t\t\t\tfail\t\t\t\t\t\n'
}

_cxp_who() { python3 "$_CCP_HOME/ccp_codex.py" who "${1:-$HOME/.codex}" 2>/dev/null || _ccp_tl z_query_fail }

# ── 렌더러 ─────────────────────────────────────────────────────────────────
# 쓸 수 있는 계정을 위로 올리고, 그중 여유가 가장 큰 하나를 '추천' 으로 찍는다.
# 막힌 계정(세션/주간 소진, 미로그인)은 흐리게 내려 보내 잘못 고르지 않게 한다.
# 렌더러는 옆 파일(ccp_render.py). 여기 heredoc 으로 두면 zsh 안에 파이썬 480줄이 갇혀
# 손대기가 어렵다 — codex 섹션을 붙이면서 분리했다.
# $1=tmpdir  $2="num"이면 번호 붙임  $3=현재 프로필(tool:이름, 없으면 "")  $4..=tool:이름 들
_ccp_render() { python3 "$_CCP_HOME/ccp_render.py" "$@" }

# ── 계정 목록 ───────────────────────────────────────────────────────────────
# 한 화면에 claude 와 codex 를 같이 세운다. 번호는 두 도구를 관통해서 매긴다.
# _CCP_TOOLS/_CCP_NAMES/_CCP_DIRS/_CCP_SPECS 는 같은 순서의 평행 배열.
#   디렉터리가 빈 값이면 그 도구의 기본 홈(claude 는 ~/.claude.json, codex 는 ~/.codex).
_ccp_entries() {
  _CCP_DEFAULT="$(_ccp_t default)"   # 호출 시점의 CCP_LANG 을 따르게(CCP_LANG=en ccp 처럼 한 번만 바꿔 쓸 때)
  _CCP_TOOLS=(); _CCP_NAMES=(); _CCP_DIRS=(); _CCP_SPECS=()
  local n
  _CCP_TOOLS+=(claude); _CCP_NAMES+=("$_CCP_DEFAULT"); _CCP_DIRS+=("");           _CCP_SPECS+=("claude:$_CCP_DEFAULT")
  for n in $(_ccp_list); do
    _CCP_TOOLS+=(claude); _CCP_NAMES+=("$n"); _CCP_DIRS+=("$CLAUDE_PROFILES/$n"); _CCP_SPECS+=("claude:$n")
  done
  _cxp_available || return 0
  _CCP_TOOLS+=(codex);  _CCP_NAMES+=("$_CCP_DEFAULT"); _CCP_DIRS+=("$HOME/.codex"); _CCP_SPECS+=("codex:$_CCP_DEFAULT")
  for n in $(_cxp_list); do
    _CCP_TOOLS+=(codex);  _CCP_NAMES+=("$n"); _CCP_DIRS+=("$CODEX_PROFILES/$n");  _CCP_SPECS+=("codex:$n")
  done
}

# 전 계정 사용량을 병렬로 (순차는 claude 프로필당 ~3.5s, codex 는 ~1s)
_ccp_collect() {
  # 백그라운드 조회의 [n] pid / done 알림을 죽인다 — 메뉴가 그걸로 뒤덮인다.
  setopt localoptions nomonitor nonotify
  local tmp="$1" i
  for i in {1..${#_CCP_TOOLS}}; do
    if [[ "${_CCP_TOOLS[$i]}" == codex ]]; then
      ( _cxp_usage_one "${_CCP_DIRS[$i]}" > "$tmp/$((i-1))" ) &
    else
      ( _ccp_usage_one "${_CCP_DIRS[$i]}" > "$tmp/$((i-1))" ) &
    fi
  done
  wait
}

# 지금 어느 프로필 안에 있는지 (렌더러의 [현재] 표식용)
_ccp_current() {
  if [ -n "$CODEX_HOME" ] && [ "$CODEX_HOME" != "$HOME/.codex" ]; then printf 'codex:%s\n' "${CODEX_HOME:t}"
  elif [ -n "$CLAUDE_CONFIG_DIR" ]; then printf 'claude:%s\n' "${CLAUDE_CONFIG_DIR:t}"
  else printf '\n'; fi
}

# 사용량을 받아 그린다. $1 = "num"(번호·대화형) 또는 "-"
_ccp_show() {
  local mode="$1" tmp="$2"
  [ -t 1 ] && { _ccp_t z_querying ${#_CCP_NAMES}; printf '\r'; }
  _ccp_collect "$tmp"
  [ -t 1 ] && printf '\033[2K\r'
  _ccp_render "$tmp" "$mode" "$(_ccp_current)" "${_CCP_SPECS[@]}"
}

ccp-usage() {
  _ccp_entries
  local tmp; tmp=$(mktemp -d)
  _ccp_show "-" "$tmp"
  rm -rf "$tmp"
}

ccp-ls() {
  _CCP_DEFAULT="$(_ccp_t default)"
  printf '\033[1;36mClaude\033[0m\n'
  printf '  %-14s %s\n' "$_CCP_DEFAULT" "$(_ccp_who "$HOME/.claude.json")"
  local n
  for n in $(_ccp_list); do
    printf '  %-14s %s\n' "$n" "$(_ccp_who "$CLAUDE_PROFILES/$n/.claude.json")"
  done
  _cxp_available || return 0
  printf '\033[1;36mCodex\033[0m\n'
  printf '  %-14s %s\n' "$_CCP_DEFAULT" "$(_cxp_who "$HOME/.codex")"
  for n in $(_cxp_list); do
    printf '  %-14s %s\n' "$n" "$(_cxp_who "$CODEX_PROFILES/$n")"
  done
}

# ── 프로필 생성 · profiles.tsv ──────────────────────────────────────────────
# 프로필의 진실은 디렉터리다(메뉴는 디렉터리를 나열한다). TSV 는 두 가지에만 쓴다:
#   (1) 새 머신에서 디렉터리를 만들 때(ccp-sync)  (2) 단축 별칭을 정의할 때.
# 형식: 도구<TAB>이름<TAB>별칭<TAB>설명   (도구 = claude | codex, 별칭·설명은 비워도 된다)

# 디렉터리 하나를 만든다. 인증만 분리하고 설정·스킬은 기본 홈과 공유한다.
#   claude: .claude.json 만 분리. projects(대화 기록)를 공유해야 계정을 바꿔도 --continue 로 이어진다.
#   codex : auth.json 과 세션만 분리. 같은 사람의 두 워크스페이스라 설정까지 나눌 이유가 없다.
#     ⚠ codex 가 config.toml 을 통째로 갈아끼우면 심링크가 실파일로 바뀌어 공유가 조용히 끊긴다.
#       설정이 한쪽에만 반영되면 그 링크부터 확인할 것.
# 반환: 0 만듦 · 2 이미 있음
_ccp_mkprofile() {
  local tool="$1" name="$2" d item
  local -a items
  if [[ "$tool" == codex ]]; then
    d="$CODEX_PROFILES/$name"; items=(config.toml skills plugins prompts rules AGENTS.md)
    [ -d "$d" ] && return 2
    mkdir -p "$d"
    for item in "${items[@]}"; do [ -e "$HOME/.codex/$item" ] && ln -s "$HOME/.codex/$item" "$d/$item"; done
  else
    d="$CLAUDE_PROFILES/$name"; items=(settings.json skills plugins commands projects)
    [ -d "$d" ] && return 2
    mkdir -p "$d"
    for item in "${items[@]}"; do [ -e "$HOME/.claude/$item" ] && ln -s "$HOME/.claude/$item" "$d/$item"; done
  fi
  return 0
}

# TSV 의 유효한 줄만 "도구<TAB>이름<TAB>별칭<TAB>설명" 으로 낸다(주석·빈 줄 제외, 도구 생략 시 claude).
_ccp_tsv_rows() {
  [ -f "$CCP_PROFILES_TSV" ] || return 0
  local tool name alias desc
  while IFS=$'\t' read -r tool name alias desc; do
    [[ -z "$tool" || "$tool" == \#* ]] && continue
    # 예전 3칸 형식(이름<TAB>별칭<TAB>설명) 호환: 첫 칸이 도구가 아니면 claude 로 본다.
    if [[ "$tool" != claude && "$tool" != codex ]]; then desc="$alias"; alias="$name"; name="$tool"; tool=claude; fi
    [[ -z "$name" ]] && continue
    printf '%s\t%s\t%s\t%s\n' "$tool" "$name" "$alias" "$desc"
  done < "$CCP_PROFILES_TSV"
}

# TSV 에 줄을 덧붙인다(같은 도구·이름이 이미 있으면 그대로).
_ccp_tsv_add() {
  local tool="$1" name="$2" alias="${3:-}" desc="${4:-}"
  mkdir -p "$CCP_CONFIG_DIR"
  [ -f "$CCP_PROFILES_TSV" ] || _ccp_tl z_tsv_header > "$CCP_PROFILES_TSV"
  _ccp_tsv_rows | awk -F'\t' -v t="$tool" -v n="$name" '$1==t && $2==n{f=1} END{exit !f}' && return 0
  printf '%s\t%s\t%s\t%s\n' "$tool" "$name" "$alias" "$desc" >> "$CCP_PROFILES_TSV"
}

# TSV 에 있는데 디렉터리가 없는 프로필을 만든다. TSV 를 고친 뒤, 또 새 머신에서 부른다.
ccp-sync() {
  local tool name alias desc made=0
  while IFS=$'\t' read -r tool name alias desc; do
    if _ccp_mkprofile "$tool" "$name"; then
      _ccp_tl z_created "$tool" "$name"; made=$((made+1))
    fi
  done < <(_ccp_tsv_rows)
  if (( made )); then _ccp_tl z_sync_next
  else _ccp_tl z_sync_all "$CCP_PROFILES_TSV"; fi
}

# 단축 별칭. TSV 의 별칭 칸이 비어 있지 않은 줄마다 alias <별칭>="ccp <도구>:<이름>".
# ('cp'·'cd' 같은 기본 명령 이름은 거부한다 — 덮어쓰면 셸이 망가진다.)
_ccp_define_aliases() {
  local tool name alias desc kind   # local 은 루프 밖에서 — 안에서 반복 선언하면 zsh 가 값을 출력한다
  while IFS=$'\t' read -r tool name alias desc; do
    [[ -z "$alias" ]] && continue
    kind="$(whence -w -- "$alias" 2>/dev/null)"; kind="${kind##*: }"
    case "$kind" in
      ''|none|alias) ;;   # 없거나(none) 우리가 이미 만든 별칭이면 (다시) 정의한다
      *) _ccp_tl z_alias_conflict "$alias" "$kind" "$CCP_PROFILES_TSV" >&2; continue ;;
    esac
    alias "$alias"="ccp $tool:$name"
  done < <(_ccp_tsv_rows)
}
_ccp_define_aliases

ccp-new() {
  local tool=claude
  if [[ "$1" == --codex || "$1" == -x ]]; then tool=codex; shift; fi
  local name="${1:?$(_ccp_t z_new_usage)}"
  local alias="${2:-}" desc="${3:-}" d
  [[ "$tool" == codex ]] && d="$CODEX_PROFILES/$name" || d="$CLAUDE_PROFILES/$name"
  if ! _ccp_mkprofile "$tool" "$name"; then _ccp_tl z_exists "$d"; return 1; fi
  _ccp_tsv_add "$tool" "$name" "$alias" "$desc"
  [[ -n "$alias" ]] && alias "$alias"="ccp $tool:$name"
  _ccp_tl z_created_at "$d" "$CCP_PROFILES_TSV"
  if [[ "$tool" == codex ]]; then
    _ccp_tl z_codex_next "$d"
    _ccp_tl z_codex_ws
  else
    _ccp_tl z_claude_next "$name"
  fi
}

# 이름 → 항목 번호(0-based). 'codex:personal' 처럼 도구를 붙여 못박을 수 있다.
# 양쪽에 같은 이름이 있으면 도구를 붙이라고 알려 준다 — 조용히 하나를 고르면 엉뚱한 계정이 뜬다.
_ccp_find() {
  local want="$1" tool="" i
  if [[ "$want" == claude:* || "$want" == codex:* ]]; then tool="${want%%:*}"; want="${want#*:}"; fi
  # 기본 프로필은 표시 언어와 무관하게 'default' 또는 '기본' 으로도 부를 수 있게
  [[ "$want" == default || "$want" == 기본 ]] && want="$_CCP_DEFAULT"
  local -a hit
  for i in {1..${#_CCP_NAMES}}; do
    [[ -n "$tool" && "${_CCP_TOOLS[$i]}" != "$tool" ]] && continue
    [[ "${_CCP_NAMES[$i]}" == "$want" ]] && hit+=($((i-1)))
  done
  (( ${#hit} == 1 )) && { printf '%s\n' "${hit[1]}"; return 0; }
  (( ${#hit} > 1 )) && { _ccp_tl z_name_dup "$want" "$want" "$want" >&2; return 2; }
  return 1
}

# 세션 옵션(-c/--continue, -r/--resume)은 자동으로 붙이지 않는다 — 사용자가 직접 줄 때만 전달.
# 이전엔 대화 기록이 있으면 --continue 를 자동으로 붙였는데, 기록 존재 판정(~/.claude/projects)과
# 실제 프로필이 보는 위치가 어긋나 "No conversation found" 로 죽는 일이 반복됐다 (2026-09-05 제거).
#   이어가기: ccp 1 -c   /   특정 세션: ccp 1 -r <id>

ccp() {
  _ccp_entries
  (( ${#_CCP_NAMES} > 1 )) || { _ccp_tl z_no_profiles >&2; return 1; }

  local sel="${1:-}" grp="" idx=""
  if [ -n "$sel" ]; then shift; else
    # 사용량을 병렬로 미리 받아 메뉴에 함께 보여준다 — 전환 판단의 근거이므로.
    local tmp; tmp=$(mktemp -d)
    _ccp_show num "$tmp"

    local rec; rec=$(awk -F'\t' '$1=="rec"{print $2}' "$tmp/_meta" 2>/dev/null)
    local picked; picked=$(awk -F'\t' '$1=="sel"{print $2}' "$tmp/_meta" 2>/dev/null)
    if [[ -n "$picked" ]]; then
      # 터미널이면 렌더러가 화살표/숫자/Enter/Esc 로 직접 받아 sel 을 남긴다. -1 = 취소.
      [[ "$picked" == "-1" ]] && { rm -rf "$tmp"; return 0; }
      sel="$picked"
    else
      # 파이프 등 터미널이 아닐 때의 예전 방식.
      _ccp_tl z_quit; printf '\n'
      # 엔터 = 추천 계정 바로 실행. 한도 터졌을 때 '엔터 한 번'이 가장 흔한 동작이다.
      if [[ -n "$rec" && "$rec" != "-1" ]]; then
        _ccp_t z_select_rec $((${#_CCP_NAMES}-1)) "$rec" "${_CCP_NAMES[$((rec+1))]}"
      else
        _ccp_t z_select $((${#_CCP_NAMES}-1))
      fi
      read -r sel
      # 쓸 수 있는 계정이 하나도 없으면 엔터는 그냥 종료로 둔다 — 붙일 곳이 없다.
      [[ -z "$sel" && -n "$rec" && "$rec" != "-1" ]] && sel="$rec"
    fi
    [[ -n "$sel" && "$sel" == <-> ]] && grp=$(awk -F'\t' -v k="$sel" '$1==k{print $2}' "$tmp/_meta" 2>/dev/null)
    rm -rf "$tmp"
  fi

  # 엔터로 여기까지 왔다면 추천이 없었다는 뜻 — 그때는 종료가 맞다.
  [[ -z "$sel" || "$sel" == [qQ] ]] && return 0

  if [[ "$sel" == <-> ]]; then
    (( sel >= 0 && sel < ${#_CCP_NAMES} )) || { _ccp_tl z_out_of_range "$sel" >&2; return 1; }
    idx="$sel"
  else
    idx=$(_ccp_find "$sel") || {
      (( $? == 2 )) && return 1
      _ccp_tl z_not_found "$sel" "$sel" >&2; return 1
    }
  fi

  # 막힌 계정을 골랐으면 실행은 하되 왜 막혔는지는 알려 준다.
  case "$grp" in
    1) printf '\033[33m%s\033[0m\n' "$(_ccp_t z_warn_session)" ;;
    2) printf '\033[31m%s\033[0m\n' "$(_ccp_t z_warn_weekly)" ;;
    3) printf '\033[31m%s\033[0m\n' "$(_ccp_t z_warn_nologin)" ;;
  esac

  local tool="${_CCP_TOOLS[$((idx+1))]}" dir="${_CCP_DIRS[$((idx+1))]}"

  if [[ "$tool" == codex ]]; then
    # 기본 홈은 CODEX_HOME 을 지워서 연다 — 프로필 세션 안에서 기본을 골랐을 때 현재 프로필이 뜨면 안 된다.
    if [[ -z "$dir" || "$dir" == "$HOME/.codex" ]]; then ( unset CODEX_HOME; command codex "$@" )
    else CODEX_HOME="$dir" command codex "$@"; fi
    return
  fi

  # 같은 이유 — 프로필 세션에서 기본을 골라도 현재 프로필로 뜨면 안 된다.
  if [[ -z "$dir" ]]; then ( unset CLAUDE_CONFIG_DIR; command claude "${CCP_CLAUDE_ARGS[@]}" "$@" ); return; fi
  [ -d "$dir" ] || { _ccp_tl z_no_dir "$dir" >&2; return 1; }
  CLAUDE_CONFIG_DIR="$dir" command claude "${CCP_CLAUDE_ARGS[@]}" "$@"
}

# 상태줄 미리보기 — 지금 계정과 예시 한도(주간 38%·세션 12%)로 statusline.conf 를 적용해 그려 본다.
# 설정을 고치면서 바로 확인하는 용도. 실제 Claude Code 안에서는 진짜 수치가 들어간다.
ccp-statusline() {
  local now; now=$(date +%s)
  printf '{"model":{"display_name":"Opus"},"workspace":{"current_dir":"%s"},"context_window":{"used_percentage":12},"rate_limits":{"seven_day":{"used_percentage":38,"resets_at":%d},"five_hour":{"used_percentage":12,"resets_at":%d}}}' \
    "$PWD" $((now+2*86400+3*3600)) $((now+100*60)) | bash "$_CCP_HOME/statusline.sh"
  printf '\n'
  [ -f "$CCP_CONFIG_DIR/statusline.conf" ] || printf '  (%s/statusline.conf 없음 — 기본값. 예시: %s/statusline.example.conf)\n' "$CCP_CONFIG_DIR" "$_CCP_HOME"
}

_ccp_names() {
  # 맨이름과 'tool:이름' 둘 다 완성한다 — 양쪽에 같은 이름이 있으면 도구를 붙여야 하므로.
  local -a cl cx
  cl=("$CLAUDE_PROFILES"/*(N/:t))
  cx=("$CODEX_PROFILES"/*(N/:t))
  compadd -- $cl $cx ${cl/#/claude:} ${cx/#/codex:} "claude:$_CCP_DEFAULT" "codex:$_CCP_DEFAULT" claude:default codex:default
}
# 비대화형 zsh(install.sh 의 zsh -c 등)에는 compdef 가 없다. 그때 실패로 끝나면 source 의 종료 코드가 0 이 아니게 된다.
(( $+functions[compdef] )) && compdef _ccp_names ccp
true
