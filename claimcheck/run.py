"""Orchestration: an `AgentTurn` (+ optional config) -> a Result.

This is the platform-neutral entry point. Adapters produce the turn; the CLI
handles I/O; this decides what to check.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .checks import Finding, run_all_checks
from .claims import Claim, extract_claims
from .config import load_config
from .model import AgentTurn


@dataclass
class Result:
    claims: list[Claim] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def verified(self) -> bool:
        """There were claims and every one checked out."""
        return bool(self.claims) and not self.findings


def check_turn(turn: AgentTurn, cfg: dict | None = None) -> Result:
    if not turn.final_message:
        return Result()
    if not turn.observed:
        return Result()  # adapter couldn't see the history -> can't verify -> stay quiet
    if not turn.commands and not turn.edits:
        return Result()  # no tool activity this turn -> claims refer elsewhere, nothing to check

    cfg = cfg if cfg is not None else load_config(turn.project_dir)
    claims = extract_claims(turn.final_message)
    if not claims:
        return Result()

    findings = run_all_checks(
        turn,
        claims,
        test_patterns=cfg.get("test_patterns"),
        build_patterns=cfg.get("build_patterns"),
        ignore=set(cfg.get("ignore") or []),
    )
    return Result(claims=claims, findings=findings)
