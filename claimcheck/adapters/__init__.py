"""Per-platform adapters. Each turns a platform payload into an `AgentTurn`.

Add a platform:
  1. write `adapters/<name>.py` with `parse(payload: dict) -> AgentTurn`
  2. register it in `ADAPTERS` below
  3. that's it — `claims.py` and `checks.py` need no changes
"""

from __future__ import annotations

from . import claude_code

ADAPTERS = {
    "claude-code": claude_code,
}

PLANNED = ("cursor", "codex")
