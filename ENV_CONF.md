# Local Environment Configuration

This document explains the local environment setup that makes `tmux-journal` work end-to-end.

The core idea: **everything happens in tmux** — so hooking into tmux's Enter key gives you complete terminal interaction history, zero friction.

---

## Terminal: Ghostty

Ghostty launches directly into a tmux session picker via a startup script.

```ini
# ~/.config/ghostty/config
command = /Users/your-name/tmux-start.sh
confirm-close-surface = false
```

This means every terminal window is a tmux session. No raw shell sessions escape the logger.

---

## Session Picker: tmux-start.sh

On Ghostty launch, this script runs `fzf` over active sessions or creates a new one:

```bash
#!/bin/bash
sessions=$(/opt/homebrew/bin/tmux list-sessions -F "#{session_name}" 2>/dev/null)
selection=$(echo -e "➕ Create New Session\n$sessions" | /opt/homebrew/bin/fzf \
  --prompt="Select tmux session: " --height=40% --reverse)

if [[ -z "$selection" ]]; then
    exec /bin/zsh
elif [[ "$selection" == "➕ Create New Session" ]]; then
    echo -n "Enter new session name (leave blank for default): "
    read session_name
    if [[ -z "$session_name" ]]; then
        exec /opt/homebrew/bin/tmux new-session -c "$PWD"
    else
        exec /opt/homebrew/bin/tmux new-session -s "$session_name" -c "$PWD"
    fi
else
    exec /opt/homebrew/bin/tmux attach-session -t "$selection"
fi
```

---

## tmux Config: Enter Key Hook

The critical piece — every `Enter` keypress in any pane triggers `capture.sh`:

```conf
# ~/.tmux.conf

# Remap prefix
unbind C-b
set -g prefix \`

# Split panes, preserve cwd
unbind '"'
unbind %
bind \\ split-window -h -c "#{pane_current_path}"
bind - split-window -v -c "#{pane_current_path}"

# Minimal status bar (session name only)
set-option -g status-style bg=default
set-option -g status-style fg=white
set -g status-left "#S"
set -g status-right ""
set -g window-status-format ""
set -g window-status-current-format ""

# Mouse support
set -g mouse on

# THE KEY HOOK: fires capture.sh on every Enter
bind-key -T root Enter \
  send-keys Enter \; \
  if-shell -F "#{pane_active}" \
    "run-shell -b \"/path/to/tmux-journal/capture.sh #{pane_id}\""

# Extended keys (Shift+Enter, etc.)
set -s extended-keys on
set -as terminal-features 'xterm*:extkeys'
```

Update `/path/to/tmux-journal/capture.sh` to the actual path after cloning.

---

## Why This Works

```
Ghostty
  └── tmux-start.sh → always in tmux
        └── every pane ← Enter hook fires capture.sh
              └── capture.sh → logs command + output per pane
                    summarize.py → structured summary (AI-powered)
                          └── → context tools (e.g. OpenViking)
```

Because the terminal environment is **fully tmux-wrapped**, the Enter hook achieves 100% coverage — every command in every session/window/pane gets captured, without any shell-level instrumentation.

---

## File Locations (example)

| File | Default path |
|------|-------------|
| `capture.sh` | `~/code/tmux-journal/capture.sh` |
| `tmux-start.sh` | `~/tmux-start.sh` |
| Ghostty config | `~/.config/ghostty/config` |
| tmux config | `~/.tmux.conf` |
| Log output | `~/.tmux-logs/` |
