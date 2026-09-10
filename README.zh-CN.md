<p align="right"><a href="README.md">한국어</a> · <a href="README.en.md">English</a> · <a href="README.ja.md">日本語</a> · <b>中文</b></p>

# ccp

在多个 Claude Code 账号之间切换、无需登出再登录的 zsh 工具。

一个账号额度用完后换到另一个，**对话记录、设置和技能原样保留**。
一个界面就能看到每个账号还剩多少额度。Codex CLI 账号也出现在同一菜单里。

```
  Claude
  ── 现在可用 ─────────────────────────────────────────
  ▸ 2) team       ← 推荐 · 本周剩余 62% · 2 天后重置
    0) 기본       本周剩余 85% · 5 天后重置
  ── 暂不可用 · 会话窗口重置后恢复 ─────────────────────
    1) personal   ⏳ 会话额度用尽 — 2 小时 12 分后恢复
```

输入 `ccp` 出现这个界面，直接按 Enter 就用当前最宽裕的账号启动。

> 菜单文字目前是韩文。下面的命令在任何语言环境下都一样。

## 开始

需要：macOS 或 Linux、zsh（macOS 默认）、python3（macOS 自带）、已安装的 Claude Code。

把这三行贴进终端。

```bash
git clone https://github.com/ssimu/ccp.git ~/projects/ccp
~/projects/ccp/install.sh
source ~/.zshrc
```

安装脚本只往 `~/.zshrc` 加一行并生成配置文件，重复运行是安全的。
它不会复制任何登录凭据，登录在第 3 步由你自己完成。

### 1. 写下你的账号

打开 `~/.config/ccp/profiles.tsv`，里面有示例，换成你的账号。
一行一个账号，列之间用 **Tab** 分隔。

```
# 工具       名称        别名   备注
claude      team        cct    公司账号
claude      personal    ccm    个人账号
```

- **名称**：会成为配置目录名。建议英文。
- **别名**：短命令，输入 `cct` 就直接用该账号启动。可留空。
- 不要写你现在正在用的 `~/.claude` 账号，它永远是 0 号「기본（默认）」。

行数就是账号数。

### 2. 创建

```bash
ccp-sync
```

按 TSV 内容为每个账号创建配置目录。

### 3. 每个账号登录一次

```bash
ccp
```

在菜单里选一个账号，Claude Code 以该账号打开。第一次会提示未登录，
在里面执行 `/login`。每个账号重复一遍。

## 用法

| 这样敲 | 就会这样 |
|---|---|
| `ccp` | 出菜单。方向键选，Enter 启动。**直接 Enter 就用推荐账号** |
| `ccp team` 或 `cct` | 直接进那个账号 |
| `ccp team -c` | 用那个账号 **接着上一次对话**。额度用完要换号时用这个 |
| `ccp-usage` | 不进菜单，只看剩余额度 |
| `ccp-ls` | 每个账号登录的是谁 |
| `ccp-new 名称 别名` | 再加一个账号 |

菜单里用 `↑↓`（或 `j` `k`）移动，按数字跳到对应编号，`v` 切换图形和表格，`q` 退出。

Claude Code 底部状态栏始终显示当前账号和剩余额度。

```
team:me@example.com │ 주간 ██░░░ 38% ↻2일3시간 │ 세션 █░░░░ 12% ↻1시간40분 │ Opus │ ~/proj │ ctx 12% │ git main
```

`주간` 是本周窗口，`세션` 是 5 小时窗口，`↻` 是距重置的时间。70% 起变黄，90% 起变红。

## 常见问题

**换账号会丢掉对话吗？**
不会。对话记录、设置、技能在所有账号间共享，只有登录不同。
额度用完时，换个账号 `ccp team -c` 就能继续同一个对话。这是主要用途。

**想增加或减少账号。**
在 `profiles.tsv` 里加行或删行，然后 `ccp-sync`。要连删掉的账号的文件夹也清掉：`rm -rf ~/.claude-profiles/名称`。
只会删掉那个账号的登录，对话记录还在。

**我一直用 `--dangerously-skip-permissions` 启动。**
在 `~/.config/ccp/config.zsh` 里取消这一行的注释。请先弄清这个参数关掉的是什么。
```zsh
CCP_CLAUDE_ARGS=(--dangerously-skip-permissions)
```

**我也用 Codex。**
只要有 `codex` 命令，它就会自动出现在菜单里。想用多个 Codex 账号，
把工具列写成 `codex`，例如：`codex	work	cxw	公司工作区`

**菜单要等几秒才出来。**
那是在查询每个账号的剩余额度：每个约 3 秒，并行执行，总时间也差不多。
不调用模型，不消耗 token。

**我已经有状态栏了。**
用 `install.sh --no-statusline` 安装就不会改动它。

**新账号里看不到 MCP 服务器。**
MCP 设置在每个账号各自的 `.claude.json` 里。用那个账号启动后重新执行 `claude mcp add --scope user …`。

## 排错

- 提示找不到 `ccp` → 开个新终端，或 `source ~/.zshrc`
- 菜单里没有我的账号 → 忘了跑 `ccp-sync`
- 显示「미로그인（未登录）」→ `ccp 名称` 打开后 `/login`
- 别名不管用 → 和 `cp` 之类已有命令重名了。开终端时会有警告。换个名字
- 还是不行 → 开 issue，附上执行的命令和输出

## 更多

- [工作原理与不可触碰的部分](docs/how-it-works.en.md)（英文） — 哪些共享、哪些分开，以及为什么
- 卸载：从 `~/.zshrc` 删掉 ccp 那一行，然后 `rm -rf ~/projects/ccp ~/.config/ccp ~/.claude-profiles ~/.codex-profiles`。`~/.claude` 原样保留。
- 测试：`zsh tests/test_ccp_zsh.sh` · `python3 -m pytest tests`

MIT License
