# tmux-journal

> Automatic tmux session logger with AI-powered workflow summaries

My work and context live entirely in the terminal. tmux-journal hooks into tmux's Enter key to silently capture every command and output — then uses an LLM to distill those interactions into structured insights that can feed context management tools like [OpenViking](https://openviking.com).

Zero friction. Zero manual note-taking.

## How it works

Full terminal workflow pipeline:

```
Ghostty (terminal)
  └── tmux-start.sh → every window auto-attaches to a tmux session
        └── every pane ← Enter hook fires capture.sh
              └── capture.sh → logs command + output per pane
                    └── summarize.py → AI-structured summary
                          └── → OpenViking / other context tools
```

Because the entire terminal environment is tmux-wrapped, the Enter hook achieves 100% coverage — every command in every session/window/pane gets captured, without any shell-level instrumentation or change in workflow.

See [ENV_CONF.md](./ENV_CONF.md) for the full local environment setup (Ghostty / tmux / session picker).

## Core mechanics

- Hooks into the tmux Enter key to capture the active pane after each command
- 5-second debounce + content deduplication to filter noise
- Per-pane log files (`pane_%0.log`, `pane_%1.log`, …) with automatic rotation (5 MB → 1 MB)
- Every 10 captures, runs an LLM summarizer in the background → `summary.log`

## Requirements

- macOS or Linux
- tmux ≥ 2.6
- Python ≥ 3.11
- uv (recommended) or pip

## Installation

```bash
git clone https://github.com/ZaynJarvis/tmux-journal
cd tmux-journal
uv venv && uv pip install -e .
./install.sh
```

Then reload tmux: `tmux source-file ~/.tmux.conf`

For local environment setup, see [ENV_CONF.md](./ENV_CONF.md).

## LLM Setup

Run the setup wizard:
```bash
python summarize.py --setup
```

Or set an environment variable (auto-detected):
```bash
# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# OpenAI
export OPENAI_API_KEY=sk-...

# Any OpenAI-compatible endpoint
export TERMINAL_LOGGER_API_URL=https://your-endpoint/v1/chat/completions
export TERMINAL_LOGGER_API_KEY=your-key
```

Config saved to `~/.config/terminal-logger/config.json`:

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

## Related

- [ENV_CONF.md](./ENV_CONF.md) — full local environment setup (Ghostty / tmux / session picker)
- [README.md](./README.md) — 中文版

## License

MIT
