# tmux-journal

> Automatic tmux session logger with AI-powered workflow summaries

tmux-journal hooks into tmux's key bindings to silently capture terminal activity as you work, then uses an LLM to generate structured insights: what you worked on, patterns in your workflow, and actionable suggestions.

## Why?

> I wanted a passive, zero-friction way to remember what I worked on across long tmux sessions — without manually keeping notes. tmux-journal runs in the background and gives me an AI-written debrief whenever I want it.

## How it works

- Hooks into the tmux Enter key to capture the active pane after each command
- Debounces captures (5 s) and deduplicates unchanged content
- Per-pane log files (`pane_%0.log`, `pane_%1.log`, …) with automatic rotation (5 MB → 1 MB)
- Every 10 captures, runs an LLM summarizer in the background → `summary.log`

## Requirements

- macOS or Linux
- tmux ≥ 2.6
- Python ≥ 3.11
- uv (recommended) or pip

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/tmux-journal
cd tmux-journal
uv venv && uv pip install -e .
./install.sh
```

Then reload tmux: `tmux source-file ~/.tmux.conf`

## LLM Setup

Run the setup wizard:
```bash
python summarize.py --setup
```

Or set an environment variable and it auto-detects:
```bash
# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# OpenAI
export OPENAI_API_KEY=sk-...

# Any OpenAI-compatible endpoint
export TERMINAL_LOGGER_API_URL=https://your-endpoint/v1/chat/completions
export TERMINAL_LOGGER_API_KEY=your-key
```

### Config file

The setup wizard saves to `~/.config/terminal-logger/config.json`:

```json
{
  "api_url": "https://api.anthropic.com/v1/messages",
  "api_key_env": "ANTHROPIC_API_KEY",
  "model": "claude-haiku-4-5-20251001",
  "provider": "anthropic"
}
```

## Commands

| Command | Description |
|---------|-------------|
| `./install.sh` | Install tmux hook |
| `./uninstall.sh` | Remove tmux hook |
| `./watch.sh` | Live-watch logs in a split pane |
| `python summarize.py` | Run summarizer now |
| `python summarize.py --since 1h` | Summarize last hour |
| `python summarize.py --setup` | Configure LLM provider |

## Logs

| File | Contents |
|------|----------|
| `debug.log` | All captured pane snapshots |
| `pane_%N.log` | Per-pane capture history |
| `summary.log` | Latest AI-generated summary |

## Output format

The LLM produces three sections:
- **Key Insights** — workflow patterns, habits, pain points
- **Suggestions** — concrete, command-specific improvements
- **Task / Event Summary** — chronological or topic-grouped activity log

## Uninstall

```bash
./uninstall.sh
rm -rf ~/.config/terminal-logger
```

## License

MIT
