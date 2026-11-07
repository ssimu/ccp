---
name: fleet-dispatch
description: "집 Mac 함대(관문 old-mbp)에 Claude Code 코딩 작업을 투입하고 결과를 회수한다. Telegram 에서 '맥미니에서 ~ 해줘', '함대에 작업', '작업 결과' 류 요청에 쓴다."
version: 1.1.0
author: ccp (ssimu/ccp fleet/hermes)
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [fleet, claude-code, dispatch, mac, herdr, ccp]
    related_skills: []
---

# 함대 작업 투입 (fleet-dispatch)

사용자의 집 Mac 네 대에 Claude Code 작업을 던지고 결과를 가져온다. 모든 명령은 관문 old-mbp 에 SSH 로 들어가서 돌린다.
관문의 `fleet-jobs` 가 각 Mac 의 데스크톱 Herdr(hc) 터미널에서 `ccp <프로필>` 로 Claude Code 를 띄운다(키체인이 열린 세션이라 로그인이 안 끊긴다).

```bash
FLEET="bash $HOME/.hermes/scripts/fleet.sh"        # 인자를 따옴표째 안전하게 관문으로 넘긴다. ssh 를 손으로 조립하지 않는다.
$FLEET machines                                     # 머신 목록·기본 프로필 (local=old-mbp, macmini, wooui, mbp2)
$FLEET dispatch --on macmini --name <짧은이름> "<작업문>"    # 투입 → '투입함 [j261106-093752] …' 의 id 를 쓴다
$FLEET dispatch --on wooui --profile amc-personal --cwd '~/projects/foo' "<작업문>"
$FLEET wait <id> --timeout 150                      # 끝나면 결과까지 출력. 150초 안에 안 끝나면 '아직 끝나지 않음'
$FLEET list                                         # 진행 중인 작업
$FLEET status <id>   /   $FLEET result <id>         # 상태 / 결과 본문
$FLEET send <id> "<추가 지시>"                       # 같은 에이전트에게 이어서 시킨다
$FLEET stop <id>
$FLEET projects                                     # 프로젝트 등록부 — 이름으로 투입하면 기계·폴더가 채워진다
$FLEET dispatch --project <이름> "<작업문>"           # 예: --project fleet-demo
$FLEET dispatch --project <이름> --agent codex "[리뷰] git diff 를 읽고 깨지는 입력·빠진 테스트를 찾아라. 고치지 말고 목록만."
$FLEET list --project <이름>
```

## 결정 필요(질문) — 승인 카드

작업자가 막히면 결과를 '질문:' 으로 쓰고 멈춘다. 상태가 **결정 필요(질문)** 로 보이고 5분 완료 알림에도 그렇게 온다.
- 읽기·테스트·리뷰·허용 폴더 안 편집·작업 브랜치 커밋·리뷰 지적 1회 반영처럼 **규칙으로 답할 수 있는 것은 직접 답한다**: `$FLEET send <id> "<답>"`.
- push·병합·배포·발송·삭제·비밀값·결제·허용 폴더 밖·설정 파일·판단이 엇갈림은 **사용자에게 묻는다.** 질문 한 줄 + 고를 답 + 추천을 같이 보낸다.
- 사용자가 "j… 승인", "j… 반려 <이유>" 또는 자유 답을 하면 `$FLEET send <id> "<그 답>"` 으로 옮기고 다시 wait.
- codex 작업(`codex:` 로 표시)은 끝나면 나가서 send 가 안 된다 — 답을 붙여 새 작업으로 투입한다.
규칙의 정본은 사용자 마스터 폴더의 POLICY.md 다. 여기 요지와 다르면 그쪽이 맞다.

작업문은 **사람에게 말하듯 자연어로** 쓴다(Claude Code 에이전트가 읽는다). 셸 명령 한 줄을 작업문으로 넣지 않는다 — 예: "fleet-work 폴더에 bye.txt 를 만들고 안에 bye 한 단어만 적어라. 다른 일은 하지 마라."
작업문이 길면 stdin 으로: `printf '%s' "$TASK" | $FLEET dispatch --on macmini -`

## 절차

1. 사용자가 머신을 안 정하면 **macmini** (항상 켜져 있고 한가함). 사용자 작업 폴더를 말하면 `--cwd` 로 넘기고, 없으면 기본 `~/fleet-work`.
2. `fleet-dispatch` 로 투입하고 **id 와 머신을 바로 답한다**("macmini 에 j… 로 투입했어요").
3. `fleet-jobs wait <id> --timeout 150` 한 번 기다린다. 끝났으면 결과 요약을 그대로 전한다.
   안 끝났으면 "아직 돌고 있어요, 끝나면 알릴게요"라고 답하고 멈춘다 — 5분마다 도는 cron '함대 작업 완료 알림'이 끝난 작업을 Telegram 으로 보낸다. 반복해서 wait 를 돌리지 않는다.
4. 상태가 `대화상자에 멈춤`·`사람 필요(blocked)` 면 화면 내용을 사용자에게 보여 주고 지시를 받는다. `hc keys` 는 직접 치지 않는다.
5. 후속 지시("거기에 테스트도 추가해")는 새 작업이 아니라 `fleet-jobs send <id> "…"` 로 같은 에이전트에 보낸다. 그 뒤 다시 wait.

## 하지 말 것

- 작업 폴더(`--cwd`)는 관문의 허용 목록(기본 `~/fleet-work`, `~/projects`) 안이어야 한다. 밖이면 '허용 폴더 밖' 으로 거부되니 사용자에게 그대로 전한다.
- 작업문에 커밋·push·발송·삭제를 넣지 않는다 — 사용자가 그 단어로 명시했을 때만 그대로 옮긴다.
- 프로필 `imok` 은 쓰지 않는다. 프로필을 바꾸라는 말이 없으면 `--profile` 을 생략한다(머신별 기본값이 있다).
- 관문에서 `claude`·`ccp` 를 SSH 로 직접 띄우지 않는다(키체인 잠김으로 로그인이 깨진다). 반드시 `fleet-dispatch`/`fleet-jobs` 만 쓴다.
- 한도가 걱정되면 먼저 `bash ~/.hermes/scripts/fleet_report.sh` 로 남은 양을 보고, 주간 20% 미만인 프로필은 피한다.
