"""The platform-neutral shape every adapter produces.

`claims.py` and `checks.py` operate only on `AgentTurn` — nothing in the core
knows whether the turn came from Claude Code, Cursor, Codex, or a plain transcript.
Adding a platform means writing one adapter that fills this in.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Command:
    """A shell command the agent ran during the turn."""

    text: str
    ok: bool = True
    exit_code: int | None = None
    output: str = ""
    subagent: bool = False  # ran inside a sub-agent / delegated task


@dataclass
class FileEdit:
    """A file the agent changed during the turn."""

    path: str
    how: str = ""  # "Edit" | "Write" | "bash:rm" | ...
    subagent: bool = False


@dataclass
class AgentTurn:
    """One completed agent turn, normalized across platforms."""

    final_message: str = ""
    user_messages: list[str] = field(default_factory=list)
    commands: list[Command] = field(default_factory=list)
    edits: list[FileEdit] = field(default_factory=list)
    project_dir: str = ""
    source: str = ""  # "claude-code" | "cursor" | "codex" | "transcript"
    observed: bool = False  # did the adapter actually see the turn's history?
