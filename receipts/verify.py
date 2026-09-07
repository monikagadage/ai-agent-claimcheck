#!/usr/bin/env python3
"""receipts — Claude Code `Stop` hook entry point.

Reads the hook payload as JSON on stdin, checks the agent's final-message claims
against the session transcript, and prints a hook-output JSON object on stdout.

Warn-only by default: emits `systemMessage` so the user sees unbacked claims.
With `"strict": true` in `.receipts.json`, also blocks the turn.

Exit code is always 0 — a hook crash must never wedge the session. Any internal
error is reported quietly on stderr and the turn proceeds.
"""

from __future__ import annotations

import json
import sys

from .checks import run_all_checks
from .claims import extract_claims
from .config import load_config
from .session import Session


def build_output(data: dict) -> dict:
    if data.get("stop_hook_active"):
        return {}  # we already blocked once this turn; don't loop

    session = Session.from_hook_input(data)
    if not session.final_message:
        return {}
    if not session.transcript_found:
        return {}  # can't see what happened this session -> can't verify -> stay quiet

    cfg = load_config(session.cwd)
    claims = extract_claims(session.final_message)
    if not claims:
        return {}

    findings = run_all_checks(
        session,
        claims,
        test_patterns=cfg.get("test_patterns"),
        build_patterns=cfg.get("build_patterns"),
        ignore=set(cfg.get("ignore") or []),
    )
    if not findings:
        return {}

    msg = _format(findings)
    out: dict = {"systemMessage": msg, "hookSpecificOutput": {"hookEventName": "Stop"}}
    if cfg.get("strict"):
        out["hookSpecificOutput"]["decision"] = "block"
        out["hookSpecificOutput"]["additionalContext"] = (
            msg + "\n\nEither make each claim true (run the command, make the edit) "
            "or restate it accurately, then finish."
        )
    return out


def _format(findings) -> str:
    n = len(findings)
    head = f"⚠️  receipts — {n} claim{'s' if n != 1 else ''} not backed by this session:"
    lines = [head]
    for f in findings:
        line = f'  • "{_trim(f.claim)}" → {f.reason}'
        if f.evidence:
            line += f"  ({f.evidence})"
        lines.append(line)
    return "\n".join(lines)


def _trim(s: str, n: int = 90) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            data = {}
        out = build_output(data)
    except Exception as exc:  # never break the session over a hook bug
        print(f"receipts: skipped ({type(exc).__name__}: {exc})", file=sys.stderr)
        print("{}")
        return 0
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
