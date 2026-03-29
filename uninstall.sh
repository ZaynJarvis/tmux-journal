#!/usr/bin/env bash
# Removes the terminal-logger hook from ~/.tmux.conf and reloads tmux config.

set -euo pipefail

TMUX_CONF="$HOME/.tmux.conf"
MARKER="# terminal-logger hook"

if ! grep -q "$MARKER" "$TMUX_CONF" 2>/dev/null; then
  echo "Hook not found in $TMUX_CONF — nothing to remove"
  exit 0
fi

# Remove the marker line and the set-hook line that follows it
# Use a temp file to avoid in-place sed issues on macOS
TMP=$(mktemp)
awk "/$MARKER/{skip=2} skip>0{skip--; next} {print}" "$TMUX_CONF" > "$TMP"
mv "$TMP" "$TMUX_CONF"

echo "Hook removed from $TMUX_CONF"

if [[ -n "${TMUX:-}" ]]; then
  tmux source-file "$TMUX_CONF"
  echo "tmux config reloaded"
else
  echo "Not inside tmux — run: tmux source-file ~/.tmux.conf"
fi
