#!/usr/bin/env python3
"""ccp 표시 문구 사전 — 한국어 · English · 日本語 · 中文.

한 곳에서만 고친다. zsh 쪽(ccp.zsh)이 쓰는 문구도 여기서 만들어 낸다:
    python3 ccp_i18n.py --zsh > ccp_i18n.zsh      (tests/test_i18n.py 가 최신인지 검사한다)

언어 선택: 환경변수 CCP_LANG (ko/en/ja/zh). 없으면 LC_ALL → LC_MESSAGES → LANG 의 앞 두 글자.
ko/ja/zh 가 아니면 en. ccp.zsh 가 같은 규칙으로 정해 export 하므로 python 자식들은 보통 CCP_LANG 을 받는다.

M 의 값은 (ko, en, ja, zh) 순서의 튜플. 키가 빠지면 KeyError 로 바로 드러나게 둔다(조용한 영어 대체 없음).
printf 자리표시자(%s %d)를 쓰는 항목은 zsh 에서 쓰는 것이다. {name} 꼴은 python 에서 .format 으로 채운다.
"""
import os
import sys

LANGS = ("ko", "en", "ja", "zh")


def detect(env=os.environ):
    v = env.get("CCP_LANG") or env.get("LC_ALL") or env.get("LC_MESSAGES") or env.get("LANG") or ""
    v = v.lower()
    for l in ("ko", "ja", "zh"):
        if v.startswith(l):
            return l
    return "en"


LANG = detect()

M = {
    # ── 공통 ──────────────────────────────────────────────────────────────
    "default":        ("기본", "default", "デフォルト", "默认"),
    "weekly":         ("주간", "weekly", "週間", "本周"),
    "session":        ("세션", "session", "セッション", "会话"),
    "model":          ("모델", "model", "モデル", "模型"),
    "weekly_short":   ("주", "wk", "週", "周"),        # 상태줄 짧은 라벨
    "session_short":  ("5h", "5h", "5h", "5h"),
    "nologin":        ("미로그인", "not logged in", "未ログイン", "未登录"),
    "query_fail":     ("조회 실패", "lookup failed", "取得失敗", "查询失败"),
    "soon":           ("곧", "soon", "まもなく", "即将"),
    "left_dh":        ("{d}일{h}시간", "{d}d{h}h", "{d}日{h}時間", "{d}天{h}小时"),
    "left_hm":        ("{h}시간{m}분", "{h}h{m}m", "{h}時間{m}分", "{h}小时{m}分"),
    "left_m":         ("{m}분", "{m}m", "{m}分", "{m}分"),
    "weekdays":       ("월화수목금토일", "Mo Tu We Th Fr Sa Su", "月火水木金土日", "一二三四五六日"),
    "today":          ("오늘 {t}", "today {t}", "今日 {t}", "今天 {t}"),
    "tomorrow":       ("내일 {t}", "tomorrow {t}", "明日 {t}", "明天 {t}"),
    "when_date":      ("{mo}/{da}({wd}) {t}", "{mo}/{da} {wd} {t}", "{mo}/{da}({wd}) {t}", "{mo}/{da}(周{wd}) {t}"),

    # ── 렌더러: 그룹 머리글 ──────────────────────────────────────────────
    "g0":             ("── 지금 쓸 수 있음 ", "── available now ", "── 今使える ", "── 现在可用 "),
    "g1":             ("── 지금 못 씀 · 세션만 차면 풀린다 ", "── blocked · frees up when the session window resets ",
                       "── 今は使えない · セッション枠が空けば復活 ", "── 暂不可用 · 会话窗口重置后恢复 "),
    "g2":             ("── 이번 주 못 씀 · 주간 한도 소진 ", "── out for the week · weekly quota exhausted ",
                       "── 今週は使えない · 週間上限 ", "── 本周不可用 · 周额度已用尽 "),
    "g3":             ("── 확인 불가 · 로그인 필요 ", "── unknown · login required ", "── 確認不可 · ログインが必要 ", "── 无法确认 · 需要登录 "),

    # ── 렌더러: 추천·메모 ────────────────────────────────────────────────
    "rec":            ("추천", "recommended", "おすすめ", "推荐"),
    "rec_none":       ("없음", "none", "なし", "无"),
    "rec_summary":    ("  추천 · {parts}", "  recommended · {parts}", "  おすすめ · {parts}", "  推荐 · {parts}"),
    "note_left":      ("{which} {n}% 남음", "{which} {n}% left", "{which} {n}% 残り", "{which} 剩余 {n}%"),
    "note_weekly_is": ("(주간은 {w}%)", "(weekly {w}%)", "(週間は {w}%)", "(本周 {w}%)"),
    "note_almost":    (" 거의 소진", " almost out", " ほぼ上限", " 几乎用尽"),
    "note_reset_in":  (" · 리셋 {t} 뒤", " · resets in {t}", " · {t}後にリセット", " · {t}后重置"),
    "seven_days":     ("7일", "7d", "7日", "7天"),
    "note_rec":       ("← 추천", "← recommended", "← おすすめ", "← 推荐"),
    "note_sess_out":  ("⏳ 세션 소진", "⏳ session exhausted", "⏳ セッション上限", "⏳ 会话额度用尽"),
    "note_week_out":  ("✕ 주간 소진", "✕ weekly exhausted", "✕ 週間上限", "✕ 周额度用尽"),
    "note_frees_in":  (" — {t} 뒤 풀림", " — frees in {t}", " — {t}後に復活", " — {t}后恢复"),
    "note_model_out": (" ({m} 소진)", " ({m} exhausted)", " ({m} 上限)", " ({m} 已用尽)"),
    "note_current":   ("  [현재]", "  [current]", "  [現在]", "  [当前]"),

    # ── 렌더러: 표 보기 ──────────────────────────────────────────────────
    "col_weekly_used": ("주간 사용", "weekly used", "週間 使用", "本周 已用"),
    "col_sess_used":   ("세션 사용", "session used", "セッション 使用", "会话 已用"),
    "col_reset":       (" ↻ 리셋", " ↻ reset", " ↻ リセット", " ↻ 重置"),
    "tbl_legend1":     ("  주간 = 7일 총량 · 세션 = 5시간 창 · 둘 중 하나라도 100%면 지금은 못 쓴다",
                        "  weekly = 7-day total · session = 5-hour window · 100% on either means blocked for now",
                        "  週間 = 7日の総量 · セッション = 5時間枠 · どちらかが 100% なら今は使えない",
                        "  本周 = 7 天总量 · 会话 = 5 小时窗口 · 任一达到 100% 即暂不可用"),
    "tbl_legend2":     ("  리셋 = 남은 시간→풀리는 시각(하루 넘으면 날짜) · {m} = 이번 주 {m} 전용 한도",
                        "  reset = time left→clock time (date if over a day) · {m} = this week's {m}-only quota",
                        "  リセット = 残り時間→復活時刻（1日超なら日付） · {m} = 今週の {m} 専用枠",
                        "  重置 = 剩余时间→恢复时刻（超过一天则为日期） · {m} = 本周 {m} 专用额度"),
    "tbl_legend1_narrow": ("  주간 = 7일 총량 · 세션 = 5시간 창 · 하나라도 100%면 못 쓴다",
                           "  weekly = 7-day total · session = 5-hour window · 100% = blocked",
                           "  週間 = 7日総量 · セッション = 5時間枠 · 100% なら使えない",
                           "  本周 = 7 天总量 · 会话 = 5 小时窗口 · 100% 即不可用"),
    "tbl_legend2_clock":  ("  리셋 = 남은 시간→풀리는 시각 · {m} = 이번 주 {m} 한도",
                           "  reset = time left→clock time · {m} = this week's {m} quota",
                           "  リセット = 残り時間→復活時刻 · {m} = 今週の {m} 枠",
                           "  重置 = 剩余时间→恢复时刻 · {m} = 本周 {m} 额度"),
    "tbl_legend2_noclock": ("  리셋 = 풀리기까지 남은 시간 · {m} = 이번 주 {m} 한도",
                            "  reset = time until it frees · {m} = this week's {m} quota",
                            "  リセット = 復活までの時間 · {m} = 今週の {m} 枠",
                            "  重置 = 距恢复的时间 · {m} = 本周 {m} 额度"),
    "new_window":      ("새 창", "new window", "新しい枠", "新窗口"),
    "warn_none_soon":  ("  ⚠ 지금 바로 쓸 계정이 없다. 가장 빨리 풀리는 건 {i}) {name} — {kind} {when} 뒤.",
                        "  ⚠ No account is usable right now. Earliest to free up: {i}) {name} — {kind} in {when}.",
                        "  ⚠ 今すぐ使えるアカウントがない。最も早く復活するのは {i}) {name} — {kind} {when}後。",
                        "  ⚠ 现在没有可用账号。最快恢复的是 {i}) {name} — {kind} {when}后。"),
    "warn_none":       ("  ⚠ 사용 가능한 계정이 없다.", "  ⚠ No usable account.", "  ⚠ 使えるアカウントがない。", "  ⚠ 没有可用账号。"),

    # ── 렌더러: 카드(그래프) 보기 ────────────────────────────────────────
    "rd_new":          ("새 창 · 아직 시작 안 함", "new window · not started", "新しい枠 · まだ開始していない", "新窗口 · 尚未开始"),
    "rd_soon":         ("곧 리셋", "resets soon", "まもなくリセット", "即将重置"),
    "rd_full":         ("{when} 리셋 · {left} 남음", "resets {when} · {left} left", "{when} リセット · 残り {left}", "{when} 重置 · 剩余 {left}"),
    "rd_mid":          ("{when} · {left} 뒤", "{when} · in {left}", "{when} · {left}後", "{when} · {left}后"),
    "rd_short":        ("{left} 뒤", "in {left}", "{left}後", "{left}后"),
    "rd_with_weekly":  ("주간과 함께 리셋", "resets with weekly", "週間と同時にリセット", "随本周一起重置"),
    "rd_binds_first":  (" · ◀ 주간보다 먼저 막음", " · ◀ blocks before weekly", " · ◀ 週間より先に上限", " · ◀ 先于本周到限"),
    "gr_legend_wide":  ("  주간 = 7일 총량 · 세션 = 5시간 창 · {m} = 이번 주 {m} 한도 · 하나라도 100%면 그때까지 못 쓴다",
                        "  weekly = 7-day total · session = 5-hour window · {m} = this week's {m} quota · 100% on any = blocked until reset",
                        "  週間 = 7日総量 · セッション = 5時間枠 · {m} = 今週の {m} 枠 · どれかが 100% ならリセットまで使えない",
                        "  本周 = 7 天总量 · 会话 = 5 小时窗口 · {m} = 本周 {m} 额度 · 任一达 100% 则重置前不可用"),
    "gr_legend_narrow": ("  주간 = 7일 총량 · 세션 = 5시간 창 · {m} = 이번 주 한도",
                         "  weekly = 7-day total · session = 5-hour window · {m} = weekly quota",
                         "  週間 = 7日総量 · セッション = 5時間枠 · {m} = 今週の枠",
                         "  本周 = 7 天总量 · 会话 = 5 小时窗口 · {m} = 本周额度"),
    "gr_legend_terse": ("  주간 7일 · 세션 5시간 · {m} 주간 · {tick} 지금 위치 · 100%면 못 씀",
                        "  weekly 7d · session 5h · {m} weekly · {tick} now · 100% = blocked",
                        "  週間 7日 · セッション 5時間 · {m} 週間 · {tick} 現在位置 · 100% で使えない",
                        "  本周 7 天 · 会话 5 小时 · {m} 本周 · {tick} 当前位置 · 100% 即不可用"),
    "gr_legend_rec":   ("  추천 = 주간 리셋이 가까운데 남은 양이 많은 계정부터 — 남은 양은 주간·{m} 중 먼저 막는 쪽(◀) 기준",
                        "  recommended = accounts whose weekly reset is near but still have plenty left — 'left' means whichever of weekly/{m} blocks first (◀)",
                        "  おすすめ = 週間リセットが近いのに残りが多いアカウントから — 残りは週間・{m} のうち先に上限になる方(◀)基準",
                        "  推荐 = 本周重置临近但剩余较多的账号优先 — 剩余以本周/{m} 中先到限的一方(◀)为准"),
    "gr_legend_tick":  ("  {tick} = 지금(창의 경과 위치, 오른쪽 끝 = 리셋 직전) — 막대가 {tick}에 못 미치면 페이스보다 덜 써서 여유, 넘으면 빠듯",
                        "  {tick} = now (position in the window, right edge = just before reset) — bar short of {tick} means under pace, past it means tight",
                        "  {tick} = 現在（枠内の経過位置、右端 = リセット直前） — 棒が {tick} に届かなければペース以下で余裕、超えれば厳しい",
                        "  {tick} = 当前（窗口内的进度位置，右端 = 重置前夕） — 条未到 {tick} 表示用得比进度慢、有余量，超过则紧张"),
    "gr_legend_codex": ("  codex = 주간(+5시간) 한도만 있고 모델별 한도는 없다 · 전환은 프로필별 CODEX_HOME",
                        "  codex = weekly (+5-hour) quota only, no per-model quota · switching = per-profile CODEX_HOME",
                        "  codex = 週間(+5時間)枠のみでモデル別枠はない · 切り替えはプロファイル別 CODEX_HOME",
                        "  codex = 仅有本周(+5 小时)额度，无按模型额度 · 切换 = 每个配置各自的 CODEX_HOME"),
    "tl_header":       ("  주간 리셋 시점 — 지금부터 7일 (● 리셋 · ┼ 자정)", "  weekly reset times — next 7 days (● reset · ┼ midnight)",
                        "  週間リセット時点 — 今から7日 (● リセット · ┼ 深夜0時)", "  本周重置时间 — 未来 7 天 (● 重置 · ┼ 午夜)"),
    "tl_weekly_used":  ("{wh} · 주간 {w}% 사용", "{wh} · weekly {w}% used", "{wh} · 週間 {w}% 使用", "{wh} · 本周已用 {w}%"),
    "tl_weekly_model": ("{wh} · 주간 {w}% · {m} {mp}% ◀", "{wh} · weekly {w}% · {m} {mp}% ◀", "{wh} · 週間 {w}% · {m} {mp}% ◀", "{wh} · 本周 {w}% · {m} {mp}% ◀"),

    # ── 렌더러: 대화형 안내줄 ────────────────────────────────────────────
    "key_forced":      ("(화면이 낮아 표로 표시)", "(table view: screen too short)", "(画面が低いため表で表示)", "(屏幕太矮，以表格显示)"),
    "key_table":       ("v 표 보기", "v table", "v 表", "v 表格"),
    "key_graph":       ("v 그래프 보기", "v graph", "v グラフ", "v 图形"),
    "key_empty":       ("아직 등록된 계정이 없어요 — a 를 눌러 추가하세요 (그다음 그 계정을 골라 Enter → /login)",
                        "no accounts yet — press a to add one (then select it, Enter, and /login)",
                        "まだアカウントがありません — a を押して追加（その後その行を選んで Enter → /login）",
                        "还没有账号 — 按 a 添加（然后选中它，Enter → /login）"),
    "key_locked":      ("기본 프로필(0번)은 수정·삭제할 수 없어요 — 다른 줄에서 e/d 를 누르세요",
                        "the default profile (item 0) cannot be edited or removed — press e/d on another line",
                        "デフォルト(0番)は編集・削除できません — 他の行で e/d を押してください",
                        "默认配置(0号)不能编辑或删除 — 请在其他行按 e/d"),
    "key_help":        ("Enter 실행 · ↑↓/j k 이동 · 숫자 = 번호로 · {other} · a 추가 · e 수정 · d 삭제 · Esc/q 취소",
                        "Enter open · ↑↓/j k move · digit = jump · {other} · a add · e edit · d delete · Esc/q cancel",
                        "Enter 起動 · ↑↓/j k 移動 · 数字 = 番号へ · {other} · a 追加 · e 編集 · d 削除 · Esc/q キャンセル",
                        "Enter 启动 · ↑↓/j k 移动 · 数字 = 跳转 · {other} · a 添加 · e 编辑 · d 删除 · Esc/q 取消"),

    # ── codex 메모 ───────────────────────────────────────────────────────
    "cx_credits":      ("크레딧 소진", "credits depleted", "クレジット枯渇", "积分耗尽"),
    "cx_spend":        ("지출 한도", "spend limit", "支出上限", "支出上限"),
    "cx_tickets":      ("리셋권 {n}", "reset credits {n}", "リセット権 {n}", "重置券 {n}"),

    # ── statusline ───────────────────────────────────────────────────────
    "sl_no_limits":    ("한도 조회 전", "quota not yet reported", "枠 未取得", "额度尚未获取"),

    # ── ccp_link (기록 연동 이관) ─────────────────────────────────────────
    "ln_dry":          ("(미리 보기 — 아무것도 바꾸지 않는다)", "(dry run — nothing is changed)", "(プレビュー — 何も変更しない)", "(预览 — 不做任何更改)"),
    "ln_share":        ("프로필 공유(file-history·paste-cache): 링크 {linked} · 옮김 {moved} · 이름 겹쳐 남김 {kept}",
                        "profile sharing (file-history, paste-cache): linked {linked} · moved {moved} · left in place (name clash) {kept}",
                        "プロファイル共有(file-history・paste-cache): リンク {linked} · 移動 {moved} · 名前重複で残し {kept}",
                        "配置共享(file-history、paste-cache): 链接 {linked} · 移动 {moved} · 因重名保留 {kept}"),
    "ln_leftover":     ("  남긴 것: {path} (같은 이름이 이미 있어 덮지 않았다 — 확인 후 지워도 된다)",
                        "  left: {path} (same name already existed, not overwritten — safe to delete after a look)",
                        "  残したもの: {path} (同名が既にあり上書きしなかった — 確認後に削除可)",
                        "  保留: {path} (已有同名文件，未覆盖 — 确认后可删除)"),
    "ln_folder":       ("  {src} → {dst}: 옮김 {moved} · 겹쳐 남김 {kept}", "  {src} → {dst}: moved {moved} · clash, left {kept}",
                        "  {src} → {dst}: 移動 {moved} · 重複で残し {kept}", "  {src} → {dst}: 移动 {moved} · 重名保留 {kept}"),
    "ln_projects":     ("워크트리 기록: 폴더 {folders}개 · 옮김 {moved} · 겹쳐 남김 {kept}", "worktree history: {folders} folder(s) · moved {moved} · clash, left {kept}",
                        "ワークツリー履歴: フォルダ {folders} 件 · 移動 {moved} · 重複で残し {kept}", "工作树记录: {folders} 个文件夹 · 移动 {moved} · 重名保留 {kept}"),
    "ln_busy":         ("  건너뜀(세션이 돌고 있다): {name} — 그 세션을 끝낸 뒤 ccp-migrate 를 다시 돌릴 것",
                        "  skipped (a session is running): {name} — end it, then run ccp-migrate again",
                        "  スキップ(セッション実行中): {name} — 終了後に ccp-migrate を再実行",
                        "  已跳过(会话运行中): {name} — 结束该会话后重新运行 ccp-migrate"),
    "ln_gone":         ("  실행 폴더가 사라진 기록 {n}개는 그대로 뒀다 — 지워진 워크트리의 것이면: ccp-migrate --map <아래 이름> <메인 체크아웃 경로>",
                        "  {n} folder(s) whose working directory no longer exists were left alone — if one belonged to a removed worktree: ccp-migrate --map <name below> <main checkout path>",
                        "  実行フォルダが消えた履歴 {n} 件はそのまま — 削除済みワークツリーのものなら: ccp-migrate --map <下の名前> <メインチェックアウトのパス>",
                        "  工作目录已不存在的 {n} 个记录保持原样 — 若属于已删除的工作树: ccp-migrate --map <下列名称> <主检出路径>"),
    "ln_map_bad":      ("--map <기록폴더이름> <메인 체크아웃 경로> — 경로가 없다: {name} {path}", "--map <history folder name> <main checkout path> — path not found: {name} {path}",
                        "--map <履歴フォルダ名> <メインチェックアウトのパス> — パスがない: {name} {path}", "--map <记录文件夹名> <主检出路径> — 路径不存在: {name} {path}"),

    # ── ccp.zsh (printf 형식) ────────────────────────────────────────────
    "z_nologin":       ("(미로그인)", "(not logged in)", "(未ログイン)", "(未登录)"),
    "z_query_fail":    ("(조회 실패)", "(lookup failed)", "(取得失敗)", "(查询失败)"),
    "z_querying":      ("  사용량 조회 중… (%d개)", "  checking usage… (%d)", "  使用量を取得中… (%d件)", "  正在查询用量… (%d 个)"),
    "z_tsv_header":    ("# 도구\\t이름\\t별칭\\t설명", "# tool\\tname\\talias\\tnote", "# ツール\\t名前\\t別名\\tメモ", "# 工具\\t名称\\t别名\\t备注"),
    "z_created":       ("생성: %s %s", "created: %s %s", "作成: %s %s", "已创建: %s %s"),
    "z_sync_next":     ("다음: ccp → 새 프로필마다 /login (codex 는 CODEX_HOME=<디렉터리> codex login)",
                        "next: ccp → /login in each new profile (codex: CODEX_HOME=<dir> codex login)",
                        "次: ccp → 新しいプロファイルごとに /login (codex は CODEX_HOME=<dir> codex login)",
                        "下一步: ccp → 在每个新配置里 /login (codex: CODEX_HOME=<目录> codex login)"),
    "z_sync_all":      ("프로필 전부 있음 (%s)", "all profiles present (%s)", "プロファイルはすべて存在 (%s)", "所有配置均已存在 (%s)"),
    "z_alias_conflict": ("ccp: 별칭 %s 은(는) 이미 있는 %s 이라 건너뜀 (%s)", "ccp: alias %s skipped — already a %s (%s)",
                         "ccp: 別名 %s は既存の %s のためスキップ (%s)", "ccp: 别名 %s 已是现有的 %s，跳过 (%s)"),
    "z_new_usage":     ("사용법: ccp-new <프로필이름> [별칭] [설명] | ccp-new --codex <프로필이름> [별칭] [설명]",
                        "usage: ccp-new <name> [alias] [note] | ccp-new --codex <name> [alias] [note]",
                        "使い方: ccp-new <名前> [別名] [メモ] | ccp-new --codex <名前> [別名] [メモ]",
                        "用法: ccp-new <名称> [别名] [备注] | ccp-new --codex <名称> [别名] [备注]"),
    "z_exists":        ("이미 있음: %s", "already exists: %s", "既に存在: %s", "已存在: %s"),
    "z_created_at":    ("생성: %s\\n기록: %s", "created: %s\\nrecorded in: %s", "作成: %s\\n記録: %s", "已创建: %s\\n已记录: %s"),
    "z_codex_next":    ("다음: CODEX_HOME=%s codex login", "next: CODEX_HOME=%s codex login", "次: CODEX_HOME=%s codex login", "下一步: CODEX_HOME=%s codex login"),
    "z_codex_ws":      ("  (같은 ChatGPT 계정이라도 브라우저 승인 화면에서 워크스페이스를 골라야 한다)",
                        "  (even with the same ChatGPT login, pick the workspace on the browser approval screen)",
                        "  (同じ ChatGPT アカウントでも、ブラウザの承認画面でワークスペースを選ぶ)",
                        "  (即使是同一个 ChatGPT 账号，也要在浏览器授权页选择工作区)"),
    "z_claude_next":   ("다음: ccp %s → /login", "next: ccp %s → /login", "次: ccp %s → /login", "下一步: ccp %s → /login"),
    "z_name_dup":      ("이름이 겹친다: %s — claude:%s / codex:%s 처럼 도구를 붙여라", "ambiguous name: %s — prefix the tool, e.g. claude:%s / codex:%s",
                        "名前が重複: %s — claude:%s / codex:%s のようにツールを付ける", "名称重复: %s — 请加上工具前缀，如 claude:%s / codex:%s"),
    "z_no_profiles":   ("등록된 계정이 없다. 터미널에서 ccp 를 열고 a 를 누르거나 ccp-new <이름>", "no accounts yet. Run ccp in a terminal and press a, or ccp-new <name>",
                        "アカウントがない。ターミナルで ccp を開いて a を押すか ccp-new <名前>", "还没有账号。在终端打开 ccp 并按 a，或 ccp-new <名称>"),
    "z_sync_empty":    ("등록된 계정이 아직 없다 — ccp 를 열고 a 로 추가하면 된다 (%s 에 직접 적고 ccp-sync 도 가능)",
                        "no accounts registered yet — open ccp and press a (or write %s and run ccp-sync)",
                        "登録済みのアカウントはまだない — ccp を開いて a で追加（%s に書いて ccp-sync でも可）",
                        "还没有登记的账号 — 打开 ccp 按 a 添加（也可写入 %s 后 ccp-sync）"),
    "z_quit":          ("  q) 종료 · a) 추가 · e N) 수정 · d N) 삭제", "  q) quit · a) add · e N) edit · d N) delete",
                        "  q) 終了 · a) 追加 · e N) 編集 · d N) 削除", "  q) 退出 · a) 添加 · e N) 编辑 · d N) 删除"),
    # ── 메뉴 안 추가·수정·삭제 ──────────────────────────────────────────
    "z_add_tool":      ("도구 [claude/codex] (Enter = claude): ", "tool [claude/codex] (Enter = claude): ",
                        "ツール [claude/codex] (Enter = claude): ", "工具 [claude/codex] (Enter = claude): "),
    "z_add_name":      ("새 프로필 이름 (Enter = 취소): ", "new profile name (Enter = cancel): ",
                        "新しいプロファイル名 (Enter = キャンセル): ", "新配置名称 (Enter = 取消): "),
    "z_add_alias":     ("별칭 (Enter = 없음): ", "alias (Enter = none): ", "別名 (Enter = なし): ", "别名 (Enter = 无): "),
    "z_add_desc":      ("설명 (Enter = 없음): ", "note (Enter = none): ", "メモ (Enter = なし): ", "备注 (Enter = 无): "),
    "z_cancel":        ("취소", "cancelled", "キャンセル", "已取消"),
    "z_back":          ("Enter 로 메뉴로 돌아간다 ", "Enter to return to the menu ", "Enter でメニューに戻る ", "按 Enter 返回菜单 "),
    "z_rm_usage":      ("사용법: ccp-rm [--codex] <프로필이름> [-f]", "usage: ccp-rm [--codex] <name> [-f]",
                        "使い方: ccp-rm [--codex] <名前> [-f]", "用法: ccp-rm [--codex] <名称> [-f]"),
    "z_rm_default":    ("기본 프로필(~/.claude, ~/.codex)은 지울 수 없다", "the default profile (~/.claude, ~/.codex) cannot be removed",
                        "デフォルトのプロファイル(~/.claude, ~/.codex)は削除できない", "默认配置 (~/.claude, ~/.codex) 不能删除"),
    "z_rm_missing":    ("없는 프로필: %s", "no such profile: %s", "存在しないプロファイル: %s", "没有这个配置: %s"),
    "z_rm_confirm":    ("%s 를 지운다 — 그 계정의 로그인만 사라지고 대화 기록·설정은 남는다. 진행? [y/N] ",
                        "remove %s — only that account's login goes away; history and settings stay. Proceed? [y/N] ",
                        "%s を削除 — そのアカウントのログインだけが消え、履歴・設定は残る。実行? [y/N] ",
                        "删除 %s — 只会清除该账号的登录，对话记录和设置保留。继续? [y/N] "),
    "z_rm_done":       ("삭제: %s", "removed: %s", "削除: %s", "已删除: %s"),
    "z_edit_usage":    ("사용법: ccp-edit [--codex] <프로필이름> [새이름] [새별칭|-]", "usage: ccp-edit [--codex] <name> [new-name] [new-alias|-]",
                        "使い方: ccp-edit [--codex] <名前> [新しい名前] [新しい別名|-]", "用法: ccp-edit [--codex] <名称> [新名称] [新别名|-]"),
    "z_edit_name":     ("새 이름 (Enter = %s 그대로): ", "new name (Enter = keep %s): ", "新しい名前 (Enter = %s のまま): ", "新名称 (Enter = 保持 %s): "),
    "z_edit_alias":    ("새 별칭 (Enter = '%s' 그대로, - = 없음): ", "new alias (Enter = keep '%s', - = none): ",
                        "新しい別名 (Enter = '%s' のまま, - = なし): ", "新别名 (Enter = 保持 '%s', - = 无): "),
    "z_edit_done":     ("수정: %s → %s (별칭 '%s')", "updated: %s → %s (alias '%s')", "変更: %s → %s (別名 '%s')", "已修改: %s → %s (别名 '%s')"),
    "z_edit_exists":   ("이미 있는 이름: %s", "name already exists: %s", "既にある名前: %s", "名称已存在: %s"),
    "z_select_rec":    ("선택 [0-%d, q]  (엔터 = 추천 %s) %s: ", "select [0-%d, q]  (Enter = recommended %s) %s: ",
                        "選択 [0-%d, q]  (Enter = おすすめ %s) %s: ", "选择 [0-%d, q]  (Enter = 推荐 %s) %s: "),
    "z_select":        ("선택 [0-%d, q]: ", "select [0-%d, q]: ", "選択 [0-%d, q]: ", "选择 [0-%d, q]: "),
    "z_out_of_range":  ("범위 밖: %s", "out of range: %s", "範囲外: %s", "超出范围: %s"),
    "z_not_found":     ("프로필 '%s' 없음. ccp-new %s", "profile '%s' not found. ccp-new %s", "プロファイル '%s' がない。ccp-new %s", "找不到配置 '%s'。ccp-new %s"),
    "z_warn_session":  ("  ⏳ 세션 한도 소진 상태다 — 곧 풀리지만 지금은 막힐 수 있다.", "  ⏳ session quota exhausted — frees soon, but may be blocked right now.",
                        "  ⏳ セッション上限に達している — まもなく復活するが今は弾かれることがある。", "  ⏳ 会话额度已用尽 — 很快恢复，但现在可能被拒。"),
    "z_warn_weekly":   ("  ✕ 주간 한도 소진 상태다 — 지금은 못 쓴다.", "  ✕ weekly quota exhausted — unusable for now.",
                        "  ✕ 週間上限に達している — 今は使えない。", "  ✕ 周额度已用尽 — 现在无法使用。"),
    "z_warn_nologin":  ("  ✕ 미로그인/조회 실패 — /login 이 필요할 수 있다.", "  ✕ not logged in / lookup failed — you may need /login.",
                        "  ✕ 未ログイン/取得失敗 — /login が必要かもしれない。", "  ✕ 未登录/查询失败 — 可能需要 /login。"),
    "z_held_bg":       ("  ⚠ 이 폴더의 백그라운드 세션 %s(%s)를 %s 프로필이 잡고 있다 — 이어가려면: ccp %s 로 들어가 claude attach %s",
                        "  ⚠ background session %s (%s) in this folder is held by profile %s — to continue it: ccp %s, then claude attach %s",
                        "  ⚠ このフォルダのバックグラウンドセッション %s(%s) は %s プロファイルが保持中 — 続けるには: ccp %s で入り claude attach %s",
                        "  ⚠ 此文件夹的后台会话 %s(%s) 由配置 %s 持有 — 要继续: ccp %s 后执行 claude attach %s"),
    "z_held_resume":   ("  ⚠ 세션 %s 는 지금 %s 프로필에서 열려 있다 — 두 곳에서 열면 기록이 엉킨다. 그래도 열까? [y/N] ",
                        "  ⚠ session %s is open right now in profile %s — opening it twice tangles the transcript. Open anyway? [y/N] ",
                        "  ⚠ セッション %s は今 %s プロファイルで開かれている — 二重に開くと履歴が絡む。それでも開く? [y/N] ",
                        "  ⚠ 会话 %s 正在配置 %s 中打开 — 同时打开两处会弄乱记录。仍要打开? [y/N] "),
    "z_migrate_hint":  ("  (프로필 간 되감기 공유·워크트리 기록 합치기: ccp-migrate -n 으로 미리 보고 ccp-migrate)",
                        "  (share rewind data across profiles and merge worktree history: preview with ccp-migrate -n, then ccp-migrate)",
                        "  (プロファイル間の巻き戻し共有・ワークツリー履歴の統合: ccp-migrate -n で確認後 ccp-migrate)",
                        "  (跨配置共享回退数据并合并工作树记录: 先 ccp-migrate -n 预览，再 ccp-migrate)"),
    # ── 대화 가져오기(--take · 계정 고른 뒤 선택 화면) ──
    "z_pick_head":     ("이 폴더에서 나눈 대화 — 번호를 고르면 %s 계정으로 가져와 연다(복사본)",
                        "conversations from this folder — pick a number to bring one over to account %s (as a copy)",
                        "このフォルダの会話 — 番号を選ぶと %s アカウントに持ち込んで開く(コピー)",
                        "此文件夹的对话 — 选择编号即带到 %s 账号打开(副本)"),
    "z_pick_prompt":   ("번호 · Enter = 새 대화 · q = 취소: ", "number · Enter = new conversation · q = cancel: ",
                        "番号 · Enter = 新しい会話 · q = 取消: ", "编号 · Enter = 新对话 · q = 取消: "),
    "z_pick_held_mark":("· %s 프로필이 잡고 있음", "· held by profile %s", "· %s プロファイルが保持中", "· 由配置 %s 持有"),
    "z_pick_cont_mark":("· %s 로 이어짐", "· continued in %s", "· %s に継続", "· 已续到 %s"),
    "z_take_start":    ("↩ 세션 %s(%s)를 %s 계정으로 가져온다 — 복사본이라 원본은 그대로다",
                        "↩ bringing session %s (%s) over to account %s — a copy; the original stays as is",
                        "↩ セッション %s(%s) を %s アカウントに持ち込む — コピーなので元はそのまま",
                        "↩ 将会话 %s(%s) 带到 %s 账号 — 是副本，原始记录不变"),
    "z_take_held":     ("  ⚠ 원본은 %s 프로필이 아직 잡고 있다 — 정리: ccp %s 로 들어가 claude stop %s",
                        "  ⚠ the original is still held by profile %s — clean up: ccp %s, then claude stop %s",
                        "  ⚠ 元のセッションは %s プロファイルがまだ保持中 — 片付け: ccp %s で入り claude stop %s",
                        "  ⚠ 原会话仍由配置 %s 持有 — 清理: ccp %s 后执行 claude stop %s"),
    "z_take_none":     ("가져올 대화가 없다: %s", "no conversation to bring over: %s", "持ち込む会話がない: %s", "没有可带过来的对话: %s"),
    "z_take_empty":    ("이 폴더에서 나눈 대화가 없다 — 새 대화로 연다", "no conversations in this folder — starting a new one",
                        "このフォルダに会話がない — 新しい会話で開く", "此文件夹没有对话 — 以新对话打开"),
    "z_take_ambig":    ("세션 ID '%s' 가 여러 개와 맞는다: %s", "session ID '%s' matches several: %s",
                        "セッション ID '%s' に複数が一致: %s", "会话 ID '%s' 匹配多个: %s"),
    "z_take_codex":    ("--take 는 claude 전용이다 — codex 세션은 이렇게 가져올 수 없다",
                        "--take is claude-only — codex sessions can't be brought over this way",
                        "--take は claude 専用 — codex のセッションはこの方法で持ち込めない",
                        "--take 仅用于 claude — codex 会话不能这样带过来"),
    "z_no_dir":        ("프로필 디렉터리 없음: %s", "profile directory missing: %s", "プロファイルのディレクトリがない: %s", "配置目录不存在: %s"),
}


def t(key, lang=None, **kw):
    s = M[key][LANGS.index(lang or LANG)]
    return s.format(**kw) if kw else s


def left(mins, lang=None):
    """남은 분 → '3일22시간' / '3d22h' 같은 짧은 표현. None 이면 ''."""
    if mins is None:
        return ""
    if mins <= 0:
        return t("soon", lang)
    d, h, m = mins // 1440, (mins % 1440) // 60, mins % 60
    if d:
        return t("left_dh", lang, d=d, h=h)
    if h:
        return t("left_hm", lang, h=h, m=m)
    return t("left_m", lang, m=m)


def weekday(idx, lang=None):
    """월요일=0. 한 글자(ko/ja/zh) 또는 두 글자(en)."""
    w = t("weekdays", lang)
    parts = w.split(" ") if " " in w else list(w)
    return parts[idx % 7]


def emit_zsh():
    """ccp.zsh 가 source 하는 파일. 언어마다 연관 배열 하나 + _ccp_t 함수."""
    out = ["# 생성 파일 — 손으로 고치지 말 것. 원본은 ccp_i18n.py:  python3 ccp_i18n.py --zsh > ccp_i18n.zsh", ""]
    keys = [k for k in M if k.startswith("z_") or k == "default"]
    for i, lang in enumerate(LANGS):
        out.append(f"typeset -gA _CCP_MSG_{lang}")
        out.append(f"_CCP_MSG_{lang}=(")
        for k in keys:
            v = M[k][i].replace("'", "'\\''")
            out.append(f"  {k} '{v}'")
        out.append(")")
    out += [
        "",
        "# _ccp_t <키> [printf 인자...] — 현재 CCP_LANG 의 문구를 printf 형식으로 채워 낸다(줄바꿈 없음).",
        "_ccp_t() {",
        "  local key=\"$1\"; shift",
        "  local ref=\"_CCP_MSG_${CCP_LANG:-en}[${key}]\"",
        "  local fmt=\"${(P)ref}\"",
        "  [[ -z \"$fmt\" ]] && { ref=\"_CCP_MSG_en[${key}]\"; fmt=\"${(P)ref}\"; }",
        "  printf -- \"$fmt\" \"$@\"",
        "}",
        "_ccp_tl() { _ccp_t \"$@\"; printf '\\n'; }   # 줄바꿈 붙인 판",
        "",
    ]
    return "\n".join(out)


if __name__ == "__main__":
    if "--zsh" in sys.argv:
        sys.stdout.write(emit_zsh())
    elif "--check" in sys.argv:
        bad = [k for k, v in M.items() if len(v) != len(LANGS) or any(not isinstance(x, str) for x in v)]
        print("ok" if not bad else f"bad entries: {bad}")
        sys.exit(1 if bad else 0)
    else:
        print(LANG)
