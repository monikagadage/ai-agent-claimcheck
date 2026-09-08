#!/usr/bin/env python3
"""Run claimcheck over past Claude Code session transcripts.

    python3 scripts/sweep.py [~/.claude/projects] [--all-turns]

Default: checks each session's final assistant message (what the last Stop hook saw).
--all-turns: checks every assistant turn against the whole session's commands/edits
(best-case evidence — conservative, good for hunting false positives in extraction).

Read-only. Nothing is written or sent anywhere.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from claimcheck.adapters.claude_code import parse
from claimcheck.run import check_turn


def _assistant_turns(path: Path) -> list[str]:
    out = []
    for raw in path.read_text(errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            o = json.loads(raw)
        except ValueError:
            continue
        if o.get("type") != "assistant" or o.get("isSidechain"):
            continue
        content = (o.get("message") or {}).get("content")
        if isinstance(content, list):
            txt = "\n".join(
                c.get("text", "")
                for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            ).strip()
            if txt:
                out.append(txt)
    return out


def _cwd_of(path: Path) -> str:
    for raw in path.read_text(errors="replace").splitlines()[:60]:
        try:
            o = json.loads(raw)
        except ValueError:
            continue
        if o.get("cwd"):
            return o["cwd"]
    return ""


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("-")]
    all_turns = "--all-turns" in argv
    root = Path(args[0]).expanduser() if args else Path("~/.claude/projects").expanduser()
    transcripts = sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not transcripts:
        print(f"no *.jsonl under {root}")
        return 1

    sessions = turns = with_claims = flagged_turns = 0
    for tp in transcripts:
        texts = _assistant_turns(tp)
        if not texts:
            continue
        sessions += 1
        cwd = _cwd_of(tp)
        base_turn = parse({"transcript_path": str(tp), "cwd": cwd})  # whole-session evidence
        checkset = texts if all_turns else texts[-1:]
        for text in checkset:
            turns += 1
            if all_turns:
                base_turn.final_message = text
                result = check_turn(base_turn)
            else:
                result = check_turn(
                    parse({"last_assistant_message": text, "transcript_path": str(tp), "cwd": cwd})
                )
            if result.claims:
                with_claims += 1
            if not result.findings:
                continue
            flagged_turns += 1
            print(f"\n─── {tp.name}  ({cwd or '?'}) ───")
            for f in result.findings:
                ev = f"  ({f.evidence})" if f.evidence else ""
                print(f"    ⚠️  [{f.kind}] {f.reason}{ev}")
                print(f'        claim: "{_oneline(f.claim)}"')

    print(f"\n{'=' * 60}")
    print(f"sessions with assistant text : {sessions}")
    print(f"turns checked               : {turns}  ({'all' if all_turns else 'final only'})")
    print(f"  with checkable claims      : {with_claims}")
    print(f"  flagged                    : {flagged_turns}")
    return 0


def _oneline(s: str, n: int = 200) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
