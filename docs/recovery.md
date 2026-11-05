# 로그인이 끊겼을 때 — 원인과 복구

ccp 로 계정을 골라 들어갔는데 Claude Code 가 로그인을 요구하거나, 메뉴의 남은 한도가 `조회 실패`로만 나오는 일이 있다.
대개 토큰이 **키체인과 파일 두 곳에 갈라져** 생긴다. 이 문서는 그 원리와, 끊긴 계정을 다시 붙이는 절차다.

## 왜 끊기나

macOS 의 Claude Code 는 로그인 토큰을 **로그인 키체인**에 둔다(프로필마다 `Claude Code-credentials-<해시>` 항목).
키체인을 열 수 없는 맥락에서 돌면 대신 `<프로필 디렉터리>/.credentials.json` 파일로 토큰을 읽고 쓴다.

키체인이 닫힌 맥락은 흔하다.
- SSH 로 들어온 셸 (`security` 가 `User interaction is not allowed` 를 낸다)
- 데스크톱 세션 밖에서 띄운 launchd 작업, 그 아래의 터미널·에이전트
- 그런 셸에서 돌린 점검 스크립트, 사용량 조회(`claude -p /usage`), 자동화

거기서 토큰이 한 번 갱신되면 파일에는 새 refresh 토큰, 키체인에는 옛 것이 남는다.
다음에 어느 한쪽이 옛 토큰으로 갱신을 시도하면 서버가 그 토큰 묶음을 통째로 무효화하고, 멀쩡하던 데스크톱의 로그인까지 끊긴다.

그래서 ccp 는 **키체인이 잠긴 셸에서는 claude 를 띄우지 않는다**(메뉴에는 `키체인 잠김`으로 표시).
알고 하는 거면 `CCP_SKIP_KEYCHAIN_CHECK=1`.

## 다른 Mac 을 원격으로 쓸 때 (Herdr / hc)

원격 Mac 에서 ccp 로 Claude 를 띄우려면 그 Mac 의 터미널이 **데스크톱 세션 안에** 있어야 한다.
SSH 로 띄운 herdr-core 는 키체인이 잠겨 있다. core 를 그 Mac 의 GUI launchd 도메인에서 띄우면 열린다.

```sh
# 원격 Mac 에서 (한 번만). ~/Library/LaunchAgents/dev.herdr.core.plist 가 herdr-core server start 를 돌린다.
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/dev.herdr.core.plist
# 확인 — 그 Mac 의 hc 터미널 안에서:
security show-keychain-info ~/Library/Keychains/login.keychain-db     # "no-timeout" 이면 열린 것
```

이 Mac 에서 `hc machine add <ssh호스트> --name <이름>` 으로 붙인 뒤 `hc run --on <이름> zsh -lic 'ccp <계정>'` 처럼 띄운다
(`ccp` 는 zsh 함수라 로그인 셸이 필요하다).

## 상태 확인 — `ccp-recover status`

```sh
ccp-recover status              # 모든 프로필
ccp-recover status team         # 하나만
```

프로필마다 `state` 가 나온다.

| state | 뜻 | 할 일 |
|---|---|---|
| `local_oauth_present` | 로컬에 claude.ai 로그인이 있다 | 없음 (서버 쪽 유효성까지 보장하지는 않는다) |
| `oauth_unavailable` | 로그인이 없거나 API 키 방식 | 아래 복구 |
| `keychain_locked` | 키체인이 잠긴 셸에서 돌렸다 | 데스크톱 터미널(또는 데스크톱에서 띄운 core 의 hc 터미널)에서 다시 |
| `check_failed` | 시간 초과·파싱 오류 | 다시 시도. 로그아웃으로 보지 않는다 |

네트워크 오류·한도 소진은 로그아웃이 아니다. `local_oauth_present` 인데도 Claude 가 로그인을 요구하면 그때 복구한다.

## 복구 — `ccp-recover login`

대상 Mac 의 **데스크톱 세션 터미널**에서 (원격이면 데스크톱에서 띄운 core 의 hc 터미널):

```sh
ccp-recover login <프로필> --email <그 프로필의 이메일> --org-id <조직 ID> --manual-browser
```

1. 공식 Claude 인증 URL 이 출력된다. 그 URL 을 **사용자의 실제 브라우저**에서 연다.
2. 브라우저에 다른 계정이 로그인돼 있으면 계정을 바꾸고, 이메일과 조직이 맞는지 확인한 뒤 승인한다.
3. 화면에 나온 코드를 그 터미널에 붙여 넣는다.
4. 명령이 `identity_verified: true` 를 찍으면 끝. 이메일이나 조직이 다르면 복구로 치지 않는다(`false`, 종료코드 3).

`--org-id` 는 `claude auth status --json` 의 `orgId` 다. 프로필마다 이메일·조직을 적어 둔 표를 하나 두면 편하다
(이 저장소에는 넣지 말 것 — `~/.config/ccp/` 아래 개인 파일로).

토큰·코드를 문서나 설정에 적지 않는다. 기기 사이에 자격증명을 복사하지 않는다 — 복사한 토큰은 한쪽이 갱신하는 순간 다른 쪽이 죽는다.
