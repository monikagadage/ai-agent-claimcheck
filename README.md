# receipts

[![ci](https://github.com/monikagadage/claude-code-receipts/actions/workflows/test.yml/badge.svg)](https://github.com/monikagadage/claude-code-receipts/actions/workflows/test.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![python: 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)

**Claude Code says "Done ✅". This checks whether it actually did the thing.**

`receipts` is a Claude Code plugin that runs when Claude finishes a turn and compares
what it *claimed* against what the session transcript *shows*:

- "all tests pass" — but no test command ran this session
- "I updated `src/auth.py`" — but nothing touched that file
- "as we agreed, switching to GraphQL" — but you never said that

It's a `Stop` hook. Deterministic — no network calls, no model, no API cost. It reads
the transcript Claude Code already writes to disk. **Warn-only by default**: it surfaces
the unbacked claims and lets you decide.

```
⚠️  receipts — 2 claims not backed by this session:
  • "All tests pass."          → no test command ran this session
  • "I refactored auth.py."    → nothing modified `auth.py`  (files edited: routes.py, config.py)
```

## Why

"Claude claimed the work was done and it wasn't" is one of the most common Claude Code
complaints of 2026. The usual advice is a habit ("always ask for receipts") or a Stop
hook that runs a *fixed* command like `npm test`. `receipts` is different: it reads the
**specific claims** in Claude's final message and checks each one, with zero configuration.

## Install

```bash
/plugin marketplace add monikagadage/claude-code-receipts
/plugin install receipts@monikagadage
```

Requires `python3` on your `PATH` (3.9+). No pip packages.

To try it without installing:

```bash
git clone https://github.com/monikagadage/claude-code-receipts
claude --plugin-dir ./claude-code-receipts
```

## What it checks (v1)

| Claim in Claude's final message | Backed by | Flagged when |
| --- | --- | --- |
| "tests pass", "all green", "suite is passing" | a test-runner command ran **and** exited 0 (pytest, jest/vitest, `go test`, `cargo test`, `mvn`/`gradle test`, rspec, `dotnet test`, …) | no test command ran, or the only one failed |
| "builds", "compiles", "no type errors", "typecheck passes" | a build/typecheck command ran and exited 0 (`tsc`, `mypy`, `go build`, `cargo build`, `javac`, `npm run build`, …) | none ran, or the only one failed |
| "I updated / created / deleted `path/to/file`" | an `Edit` / `Write` / `rm` / `mv` touched that path this session | nothing touched it |
| "as we agreed / decided / you asked, X" | X's keywords appear in one of **your** earlier messages | X appears only in Claude's own messages |

A check stays silent unless it's confident. Missing a claim is fine; a false alarm is not.

## Configuration

Optional `.receipts.json` in your project root:

```json
{
  "strict": false,
  "ignore": ["agreements"],
  "test_patterns": ["\\bbazel test\\b"],
  "build_patterns": ["\\bbazel build\\b"]
}
```

| key | default | meaning |
| --- | --- | --- |
| `strict` | `false` | `true` → **block** the turn and send Claude back to make the claim true, instead of just warning |
| `ignore` | `[]` | check names to skip: `tests`, `build`, `edits`, `agreements` |
| `test_patterns` / `build_patterns` | `[]` | extra regexes for project-specific commands |

## How it works

The `Stop` hook fires when Claude tries to end its turn. Claude Code hands the hook:

- `last_assistant_message` — the final text → **the claims**
- `transcript_path` — a JSONL log of every tool call this session (commands + exit status, file edits)

`receipts` parses the claims (regex), loads the tool-call history, runs the four checks,
and prints a hook result. On any internal error it prints nothing and exits 0 — a hook
bug must never wedge your session.

## Limitations (read this)

v1 is deliberately narrow and deterministic. It does **not**:

- check whether a code *diff* matches the prose summary (needs an LLM — planned as an opt-in layer)
- tell apart test runners (if *any* test suite passed, "tests pass" is considered backed)
- understand paraphrase or negation ("as we discussed, Postgres" vs an earlier "let's not use Postgres")
- resolve monorepo path aliases perfectly

It catches the blunt, common cases well. See [ROADMAP](#roadmap).

## Roadmap

- **v1.1** — opt-in LLM layer: on `Stop`, ask a subagent "cite the tool call behind each claim or retract it". Catches the semantic cases regex can't.
- **v1.1** — `PostToolUse` companion: catch "I ran the tests" mid-turn.
- **v1.2** — diff-vs-summary check.

## Development

```bash
python -m unittest discover -s tests -v
```

Stdlib only. Tests build fake transcripts in the real Claude Code JSONL shape and assert
on the findings.

## License

MIT
