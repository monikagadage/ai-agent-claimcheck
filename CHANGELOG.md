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
- Recognize "N tests green / N passing / N passed / N/N green" as test claims;
  match Gradle camelCase test tasks (jvmTest, testDebugUnitTest) + gradle check / sbt test.
- Skip sentences that report on or deny a claim ("it states that... neither happened",
  "I did not run the tests") — reported speech and negation. (dogfood FP)
- `CLAIMCHECK_LOG=/path` appends every flagged turn to a JSONL file (dogfood / FP review).
- Stdlib only, Python 3.9+.

_(Started life as `claude-code-receipts`; renamed `ai-agent-claimcheck` before first release. Python import path stays `claimcheck`.)_
