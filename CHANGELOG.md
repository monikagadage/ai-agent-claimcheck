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
- Stdlib only, Python 3.9+.

_(Started life as `claude-code-receipts`; renamed to `claimcheck` before first release.)_
