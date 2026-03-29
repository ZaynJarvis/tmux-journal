#!/usr/bin/env bash
# Opens a tmux split showing debug.log (left) and summary.log (right) live.
# Run from inside tmux. Creates a new window named "tl-watch".

set -euo pipefail

WORKSPACE="$(cd "$(dirname "$0")" && pwd)"

if [[ -z "${TMUX:-}" ]]; then
  echo "Must be run inside tmux"
  exit 1
fi

tmux new-window -n "tl-watch" \
  "tail -f '$WORKSPACE/debug.log' 2>/dev/null || { echo 'debug.log not found'; sleep 999; }"

tmux split-window -h \
  "tail -f '$WORKSPACE/summary.log' 2>/dev/null || { echo 'summary.log not found'; sleep 999; }"

tmux select-pane -L
echo "Watching terminal-logger logs in new window 'tl-watch'"
