# How ccp works (and what not to touch)

[한국어](how-it-works.md) · **English**

## Claude: one config dir per account

`CLAUDE_CONFIG_DIR` separates everything, including authentication. Run claude with an empty directory and it says `Not logged in`.
A profile is `~/.claude-profiles/<name>/`. Inside it, only `.claude.json` (auth + MCP) is real; everything else is a symlink back to `~/.claude`.

| | What |
|---|---|
| Separate | `.claude.json` |
| Shared (symlink) | `settings.json` `skills` `plugins` `commands` **`projects` (conversation history)** |

- ⚠ **Never symlink `.claude.json`.** Auth and MCP live in the same file; linking it makes two profiles see the same account.
- ⚠ **Always share `projects`.** The whole point of switching when a quota runs out is continuing the conversation with `-c`.
- ⚠ Inside a profile session `CLAUDE_CONFIG_DIR` stays in the environment and child processes inherit it. When you pick "default", ccp `unset`s it in a subshell first.
- MCP servers are stored in `.claude.json`, so they must be registered and authenticated **per profile** (`claude mcp add --scope user …`).

## Codex: one `CODEX_HOME` per account

codex keeps exactly one account in `auth.json`, so a separate `CODEX_HOME` per profile is the only way.
Only `auth.json` and session/state files are separated; `config.toml` `skills` `plugins` `prompts` `rules` `AGENTS.md` are symlinked to `~/.codex`.
Even with the same ChatGPT login, each workspace needs its own `CODEX_HOME=<dir> codex login`, choosing the workspace in the browser.

- ⚠ If codex rewrites `config.toml` wholesale, the symlink becomes a real file and sharing silently breaks. If a setting only applies on one side, check that link first.

## Where the quota numbers come from

- Claude: `claude -p /usage` per profile, in parallel (about 3 s each). No model call, no tokens.
- Codex: `codex app-server` JSON-RPC (`account/read`, `account/rateLimits/read`), about 1 s, zero tokens.

Each probe emits one 12-column TSV line; `ccp_render.py` reads them all and draws the menu.
Recommendation = among usable accounts, the one whose weekly reset is nearest while it still has the most left (remaining quota disappears at reset, so spend it first). Claude and Codex are ranked separately because their limits mean different things.

## Files

```
ccp.zsh                main — menu, switching, ccp-new, ccp-sync, aliases, Tab completion
ccp_render.py          menu renderer — cards/table, recommendation, interactive keys
ccp_codex.py           codex quota (app-server JSON-RPC → TSV)
statusline.sh          (optional) Claude Code status line
install.sh             installer (idempotent)
profiles.example.tsv   → ~/.config/ccp/profiles.tsv
config.example.zsh     → ~/.config/ccp/config.zsh
tests/                 zsh tests/test_ccp_zsh.sh · python3 -m pytest tests
```

All user state lives outside the repo: `~/.config/ccp/` (settings, menu view), `~/.claude-profiles/`, `~/.codex-profiles/`.

## Status line (optional)

`install.sh` (unless `--no-statusline`) links `statusline.sh` to `~/.claude/statusline-command.sh` and points `statusLine` in `~/.claude/settings.json` at it.
Claude Code then shows `team:me@example.com │ 주간 ██░░░ 38% ↻2일3시간 │ 세션 █░░░░ 12% ↻1시간40분 │ Opus │ ~/proj │ ctx 12% │ git main`.
`주간` is the weekly window and `세션` the 5-hour window, each as used %, a 5-cell bar and `↻` time until reset. The numbers come from the `rate_limits`
object Claude Code passes to the status line command (Pro/Max subscriptions, after the first response), so nothing extra is queried and no tokens are spent.
Colors: yellow from 70% used, red from 90%, bold red at 100% — the same thresholds as the ccp menu. The account email is read from the profile's `.claude.json`.
Requires only python3 (no jq). If you already had a status line, the previous value is printed and replaced.
