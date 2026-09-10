<p align="right"><b>한국어</b> · <a href="README.en.md">English</a> · <a href="README.ja.md">日本語</a> · <a href="README.zh-CN.md">中文</a></p>

# ccp

**Claude Code 계정을 여러 개 쓰는 사람을 위한 전환기.**
로그아웃·로그인 없이 계정을 바꾸고, 어느 계정에 한도가 얼마나 남았는지 한 화면에서 봅니다.
Codex CLI 계정도 같이 보입니다.

```
  Claude
  ── 지금 쓸 수 있음 ──────────────────────────────────
  ▸ 2) team       ← 추천 · 주간 62% 남음 · 리셋 2일 뒤
    0) 기본       주간 85% 남음 · 리셋 5일 뒤
  ── 지금 못 씀 · 세션만 차면 풀린다 ───────────────────
    1) personal   ⏳ 세션 소진 — 2시간12분 뒤 풀림
```

## 이런 분께

- 회사 계정과 개인 계정을 번갈아 쓴다
- 한 계정 한도가 차면 다른 계정으로 옮겨서 **하던 대화를 이어가고** 싶다
- 매번 `/logout` `/login` 하기 귀찮다

## 설치 (3분)

필요한 것: Mac 또는 Linux, zsh, python3, [Claude Code](https://docs.anthropic.com/claude-code)가 깔려 있을 것.

```bash
git clone https://github.com/ssimu/ccp.git ~/projects/ccp
~/projects/ccp/install.sh
source ~/.zshrc
```

끝나면 세 가지만 하면 됩니다.

**1. 내 계정 적기** — `~/.config/ccp/profiles.tsv` 를 열어 한 줄에 계정 하나씩. 칸은 **탭**으로 구분합니다.

```
# 도구     이름        별칭   설명
claude     team        cct    회사 계정
claude     personal    ccm    개인 계정
```

- 이름: 내가 알아볼 이름 (영문 권장)
- 별칭: 짧은 명령. `cct` 라고 치면 그 계정으로 바로 켜집니다. 비워도 됩니다.
- 이미 있는 `~/.claude` 계정은 적지 않습니다. 항상 0번 "기본"으로 뜹니다.

**2. 디렉터리 만들기**

```bash
ccp-sync
```

**3. 계정마다 한 번 로그인**

```bash
ccp            # 메뉴에서 계정 선택 → 열리면 /login
```

이제부터는 `ccp` 로 고르거나 `cct` 처럼 별칭으로 바로 켭니다.

## 매일 쓰는 명령

| 명령 | 뜻 |
|---|---|
| `ccp` | 메뉴. 방향키로 고르고 Enter. **Enter 만 치면 추천 계정**으로 켜짐 |
| `ccp team` / `cct` | 이름 또는 별칭으로 바로 |
| `ccp team -c` | 그 계정으로 **직전 대화 이어가기** (뒤의 옵션은 claude 에 그대로 전달) |
| `ccp-usage` | 메뉴 없이 남은 한도만 보기 |
| `ccp-ls` | 계정마다 누가 로그인돼 있는지 |
| `ccp-new 이름 별칭` | 계정 추가 (TSV 에도 자동 기록) |

메뉴 키: `↑↓` 또는 `j` `k` 이동 · 숫자 = 그 번호 · `v` 그래프↔표 · `q` 취소

## 자주 묻는 것

**계정을 바꾸면 대화 기록이 사라지나요?**
아니요. 대화 기록·설정·스킬은 모든 계정이 공유합니다. 로그인만 다릅니다. 그래서 한도가 차면 다른 계정으로 `ccp team -c` 해서 이어갈 수 있습니다.

**계정을 늘리거나 줄이려면?**
`profiles.tsv` 에 줄을 넣거나 빼고 `ccp-sync`. 줄을 뺀 뒤 디렉터리까지 지우려면 `rm -rf ~/.claude-profiles/이름`.

**항상 `--dangerously-skip-permissions` 로 켜고 싶어요.**
`~/.config/ccp/config.zsh` 에서 이 줄의 주석을 풉니다. 뜻을 알고 켜세요.
```zsh
CCP_CLAUDE_ARGS=(--dangerously-skip-permissions)
```

**Codex 도 쓰는데요.**
`codex` 명령이 있으면 메뉴에 자동으로 함께 뜹니다. `profiles.tsv` 에 `codex	work	cxw	회사` 처럼 도구 칸을 `codex` 로 적으면 Codex 계정도 여러 개 쓸 수 있습니다.

**메뉴가 뜨는 데 몇 초 걸려요.**
계정마다 남은 한도를 물어보는 시간입니다 (계정당 3초 정도, 병렬). 모델을 부르지 않아 토큰은 들지 않습니다.

**Claude Code 화면 아래에 지금 어느 계정인지, 한도가 얼마 남았는지 보고 싶어요.**
설치하면 기본으로 켜집니다. 상태줄 맨 앞에 이렇게 뜹니다.
```
team:me@example.com │ 주간 ██░░░ 38% ↻2일3시간 │ 세션 █░░░░ 12% ↻1시간40분 │ Opus │ ~/proj │ ctx 12% │ git main
```
한도는 Claude Code 가 직접 넘겨주는 값이라 추가 비용이 없습니다. 70% 노랑, 90% 빨강으로 색이 바뀝니다.
원래 쓰던 상태줄을 지키려면 `install.sh --no-statusline` 으로 설치하세요.

**MCP 서버가 새 계정에서 안 보여요.**
MCP 설정은 계정마다 따로 있습니다. 그 계정으로 켠 상태에서 다시 `claude mcp add --scope user …` 하세요.

## 더 알아보기

- [동작 원리와 주의사항](docs/how-it-works.md) — 무엇을 공유하고 무엇을 분리하는지, 고칠 때 건드리면 안 되는 것
- 제거: `~/.zshrc` 에서 ccp 줄 삭제 후 `rm -rf ~/projects/ccp ~/.config/ccp ~/.claude-profiles ~/.codex-profiles`
- 테스트: `zsh tests/test_ccp_zsh.sh` · `python3 -m pytest tests`

MIT License
