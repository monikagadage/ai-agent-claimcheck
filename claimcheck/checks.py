"""The four v1 checks. Each takes (turn, claims) and returns Findings.

Deterministic only: no network, no model. A check stays silent unless it is
confident a claim is unbacked. Operates purely on the platform-neutral
`AgentTurn` — nothing in here knows which agent produced it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .claims import Claim
from .model import AgentTurn

TEST_RUNNER_PATTERNS = [
    r"\bpytest\b",
    r"\bpy\.test\b",
    r"\bpython3?\s+-m\s+(pytest|unittest|nose2?|tox)\b",
    r"\bpython3?\s+-m\s+django\s+test\b",
    r"\bmanage\.py\s+test\b",
    r"\bnpm\s+(run\s+)?test\b",
    r"\byarn\s+test\b",
    r"\bpnpm\s+(run\s+)?test\b",
    r"\bnpx\s+(jest|vitest|mocha|playwright)\b",
    r"\bjest\b",
    r"\bvitest\b",
    r"\bmocha\b",
    r"\bgo\s+test\b",
    r"\bcargo\s+test\b",
    r"\bcargo\s+nextest\b",
    r"\bmvn\b[^\n]*\b(test|verify|integration-test)\b",
    r"\bgradlew?\b[^\n]*\b\w*[Tt]est\w*\b",  # gradlew :shared:jvmTest, testDebugUnitTest, test
    r"\bgradlew?\b[^\n]*\bcheck\b",
    r"\bsbt\b[^\n]*\btest\b",
    r"\brspec\b",
    r"\bbundle\s+exec\s+rspec\b",
    r"\brake\s+test\b",
    r"\bphpunit\b",
    r"\bdotnet\s+test\b",
    r"\bctest\b",
    r"\btox\b",
    r"\bnose2?\b",
    r"\bbin/rails\s+test\b",
    r"\bmake\s+test\b",
    r"\bmake\s+check\b",
]

BUILD_PATTERNS = [
    r"\btsc\b",
    r"\bmypy\b",
    r"\bpyright\b",
    r"\bpython3?\s+-m\s+mypy\b",
    r"\bnpm\s+run\s+build\b",
    r"\byarn\s+build\b",
    r"\bpnpm\s+(run\s+)?build\b",
    r"\bnpx\s+tsc\b",
    r"\bgo\s+build\b",
    r"\bgo\s+vet\b",
    r"\bcargo\s+(build|check)\b",
    r"\bmvn\b[^\n]*\b(compile|package|install)\b",
    r"\bgradle\b[^\n]*\b(build|assemble|compile\w*)\b",
    r"\./gradlew\b[^\n]*\bbuild\b",
    r"\bjavac\b",
    r"\bmake\b",
    r"\bcmake\b",
    r"\bdotnet\s+build\b",
    r"\bnext\s+build\b",
    r"\bvite\s+build\b",
    r"\bwebpack\b",
    r"\bgcc\b",
    r"\bg\+\+\b",
    r"\bclang\b",
]


@dataclass
class Finding:
    kind: str
    claim: str
    reason: str
    evidence: str = ""


def _matches(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, re.I) for p in patterns)


def check_tests(turn: AgentTurn, claims: list[Claim], patterns: list[str]) -> list[Finding]:
    cs = [c for c in claims if c.kind == "tests"]
    if not cs:
        return []
    ran = [cmd for cmd in turn.commands if _matches(cmd.text, patterns)]
    if not ran:
        return [Finding("tests", c.text, "no test command ran this session") for c in cs]
    if any(cmd.ok for cmd in ran):
        return []
    last = ran[-1]
    ev = f"`{_short(last.text)}` exited {last.exit_code if last.exit_code is not None else 'non-zero'}"
    return [Finding("tests", c.text, "the only test command this session failed", ev) for c in cs]


def check_build(turn: AgentTurn, claims: list[Claim], patterns: list[str]) -> list[Finding]:
    cs = [c for c in claims if c.kind == "build"]
    if not cs:
        return []
    ran = [cmd for cmd in turn.commands if _matches(cmd.text, patterns)]
    if not ran:
        return [Finding("build", c.text, "no build/typecheck command ran this session") for c in cs]
    if any(cmd.ok for cmd in ran):
        return []
    last = ran[-1]
    ev = f"`{_short(last.text)}` exited {last.exit_code if last.exit_code is not None else 'non-zero'}"
    return [Finding("build", c.text, "the only build command this session failed", ev) for c in cs]


def check_edits(turn: AgentTurn, claims: list[Claim]) -> list[Finding]:
    cs = [c for c in claims if c.kind == "edit" and c.target]
    if not cs:
        return []
    touched = [e.path for e in turn.edits if _looks_like_file(e.path)]
    findings = []
    for c in cs:
        if not _path_touched(c.target, touched):
            names = _unique(_basename(p) for p in touched)
            ev = (
                (
                    "files edited this session: "
                    + ", ".join(names[:5])
                    + ("…" if len(names) > 5 else "")
                )
                if names
                else "no files were edited this session"
            )
            findings.append(Finding("edit", c.text, f"nothing modified `{c.target}`", ev))
    return findings


def check_agreements(turn: AgentTurn, claims: list[Claim]) -> list[Finding]:
    cs = [c for c in claims if c.kind == "agreement" and c.target]
    if not cs:
        return []
    corpus = "\n".join(turn.user_messages).lower()
    if not corpus:
        return []
    findings = []
    for c in cs:
        kws = _keywords(c.target)
        if not kws:
            continue
        hits = [k for k in kws if k in corpus]
        if len(hits) < max(1, len(kws) // 2):
            findings.append(
                Finding(
                    "agreement",
                    c.text,
                    f"no earlier message from you mentions “{c.target.strip()}”",
                    "possible invented agreement",
                )
            )
    return findings


def run_all_checks(
    turn: AgentTurn, claims: list[Claim], test_patterns=None, build_patterns=None, ignore=()
) -> list[Finding]:
    tp = TEST_RUNNER_PATTERNS + list(test_patterns or [])
    bp = BUILD_PATTERNS + list(build_patterns or [])
    out: list[Finding] = []
    if "tests" not in ignore:
        out += check_tests(turn, claims, tp)
    if "build" not in ignore:
        out += check_build(turn, claims, bp)
    if "edits" not in ignore:
        out += check_edits(turn, claims)
    if "agreements" not in ignore:
        out += check_agreements(turn, claims)
    return out


# ---- helpers ---------------------------------------------------------------


def _short(s: str, n: int = 60) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _basename(p: str) -> str:
    return p.rstrip("/").split("/")[-1]


def _unique(xs):
    seen, out = set(), []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _looks_like_file(path: str) -> bool:
    if not path or not isinstance(path, str):
        return False
    if any(ch in path for ch in "{}$*?()"):  # shell metachars -> not a real path
        return False
    return "." in _basename(path)


def _path_touched(target: str, touched: list[str]) -> bool:
    t = target.strip().lstrip("./")
    tb = _basename(t)
    for p in touched:
        pp = p.strip().lstrip("./")
        if pp == t or pp.endswith("/" + t) or _basename(pp) == tb:
            return True
    return False


def _keywords(phrase: str) -> list[str]:
    stop = {
        "the",
        "a",
        "an",
        "to",
        "of",
        "for",
        "and",
        "or",
        "we",
        "you",
        "i",
        "use",
        "using",
        "with",
        "this",
        "that",
        "it",
        "in",
        "on",
        "as",
        "will",
        "should",
        "our",
        "your",
        "be",
        "is",
        "are",
        "was",
        "were",
        "do",
        "did",
        "have",
    }
    words = re.findall(r"[A-Za-z0-9_.\-]{3,}", phrase.lower())
    return [w for w in words if w not in stop][:6]
