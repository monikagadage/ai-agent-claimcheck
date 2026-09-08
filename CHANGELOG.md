# Changelog

## [0.1.0] — unreleased

First cut.

- Platform-neutral core: `AgentTurn` model, claim extraction, four checks, all
  independent of which agent produced the turn.
- Claude Code adapter: `Stop`-hook payload + transcript JSONL → `AgentTurn`, and
  findings → Claude Code hook output.
- Four deterministic checks: test claims, build/typecheck claims, file-edit claims,
  invented agreements.
- Warn-only by default; `strict` mode blocks the turn.
- CLI: `python -m claimcheck.cli --from claude-code` (`--text`, `--strict-exit` for CI).
- `.claimcheck.json` config: `strict`, `ignore`, `test_patterns`, `build_patterns`.
- Transcript parser for the real Claude Code JSONL format (nested `message.content`,
  `is_error` / `Exit code N` for failed commands, sub-agent calls).
- **Cursor adapter** (`--from cursor`): parses the `stop`-hook payload + agent transcript.
  Warn mode logs only (Cursor hooks can't show a passive note); strict mode sends a
  follow-up. Transcript parsing is provisional — undocumented format, parsed defensively.
- **Generic adapter** (`--from generic`): pipe a small JSON of the turn; works with any agent.
- Hook shim forwards args, so one script serves every platform.
- Ignore claims inside quotes, backtick spans, blockquotes and fenced code — the agent
  discussing, quoting, or illustrating a claim is not making one. Also ignores long
  parenthetical asides and "for example / e.g. / such as" sentences. (dogfood FPs)
- `confirm` mode (config key or `CLAIMCHECK_CONFIRM=1`): show `✅ claimcheck — N claims
  check out` when a turn's claims all verify. Silent by default / when no claims.
- File-edit check now also consults **read-only git** (`status --porcelain`, recent
  `log --name-only`) when the transcript doesn't show the claimed path touched — catches
  "removed the file" when the deletion never landed. Fixed argv, no shell, ~10s timeout,
  failures swallowed. Disable with `.claimcheck.json` `{"git": false}`.
- Wider edit-claim detection: verb-first ("Created Fort.kt", "- Deleted bun.lockb"),
  "the new X.kt", "X has been created", multi-verb. Test/build claims now match through
  a filename that names a file before the verb ("the tests in auth_test.py pass").
- `scripts/sweep.py` — run claimcheck over past Claude Code transcripts to hunt false
  positives (swept 1600+ real turns; 0 flagged after the guards below).
- Skip turns with no tool activity (research/summary sessions), test-coverage inventory
  ("45 pytest tests", "suite grew 21 → 60"), proposals ("let's check it compiles"),
  and "as an example" mentions. Recognize interpreted-language compile checks
  (`python -c import`, `py_compile`, `node --check`, `ruby -c`).
- More guards: skip hedged / future / conditional claims ("tests should pass", "will
  compile if…"), restated goals ("you asked me to…", "the task was…"), work from a
  different session ("previously…", "in an earlier session"), transitive "passes" ("test
  passes a mock"), and more reported-speech sources (README, spec, PR, commit message).
- Recognize "N tests green / N passing / N passed / N/N green" as test claims;
  match Gradle camelCase test tasks (jvmTest, testDebugUnitTest) + gradle check / sbt test.
- Skip sentences that report on or deny a claim ("it states that... neither happened",
  "I did not run the tests") — reported speech and negation. (dogfood FP)
- `CLAIMCHECK_LOG=/path` appends every flagged turn to a JSONL file (dogfood / FP review).
- Stdlib only, Python 3.9+.

_(Started life as `claude-code-receipts`; renamed `ai-agent-claimcheck` before first release. Python import path stays `claimcheck`.)_
