#!/usr/bin/env python3
"""
Reads debug.log (or per-pane pane_*.log files), sends to an LLM,
writes workflow summary + suggestions to summary.log.

LLM provider resolution order:
  1. Config file at ~/.config/terminal-logger/config.json
  2. ANTHROPIC_API_KEY env var  → Anthropic Messages API
  3. OPENAI_API_KEY env var     → OpenAI Chat Completions API
  4. TERMINAL_LOGGER_API_URL + TERMINAL_LOGGER_API_KEY → generic OpenAI-compatible endpoint
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx

WORKSPACE = Path(__file__).parent
DEBUG_LOG = WORKSPACE / "debug.log"
SUMMARY_LOG = WORKSPACE / "summary.log"
CONFIG_PATH = Path.home() / ".config" / "terminal-logger" / "config.json"

MAX_ENTRIES = 50
MAX_ENTRIES_PER_PANE = 10


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def parse_since(s: str) -> datetime:
    """Parse '1h', '30m', '2h' etc. into a cutoff datetime."""
    m = re.fullmatch(r'(\d+)([hm])', s)
    if not m:
        raise ValueError(f"Invalid --since format: {s!r}. Use e.g. '1h', '30m'")
    n, unit = int(m.group(1)), m.group(2)
    delta = timedelta(hours=n) if unit == 'h' else timedelta(minutes=n)
    return datetime.now() - delta


def _entry_time(entry: str) -> datetime | None:
    """Parse the timestamp from an entry header line."""
    m = re.match(r'^=== (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', entry)
    if m:
        try:
            return datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Log reading
# ---------------------------------------------------------------------------

def _extract_cmd(entry: str) -> str:
    """Extract the cmd= field from an entry header, e.g. 'cmd=nvim' -> 'nvim'."""
    m = re.search(r'\bcmd=(\S+)', entry)
    return m.group(1) if m else "unknown"


def _split_and_filter_entries(text: str, since_dt: datetime | None) -> list[str]:
    """Split a log file into individual entries and optionally filter by time."""
    parts = re.split(r'(?=^=== \d{4})', text, flags=re.MULTILINE)
    parts = [p.strip() for p in parts if p.strip()]
    if since_dt is not None:
        parts = [p for p in parts if (t := _entry_time(p)) is not None and t >= since_dt]
    return parts


def _discover_pane_logs() -> list[Path]:
    """Return sorted list of pane_*.log files in WORKSPACE."""
    return sorted(WORKSPACE.glob("pane_*.log"))


def _extract_pane_id(path: Path) -> str:
    """Extract pane ID from filename like pane_%1.log -> %1."""
    m = re.match(r'pane_(.+)\.log$', path.name)
    return m.group(1) if m else path.stem


def read_pane_entries(since_dt: datetime | None = None) -> str:
    """
    Read per-pane log files and return a structured context block grouped by pane.
    Falls back to debug.log if no pane files exist.
    """
    pane_logs = _discover_pane_logs()
    if not pane_logs:
        return read_recent_entries(MAX_ENTRIES, since_dt=since_dt)

    sections: list[str] = []
    for pane_path in pane_logs:
        if not pane_path.exists():
            continue
        text = pane_path.read_text(errors="replace")
        entries = _split_and_filter_entries(text, since_dt)
        if not entries:
            continue

        # Take last N entries per pane
        recent = entries[-MAX_ENTRIES_PER_PANE:]

        # Determine the dominant command for this pane from the most recent entry
        cmd = _extract_cmd(recent[-1]) if recent else "unknown"
        pane_id = _extract_pane_id(pane_path)

        header = f"[Pane {pane_id} — {cmd}]"
        body = "\n\n".join(recent)
        sections.append(f"{header}\n{body}")

    if not sections:
        # All pane files exist but were filtered empty — fall back to debug.log
        return read_recent_entries(MAX_ENTRIES, since_dt=since_dt)

    return "\n\n---\n\n".join(sections)


def read_recent_entries(n: int, since_dt: datetime | None = None) -> str:
    """Read the last n entries from debug.log, optionally filtered by time."""
    if not DEBUG_LOG.exists():
        return ""
    text = DEBUG_LOG.read_text(errors="replace")
    parts = _split_and_filter_entries(text, since_dt)
    recent = parts[-n:] if len(parts) > n else parts
    return "\n\n".join(recent)


def read_existing_summary() -> str:
    if not SUMMARY_LOG.exists():
        return ""
    return SUMMARY_LOG.read_text(errors="replace").strip()


# ---------------------------------------------------------------------------
# LLM provider detection
# ---------------------------------------------------------------------------

def load_config() -> dict | None:
    """Load config from ~/.config/terminal-logger/config.json if it exists."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception as e:
            print(f"Warning: failed to parse config file: {e}", file=sys.stderr)
    return None


def detect_provider() -> dict | None:
    """
    Detect an LLM provider from config file or environment variables.
    Returns a dict with keys: provider, api_url, api_key, model
    """
    # 1. Config file
    cfg = load_config()
    if cfg:
        api_key_env = cfg.get("api_key_env", "")
        api_key = os.environ.get(api_key_env, "") if api_key_env else ""
        if not api_key:
            # Try using api_key directly if present in config
            api_key = cfg.get("api_key", "")
        if api_key:
            return {
                "provider": cfg.get("provider", "openai"),
                "api_url": cfg["api_url"],
                "api_key": api_key,
                "model": cfg.get("model", "gpt-4o-mini"),
            }
        else:
            print(
                f"Warning: config references env var {api_key_env!r} which is not set.",
                file=sys.stderr,
            )

    # 2. ANTHROPIC_API_KEY
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        return {
            "provider": "anthropic",
            "api_url": "https://api.anthropic.com/v1/messages",
            "api_key": anthropic_key,
            "model": "claude-haiku-4-5-20251001",
        }

    # 3. OPENAI_API_KEY
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        return {
            "provider": "openai",
            "api_url": "https://api.openai.com/v1/chat/completions",
            "api_key": openai_key,
            "model": "gpt-4o-mini",
        }

    # 4. Generic OpenAI-compatible endpoint
    generic_url = os.environ.get("TERMINAL_LOGGER_API_URL", "")
    generic_key = os.environ.get("TERMINAL_LOGGER_API_KEY", "")
    if generic_url and generic_key:
        return {
            "provider": "openai",
            "api_url": generic_url,
            "api_key": generic_key,
            "model": os.environ.get("TERMINAL_LOGGER_MODEL", "gpt-4o-mini"),
        }

    return None


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def call_llm(provider_cfg: dict, prompt: str) -> str:
    """Call the LLM and return the response text."""
    provider = provider_cfg["provider"]
    api_url = provider_cfg["api_url"]
    api_key = provider_cfg["api_key"]
    model = provider_cfg["model"]

    if provider == "anthropic":
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = httpx.post(api_url, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]
    else:
        # OpenAI-compatible
        headers = {
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = httpx.post(api_url, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def build_prompt(recent_entries: str, existing_summary: str) -> str:
    prior = f"## Prior Summary (context for continuity)\n{existing_summary}\n\n---\n" if existing_summary else ""
    return f"""{prior}## Recent Terminal Activity
{recent_entries}

---

You are analyzing a developer's terminal activity captured from tmux panes. The captures may be grouped by pane and labeled with the command running in each pane (e.g. [Pane %1 — zsh], [Pane %3 — nvim]).

Produce exactly three sections with these headings:

## Key Insights
(~200 words) Patterns, notable decisions, repeated actions, things the developer keeps running into. Focus on *what's interesting* about how this developer works — not just a list of commands, but observations about their workflow style, pain points, and habits.

## Suggestions
(~200 words) 3-5 concrete, actionable workflow improvements grounded in what was observed. Be specific — name the exact commands or patterns you saw. For example: "You ran X manually 3 times — consider aliasing it as Y."

## Task / Event Summary
A chronological or grouped summary of what actually happened — what tasks were worked on, what completed, what's in-flight. Choose the best structure (timeline, grouped by topic, etc.) based on what the content calls for.

Keep the tone direct and practical. Prioritize signal over noise.
"""


# ---------------------------------------------------------------------------
# Setup wizard
# ---------------------------------------------------------------------------

def run_setup():
    """Interactive setup wizard that saves config to ~/.config/terminal-logger/config.json."""
    print("tmux-journal LLM Setup Wizard")
    print("=" * 40)
    print()
    print("Choose a provider:")
    print("  1. Anthropic (Claude)")
    print("  2. OpenAI")
    print("  3. Custom OpenAI-compatible endpoint")
    print()

    choice = input("Enter choice [1/2/3]: ").strip()

    if choice == "1":
        provider = "anthropic"
        api_url = "https://api.anthropic.com/v1/messages"
        model_default = "claude-haiku-4-5-20251001"
        key_env = "ANTHROPIC_API_KEY"
        print(f"\nUsing Anthropic. Set your API key as: export {key_env}=sk-ant-...")
    elif choice == "2":
        provider = "openai"
        api_url = "https://api.openai.com/v1/chat/completions"
        model_default = "gpt-4o-mini"
        key_env = "OPENAI_API_KEY"
        print(f"\nUsing OpenAI. Set your API key as: export {key_env}=sk-...")
    elif choice == "3":
        provider = "openai"
        api_url = input("API URL (e.g. https://your-endpoint/v1/chat/completions): ").strip()
        model_default = "gpt-4o-mini"
        key_env = "TERMINAL_LOGGER_API_KEY"
        print(f"\nUsing custom endpoint. Set your API key as: export {key_env}=your-key")
    else:
        print("Invalid choice. Exiting.", file=sys.stderr)
        sys.exit(1)

    model = input(f"Model name [{model_default}]: ").strip() or model_default

    config = {
        "provider": provider,
        "api_url": api_url,
        "api_key_env": key_env,
        "model": model,
    }

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")
    print(f"\nConfig saved to {CONFIG_PATH}")
    print("Done! Run `python summarize.py` to generate your first summary.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate an AI summary of your tmux terminal activity."
    )
    parser.add_argument(
        '--since',
        default=None,
        help="Only include entries from last N hours/minutes, e.g. '1h', '30m'",
    )
    parser.add_argument(
        '--setup',
        action='store_true',
        help="Run the interactive LLM provider setup wizard",
    )
    args = parser.parse_args()

    if args.setup:
        run_setup()
        return

    since_dt = parse_since(args.since) if args.since else None
    recent = read_pane_entries(since_dt=since_dt)
    if not recent:
        print("No terminal entries found.", file=sys.stderr)
        sys.exit(0)

    existing_summary = read_existing_summary()
    prompt = build_prompt(recent, existing_summary)

    provider_cfg = detect_provider()
    if not provider_cfg:
        print(
            "No LLM provider configured.\n"
            "Run `python summarize.py --setup` or set one of:\n"
            "  ANTHROPIC_API_KEY, OPENAI_API_KEY,\n"
            "  or TERMINAL_LOGGER_API_URL + TERMINAL_LOGGER_API_KEY",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Calling LLM ({provider_cfg['provider']}: {provider_cfg['model']})...", file=sys.stderr)
    result = call_llm(provider_cfg, prompt)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output = f"# Terminal Activity Summary\n_Generated: {timestamp}_\n\n{result}\n"
    SUMMARY_LOG.write_text(output)
    print(f"Summary written to {SUMMARY_LOG}", file=sys.stderr)


if __name__ == "__main__":
    main()
