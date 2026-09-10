# ccp 팀 공유용 분리 — 설계

날짜: 2026-09-10

## 목적

개인 저장소(claude_code_skills) 안에 흩어져 있던 Claude Code / Codex 계정 프로필
전환기 `ccp` 를 독립 저장소로 떼어내 팀원이 clone 한 줄로 쓸 수 있게 한다.
개인정보(이메일·계정명)는 저장소에서 빼고, 계정 수와 이름은 각자 로컬 설정으로 정한다.

## 범위

옮기는 것: `ccp.zsh`(본체) · `ccp_render.py`(메뉴 렌더러) · `ccp_codex.py`(codex 사용량) ·
`statusline.sh`(선택) · `tests/`.

옮기지 않는 것: 스킬, API 키 관리(skills-env), MCP 등록, `alias cc`. 기존 저장소에 남는다.

## 구조

```
~/projects/ccp/                    저장소 (코드만, 개인 설정 없음)
  ccp.zsh  ccp_render.py  ccp_codex.py  statusline.sh
  install.sh  profiles.example.tsv  config.example.zsh
  tests/  README.md

~/.config/ccp/                     사용자 로컬 (저장소에 없음)
  profiles.tsv     도구<TAB>이름<TAB>별칭<TAB>설명   — 계정 수·이름은 여기서 정한다
  config.zsh       CCP_CLAUDE_ARGS 등 실행 옵션
  view             메뉴 보기 상태(graph/table)

~/.claude-profiles/<이름>/         claude 프로필 (CLAUDE_CONFIG_DIR)
~/.codex-profiles/<이름>/          codex 프로필 (CODEX_HOME)
```

## 동작

- **프로필의 진실은 디렉터리다.** 메뉴는 `~/.claude-profiles/*`, `~/.codex-profiles/*` 를 나열한다.
  TSV 는 (1) 디렉터리를 만들 때 (2) 별칭을 정의할 때 쓴다.
- `ccp-sync` — TSV 에 있는데 디렉터리가 없는 프로필을 만든다. TSV 를 고친 뒤 부른다. install.sh 도 이걸 부른다.
- `ccp-new [--codex] <이름>` — 디렉터리를 만들고 TSV 에 줄을 덧붙인다(없을 때만).
- `--dangerously-skip-permissions` 는 코드에서 빼고 `CCP_CLAUDE_ARGS` 배열로 옮긴다. 기본은 빈 배열.
- 렌더러의 보기 상태 파일은 `~/.claude-profiles/.ccp-view` 에서 `$CCP_CONFIG_DIR/view` 로 옮긴다.

## install.sh (멱등)

1. `~/.zshrc` 에 `source <clone경로>/ccp.zsh` 한 줄 (이미 있으면 건너뜀)
2. `~/.config/ccp/{profiles.tsv,config.zsh}` 를 예시에서 복사 (있으면 그대로 둠)
3. `ccp-sync` 로 TSV 의 프로필 디렉터리 생성
4. `--statusline` 을 주면 `~/.claude/statusline-command.sh` 링크 + settings.json 의 `statusLine` 설정

## 기존 저장소(claude_code_skills) 변경

- `shell/claude-profiles.zsh` `ccp_render.py` `ccp_codex.py` `statusline-command.sh` `tests/test_ccp_codex.py` `config/profiles.tsv` 삭제
- `init.zsh`: ccp source·별칭 루프 제거 (`alias cc` 는 유지)
- `setup.sh`: 5단계를 "ccp 저장소 clone/pull + install.sh --statusline" 으로 교체. statusline 링크 단계 제거.
- 문서의 ccp 설명은 새 저장소 링크로 대체

## 테스트

- `tests/test_ccp_codex.py` — 기존 그대로 (경로만 조정)
- `tests/test_ccp_zsh.sh` — 가짜 HOME 에서 zsh 로: TSV 별칭 정의, `ccp-sync` 디렉터리·심링크 생성,
  `ccp-new` 의 TSV 추가, 가짜 `claude`/`codex` 실행파일로 `ccp <이름>` 이 올바른 환경변수·인자로 부르는지
