#!/usr/bin/env bash
# Installs the terminal-logger after-send-keys hook into ~/.tmux.conf.
#
# How it works:
#   - Binds the Enter key (root table) to forward Enter + call capture.sh.
#   - capture.sh uses a debounce (5 s) + content-hash dedup to avoid redundant entries.
#   - capture.sh resolves the tmux binary by full path because run-shell hooks
#     execute in a minimal sh environment (no /opt/homebrew/bin on macOS).

set -euo pipefail

WORKSPACE="$(cd "$(dirname "$0")" && pwd)"
CAPTURE="$WORKSPACE/capture.sh"
TMUX_CONF="$HOME/.tmux.conf"
MARKER="# terminal-logger hook"

# Remove any stale lock left by a previous crashed run
LOCK="$WORKSPACE/.capture.lock"
if [[ -d "$LOCK" ]]; then
  rmdir "$LOCK" 2>/dev/null && echo "Removed stale lock: $LOCK" || true
fi

if grep -q "$MARKER" "$TMUX_CONF" 2>/dev/null; then
  echo "Hook already installed in $TMUX_CONF"
else
  cat >> "$TMUX_CONF" <<EOF

$MARKER
bind-key -T root Enter send-keys Enter \; if-shell -F "#{pane_active}" "run-shell -b \"$CAPTURE #{pane_id}\""
EOF
  echo "Hook added to $TMUX_CONF"
fi

# Reload tmux config if inside tmux
if [[ -n "${TMUX:-}" ]]; then
  tmux source-file "$TMUX_CONF"
  echo "tmux config reloaded"
else
  echo "Not inside tmux — run: tmux source-file ~/.tmux.conf"
fi
