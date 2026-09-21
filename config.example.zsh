# ccp 실행 옵션 — ~/.config/ccp/config.zsh 로 복사해 고친다. zsh 문법이다.

# claude 를 띄울 때 항상 붙일 인자. 기본은 없음(평소 claude 와 같다).
# 권한 확인을 건너뛰려면 아래 줄의 주석을 푼다. 그만큼 위험하다 — 뜻을 알고 켤 것.
# CCP_CLAUDE_ARGS=(--dangerously-skip-permissions)

# 표시 언어. 비우면 터미널 로케일(LANG)을 따른다: ko/ja/zh 는 그 언어, 그 외는 en.
# CCP_LANG=ko      # ko | en | ja | zh

# 프로필 디렉터리 위치를 바꾸고 싶을 때만.
# CLAUDE_PROFILES="$HOME/.claude-profiles"
# CODEX_PROFILES="$HOME/.codex-profiles"

# 워크트리(Orca 등)에서 띄울 때 메인 체크아웃의 대화 기록 폴더를 함께 쓴다(기본 켬). 끄려면 0.
# CCP_LINK_WORKTREES=0

# 계정을 고른 뒤 이 폴더의 대화 목록을 보이고 골라서 가져오기(복사본). 0 = 끄기(늘 새 대화), 기본은 1.
# CCP_PICK_SESSION=0
# 목록에 보일 대화 수(기본 8)
# CCP_PICK_N=12
