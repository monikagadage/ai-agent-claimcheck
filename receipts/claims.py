"""Pull checkable claims out of the agent's final message.

Layer 1: regex/keyword. Deliberately conservative — a missed claim is fine
(we just don't check it), a hallucinated claim match is not (false alarm).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SENT_SPLIT = re.compile(r"(?<=[.!?\n])\s+|(?<=[;:])\s+")

TESTS_RE = re.compile(
    r"""(
        \b(all\s+|the\s+)?(unit\s+|integration\s+|e2e\s+)?tests?\b [^.!?\n]{0,50}?
            \b(pass(e[sd]|ing)?|are\s+green|succeed(s|ed)?|go(es)?\s+through)\b
      | \ball\s+green\b
      | \btest\s+suite\b [^.!?\n]{0,30}? \b(pass|green|clean|succeed)
      | \b(the\s+)?tests?\s+are\s+(now\s+)?passing\b
    )""",
    re.I | re.X,
)

BUILD_RE = re.compile(
    r"""(
        \b(the\s+)?(build|compilation)\b [^.!?\n]{0,30}? \b(pass(es|ed)?|succeed(s|ed)?|is\s+clean|works?|green)\b
      | \b(it\s+)?(builds|compiles)\s+(cleanly|fine|now|successfully|without\s+errors)\b
      | \bno\s+(type|compile|compilation|build|typescript)\s+errors\b
      | \b(type[- ]?check(ing)?|tsc|mypy)\b [^.!?\n]{0,25}? \b(pass(es|ed)?|clean|succeed|ok)\b
    )""",
    re.I | re.X,
)

EDIT_RE = re.compile(
    r"""(?:\bI(?:['’]ve|\s+have)?\s+ | \b(?:and|then|also)\s+ )
        (updated|created|added|removed|deleted|modified|refactored|edited|fixed|
         renamed|moved|rewrote|wrote)
        \s+(?:the\s+|a\s+|new\s+)?
        [`'\"]?([\w./\-]+\.[A-Za-z0-9]{1,6})[`'\"]?
    """,
    re.I | re.X,
)

AGREEMENT_RE = re.compile(
    r"""(?:
        as\s+(?:we|you)\s+(?:agreed|discussed|decided|requested|asked)
      | as\s+per\s+(?:our|your)\s+(?:discussion|request|decision|instruction)
      | (?:per|following)\s+(?:our|your|the)\s+(?:earlier\s+)?(?:decision|agreement|plan\s+we\s+made)
    )\b[,:\s]*([^.!?\n]{0,90})""",
    re.I | re.X,
)


@dataclass
class Claim:
    kind: str            # "tests" | "build" | "edit" | "agreement"
    text: str            # the sentence it came from
    target: str | None = None   # file path (edit) or the referenced thing (agreement)


def extract_claims(message: str) -> list[Claim]:
    if not message:
        return []
    claims: list[Claim] = []
    sentences = [s.strip() for s in _SENT_SPLIT.split(message) if s.strip()]
    for sent in sentences:
        low = sent.lower()
        if TESTS_RE.search(sent) and "did the tests pass" not in low and not low.startswith(("if ", "do the", "should ", "make sure", "run the", "once ")):
            claims.append(Claim("tests", sent))
        if BUILD_RE.search(sent) and not low.startswith(("if ", "does it", "should ", "make sure", "verify ")):
            claims.append(Claim("build", sent))
        for m in EDIT_RE.finditer(sent):
            claims.append(Claim("edit", sent, target=m.group(2)))
        for m in AGREEMENT_RE.finditer(sent):
            ref = m.group(1).strip(" ,:;-") if m.group(1) else ""
            claims.append(Claim("agreement", sent, target=ref or None))
    return _dedupe(claims)


def _dedupe(claims: list[Claim]) -> list[Claim]:
    seen = set()
    out = []
    for c in claims:
        key = (c.kind, c.target, c.text[:80])
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out
