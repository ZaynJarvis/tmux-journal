#!/usr/bin/env bash
# Usage: capture.sh <pane_id>
# Captures the given tmux pane and appends a timestamped snapshot to debug.log.
# Debounce: skips if last capture was <5 seconds ago.

set -euo pipefail

# Resolve tmux binary explicitly — run-shell hooks run in a minimal /bin/sh
# environment without /opt/homebrew/bin in PATH on macOS.
TMUX_BIN="$(command -v tmux 2>/dev/null || echo /opt/homebrew/bin/tmux)"

WORKSPACE="$(cd "$(dirname "$0")" && pwd)"
LOG="$WORKSPACE/debug.log"
DEBOUNCE_FILE="$WORKSPACE/.last_capture"
DEBOUNCE_SECS=5

PANE_ID="${1:-}"
if [[ -z "$PANE_ID" ]]; then
  exit 0
fi

# Debounce check
NOW=$(date +%s)
if [[ -f "$DEBOUNCE_FILE" ]]; then
  LAST=$(cat "$DEBOUNCE_FILE")
  DIFF=$(( NOW - LAST ))
  if (( DIFF < DEBOUNCE_SECS )); then
    exit 0
  fi
fi
echo "$NOW" > "$DEBOUNCE_FILE"

# Lock file — prevent parallel runs from overlapping
LOCK_FILE="$WORKSPACE/.capture.lock"
if ! mkdir "$LOCK_FILE" 2>/dev/null; then
  exit 0  # Another instance is running
fi
trap 'rmdir "$LOCK_FILE" 2>/dev/null || true' EXIT

# Capture pane (-p stdout, -S -200 last 200 lines)
CONTENT=$("$TMUX_BIN" capture-pane -p -S -200 -t "$PANE_ID" 2>/dev/null || echo "")
CONTENT=$(echo "$CONTENT" | sed 's/\x1b\[[0-9;]*[mGKHF]//g; s/\x1b[()][AB]//g; s/\r//g')
if [[ -z "$CONTENT" ]]; then
  exit 0
fi

# Deduplicate consecutive similar captures via prefix+suffix match.
# If the first N lines AND last M lines are identical to the last captured
# content, the visible terminal content hasn't meaningfully changed — skip.
PREFIX_LINES=10
SUFFIX_LINES=5
LAST_CONTENT_FILE="$WORKSPACE/.last_content"

if [[ -f "$LAST_CONTENT_FILE" ]]; then
  LAST_CONTENT=$(cat "$LAST_CONTENT_FILE")
  NEW_PREFIX=$(echo "$CONTENT"      | head -n "$PREFIX_LINES")
  LAST_PREFIX=$(echo "$LAST_CONTENT" | head -n "$PREFIX_LINES")
  NEW_SUFFIX=$(echo "$CONTENT"      | tail -n "$SUFFIX_LINES")
  LAST_SUFFIX=$(echo "$LAST_CONTENT" | tail -n "$SUFFIX_LINES")
  if [[ "$NEW_PREFIX" == "$LAST_PREFIX" && "$NEW_SUFFIX" == "$LAST_SUFFIX" ]]; then
    exit 0
  fi
fi
printf '%s' "$CONTENT" > "$LAST_CONTENT_FILE"

# Derive a safe filename component from the pane ID (e.g. %1 -> pane_%1.log)
PANE_SAFE="${PANE_ID//%/}"   # strip leading % for filesystem safety — keep digits
PANE_LOG="$WORKSPACE/pane_%${PANE_SAFE}.log"

# Rotate a log file if it exceeds 5MB (keep last ~1MB)
rotate_log() {
  local file="$1"
  local max_size=$((5 * 1024 * 1024))
  if [[ -f "$file" ]]; then
    local size
    size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo 0)
    if (( size > max_size )); then
      local keep=$((1024 * 1024))
      tail -c "$keep" "$file" > "$file.tmp" && mv "$file.tmp" "$file"
    fi
  fi
}

rotate_log "$LOG"
rotate_log "$PANE_LOG"

# Build the log entry once and append to both files
PANE_CMD=$("$TMUX_BIN" display-message -p -t "$PANE_ID" '#{pane_current_command}' 2>/dev/null || echo "unknown")
PANE_SESSION=$("$TMUX_BIN" display-message -p -t "$PANE_ID" '#{session_name}:#{window_name}' 2>/dev/null || echo "")
if [[ -n "$PANE_SESSION" ]]; then
  printf '%s' "$PANE_SESSION" > "${PANE_LOG%.log}.name"
fi
ENTRY="=== $(date '+%Y-%m-%d %H:%M:%S') pane=$PANE_ID session=$PANE_SESSION cmd=$PANE_CMD ===
$CONTENT
"

printf '%s\n' "$ENTRY" >> "$PANE_LOG"
printf '%s\n' "$ENTRY" >> "$LOG"

# Auto-summarize every 10 entries (count across the global debug.log)
COUNT=$(grep -c '^===' "$LOG" 2>/dev/null || echo 0)
if (( COUNT % 10 == 0 )); then
  "$WORKSPACE/.venv/bin/python" "$WORKSPACE/summarize.py" &
fi
