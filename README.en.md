<p align="right"><a href="README.md">한국어</a> · <b>English</b> · <a href="README.ja.md">日本語</a> · <a href="README.zh-CN.md">中文</a></p>

# ccp

**Account switcher for people who use more than one Claude Code account.**
Switch accounts without logging out and in, and see how much quota each account has left on one screen.
Codex CLI accounts show up too.

```
  Claude
  ── available now ────────────────────────────────────
  ▸ 2) team       ← recommended · 62% weekly left · resets in 2d
    0) default    85% weekly left · resets in 5d
  ── blocked · frees up when the session window resets ─
    1) personal   ⏳ session exhausted — 2h12m to go
```

> The menu itself is currently in Korean. The commands below work the same in any locale.

## Who this is for

- You alternate between a work account and a personal one
- When one account hits its limit you want to move to another **and keep the conversation going**
- You are tired of `/logout` `/login`

## Install (3 minutes)

You need: macOS or Linux, zsh, python3, and [Claude Code](https://docs.anthropic.com/claude-code) already installed.

```bash
git clone https://github.com/ssimu/ccp.git ~/projects/ccp
~/projects/ccp/install.sh
source ~/.zshrc
```

Then three steps.

**1. List your accounts** — open `~/.config/ccp/profiles.tsv`, one account per line. Columns are separated by **tabs**.

```
# tool      name        alias  note
claude      team        cct    work account
claude      personal    ccm    personal account
```

- name: anything you will recognize (ASCII recommended)
- alias: a short command. Typing `cct` opens that account directly. Optional.
- Do not list your existing `~/.claude` account. It is always item 0, "기본" (default).

**2. Create the profile directories**

```bash
ccp-sync
```

**3. Log in once per account**

```bash
ccp            # pick an account in the menu → when it opens, run /login
```

From now on, pick with `ccp` or jump straight in with an alias like `cct`.

## Everyday commands

| Command | What it does |
|---|---|
| `ccp` | Menu. Arrow keys to choose, Enter to open. **Enter alone opens the recommended account** |
| `ccp team` / `cct` | Open by name or alias |
| `ccp team -c` | Open that account and **continue the last conversation** (anything after the name is passed to claude) |
| `ccp-usage` | Just the remaining quota, no menu |
| `ccp-ls` | Who is logged in on each profile |
| `ccp-new name alias` | Add an account (also appended to the TSV) |

Menu keys: `↑↓` or `j` `k` move · a digit jumps to that number · `v` graph↔table · `q` cancel

## FAQ

**Do I lose my conversation history when I switch?**
No. History, settings and skills are shared by every account. Only the login differs. That is why you can run `ccp team -c` on another account and pick up where you left off.

**How do I add or remove accounts?**
Add or delete lines in `profiles.tsv`, then `ccp-sync`. To remove the directory of a deleted line: `rm -rf ~/.claude-profiles/<name>`.

**I always want `--dangerously-skip-permissions`.**
Uncomment this line in `~/.config/ccp/config.zsh`. Know what it does before you turn it on.
```zsh
CCP_CLAUDE_ARGS=(--dangerously-skip-permissions)
```

**I use Codex too.**
If the `codex` command exists it appears in the menu automatically. Put `codex` in the tool column, e.g. `codex	work	cxw	company`, to have several Codex accounts.

**The menu takes a few seconds to appear.**
That is the time spent asking each account for its remaining quota (about 3 s per account, in parallel). No model call is made, so it costs no tokens.

**I want to see which account I am on, and how much quota is left, at the bottom of Claude Code.**
It is on by default after install. The status line starts with:
```
team:me@example.com │ 주간 ██░░░ 38% ↻2일3시간 │ 세션 █░░░░ 12% ↻1시간40분 │ Opus │ ~/proj │ ctx 12% │ git main
```
(`주간` = weekly used, `세션` = 5-hour session used, `↻` = time until reset.) The numbers come straight from Claude Code, so there is no extra cost. Colors turn yellow at 70% and red at 90%.
To keep your own status line, install with `install.sh --no-statusline`.

**My MCP servers are missing on the new account.**
MCP settings live per account. Open that account and run `claude mcp add --scope user …` again.

## More

- [How it works and what not to touch](docs/how-it-works.en.md) — what is shared, what is separated, and why
- Uninstall: delete the ccp line from `~/.zshrc`, then `rm -rf ~/projects/ccp ~/.config/ccp ~/.claude-profiles ~/.codex-profiles`
- Tests: `zsh tests/test_ccp_zsh.sh` · `python3 -m pytest tests`

MIT License
