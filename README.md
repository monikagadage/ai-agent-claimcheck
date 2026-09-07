# claimcheck

[![ci](https://github.com/monikagadage/claimcheck/actions/workflows/test.yml/badge.svg)](https://github.com/monikagadage/claimcheck/actions/workflows/test.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![python: 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)

**Your AI coding agent says "Done ✅". `claimcheck` checks whether it actually did the thing.**

When the agent finishes a turn, `claimcheck` reads what it *claimed* and compares it to
what the session actually *shows*:

- "all tests pass" — but no test command ran this session
- "I updated `src/auth.py`" — but nothing touched that file
- "as we agreed, switching to GraphQL" — but you never said that

Deterministic — no network calls, no model, no API cost. It reads the transcript your
agent already writes. **Warn-only by default**: it surfaces the unbacked claims and lets
you decide.

```
⚠️  claimcheck — 2 claims not backed by this session:
  • "All tests pass."          → no test command ran this session
  • "I refactored auth.py."    → nothing modified `auth.py`  (files edited: routes.py, config.py)
```

## Why

"The agent claimed the work was done and it wasn't" is one of the most common complaints
about AI coding agents in 2026 — false "done", summaries that don't match the diff,
invented agreements. The usual advice is a habit ("always ask for receipts") or a hook
that runs a *fixed* command like `npm test`. `claimcheck` is different: it reads the
**specific claims** the agent made and checks each one, with zero configuration.

## Platforms

| Platform | Status |
| --- | --- |
| **Claude Code** | ✅ supported (a `Stop`-hook plugin) |
| Cursor | planned |
| Codex CLI | planned |
| Any transcript | via the CLI (`claimcheck --from …`) |

The claim logic and the checks are platform-neutral (`claimcheck/claims.py`,
`claimcheck/checks.py`). Each platform is one small adapter in `claimcheck/adapters/`.
[Adapters welcome.](CONTRIBUTING.md#adding-a-platform-adapter)

## Install (Claude Code)

```bash
/plugin marketplace add monikagadage/claimcheck
/plugin install claimcheck@monikagadage
```

Requires `python3` on your `PATH` (3.9+). No pip packages.

Try it without installing:

```bash
git clone https://github.com/monikagadage/claimcheck
claude --plugin-dir ./claimcheck
```

## What it checks (v1)

| Claim in the agent's final message | Backed by | Flagged when |
| --- | --- | --- |
| "tests pass", "all green", "suite is passing" | a test-runner command ran **and** exited 0 (pytest, jest/vitest, `go test`, `cargo test`, `mvn`/`gradle test`, rspec, `dotnet test`, …) | no test command ran, or the only one failed |
| "builds", "compiles", "no type errors", "typecheck passes" | a build/typecheck command ran and exited 0 (`tsc`, `mypy`, `go build`, `cargo build`, `javac`, `npm run build`, …) | none ran, or the only one failed |
| "I updated / created / deleted `path/to/file`" | an edit or an `rm` / `mv` touched that path this session | nothing touched it |
| "as we agreed / decided / you asked, X" | X's keywords appear in one of **your** earlier messages | X appears only in the agent's own messages |

A check stays silent unless it's confident. Missing a claim is fine; a false alarm is not.

## Configuration

Optional `.claimcheck.json` in your project root:

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
| `strict` | `false` | `true` → **block** the turn and send the agent back to make the claim true, instead of just warning |
| `ignore` | `[]` | checks to skip: `tests`, `build`, `edits`, `agreements` |
| `test_patterns` / `build_patterns` | `[]` | extra regexes for project-specific commands |

## Use it in CI / pre-commit

The CLI reads a platform payload on stdin and exits non-zero (with `--strict-exit`) when
claims don't check out:

```bash
cat stop-hook-payload.json | python -m claimcheck.cli --from claude-code --text --strict-exit
```

## How it works

The Claude Code `Stop` hook fires when the agent tries to end its turn. It hands the hook:

- `last_assistant_message` — the final text → **the claims**
- `transcript_path` — a JSONL log of every tool call this turn (commands + exit status, file edits)

The adapter turns that into a neutral `AgentTurn`; the core parses the claims (regex),
runs the four checks, and prints a hook result. On any internal error it prints nothing
and exits 0 — a hook bug must never wedge your session.

```
claimcheck/
├── model.py            # AgentTurn — the neutral shape every adapter produces
├── claims.py           # extract claims from the final message   (platform-neutral)
├── checks.py           # the four checks                          (platform-neutral)
├── run.py              # AgentTurn + config -> findings
├── report.py           # findings -> text
├── cli.py              # stdin -> adapter -> run -> stdout
└── adapters/
    └── claude_code.py  # Stop-hook payload + transcript JSONL -> AgentTurn
```

## Limitations (read this)

v1 is deliberately narrow and deterministic. It does **not**:

- check whether a code *diff* matches the prose summary (needs an LLM — planned, opt-in)
- tell test runners apart (if *any* test suite passed, "tests pass" is considered backed)
- understand paraphrase or negation ("as we discussed, Postgres" vs an earlier "let's not use Postgres")
- resolve monorepo path aliases perfectly

It catches the blunt, common cases well.

## Roadmap

- Opt-in LLM layer: on `Stop`, ask a subagent "cite the tool call behind each claim or retract it" — catches the semantic cases regex can't.
- `PostToolUse` companion: catch "I ran the tests" mid-turn.
- Diff-vs-summary check.
- Cursor and Codex CLI adapters.

## Development

```bash
python -m unittest discover -s tests -v
ruff check . && ruff format --check .
```

Stdlib only. Tests build fake transcripts in the real Claude Code JSONL shape and assert
on the findings.

## License

MIT
