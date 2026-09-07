"""Orchestration: an `AgentTurn` (+ optional config) -> findings.

This is the platform-neutral entry point. Adapters produce the turn; the CLI
handles I/O; this decides what to check.
"""

from __future__ import annotations

from .checks import Finding, run_all_checks
from .claims import extract_claims
from .config import load_config
from .model import AgentTurn


def check_turn(turn: AgentTurn, cfg: dict | None = None) -> list[Finding]:
    if not turn.final_message:
        return []
    if not turn.observed:
        return []  # the adapter couldn't see the turn's history -> can't verify -> stay quiet

    cfg = cfg if cfg is not None else load_config(turn.project_dir)
    claims = extract_claims(turn.final_message)
    if not claims:
        return []

    return run_all_checks(
        turn,
        claims,
        test_patterns=cfg.get("test_patterns"),
        build_patterns=cfg.get("build_patterns"),
        ignore=set(cfg.get("ignore") or []),
    )
