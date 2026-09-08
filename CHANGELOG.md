# Changelog

## [0.1.0] — unreleased

First public alpha.

### Core

- Platform-neutral `AgentTurn` model — adapters fill it in, checks read only it.
- Four deterministic checks: **tests** (a test runner ran and exited 0), **build**
  (a build/typecheck ran and exited 0), **edits** (an edit / `rm` / `mv` — or, as a
  fallback, `git status` / recent commits — touched the claimed path), **agreements**
  (the referenced thing appears in one of the user's earlier messages).
- `.claimcheck.json` config: `strict` (block instead of warn), `confirm` (show a ✅ when
  claims verify), `git` (toggle the read-only git fallback), `ignore`, `test_patterns`,
  `build_patterns`. `strict` / `confirm` also via `CLAIMCHECK_STRICT` / `CLAIMCHECK_CONFIRM`.
- Silent by default: nothing on a turn with no claims, or one where every claim checks out.
- `CLAIMCHECK_LOG=/path` appends every flagged turn to a JSONL file.
- The only subprocess is read-only `git` (`rev-parse`, `status --porcelain`,
  `log --name-only`) — fixed argv, never a shell, ~10s timeout, failures swallowed.

### Adapters

- **Claude Code** — `Stop`-hook payload + the real transcript JSONL (nested
  `message.content`, `is_error` / `Exit code N` for failures, sub-agent calls).
- **Cursor** — `stop`-hook payload + agent transcript. Warn mode logs only (Cursor hooks
  can't surface a passive note); strict mode sends a follow-up. Transcript format is
  undocumented and parsed defensively.
- **generic** — a plain JSON turn description; works with any agent.

### Claim extraction & guards

- Recognizes: "tests pass" / "N tests green" / "N passing" / "N/N green", "builds" /
  "compiles cleanly" / "no type errors", "I updated `X`" / "Created `X.kt`" / "`Y` has
  been created" (verb-first, bullet, multi-verb), "as we agreed, Z".
- Test/build runners include Gradle camelCase tasks (`jvmTest`), `sbt test`, and
  interpreted-language compile checks (`python -c "import …"`, `py_compile`, `node --check`).
- ~12 false-positive guards, tuned against a 1,600-turn sweep of real Claude Code history
  (`scripts/sweep.py`), on which it ends at zero false positives:
  quoted / code / blockquote text, hypotheticals ("for example", "e.g."), questions,
  instructions ("re-run and confirm…"), restated goals ("you asked me to…"), coverage
  inventory ("45 pytest tests", "suite grew 21 → 60"), reported speech ("the README
  says…"), denials ("neither happened"), hedged / future / conditional ("tests should
  pass"), other-session references, transitive "passes" ("test passes a mock"), and
  turns with no tool activity at all.

### Tooling

- `scripts/sweep.py` — replay claimcheck over past Claude Code transcripts (`--strict`
  for per-turn evidence). Read-only.
- CLI `--strict-exit` for CI / pre-commit.
- CI: unittest on Python 3.9–3.13, `ruff` lint + format, plugin-manifest validation, CodeQL.

_(Began as `claude-code-receipts`; renamed `ai-agent-claimcheck` before first release.
Python import path is `claimcheck`.)_
