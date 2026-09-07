#!/usr/bin/env python3
"""claimcheck CLI — reads a platform payload on stdin, reports unbacked claims.

    <stop-hook-payload.json> | python -m claimcheck.cli --from claude-code

Options:
  --from {claude-code}   which agent produced the payload (default: claude-code)
  --text                 print plain-text findings instead of the platform's hook JSON
  --strict-exit          exit 1 when there are unbacked claims (for CI / pre-commit)

Set CLAIMCHECK_LOG=/path/to/file.jsonl to also append every flagged turn there.

Without --strict-exit the exit code is always 0 — a hook must never wedge a session.
Internal errors are reported on stderr and the turn proceeds.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import log, report, run
from .adapters import ADAPTERS
from .config import load_config


def _parse_args(argv):
    ap = argparse.ArgumentParser(prog="claimcheck")
    ap.add_argument("--from", dest="source", default="claude-code", choices=sorted(ADAPTERS))
    ap.add_argument("--text", action="store_true", help="plain-text output instead of hook JSON")
    ap.add_argument("--strict-exit", action="store_true", help="exit 1 when claims are unbacked")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    empty = "" if args.text else "{}"
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}

        adapter = ADAPTERS[args.source]
        if getattr(adapter, "already_reprompted", lambda _p: False)(payload):
            print(empty)
            return 0

        turn = adapter.parse(payload)
        cfg = load_config(turn.project_dir)
        findings = run.check_turn(turn, cfg)
        if not findings:
            print(empty)
            return 0

        log.append(turn, findings)
        text = report.format_findings(findings)
        if args.text or not hasattr(adapter, "to_hook_output"):
            print(text)
        else:
            print(json.dumps(adapter.to_hook_output(text, block=bool(cfg.get("strict")))))
        return 1 if args.strict_exit else 0

    except Exception as exc:  # never break the session over a bug in here
        print(f"claimcheck: skipped ({type(exc).__name__}: {exc})", file=sys.stderr)
        print(empty)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
