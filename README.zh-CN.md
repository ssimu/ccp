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
team:me@example.com │ Opus │ 주간 ████░░┃░░░ 38% │ 세션 █░░░░░┃░░░ 12% │ Fable █████░┃░░░ 47% │ ~/proj │ ctx 12% │ git main
```

`주간` 是本周窗口，`세션` 是 5 小时窗口。条内的 `┃` 是你在该窗口中的当前位置：越靠右越接近重置，条没到 `┃` 说明用得比进度慢（和 ccp 菜单一样的读法）。70% 起变黄，90% 起变红。
想同时显示距重置的时间，在 `statusline.conf` 里设 `show_reset = yes`。
本周和会话由 Claude Code 直接提供。像 Fable 这样的 **按模型的本周额度** 不会传给状态栏，
所以 ccp 把 `/usage` 查到的值缓存后接着显示为 `Fable ██░░░ 47%`，每 10 分钟后台刷新，过期的值带 `~`。

## 常见问题

**换账号会丢掉对话吗？**
不会。对话记录、设置、技能在所有账号间共享，只有登录不同。
额度用完时，换个账号 `ccp team -c` 就能继续同一个对话。这是主要用途。

**查询额度会消耗积分或 token 吗？**
不会。三条路径都不调用模型。
- 状态栏：只读取 Claude Code 传给状态栏脚本的 `rate_limits` 值，根本没有发请求。
- 菜单里的 Claude 账号：执行 `claude -p /usage`。`/usage` 是内置命令，只查询用量 API，不向模型发送任何内容。
  JSON 输出可以证实：模型轮次 0、费用 0 USD、输入输出 token 均为 0。
- 菜单里的 Codex 账号：只向 `codex app-server` 发两个只读请求（账号和限额）。
菜单出现前的几秒是网络往返时间，不计入额度。

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
把工具列写成 `codex`。Codex 配置以 **工作区** 为单位：个人工作区一个、每个团队一个，在各配置里执行
`CODEX_HOME=~/.codex-profiles/名称 codex login` 时，在浏览器授权页选择对应工作区。同一个 ChatGPT 账号下各工作区的额度也是分开的。安装时会在 `~/.codex/config.toml` 的 `[tui] status_line` 里加入 **模型、5 小时额度、本周额度、上下文**，
所以 Codex 自己的底栏也能看到（已有设置则不动）。要改项目，在 Codex 里用 `/statusline`。Codex 不能挂外部状态栏脚本，所以 ccp 的配置（账号）名
无法显示在那里，当前账号请看 ccp 菜单。
Codex 不返回工作区名称，菜单里只显示配置名和套餐（pro/team）。若两个配置的邮箱、套餐、用量完全相同，说明登录的是同一个工作区，
在其中一个里重新 `codex login` 选另一个工作区即可。例如：`codex	work	cxw	公司工作区`

**菜单要等几秒才出来。**
那是在查询每个账号的剩余额度：每个约 3 秒，并行执行，总时间也差不多。如上所述，不消耗积分。

**想换菜单语言。**
菜单、提示信息和状态栏支持 中文、English、한국어、日本語。默认跟随终端语言环境（`LANG`），
在 `~/.config/ccp/config.zsh` 里写 `CCP_LANG=zh` 可固定；只想临时切换用 `CCP_LANG=en ccp`。

**想改状态栏的样子。**
在 `~/.config/ccp/statusline.conf` 里设置：显示哪些部分及顺序、分隔符、进度条宽度和字符、已用还是剩余百分比、变色阈值、账号显示格式。
边改边用 `ccp-statusline` 预览。几个例子：
```
segments = account weekly session      # 只看额度，不要模型/目录/git
bar = 0                                # 只要数字
percent = left                         # 显示剩余而不是已用
account = "{profile}"                  # 隐藏邮箱
format = "{account} · {weekly} · {session} ▏{dir}"   # 用模板代替顺序
```
想完全换一套，创建 `~/.config/ccp/statusline.sh`，它会代替内置的运行。

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
