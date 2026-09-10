<p align="right"><b>한국어</b> · <a href="README.en.md">English</a> · <a href="README.ja.md">日本語</a> · <a href="README.zh-CN.md">中文</a></p>

# ccp

Claude Code 계정을 여러 개 쓸 때, 로그아웃·로그인 없이 계정을 바꾸는 zsh 도구입니다.

한도가 찬 계정에서 다른 계정으로 옮겨도 **대화 기록·설정·스킬은 그대로 이어지고**,
어느 계정에 얼마나 남았는지 한 화면에서 확인할 수 있습니다. Codex CLI 계정도 같은 메뉴에 나옵니다.

```
  Claude
  ── 지금 쓸 수 있음 ──────────────────────────────────
  ▸ 2) team       ← 추천 · 주간 62% 남음 · 리셋 2일 뒤
    0) 기본       주간 85% 남음 · 리셋 5일 뒤
  ── 지금 못 씀 · 세션만 차면 풀린다 ───────────────────
    1) personal   ⏳ 세션 소진 — 2시간12분 뒤 풀림
```

`ccp`를 치면 이 화면이 뜨고, Enter만 치면 지금 가장 여유 있는 계정으로 켜집니다.

## 시작하기

필요한 것: Mac 또는 Linux, zsh(Mac은 기본), python3(Mac에 포함), 그리고 이미 설치된 Claude Code.

터미널에 이 세 줄을 붙여 넣으세요.

```bash
git clone https://github.com/ssimu/ccp.git ~/projects/ccp
~/projects/ccp/install.sh
source ~/.zshrc
```

설치 스크립트가 하는 일은 `~/.zshrc`에 한 줄 추가하고 설정 파일을 만드는 것뿐이라 몇 번 돌려도 안전합니다.
로그인 토큰은 어디에도 복사하지 않습니다. 로그인은 아래 3단계에서 직접 합니다.

### 1. 내 계정 적기

`~/.config/ccp/profiles.tsv`를 열면 예시가 들어 있습니다. 내 계정으로 바꿉니다.
한 줄이 계정 하나고, 칸은 **탭**으로 나눕니다.

```
# 도구     이름        별칭   설명
claude     team        cct    회사 계정
claude     personal    ccm    개인 계정
```

- **이름**: 프로필 디렉터리 이름이 됩니다. 영문 권장.
- **별칭**: 짧은 명령. `cct`라고 치면 그 계정으로 바로 켜집니다. 비워도 됩니다.
- 지금 쓰는 `~/.claude` 계정은 적지 않습니다. 항상 0번 "기본"으로 나옵니다.

계정 수는 줄 수로 정해집니다.

### 2. 만들기

```bash
ccp-sync
```

TSV에 적은 대로 프로필 디렉터리를 만듭니다.

### 3. 계정마다 한 번씩 로그인

```bash
ccp
```

메뉴에서 계정을 고르면 Claude Code가 그 계정으로 열립니다. 처음에는 로그인이 안 되어 있다고 나오므로
거기서 `/login` 합니다. 계정 수만큼 반복하면 설정이 끝납니다.

## 사용법

| 이렇게 치면 | 이렇게 됩니다 |
|---|---|
| `ccp` | 메뉴가 뜹니다. 방향키로 고르고 Enter. **그냥 Enter면 추천 계정** |
| `ccp team` 또는 `cct` | 그 계정으로 바로 |
| `ccp team -c` | 그 계정으로 **직전 대화를 이어서**. 한도 차서 옮길 때 이걸 씁니다 |
| `ccp-usage` | 메뉴 없이 남은 한도만 확인 |
| `ccp-ls` | 계정마다 누가 로그인돼 있는지 |
| `ccp-new 이름 별칭` | 계정 하나 더 |

메뉴에서는 `↑↓`(또는 `j` `k`)로 움직이고, 숫자를 누르면 그 번호로 가고, `v`를 누르면 그래프와 표가 바뀌고, `q`로 나옵니다.

Claude Code 하단 상태줄에는 현재 계정과 남은 한도가 항상 표시됩니다.

```
team:me@example.com │ 주간 ██░░░ 38% ↻2일3시간 │ 세션 █░░░░ 12% ↻1시간40분 │ Opus │ ~/proj │ ctx 12% │ git main
```

70%부터 노랑, 90%부터 빨강으로 바뀝니다.

## 자주 묻는 질문

**계정을 바꾸면 지금까지 대화가 날아가나요?**
아닙니다. 대화 기록·설정·스킬은 모든 계정이 공유하고 로그인만 다릅니다.
한도가 차면 다른 계정으로 `ccp team -c` 해서 바로 이어갈 수 있습니다. 이 도구의 핵심 용도입니다.

**계정을 늘리거나 줄이고 싶어요.**
`profiles.tsv`에서 줄을 넣거나 빼고 `ccp-sync`. 뺀 계정의 폴더까지 정리하려면 `rm -rf ~/.claude-profiles/이름`.
그 계정의 로그인만 지워지고 대화 기록은 남습니다.

**항상 `--dangerously-skip-permissions`로 켜고 싶습니다.**
`~/.config/ccp/config.zsh`에서 이 줄의 주석을 풉니다. 무엇을 끄는 옵션인지 알고 켜세요.
```zsh
CCP_CLAUDE_ARGS=(--dangerously-skip-permissions)
```

**Codex도 씁니다.**
`codex` 명령이 있으면 메뉴에 자동으로 함께 나옵니다. Codex 계정을 여러 개 두려면
`profiles.tsv`의 도구 칸을 `codex`로 적습니다. 예: `codex	work	cxw	회사 워크스페이스`

**메뉴가 뜨는 데 몇 초 걸립니다.**
계정마다 남은 한도를 조회하는 시간입니다. 계정당 3초 정도이고 병렬로 돌아 전체도 그 정도입니다.
모델을 호출하지 않으므로 토큰은 들지 않습니다.

**메뉴 언어를 바꾸고 싶습니다.**
메뉴·메시지·상태줄은 한국어, English, 日本語, 中文을 지원합니다. 기본은 터미널 로케일(`LANG`)을 따르고,
`~/.config/ccp/config.zsh`에 `CCP_LANG=en`처럼 적으면 고정됩니다. 한 번만 바꿔 보려면 `CCP_LANG=en ccp`.

**상태줄 모양을 바꾸고 싶습니다.**
`~/.config/ccp/statusline.conf`에서 정합니다. 보일 조각과 순서, 구분자, 막대 폭과 글자, 사용률/남은 비율, 색 기준, 계정 표시 형식을 바꿀 수 있습니다.
고치면서 `ccp-statusline`으로 바로 미리 봅니다. 몇 가지 예:
```
segments = account weekly session      # 모델·디렉터리·git 없이 한도만
bar = 0                                # 막대 없이 숫자만
percent = left                         # 남은 비율로
account = "{profile}"                  # 이메일 숨기기
format = "{account} · {weekly} · {session} ▏{dir}"   # 순서 대신 틀을 직접
```
아예 다른 상태줄을 쓰려면 `~/.config/ccp/statusline.sh`를 만들면 그것이 대신 실행됩니다.

**원래 쓰던 상태줄이 있습니다.**
`install.sh --no-statusline`으로 설치하면 상태줄은 건드리지 않습니다.

**새 계정에서 MCP 서버가 안 보입니다.**
MCP 설정은 계정(`.claude.json`)마다 따로 있습니다. 그 계정으로 켠 상태에서 `claude mcp add --scope user …`를 다시 합니다.

## 문제가 생기면

- `ccp` 명령이 없다 → 새 터미널을 열거나 `source ~/.zshrc`
- 메뉴에 내 계정이 없다 → `ccp-sync`를 아직 안 돌렸습니다
- "미로그인"으로 나온다 → `ccp 이름`으로 열고 `/login`
- 별칭이 안 된다 → `cp`처럼 기존 명령과 겹치는 이름입니다. 터미널을 열 때 경고가 뜹니다. 다른 이름으로 바꾸세요
- 그래도 안 되면 → 이슈에 실행한 명령과 출력을 함께 남겨 주세요

## 더 보기

- [동작 원리와 건드리면 안 되는 것](docs/how-it-works.md) — 무엇을 공유하고 무엇을 분리하는지
- 제거: `~/.zshrc`에서 ccp 줄을 지우고 `rm -rf ~/projects/ccp ~/.config/ccp ~/.claude-profiles ~/.codex-profiles`. `~/.claude`는 그대로 남습니다.
- 테스트: `zsh tests/test_ccp_zsh.sh` · `python3 -m pytest tests`

MIT License
