#!/bin/bash

# Read JSON input from stdin
input=$(cat)

# Extract model display name
model=$(echo "$input" | jq -r '.model.display_name')

# Get current directory
cwd=$(echo "$input" | jq -r '.workspace.current_dir')

# Format directory path (replace home directory with ~)
home="$HOME"
if [[ "$cwd" == "$home"* ]]; then
    dir_display="~${cwd#$home}"
else
    dir_display="$cwd"
fi

# Extract context usage percentage
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
context_info=""
if [ -n "$used" ]; then
    context_info=$(printf " | Context: %.1f%%" "$used")
fi

# Git information (skip optional locks for safety)
git_info=""
if git -C "$cwd" rev-parse --git-dir > /dev/null 2>&1; then
    # Get branch name
    branch=$(git -C "$cwd" --no-optional-locks branch --show-current 2>/dev/null || echo "detached")

    # Get status indicators
    status=$(git -C "$cwd" --no-optional-locks status --porcelain 2>/dev/null)
    if [ -n "$status" ]; then
        # Count changes
        modified=$(echo "$status" | grep -c "^ M" || true)
        added=$(echo "$status" | grep -c "^A" || true)
        untracked=$(echo "$status" | grep -c "^??" || true)

        status_indicator=""
        [ "$modified" -gt 0 ] && status_indicator="${status_indicator}*${modified}"
        [ "$added" -gt 0 ] && status_indicator="${status_indicator}+${added}"
        [ "$untracked" -gt 0 ] && status_indicator="${status_indicator}?${untracked}"

        git_info=$(printf " | git: %s [%s]" "$branch" "$status_indicator")
    else
        git_info=$(printf " | git: %s" "$branch")
    fi
fi

# 로그인 계정 (여러 구독 계정을 ccp 로 오가므로 어느 계정인지 항상 보여야 한다)
# 프로필 세션이면 CLAUDE_CONFIG_DIR 이 설정돼 있고, 기본 세션이면 ~/.claude.json 이다.
if [ -n "$CLAUDE_CONFIG_DIR" ]; then
    acct_file="$CLAUDE_CONFIG_DIR/.claude.json"
    profile="$(basename "$CLAUDE_CONFIG_DIR")"
else
    acct_file="$HOME/.claude.json"
    profile="기본"
fi
acct_info=""
if [ -f "$acct_file" ]; then
    # 291KB 짜리 파일이라 매 렌더마다 파싱하지 않도록 mtime 으로 캐시한다.
    cache="${TMPDIR:-/tmp}/.ccp-acct-$(echo "$acct_file" | md5 -q 2>/dev/null || echo default)"
    if [ ! -f "$cache" ] || [ "$acct_file" -nt "$cache" ]; then
        jq -r '.oauthAccount.emailAddress // empty' "$acct_file" 2>/dev/null > "$cache"
    fi
    email="$(cat "$cache" 2>/dev/null)"
    [ -n "$email" ] && acct_info="$profile:$email | " || acct_info="$profile:미로그인 | "
fi

# Build status line
printf "%s%s | %s%s%s" "$acct_info" "$model" "$dir_display" "$context_info" "$git_info"
