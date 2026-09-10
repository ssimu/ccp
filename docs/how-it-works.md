# ccp 동작 원리와 주의사항

**한국어** · [English](how-it-works.en.md)

> 쉬운 설치·사용법은 [README](../README.md). 이 문서는 무엇을 공유하고 무엇을 분리하는지, 고칠 때 건드리면 안 되는 것을 적는다.

구독 계정이 여러 개일 때 로그아웃·로그인 없이 계정을 오가는 zsh 도구.
메뉴 한 화면에 계정별 **남은 한도·리셋 시각**을 보여주고, 지금 쓸 계정을 추천한다.

```
  Claude
  ── 지금 쓸 수 있음 ──────────────────────────────────────────
  ▸ 2) team          ← 추천 · 주간 62% 남음 · 리셋 2일3시간 뒤
        주간 ███████░░░░░░░░░░░░░  38%   9/12(토) 14:00 리셋 · 2일3시간 남음
        세션 ██░░░░░░░░░░░░░░░░░░  12%   오늘 18:10 리셋 · 1시간40분 남음
    0) 기본          주간 85% 남음 · 리셋 5일 뒤
  ── 지금 못 씀 · 세션만 차면 풀린다 ───────────────────────────
    1) personal      ⏳ 세션 소진 — 2시간12분 뒤 풀림
  Codex
  ── 지금 쓸 수 있음 ──────────────────────────────────────────
  ▸ 3) 기본          ← 추천 · 주간 71% 남음 · 리셋 4일 뒤 · plus
```

- 계정 수와 이름은 각자 정한다 (`~/.config/ccp/profiles.tsv` 한 줄 = 프로필 하나)
- 계정을 바꿔도 **대화 기록·설정·스킬은 공유**된다 — 한도가 차서 옮겨도 `-c` 로 하던 대화를 잇는다
- Codex CLI 가 있으면 같은 메뉴에 함께 뜬다 (없으면 안 뜬다)

## 설치

필요한 것: macOS 또는 Linux, zsh, python3 (3.9+), [Claude Code CLI](https://docs.anthropic.com/claude-code). Codex CLI 는 선택.

```bash
git clone https://github.com/ssimu/ccp.git ~/projects/ccp
~/projects/ccp/install.sh              # 상태줄에 현재 계정도 띄우려면: install.sh --statusline
source ~/.zshrc
```

그다음 사람이 할 일 세 가지:

```bash
$EDITOR ~/.config/ccp/profiles.tsv     # 1. 계정 이름·별칭을 내 것으로
ccp-sync                               # 2. 고친 대로 프로필 디렉터리 생성
ccp                                    # 3. 메뉴에서 프로필 골라 → /login  (프로필마다 한 번)
```

`install.sh` 는 몇 번 돌려도 안전하다. 하는 일은 `~/.zshrc` 에 source 한 줄, `~/.config/ccp` 에 예시 설정 복사,
프로필 디렉터리 생성. **로그인 토큰은 어디에도 복사하지 않는다** — 프로필마다 직접 `/login` 한다.

## 설정: 계정 수·이름 정하기

`~/.config/ccp/profiles.tsv` — 탭으로 구분한 네 칸. 원하는 만큼 줄을 넣고 뺀다.

```
# 도구     이름        별칭   설명
claude     team        cct    팀 계정
claude     personal    ccm    개인 계정
codex      work        cxw    Codex 회사 워크스페이스
```

| 칸 | 뜻 |
|---|---|
| 도구 | `claude` 또는 `codex` |
| 이름 | 프로필 디렉터리 이름. 메뉴와 `ccp <이름>` 에 쓴다 |
| 별칭 | 비워도 된다. 있으면 `alias cct="ccp claude:team"` 이 정의된다. `cp` `cd` 처럼 이미 있는 명령은 거부한다 |
| 설명 | 메모. 아무 데도 안 쓴다 |

기본 프로필(`~/.claude`, `~/.codex`)은 적지 않는다. 항상 메뉴 0번에 있다.

TSV 를 고쳤으면 `ccp-sync` — TSV 에 있는데 없는 디렉터리만 만든다. 줄을 지웠을 때 디렉터리까지 지우려면
`rm -rf ~/.claude-profiles/<이름>` (그 프로필의 로그인만 사라진다. 대화 기록은 공유라 남는다).

`~/.config/ccp/config.zsh` — 실행 옵션. 주로 하나다:

```zsh
# claude 를 띄울 때 항상 붙일 인자. 기본은 없음.
CCP_CLAUDE_ARGS=(--dangerously-skip-permissions)
```

## 명령

```
ccp                 메뉴. ↑↓/j k 이동 · 숫자 = 그 번호 · Enter 실행 · v 그래프↔표 · Esc/q 취소
                    엔터만 치면 추천 계정으로 바로 실행
ccp 2               번호로 바로
ccp team            이름으로 (Tab 완성). 양쪽 도구에 같은 이름이 있으면 claude:team / codex:team
ccp team -c         뒤의 인자는 그대로 claude 에 전달 (-c 이어가기, -r <id> 특정 세션 …)
cct                 profiles.tsv 의 별칭 = ccp claude:team

ccp-ls              프로필마다 로그인한 계정·조직
ccp-usage           사용량만 (메뉴 없이)
ccp-new <이름> [별칭] [설명]          claude 프로필 추가 + TSV 기록
ccp-new --codex <이름> [별칭] [설명]  codex 프로필 추가 + TSV 기록
ccp-sync            TSV 대로 빠진 디렉터리 생성
```

`which ccp` 는 못 찾는다(셸 함수). `whence -w ccp`.

메뉴는 프로필마다 `claude -p /usage` 를 병렬로 불러 한도를 읽는다(프로필당 3초 남짓, 모델 호출 아님).
Codex 는 `codex app-server` 의 JSON-RPC 로 읽는다(1초, 토큰 0).

## 동작 원리 (고치기 전에 읽을 것)

**Claude** — `CLAUDE_CONFIG_DIR` 은 인증까지 분리한다. 프로필은 `~/.claude-profiles/<이름>/` 이고
그 안에서 `.claude.json`(인증·MCP) 만 따로 두고 나머지는 `~/.claude` 로 심링크한다.

| | 무엇 |
|---|---|
| 분리 | `.claude.json` |
| 공유(심링크) | `settings.json` `skills` `plugins` `commands` **`projects`(대화 기록)** |

- ⚠ **`.claude.json` 은 절대 심링크하지 말 것.** 인증과 MCP 가 한 파일이라 링크하면 두 프로필이 같은 계정을 본다.
- ⚠ **`projects` 는 반드시 공유할 것.** 한도가 차서 계정을 바꾸는 순간 `-c` 로 대화를 이어가는 게 전환의 핵심이다.
- ⚠ 프로필 세션 안에서는 `CLAUDE_CONFIG_DIR` 이 환경에 남아 자식 프로세스가 물려받는다. ccp 는 "기본"을 고르면
  서브셸에서 `unset` 하고 띄운다.
- MCP 서버는 `.claude.json` 에 들어 있어 **프로필마다 따로** 등록·인증해야 한다 (`claude mcp add --scope user …`).

**Codex** — `CODEX_HOME` 을 프로필마다 둔다. codex 는 `auth.json` 에 계정을 하나만 들고 있어 이 방법밖에 없다.
`auth.json` 과 세션·상태 파일만 분리하고 `config.toml` `skills` `plugins` `prompts` `rules` `AGENTS.md` 는 `~/.codex` 로 심링크한다.
같은 ChatGPT 로그인이라도 워크스페이스가 다르면 각각 `CODEX_HOME=<디렉터리> codex login` 하고 브라우저에서 워크스페이스를 고른다.

- ⚠ codex 가 `config.toml` 을 통째로 다시 쓰면 심링크가 실파일로 바뀌어 공유가 조용히 끊긴다. 설정이 한쪽에만 반영되면 그 링크부터 확인.

## 상태줄 (선택)

`install.sh` 는(`--no-statusline` 이 아니면) `statusline.sh` 를 `~/.claude/statusline-command.sh` 로 링크하고 `~/.claude/settings.json` 의
`statusLine` 을 그쪽으로 잡는다. Claude Code 하단에
`team:me@example.com │ Opus │ 주간 ██░░░ 38% ↻2일3시간 │ 세션 █░░░░ 12% ↻1시간40분 │ Fable ██░░░ 47% ↻2일3시간 │ ~/proj │ ctx 12% │ git main` 처럼 뜬다.
어느 계정으로 대화 중인지, 한도가 얼마 남았는지 늘 보여야 하기 때문이다.
`주간` 은 7일 창, `세션` 은 5시간 창의 사용률·막대·`↻` 리셋까지 남은 시간이다. 수치는 Claude Code 가 상태줄 명령의 stdin JSON 으로 넘겨주는
`rate_limits`(Pro/Max 구독, 첫 응답 뒤부터)에서 읽으므로 따로 조회하지 않고 토큰도 들지 않는다.
색은 70% 노랑, 90% 빨강, 100% 굵은 빨강 — ccp 메뉴와 같은 기준. 계정 이메일은 프로필의 `.claude.json` 에서 읽는다.
python3 만 있으면 된다(jq 불필요). 이미 다른 statusline 을 쓰고 있으면 이전 값을 출력하고 덮는다.

## 파일

```
ccp.zsh                본체 — 메뉴·전환·ccp-new·ccp-sync·별칭·Tab 완성
ccp_i18n.py            표시 문구 사전(ko/en/ja/zh). ccp_i18n.zsh 는 여기서 생성 — 손으로 고치지 않는다
ccp_render.py          메뉴 렌더러 — 카드/표, 추천 계산, 대화형 키 입력
ccp_codex.py           codex 사용량 (app-server JSON-RPC → TSV)
statusline.sh          Claude Code 상태줄 진입점 → ccp_statusline.py (statusline.conf 로 조각·막대·색·형식을 정한다)
install.sh             설치 (멱등)
profiles.example.tsv   설정 예시 → ~/.config/ccp/profiles.tsv
config.example.zsh     설정 예시 → ~/.config/ccp/config.zsh
tests/                 zsh tests/test_ccp_zsh.sh · python3 -m pytest tests
```

사용자 상태는 전부 저장소 밖에 있다: `~/.config/ccp/` (설정·메뉴 보기 상태), `~/.claude-profiles/`, `~/.codex-profiles/`.

## 제거

```bash
# ~/.zshrc 에서 ccp.zsh source 줄 삭제
rm -rf ~/projects/ccp ~/.config/ccp
rm -rf ~/.claude-profiles ~/.codex-profiles     # 프로필 로그인만 사라진다. ~/.claude 는 그대로.
```

## 테스트

```bash
zsh tests/test_ccp_zsh.sh        # 가짜 HOME·가짜 claude/codex 로 — 실제 계정을 건드리지 않는다
python3 -m pytest tests          # codex 사용량 파서
```
