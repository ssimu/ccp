<p align="right"><a href="README.md">한국어</a> · <b>English</b> · <a href="README.ja.md">日本語</a> · <a href="README.zh-CN.md">中文</a></p>

# ccp

Hi. ccp is a small tool I built after getting tired of juggling several Claude Code accounts.

You know the moment: you are deep in a task on your work account, the quota runs out, and you would love to hop over
to your personal account. But `/logout`, `/login`, browser approval… and by then the thread of the conversation is gone.
So I made something that **switches accounts while keeping the conversation, and shows how much each account has left at a glance.**

```
  Claude
  ── available now ────────────────────────────────────
  ▸ 2) team       ← recommended · 62% weekly left · resets in 2d
    0) default    85% weekly left · resets in 5d
  ── blocked · frees up when the session window resets ─
    1) personal   ⏳ session exhausted — 2h12m to go
```

Type `ccp`, this screen appears, and hitting Enter opens the account with the most room right now.
If you use Codex CLI, those accounts show up on the same screen.

> One honest note: the menu text is in Korean for now. Everything below works the same regardless of your locale.

## Getting started

You need three things: macOS or Linux, zsh (the default on macOS), and Claude Code already installed.
python3 too, but it ships with macOS.

Paste these three lines into a terminal.

```bash
git clone https://github.com/ssimu/ccp.git ~/projects/ccp
~/projects/ccp/install.sh
source ~/.zshrc
```

The installer only adds one line to `~/.zshrc` and creates a config file, so running it twice is harmless.
It never copies login tokens anywhere. You will do that part yourself in a minute.

### 1. Write down your accounts

Open `~/.config/ccp/profiles.tsv`. It comes with an example; replace it with your own.
One line per account, columns separated by **tabs**.

```
# tool      name        alias  note
claude      team        cct    work account
claude      personal    ccm    personal account
```

- **name** is anything you will recognize. ASCII is easiest.
- **alias** is a short command. Typing `cct` opens that account directly. Leave it blank if you do not care.
- Do not list the `~/.claude` account you already use. It is always item 0, "기본" (default).

Two accounts or five, just match the number of lines.

### 2. Create them

```bash
ccp-sync
```

This creates a folder for each account you listed.

### 3. Log in once per account

```bash
ccp
```

Pick an account in the menu and Claude Code opens as that account. The first time it will say you are not logged in,
so run `/login` there. Repeat for each account and you are done.

## Day to day

| Type this | And this happens |
|---|---|
| `ccp` | The menu. Arrow keys to choose, Enter to open. **Just Enter opens the recommended account** |
| `ccp team` or `cct` | Straight into that account |
| `ccp team -c` | That account, **continuing your last conversation**. This is the one you use when a quota runs out |
| `ccp-usage` | Just peek at the remaining quota, no menu |
| `ccp-ls` | Who is logged in where |
| `ccp-new name alias` | One more account |

In the menu: `↑↓` (or `j` `k`) to move, a digit jumps to that number, `v` toggles graph and table, `q` leaves.

And the status line at the bottom of Claude Code always shows which account you are on and how much is left.

```
team:me@example.com │ 주간 ██░░░ 38% ↻2일3시간 │ 세션 █░░░░ 12% ↻1시간40분 │ Opus │ ~/proj │ ctx 12% │ git main
```

`주간` is the weekly window, `세션` the 5-hour one, `↻` the time until reset. It turns yellow past 70% and red past 90%, so a glance is enough.

## Questions people ask

**Do I lose my conversation when I switch?**
No. History, settings and skills are shared by every account. Only the login differs.
That is why, when a quota runs out, `ccp team -c` on another account picks up right where you were. It is the whole reason this exists.

**I want more (or fewer) accounts.**
Add or remove lines in `profiles.tsv`, then `ccp-sync`. To also remove the folder of a deleted account: `rm -rf ~/.claude-profiles/<name>`.
Only that account's login goes away; the history stays.

**I always run with `--dangerously-skip-permissions`.**
Open `~/.config/ccp/config.zsh` and uncomment this line. Only if you know what it does.
```zsh
CCP_CLAUDE_ARGS=(--dangerously-skip-permissions)
```

**I use Codex too.**
If the `codex` command exists, it appears in the menu automatically. For several Codex accounts,
put `codex` in the tool column: `codex	work	cxw	company workspace`

**The menu takes a few seconds.**
That is ccp asking each account how much is left. About 3 seconds per account, but asked in parallel, so the total is about the same.
It does not call a model, so it costs no tokens.

**I already have a status line I like.**
Install with `install.sh --no-statusline` and yours is left alone.

**My MCP servers are missing on the new account.**
MCP settings are per account. Open that account and run `claude mcp add --scope user …` once more.

## When something is off

- "command not found: ccp" → open a new terminal or `source ~/.zshrc`
- Your account is not in the menu → you skipped `ccp-sync`
- It says 미로그인 (not logged in) → `ccp <name>`, then `/login`
- An alias does not work → it clashes with an existing command like `cp`. You get a warning when the terminal opens. Pick another name
- Still stuck → open an issue here and include what you typed and what came back

## Want to know more?

- [How it works and what not to touch](docs/how-it-works.en.md) — what is shared, what is kept apart, and why
- Uninstall: remove the ccp line from `~/.zshrc`, then `rm -rf ~/projects/ccp ~/.config/ccp ~/.claude-profiles ~/.codex-profiles`. Your `~/.claude` stays as it was.
- Tests: `zsh tests/test_ccp_zsh.sh` · `python3 -m pytest tests`

MIT License. Use it, change it, share it.
