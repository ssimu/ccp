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
```

- 작업 폴더는 `allowed_cwd`(기본 `~/fleet-work`, `~/projects`) 안이어야 한다 — 투입된 작업은 권한 확인 없이 돌기 때문이다. 커밋·push·발송은 작업문이 명시할 때만.
- 작업문 끝에 "결과 요약을 결과 파일에 써라" 지시가 자동으로 붙는다. 그 파일이 생기면 완료로 본다(상태 보고가 없는 옛 claude 도 잡힌다).
- 첫 실행 대화상자(폴더 신뢰 · 테마 · 권한 수락 · 전체화면 홍보)는 `fleet-jobs` 가 알아서 넘긴다. 모르는 대화상자는 `대화상자에 멈춤` 으로 알리고 사람에게 넘긴다.
- `hc run` 의 `--cwd` 와 `hc file write` 는 `~` 를 풀지 않는다 — 절대 경로로 넘긴다(네 Mac 모두 홈이 같다는 가정).
- 한 문자열 명령은 `--no-parent` 와 함께일 때 프로그램 이름으로 취급돼 `spawn_failed` 가 난다 → argv 로 나눠 넘긴다.
- SSH 맥락에서 `hc wait` 가 `--timeout` 을 넘겨 안 돌아올 때가 있어 subprocess 시간제한 + 폴링으로 보완한다.
