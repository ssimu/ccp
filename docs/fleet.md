# 함대 — 여러 Mac 의 Claude Code 를 한 곳에서 (fleet/)

여러 Mac 에 ccp 를 깔아 두고, 한 대(관문)에서 나머지에 작업을 던지고 결과를 거두는 구성이다.
전송은 [Herdr](https://herdr.dev) 의 `hc`(herdr-core) 가 맡는다 — 각 Mac 의 **데스크톱 세션에서 뜬 core** 의 터미널에서
`ccp <프로필>` 로 Claude Code 를 띄우므로 키체인이 열려 있어 로그인이 끊기지 않는다(SSH 로 `claude` 를 띄우면 끊긴다, docs/recovery.md).

```
Telegram ──► Hermes(서버) ──ssh/Tailscale──► 관문 Mac: fleet-jobs ──hc run --on <m>──► 각 Mac: fleet-job-run → ccp <프로필> → claude
                                                   ▲                                              │
                                                   └──── 결과 파일(~/.local/share/fleet-jobs/<id>.result.md) ◄──┘
```

| 파일 | 어디에 | 하는 일 |
|---|---|---|
| `fleet-job-run` | **모든 Mac** `~/.local/bin` | 작업 하나를 이 Mac 에서 돌린다: 신뢰·온보딩 대화상자를 프로필 `.claude.json` 에 미리 적고 `ccp <프로필> --dangerously-skip-permissions "<작업문>"` |
| `ccp-worker` | **모든 Mac** `~/.local/bin` | hc 템플릿용 실행기: 지금 폴더에서 `ccp <프로필>` 을 대화형으로 띄운다. 허용 폴더(`~/fleet-work`, `~/projects`, `CCP_WORKER_ALLOWED`) 밖이면 거부, 신뢰·온보딩 대화상자는 미리 적는다. 작업문은 hc 가 첫 메시지로 넣는다 — 예: 템플릿 `command: ccp-worker dranswer` 후 `hc run --on <m> --bg --cwd ~/projects/x worker "<작업>"` |
| `fleet-jobs` | 관문 | 투입(`dispatch`)·목록·`wait`·`result`·`send`·`stop`·`unreported`(끝난 작업 알림용)·`clean`·`machines` |
| `fleet-dispatch` | 관문 | `fleet-jobs dispatch` 의 짧은 이름 |
| `fleet-dispatch.example.json` | → `~/.config/ccp/fleet-dispatch.json` | 머신별 기본 프로필·작업 폴더 |
| `ccp-fleet-status` | 관문(어느 Mac 이든) | 네 Mac 의 `ccp-recover status` 를 hc 터미널로 모아 보인다 (`--json`) |
| `fleet-net-check` | 모든 Mac(관문은 `--all`) | 나가는 연결이 되는지, TIME_WAIT 개수, macOS 26 이상이면 부팅 일수를 본다. `fleet-report` 가 `net` 으로 싣고 Hermes 경보가 알린다 — 아래 "macOS 26: 49.7일마다 재부팅" |
| `fleet-report` | 관문 | SSH 로 들어온 맥락에서도 안전하게 상태+한도를 JSON 으로 — Hermes 의 아침 보고·경보가 읽는다 |
| `ccp-relogin` | 모든 Mac | `~/.config/ccp/fleet.json`(프로필↔이메일↔조직) 을 읽어 `ccp-recover login` 을 부른다. 비밀값은 화면에 안 찍는다 |
| `hermes/` | Hermes 서버 `~/.hermes/scripts`, `~/.hermes/skills/devops/fleet-dispatch/` | `fleet.sh`(인자 안전 전달), `fleet_report.sh`, `fleet_alert.py`, `fleet_jobs_notify.sh`, 스킬 `SKILL.md` |

## 설치

1. 모든 Mac: `install.sh` 가 `fleet/` 의 명령을 `~/.local/bin` 에 링크한다. Herdr core 는 데스크톱 세션에서 띄운다
   (`~/Library/LaunchAgents/dev.herdr.core.plist`, gui 도메인). 관문에서 `hc machine add <ssh별칭> --name <이름>`.
2. 관문: `cp fleet/fleet-dispatch.example.json ~/.config/ccp/fleet-dispatch.json` 후 머신 이름·기본 프로필을 맞춘다. `fleet-jobs machines` 로 확인.
3. Hermes(선택): `hermes/` 를 올리고 cron 둘 — 매일 아침 보고(`--script fleet_report.sh`, 에이전트 요약), 6시간마다 경보(`fleet_alert.py --no-agent`),
   5분마다 완료 알림(`fleet_jobs_notify.sh --no-agent`). 스킬이 Telegram 의 "맥미니에서 ~ 해줘" 를 `fleet.sh dispatch` 로 옮긴다.

## 쓰기

```sh
fleet-dispatch --on macmini --name fix-x --cwd '~/projects/x' "테스트가 깨진 원인을 찾아 고쳐라. 커밋은 하지 마라."
fleet-jobs wait j261106-093752 --timeout 150     # 끝나면 결과 요약까지. 아니면 '아직 끝나지 않음'
fleet-jobs send j261106-093752 "그 수정에 테스트도 추가해"
fleet-jobs list · status <id> · result <id> · stop <id> · clean
fleet-jobs projects                                         # ~/.config/ccp/fleet-projects.json (예시: fleet/fleet-projects.example.json)
fleet-dispatch --project demo "…"                           # 등록부가 기계·폴더·프로필을 채운다(명시한 인자가 이긴다)
fleet-dispatch --project demo --agent codex "[리뷰] git diff 를 읽고 문제만 적어라"   # Codex 작업자, [리뷰] 는 읽기 전용
```

- **Codex 작업자**: `codex exec -o <결과파일>` 로 돈다. 마지막 답이 결과가 되고, 끝나면 프로세스가 나간다(그래서 `send` 는 안 된다).
  CODEX_HOME 은 등록부의 `codex_profile`(기본 `~/.codex`). brew 판 codex 를 먼저 쓴다 — 옛 단독 실행 파일은 셸 도구가 없다.
- **계정 자동 선택**: `profile`·`codex_profile` 이 `auto`(기본)면 투입 순간 대상 Mac 에서 `fleet-pick` 이 그 Mac 의 로그인된 계정 중
  **여유가 가장 큰 것**을 고른다 — 주간 전체와 모델 전용 주간 한도(Fable 등) 중 빠듯한 쪽으로 견준다(`exclude_profiles` 제외,
  주간이나 모델 한도가 `max_weekly_pct`(기본 95, 남은 양 5% 이하) 이상·5시간 창 95% 이상은 건너뜀. 모든 계정의 모델 한도가 바닥이면
  주간으로 고르고 결과에 적는다). 고를 게 없으면
  머신의 `fallback_profile`. `--profile`/등록부로 지정한 계정이 늘 이긴다. 고른 결과는 작업 줄에 `(자동 · 주간 39%)` 로 남는다.
- **결정 필요**: 결과 파일이 `질문:` 으로 시작하면 상태가 `question`. `send` 로 답하면 지난 결과는 `<id>.result.md.prev` 로 치워진다.
- 사람에게 올릴 것과 스스로 답할 것의 구분은 각자 운영 규칙에 둔다(저장소에는 넣지 않는다).

- 작업 폴더는 `allowed_cwd`(기본 `~/fleet-work`, `~/projects`) 안이어야 한다 — 투입된 작업은 권한 확인 없이 돌기 때문이다. 커밋·push·발송은 작업문이 명시할 때만.
- 작업문 끝에 "결과 요약을 결과 파일에 써라" 지시가 자동으로 붙는다. 그 파일이 생기면 완료로 본다(상태 보고가 없는 옛 claude 도 잡힌다).
- 첫 실행 대화상자(폴더 신뢰 · 테마 · 권한 수락 · 전체화면 홍보)는 `fleet-jobs` 가 알아서 넘긴다. 모르는 대화상자는 `대화상자에 멈춤` 으로 알리고 사람에게 넘긴다.
- `hc run` 의 `--cwd` 와 `hc file write` 는 `~` 를 풀지 않는다 — 절대 경로로 넘긴다(네 Mac 모두 홈이 같다는 가정).
- 한 문자열 명령은 `--no-parent` 와 함께일 때 프로그램 이름으로 취급돼 `spawn_failed` 가 난다 → argv 로 나눠 넘긴다.
- SSH 맥락에서 `hc wait` 가 `--timeout` 을 넘겨 안 돌아올 때가 있어 subprocess 시간제한 + 폴링으로 보완한다.

## macOS 26: 49.7일마다 재부팅

2026-11-11 macmini(macOS 26.3, 부팅 55일째)가 **나가는 연결만** 전부 실패했다(`connect: Can't assign requested address`).
들어오는 ssh·웹앱은 됐고 ping 도 됐으므로 겉으로는 Wi‑Fi 문제처럼 보였지만 Wi‑Fi 재시작으로는 안 나았다.
TIME_WAIT 35,483개가 1분 뒤에도 하나도 줄지 않았다 — 부팅 후 약 49.7일(2^32 ms)에 TCP 내부 시계가 넘쳐 TIME_WAIT 가
만료되지 않고 쌓여 임시 포트가 바닥나는 결함이다. 같은 날 macOS 15.7(wooui, 164일)·13.7(old-mbp)은 멀쩡했다.
관문이 이 상태가 되면 함대 투입·Codex 사용량 조회(`fleet-pick codex` 가 세 계정 모두 `fail` → 대체 `default`)도 같이 멈춘다.

- **고치는 법은 재부팅뿐.** FileVault 가 켜진 Mac 은 `sudo fdesetup authrestart`(암호 두 번) 로 다시 켜면 로그인 화면 없이 데스크톱까지 올라온다.
- **막는 법**: macOS 26 이상 Mac 은 42일 안에 한 번 재부팅한다. `fleet-net-check` 가 42일째부터, TIME_WAIT 1만 개 이상이거나
  나가는 연결이 안 되면 경고를 내고 Hermes 함대 경보(6시간마다)가 Telegram 으로 보낸다. 관문 자신이 막히면 Tailscale 도 끊겨 Hermes 의 SSH 가 못 들어온다 — 그때는 "관문 접속 실패" 경보가 이 결함일 수 있다는 안내와 함께 간다(2026-11-11 실측). 그래서 42일째 경고가 결함보다 먼저 오는 것이 핵심이다.

