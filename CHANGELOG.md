# Changelog

## [0.1.0] — unreleased

First cut.

- `Stop` hook that checks the agent's final-message claims against the session transcript.
- Four deterministic checks: test claims, build/typecheck claims, file-edit claims, invented agreements.
- Warn-only by default; `strict` mode blocks the turn.
- `.receipts.json` config: `strict`, `ignore`, `test_patterns`, `build_patterns`.
- Transcript parser for the real Claude Code JSONL format (nested `message.content`,
  `is_error` / `Exit code N` for failed commands, subagent/sidechain calls).
- Stdlib only, Python 3.9+.
