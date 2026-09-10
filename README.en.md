<p align="right"><a href="README.md">한국어</a> · <b>English</b> · <a href="README.ja.md">日本語</a> · <a href="README.zh-CN.md">中文</a></p>

# ccp

A zsh tool for switching between several Claude Code accounts without logging out and back in.

When one account hits its quota you move to another, and **conversation history, settings and skills carry over**.
One screen shows how much each account has left. Codex CLI accounts appear in the same menu.

```
  Claude
  ── available now ────────────────────────────────────
  ▸ 2) team       ← recommended · 62% weekly left · resets in 2d
    0) default    85% weekly left · resets in 5d
  ── blocked · frees up when the session window resets ─
    1) personal   ⏳ session exhausted — 2h12m to go
```

Type `ccp` to get this screen; Enter alone opens the account with the most room right now.

## Getting started

Requirements: macOS or Linux, zsh (default on macOS), python3 (ships with macOS), and Claude Code already installed.

Paste these three lines into a terminal.

```bash
git clone https://github.com/ssimu/ccp.git ~/projects/ccp
~/projects/ccp/install.sh
source ~/.zshrc
```

The installer adds one line to `~/.zshrc` and creates a config file. Running it again is safe.
It never copies login tokens; you log in yourself in step 3.

### 1. Write down your accounts

Open `~/.config/ccp/profiles.tsv`. It contains an example; replace it with your accounts.
One line per account, columns separated by **tabs**.

```
# tool      name        alias  note
claude      team        cct    work account
claude      personal    ccm    personal account
```

- **name** becomes the profile directory name. ASCII recommended.
- **alias** is a short command: typing `cct` opens that account directly. Optional.
- Do not list the `~/.claude` account you already use. It is always item 0, "기본" (default).

The number of lines is the number of accounts.

### 2. Create them

```bash
ccp-sync
```

Creates a profile directory for each line in the TSV.

### 3. Log in once per account

```bash
ccp
```

Pick an account in the menu and Claude Code opens as that account. The first time it reports you are not logged in,
so run `/login` there. Repeat for each account.

## Usage

| Type this | And this happens |
|---|---|
| `ccp` | The menu. Arrow keys to choose, Enter to open. **Just Enter opens the recommended account** |
| `ccp team` or `cct` | Straight into that account |
| `ccp team -c` | That account, **continuing your last conversation**. This is the one you use when a quota runs out |
| `ccp-usage` | Remaining quota only, no menu |
| `ccp-ls` | Who is logged in where |
| `ccp-new name alias` | One more account |
| `ccp-edit name new-name new-alias` | Rename / change alias. The folder moves too, so the login is kept |
| `ccp-rm name` | Remove an account. Only its login goes away; history stays |

In the menu: `↑↓` (or `j` `k`) to move, a digit jumps to that number, `v` toggles graph and table, `q` leaves.
You can also manage accounts right there: `a` adds one, `e` on the selected line renames it or changes its alias, `d` removes it. Answer a few prompts and you are back in the menu.

The status line at the bottom of Claude Code always shows the current account and remaining quota.

```
team:me@example.com │ Opus │ 주간 ████░░┃░░░ 38% │ 세션 █░░░░░┃░░░ 12% │ Fable █████░┃░░░ 47% │ ~/proj │ ctx 12% │ git main
```

`주간` is the weekly window, `세션` the 5-hour one. The `┃` inside a bar is where you are in that window: nearer the right edge means closer to reset, and a bar that stops short of `┃` means you are under pace (same reading as the ccp menu). Yellow from 70% used, red from 90%.
Set `show_reset = yes` in `statusline.conf` to also print the time until reset.
Weekly and session come straight from Claude Code. The **model-only weekly quota** (e.g. Fable) is not handed to the status line,
so ccp shows its cached `/usage` lookup as `Fable ██░░░ 47%`, refreshed in the background every 10 minutes; a trailing `~` marks a stale value.

## FAQ

**Do I lose my conversation when I switch?**
No. History, settings and skills are shared by all accounts; only the login differs.
When a quota runs out, `ccp team -c` on another account continues the same conversation. That is the main use case.

**Does checking the quota cost credits or tokens?**
No. None of the three paths calls a model.
- Status line: it only reads the `rate_limits` values Claude Code already hands to the status line script. No request is made.
- Claude accounts in the menu: `claude -p /usage`. `/usage` is a built-in command that queries the usage API and sends nothing to the model.
  Its JSON output confirms it: 0 model turns, 0 USD, 0 input and output tokens.
- Codex accounts in the menu: two read-only requests to `codex app-server` (account and rate limits).
The few seconds before the menu appears are network round trips; they do not count against your quota.

**I want to add, remove or rename accounts.**
Three ways, same result.
- In the menu: `ccp` → `a` to add, select a line and `e` to edit, `d` to remove.
- Commands: `ccp-new name alias`, `ccp-edit name new-name new-alias`, `ccp-rm name`.
- File: edit `~/.config/ccp/profiles.tsv`, then `ccp-sync`. Folders of removed lines go with `ccp-rm` or `rm -rf ~/.claude-profiles/<name>`.
Removing an account deletes only its login; history and settings stay. Item 0, the default, cannot be removed or renamed.

**I always run with `--dangerously-skip-permissions`.**
Uncomment this line in `~/.config/ccp/config.zsh`. Make sure you know what the flag disables.
```zsh
CCP_CLAUDE_ARGS=(--dangerously-skip-permissions)
```

**I use Codex too.**
If the `codex` command exists, it appears in the menu automatically. For several Codex accounts,
put `codex` in the tool column. A Codex profile is **one workspace**: make one profile for your personal workspace and one per team,
and when you run `CODEX_HOME=~/.codex-profiles/<name> codex login` in each, pick that workspace on the browser approval screen.
Quotas are per workspace even under the same ChatGPT login. The installer also puts **model, 5-hour limit, weekly limit and context**
into Codex's own footer via `[tui] status_line` in `~/.codex/config.toml` (left alone if already set); change the items with `/statusline`
inside Codex. Codex cannot run an external status line script, so the ccp profile name cannot appear there; use the ccp menu for that.
Codex does not report the workspace name, so the menu shows only your
profile name and the plan (pro/team). If two profiles show the same email, plan and usage, they are logged into the same workspace;
run `codex login` again in one of them and choose the other workspace. Example line: `codex	work	cxw	company workspace`

**The menu takes a few seconds.**
That is the quota lookup per account: about 3 seconds each, run in parallel, so the total is about the same. As noted above, it costs no credits.

**Can I change the menu language?**
Menu, messages and status line come in English, 한국어, 日本語 and 中文. The default follows your terminal locale (`LANG`);
set `CCP_LANG=en` in `~/.config/ccp/config.zsh` to pin it, or `CCP_LANG=ja ccp` for a one-off.

**Can I change what the status line shows?**
Yes, in `~/.config/ccp/statusline.conf`: which pieces and in what order, the separator, bar width and characters, used vs remaining %,
color thresholds, how the account is shown. Preview while editing with `ccp-statusline`. A few examples:
```
segments = account weekly session      # quota only, no model/dir/git
bar = 0                                # numbers only
percent = left                         # remaining instead of used
account = "{profile}"                  # hide the email
format = "{account} · {weekly} · {session} ▏{dir}"   # free-form template
```
For something completely different, create `~/.config/ccp/statusline.sh` and it runs instead.

**I already have a status line.**
Install with `install.sh --no-statusline` and it is left untouched.

**My MCP servers are missing on the new account.**
MCP settings live in each account's `.claude.json`. Open that account and run `claude mcp add --scope user …` again.

## Troubleshooting

- "command not found: ccp" → open a new terminal or `source ~/.zshrc`
- Your account is not in the menu → you skipped `ccp-sync`
- It says 미로그인 (not logged in) → `ccp <name>`, then `/login`
- An alias does not work → it clashes with an existing command like `cp`. You get a warning when the terminal opens. Pick another name
- Still stuck → open an issue with the command you ran and its output

## More

- [How it works and what not to touch](docs/how-it-works.en.md) — what is shared, what is kept apart, and why
- Uninstall: remove the ccp line from `~/.zshrc`, then `rm -rf ~/projects/ccp ~/.config/ccp ~/.claude-profiles ~/.codex-profiles`. Your `~/.claude` stays as it was.
- Tests: `zsh tests/test_ccp_zsh.sh` · `python3 -m pytest tests`

MIT License
