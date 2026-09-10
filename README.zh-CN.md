<p align="right"><a href="README.md">한국어</a> · <a href="README.en.md">English</a> · <a href="README.ja.md">日本語</a> · <b>中文</b></p>

# ccp

**给同时使用多个 Claude Code 账号的人的切换工具。**
不用登出再登录就能切换账号，并在一个界面里看到每个账号还剩多少额度。
Codex CLI 的账号也会一起显示。

```
  Claude
  ── 现在可用 ─────────────────────────────────────────
  ▸ 2) team       ← 推荐 · 本周剩余 62% · 2 天后重置
    0) 기본       本周剩余 85% · 5 天后重置
  ── 暂不可用 · 会话窗口重置后恢复 ─────────────────────
    1) personal   ⏳ 会话额度用尽 — 2 小时 12 分后恢复
```

> 菜单界面目前是韩文。下面的命令在任何语言环境下都一样。

## 适合谁

- 在公司账号和个人账号之间来回切换
- 一个账号额度用完后，想换到另一个账号 **继续刚才的对话**
- 厌倦了反复 `/logout` `/login`

## 安装（3 分钟）

需要：macOS 或 Linux、zsh、python3，并已安装 [Claude Code](https://docs.anthropic.com/claude-code)。

```bash
git clone https://github.com/ssimu/ccp.git ~/projects/ccp
~/projects/ccp/install.sh
source ~/.zshrc
```

然后只需三步。

**1. 填写你的账号** — 打开 `~/.config/ccp/profiles.tsv`，一行一个账号。列之间用 **Tab** 分隔。

```
# 工具       名称        别名   备注
claude      team        cct    公司账号
claude      personal    ccm    个人账号
```

- 名称：你自己认得出来就行（建议用英文）
- 别名：一个短命令。输入 `cct` 就直接用该账号启动。可留空。
- 不要写已有的 `~/.claude` 账号，它永远是 0 号「기본（默认）」。

**2. 创建配置目录**

```bash
ccp-sync
```

**3. 每个账号登录一次**

```bash
ccp            # 在菜单里选账号 → 启动后执行 /login
```

之后用 `ccp` 选择，或用 `cct` 这样的别名直接启动。

## 常用命令

| 命令 | 作用 |
|---|---|
| `ccp` | 菜单。方向键选择，Enter 启动。**只按 Enter 会用推荐账号**启动 |
| `ccp team` / `cct` | 按名称或别名直接启动 |
| `ccp team -c` | 用该账号 **继续上一次对话**（名称后面的参数原样传给 claude） |
| `ccp-usage` | 不进菜单，只看剩余额度 |
| `ccp-ls` | 每个配置登录的是谁 |
| `ccp-new 名称 别名` | 添加账号（同时写入 TSV） |

菜单按键：`↑↓` 或 `j` `k` 移动 · 数字 = 跳到该编号 · `v` 图形↔表格 · `q` 取消

## 常见问题

**切换账号会丢失对话记录吗？**
不会。对话记录、设置和技能在所有账号间共享，只有登录信息不同。所以额度用完时可以用另一个账号 `ccp team -c` 接着聊。

**如何增减账号？**
在 `profiles.tsv` 里增删行，然后 `ccp-sync`。要连目录一起删：`rm -rf ~/.claude-profiles/名称`。

**我想一直带 `--dangerously-skip-permissions` 启动。**
在 `~/.config/ccp/config.zsh` 里取消这一行的注释。请先弄清它的含义再开启。
```zsh
CCP_CLAUDE_ARGS=(--dangerously-skip-permissions)
```

**我也用 Codex。**
只要有 `codex` 命令，它就会自动出现在菜单里。把工具列写成 `codex`（例如 `codex	work	cxw	公司`）即可使用多个 Codex 账号。

**菜单要等几秒才出来。**
那是在向每个账号查询剩余额度（每个约 3 秒，并行进行）。不会调用模型，不消耗 token。

**想在 Claude Code 底部看到当前账号和剩余额度。**
安装后默认开启。状态栏开头会显示：
```
team:me@example.com │ 주간 ██░░░ 38% ↻2일3시간 │ 세션 █░░░░ 12% ↻1시간40분 │ Opus │ ~/proj │ ctx 12% │ git main
```
（`주간` = 本周已用，`세션` = 5 小时会话已用，`↻` = 距重置时间。）数值由 Claude Code 直接提供，无额外开销。70% 变黄，90% 变红。
想保留自己原来的状态栏，请用 `install.sh --no-statusline` 安装。

**新账号里看不到 MCP 服务器。**
MCP 设置是按账号分开的。用该账号启动后重新执行 `claude mcp add --scope user …`。

## 进一步了解

- [工作原理与不可触碰的部分](docs/how-it-works.en.md)（英文） — 哪些共享、哪些分离，以及原因
- 卸载：从 `~/.zshrc` 删掉 ccp 那一行，然后 `rm -rf ~/projects/ccp ~/.config/ccp ~/.claude-profiles ~/.codex-profiles`
- 测试：`zsh tests/test_ccp_zsh.sh` · `python3 -m pytest tests`

MIT License
