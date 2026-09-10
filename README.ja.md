<p align="right"><a href="README.md">한국어</a> · <a href="README.en.md">English</a> · <b>日本語</b> · <a href="README.zh-CN.md">中文</a></p>

# ccp

**Claude Code のアカウントを複数使う人のための切り替えツール。**
ログアウト・ログインなしでアカウントを切り替え、どのアカウントに残り枠がどれだけあるかを一画面で確認できます。
Codex CLI のアカウントも一緒に表示されます。

```
  Claude
  ── 今使える ─────────────────────────────────────────
  ▸ 2) team       ← おすすめ · 週間 62% 残り · 2日後にリセット
    0) 기본       週間 85% 残り · 5日後にリセット
  ── 今は使えない · セッション枠が空けば復活 ───────────
    1) personal   ⏳ セッション上限 — 2時間12分後に復活
```

> メニューの表示は現在韓国語です。以下のコマンドはどのロケールでも同じように動きます。

## こんな人に

- 会社用と個人用のアカウントを行き来している
- 片方が上限に達したら別のアカウントに移って **会話をそのまま続けたい**
- 毎回 `/logout` `/login` するのが面倒

## インストール（3分）

必要なもの: macOS または Linux、zsh、python3、[Claude Code](https://docs.anthropic.com/claude-code) がインストール済みであること。

```bash
git clone https://github.com/ssimu/ccp.git ~/projects/ccp
~/projects/ccp/install.sh
source ~/.zshrc
```

あとは3ステップです。

**1. 自分のアカウントを書く** — `~/.config/ccp/profiles.tsv` を開き、1行に1アカウント。列は **タブ** で区切ります。

```
# ツール     名前        別名   メモ
claude      team        cct    会社アカウント
claude      personal    ccm    個人アカウント
```

- 名前: 自分が分かる名前（半角英数推奨）
- 別名: 短いコマンド。`cct` と打つとそのアカウントで直接起動します。省略可。
- 既存の `~/.claude` アカウントは書きません。常に 0 番「기본（デフォルト）」として表示されます。

**2. プロファイルのディレクトリを作る**

```bash
ccp-sync
```

**3. アカウントごとに1回ログイン**

```bash
ccp            # メニューでアカウントを選ぶ → 起動したら /login
```

これ以降は `ccp` で選ぶか、`cct` のような別名で直接起動します。

## 日常のコマンド

| コマンド | 意味 |
|---|---|
| `ccp` | メニュー。矢印キーで選んで Enter。**Enter だけ押すとおすすめアカウント**で起動 |
| `ccp team` / `cct` | 名前または別名で直接 |
| `ccp team -c` | そのアカウントで **直前の会話を続ける**（名前以降のオプションは claude にそのまま渡す） |
| `ccp-usage` | メニューなしで残り枠だけ見る |
| `ccp-ls` | 各プロファイルに誰がログインしているか |
| `ccp-new 名前 別名` | アカウント追加（TSV にも自動記録） |

メニューのキー: `↑↓` または `j` `k` 移動 · 数字 = その番号へ · `v` グラフ↔表 · `q` キャンセル

## よくある質問

**切り替えると会話履歴は消えますか？**
消えません。履歴・設定・スキルはすべてのアカウントで共有され、ログインだけが別です。だから上限に達したら別アカウントで `ccp team -c` して続けられます。

**アカウントを増やす・減らすには？**
`profiles.tsv` の行を追加・削除して `ccp-sync`。削除した行のディレクトリも消すなら `rm -rf ~/.claude-profiles/名前`。

**常に `--dangerously-skip-permissions` で起動したい。**
`~/.config/ccp/config.zsh` でこの行のコメントを外します。意味を理解した上で有効にしてください。
```zsh
CCP_CLAUDE_ARGS=(--dangerously-skip-permissions)
```

**Codex も使っています。**
`codex` コマンドがあればメニューに自動で表示されます。ツール列に `codex` と書けば（例: `codex	work	cxw	会社`）Codex アカウントも複数使えます。

**メニューが出るまで数秒かかります。**
各アカウントに残り枠を問い合わせている時間です（1アカウント約3秒、並列）。モデルは呼ばないのでトークンは消費しません。

**Claude Code の画面下に今のアカウントと残り枠を表示したい。**
インストールすると既定で有効です。ステータス行の先頭にこう表示されます。
```
team:me@example.com │ 주간 ██░░░ 38% ↻2일3시간 │ 세션 █░░░░ 12% ↻1시간40분 │ Opus │ ~/proj │ ctx 12% │ git main
```
（`주간` = 週間使用率、`세션` = 5時間セッション使用率、`↻` = リセットまでの時間。）値は Claude Code が直接渡すもので追加コストはありません。70% で黄、90% で赤になります。
自分のステータス行を残したい場合は `install.sh --no-statusline` でインストールしてください。

**新しいアカウントで MCP サーバーが見えません。**
MCP 設定はアカウントごとに別です。そのアカウントで起動した状態で `claude mcp add --scope user …` をやり直してください。

## さらに詳しく

- [仕組みと触ってはいけない箇所](docs/how-it-works.en.md)（英語） — 何を共有し何を分離しているか
- 削除: `~/.zshrc` から ccp の行を消してから `rm -rf ~/projects/ccp ~/.config/ccp ~/.claude-profiles ~/.codex-profiles`
- テスト: `zsh tests/test_ccp_zsh.sh` · `python3 -m pytest tests`

MIT License
