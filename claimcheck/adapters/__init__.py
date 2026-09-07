"""Per-platform adapters. Each turns a platform payload into an `AgentTurn`.

An adapter module exposes:
  parse(payload: dict) -> AgentTurn                (required)
  already_reprompted(payload: dict) -> bool        (optional — loop guard)
  to_hook_output(message: str, *, block) -> dict   (optional — platform hook JSON)

Add a platform: write `adapters/<name>.py`, register it below. `claims.py` /
`checks.py` / `run.py` need no changes.
"""

from __future__ import annotations

from . import claude_code, cursor, generic

ADAPTERS = {
    "claude-code": claude_code,
    "cursor": cursor,
    "generic": generic,
}

PLANNED = ("codex", "copilot")
