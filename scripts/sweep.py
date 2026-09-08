#!/usr/bin/env python3
"""Run claimcheck over past Claude Code session transcripts.

    python3 scripts/sweep.py [~/.claude/projects] [--all-turns]

Default: checks each session's final assistant message (what the last Stop hook saw).
--all-turns: checks every assistant turn against the whole session's commands/edits
(lenient — good for hunting false positives in extraction).
--strict: checks every assistant turn against only what happened *before* it
(what the Stop hook actually sees — the real test).

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
    return [t for t, _ in _turns_with_prefix(path)]


def _turns_with_prefix(path: Path):
    """(assistant text, transcript prefix ending just before it) for each turn.

    The prefix lets us verify a turn against only what happened *before* it — a much
    stricter test than the whole-session evidence.
    """
    lines = path.read_text(errors="replace").splitlines()
    for i, raw in enumerate(lines):
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
        if not isinstance(content, list):
            continue
        txt = "\n".join(
            c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
        ).strip()
        if txt:
            yield txt, "\n".join(lines[: i + 1])


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
    import tempfile
    from collections import Counter

    args = [a for a in argv[1:] if not a.startswith("-")]
    all_turns = "--all-turns" in argv
    strict = "--strict" in argv
    root = Path(args[0]).expanduser() if args else Path("~/.claude/projects").expanduser()
    transcripts = sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not transcripts:
        print(f"no *.jsonl under {root}")
        return 1

    sessions = turns = with_claims = flagged_turns = 0
    claims_by_kind: Counter = Counter()
    flags_by_kind: Counter = Counter()
    for tp in transcripts:
        cwd = _cwd_of(tp)
        if strict:
            checkset = list(_turns_with_prefix(tp))
        else:
            texts = _assistant_turns(tp)
            checkset = [(t, None) for t in (texts if all_turns else texts[-1:])]
        if not checkset:
            continue
        sessions += 1
        base_turn = parse({"transcript_path": str(tp), "cwd": cwd}) if all_turns else None
        for text, prefix in checkset:
            turns += 1
            if strict:
                with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
                    fh.write(prefix)
                    pfx_path = fh.name
                result = check_turn(
                    parse({"last_assistant_message": text, "transcript_path": pfx_path, "cwd": cwd})
                )
                Path(pfx_path).unlink(missing_ok=True)
            elif all_turns:
                base_turn.final_message = text
                result = check_turn(base_turn)
            else:
                result = check_turn(
                    parse({"last_assistant_message": text, "transcript_path": str(tp), "cwd": cwd})
                )
            for c in result.claims:
                claims_by_kind[c.kind] += 1
            if result.claims:
                with_claims += 1
            if not result.findings:
                continue
            flagged_turns += 1
            print(f"\n─── {tp.name}  ({cwd or '?'}) ───")
            for f in result.findings:
                flags_by_kind[f.kind] += 1
                ev = f"  ({f.evidence})" if f.evidence else ""
                print(f"    ⚠️  [{f.kind}] {f.reason}{ev}")
                print(f'        claim: "{_oneline(f.claim)}"')

    mode = "strict / before-turn" if strict else ("all turns" if all_turns else "final only")
    all_kinds = ("tests", "build", "edit", "agreement")
    print(f"\n{'=' * 60}")
    print(f"sessions with assistant text : {sessions}")
    print(f"turns checked               : {turns}  ({mode})")
    print(f"  turns with checkable claims: {with_claims}")
    print(f"  turns flagged              : {flagged_turns}")
    print(
        "  claims extracted by kind   : " + ", ".join(f"{k}={claims_by_kind[k]}" for k in all_kinds)
    )
    print(
        "  flags by kind              : " + ", ".join(f"{k}={flags_by_kind[k]}" for k in all_kinds)
    )
    return 0


def _oneline(s: str, n: int = 200) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
