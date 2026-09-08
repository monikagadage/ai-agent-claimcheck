"""Findings / results -> human-readable text. Platform-neutral."""

from __future__ import annotations

from .checks import Finding
from .claims import Claim

_KIND_LABEL = {"tests": "tests", "build": "build", "edit": "file edits", "agreement": "agreements"}


def format_findings(findings: list[Finding]) -> str:
    n = len(findings)
    lines = [f"⚠️  claimcheck — {n} claim{'s' if n != 1 else ''} not backed by this session:"]
    for f in findings:
        line = f'  • "{_trim(f.claim)}" → {f.reason}'
        if f.evidence:
            line += f"  ({f.evidence})"
        lines.append(line)
    return "\n".join(lines)


def format_confirmation(claims: list[Claim]) -> str:
    n = len(claims)
    kinds = [_KIND_LABEL.get(k, k) for k in dict.fromkeys(c.kind for c in claims)]
    return f"✅  claimcheck — {n} claim{'s' if n != 1 else ''} check out ({', '.join(kinds)})"


def _trim(s: str, n: int = 90) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"
