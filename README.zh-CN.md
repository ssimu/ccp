<p align="right"><a href="README.md">한국어</a> · <a href="README.en.md">English</a> · <a href="README.ja.md">日本語</a> · <b>中文</b></p>

# ccp

你好。ccp 是我在同时用好几个 Claude Code 账号、被折腾够了之后写的一个小工具。

你大概也遇到过：用公司账号干得正投入，额度突然用完了，想换到个人账号继续。
可是 `/logout`、`/login`、浏览器授权……一套下来，刚才对话的思路已经断了。
所以我做了这个：**换账号时对话不断，而且每个账号还剩多少额度一眼就能看到。**

```
  Claude
  ── 现在可用 ─────────────────────────────────────────
  ▸ 2) team       ← 推荐 · 本周剩余 62% · 2 天后重置
    0) 기본       本周剩余 85% · 5 天后重置
  ── 暂不可用 · 会话窗口重置后恢复 ─────────────────────
    1) personal   ⏳ 会话额度用尽 — 2 小时 12 分后恢复
```

敲一下 `ccp` 就出现这个界面，直接按 Enter 就用当前最宽裕的账号启动。
如果你也用 Codex CLI，那些账号会出现在同一个界面里。

> 坦白说一句：菜单文字目前是韩文。下面的命令在任何语言环境下都一样能用。

## 开始

需要三样东西：macOS 或 Linux、zsh（macOS 默认就是）、以及已经装好的 Claude Code。
还要 python3，macOS 自带。

把这三行贴进终端。

```bash
git clone https://github.com/ssimu/ccp.git ~/projects/ccp
~/projects/ccp/install.sh
source ~/.zshrc
```

安装脚本只做两件事：往 `~/.zshrc` 加一行，再生成一个配置文件。多跑几次也没关系。
它不会把登录凭据复制到任何地方，那一步稍后由你自己完成。

### 1. 写下你的账号

打开 `~/.config/ccp/profiles.tsv`。里面有个示例，换成你自己的就行。
一行一个账号，列之间用 **Tab** 分隔。

```
# 工具       名称        别名   备注
claude      team        cct    公司账号
claude      personal    ccm    个人账号
```

- **名称** 只要你自己认得出来就行，英文最省事。
- **别名** 是个短命令。输入 `cct` 就直接用那个账号启动。懒得起就留空。
- 不要写你现在正在用的 `~/.claude` 账号，它永远是 0 号「기본（默认）」。

两个账号还是五个账号，行数对上就好。

### 2. 创建

```bash
ccp-sync
```

它会按你写的内容为每个账号建一个文件夹。

### 3. 每个账号登录一次

```bash
ccp
```

在菜单里选一个账号，Claude Code 就以该账号打开。第一次会提示你还没登录，
在里面执行 `/login` 就行。每个账号重复一遍，准备工作就结束了。

## 平时这样用

| 这样敲 | 就会这样 |
|---|---|
| `ccp` | 出菜单。方向键选，Enter 启动。**直接 Enter 就用推荐账号** |
| `ccp team` 或 `cct` | 直接进那个账号 |
| `ccp team -c` | 用那个账号 **接着上一次对话**。额度用完要换号时用这个 |
| `ccp-usage` | 不进菜单，只瞄一眼剩余额度 |
| `ccp-ls` | 每个账号登录的是谁 |
| `ccp-new 名称 别名` | 再加一个账号 |

菜单里用 `↑↓`（或 `j` `k`）移动，按数字跳到对应编号，`v` 切换图形和表格，`q` 退出。

Claude Code 底部的状态栏会一直显示你当前在哪个账号、还剩多少。

```
team:me@example.com │ 주간 ██░░░ 38% ↻2일3시간 │ 세션 █░░░░ 12% ↻1시간40분 │ Opus │ ~/proj │ ctx 12% │ git main
```

`주간` 是本周窗口，`세션` 是 5 小时窗口，`↻` 是距重置的时间。超过 70% 变黄，超过 90% 变红，扫一眼就够了。

## 常有人问

**换账号会丢掉对话吗？**
不会。对话记录、设置、技能在所有账号间是同一份，只有登录不同。
所以额度用完时，换个账号 `ccp team -c` 就能从刚才的地方接着来。这正是做这个工具的初衷。

**想增加或减少账号。**
在 `profiles.tsv` 里加行或删行，然后 `ccp-sync`。要连删掉的账号的文件夹也清掉：`rm -rf ~/.claude-profiles/名称`。
只会删掉那个账号的登录，对话记录还在。

**我一直用 `--dangerously-skip-permissions` 启动。**
打开 `~/.config/ccp/config.zsh`，把这一行的注释去掉。请确认你知道它的含义。
```zsh
CCP_CLAUDE_ARGS=(--dangerously-skip-permissions)
```

**我也用 Codex。**
只要有 `codex` 命令，它就会自动出现在菜单里。想用多个 Codex 账号，
把工具列写成 `codex`，例如：`codex	work	cxw	公司工作区`

**菜单要等几秒才出来。**
那是在逐个问账号「还剩多少」。每个约 3 秒，但是并行问的，所以总共也差不多。
不会调用模型，不消耗 token。

**我本来就有自己的状态栏。**
用 `install.sh --no-statusline` 安装，就不会碰你的状态栏。

**新账号里看不到 MCP 服务器。**
MCP 设置是按账号分开的。用那个账号启动后再执行一次 `claude mcp add --scope user …`。

## 哪里不对劲的时候

- 提示找不到 `ccp` → 开个新终端，或 `source ~/.zshrc`
- 菜单里没有我的账号 → 忘了跑 `ccp-sync`
- 显示「미로그인（未登录）」→ `ccp 名称` 打开后 `/login`
- 别名不管用 → 和 `cp` 之类已有命令重名了。开终端时会有警告。换个名字
- 还是不行 → 来仓库开个 issue，附上你敲了什么、返回了什么

## 想了解更多

- [工作原理与不可触碰的部分](docs/how-it-works.en.md)（英文） — 哪些共享、哪些分开，以及为什么
- 卸载：从 `~/.zshrc` 删掉 ccp 那一行，然后 `rm -rf ~/projects/ccp ~/.config/ccp ~/.claude-profiles ~/.codex-profiles`。`~/.claude` 原样保留。
- 测试：`zsh tests/test_ccp_zsh.sh` · `python3 -m pytest tests`

MIT License。随便用、随便改、随便分享。
