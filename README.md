# ai-agent-claimcheck

[![ci](https://github.com/monikagadage/ai-agent-claimcheck/actions/workflows/test.yml/badge.svg)](https://github.com/monikagadage/ai-agent-claimcheck/actions/workflows/test.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![python: 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)

**Your AI coding agent says "Done ✅". `claimcheck` checks whether it actually did the thing.**

> Repo/plugin: `ai-agent-claimcheck`. Called `claimcheck` for short (and that's the Python import path).

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

| Surface | Status |
| --- | --- |
| **Claude Code** — CLI, IDE extensions, desktop Code tab | ✅ `Stop`-hook plugin or `settings.json` hook |
| **Cursor** | ✅ `stop`-hook adapter (`--from cursor`) — transcript parsing is provisional, verify against a real session |
| **Cowork** (Claude Desktop) | ⚠️ user `settings.json` hooks don't fire here; try installing as a plugin (untested) |
| **Any agent** | ✅ `--from generic` — pipe it a small JSON of the turn (no auto-hook) |
| Codex CLI, VS Code Copilot | planned — Copilot needs a companion extension (no end-of-turn hook API) |

The claim logic and the checks are platform-neutral (`claimcheck/claims.py`,
`claimcheck/checks.py`). Each platform is one small adapter in `claimcheck/adapters/`.
[Adapters welcome.](CONTRIBUTING.md#adding-a-platform-adapter)

## Install (Claude Code)

```bash
/plugin marketplace add monikagadage/ai-agent-claimcheck
/plugin install ai-agent-claimcheck@monikagadage
```

Requires `python3` on your `PATH` (3.9+). No pip packages.

Try it without installing:

```bash
git clone https://github.com/monikagadage/ai-agent-claimcheck
claude --plugin-dir ./ai-agent-claimcheck
```

## Install (Cursor)

Clone the repo, then add to `~/.cursor/hooks.json`:

```json
{
  "version": 1,
  "hooks": {
    "stop": [
      { "command": "python3 /abs/path/to/ai-agent-claimcheck/scripts/hook.py --from cursor" }
    ]
  }
}
```

Cursor's `stop` hook can't show a passive message, so **warn mode writes to the log
only** — set `CLAIMCHECK_LOG` (see below), or use `"strict": true` in `.claimcheck.json`
to have it send a follow-up asking the agent to fix or restate.

> The Cursor transcript format isn't documented; the adapter parses it defensively.
> If it misses commands/edits on your machine, open an issue with a redacted transcript
> snippet from `~/.cursor/projects/.../agent-transcripts/`.

## Any other agent (`generic`)

Pipe a JSON description of the turn to the CLI:

```bash
echo '{
  "final_message": "All tests pass. I updated auth.py.",
  "user_messages": ["fix the login bug"],
  "commands": [{"text": "pytest -q", "ok": true, "exit_code": 0}],
  "edits": [{"path": "src/routes.py"}]
}' | python -m claimcheck.cli --from generic --text
```

Wire that into whatever end-of-turn mechanism your agent has.

## What it checks (v1)

| Claim in the agent's final message | Backed by | Flagged when |
| --- | --- | --- |
| "tests pass", "all green", "suite is passing" | a test-runner command ran **and** exited 0 (pytest, jest/vitest, `go test`, `cargo test`, `mvn`/`gradle test`, rspec, `dotnet test`, …) | no test command ran, or the only one failed |
| "builds", "compiles", "no type errors", "typecheck passes" | a build/typecheck command ran and exited 0 (`tsc`, `mypy`, `go build`, `cargo build`, `javac`, `npm run build`, …) | none ran, or the only one failed |
| "I updated / created / deleted `path/to/file`" (also "Created `X.kt`", "the new `Y.kt`", "`Z` has been created") | an edit / `rm` / `mv` touched that path this session, **or** `git status` / recent commits show it changed | nothing in the session or git touched it |
| "as we agreed / decided / you asked, X" | X's keywords appear in one of **your** earlier messages | X appears only in the agent's own messages |

By default claimcheck is **silent unless something's wrong** — no claims, or all claims
check out → nothing. Turn on `confirm` (below) if you want a ✅ line when they check out.

A check stays silent unless it's confident. Missing a claim is fine; a false alarm is not.

## Configuration

Optional `.claimcheck.json` in your project root:

```json
{
  "strict": false,
  "confirm": false,
  "git": true,
  "ignore": ["agreements"],
  "test_patterns": ["\\bbazel test\\b"],
  "build_patterns": ["\\bbazel build\\b"]
}
```

| key | default | meaning |
| --- | --- | --- |
| `strict` | `false` | `true` → **block** the turn and send the agent back to make the claim true, instead of just warning |
| `confirm` | `false` | `true` → also show `✅ claimcheck — N claims check out` when the turn's claims all verify (silent when there are no claims) |
| `git` | `true` | `false` → don't shell out to read-only `git` for the file-edit check (regex/transcript evidence only) |
| `ignore` | `[]` | checks to skip: `tests`, `build`, `edits`, `agreements` |
| `test_patterns` / `build_patterns` | `[]` | extra regexes for project-specific commands |

`confirm` and `strict` also read from env vars — `CLAIMCHECK_CONFIRM=1`, `CLAIMCHECK_STRICT=1` —
so you can set a global default in your hook command. A project's `.claimcheck.json` wins.

## Keep a findings log

Set the `CLAIMCHECK_LOG` env var to a file path and every flagged turn is appended there
as one JSON line — timestamp, project, the final message, each finding. Useful for
reviewing false positives and tuning the claim patterns. In a hook command:

```
CLAIMCHECK_LOG="$HOME/.claude/claimcheck-log.jsonl" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/hook.py"
```

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

- Verify the Cursor transcript parser against real sessions.
- Codex CLI adapter (has `notify` hooks + `~/.codex/` session logs).
- Opt-in LLM layer: on `Stop`, ask a subagent "cite the tool call behind each claim or retract it" — catches the semantic cases regex can't.
- `PostToolUse` companion: catch "I ran the tests" mid-turn.
- Diff-vs-summary check.
- **VS Code Copilot** — no agent-lifecycle API exists. Copilot *does* persist chat
  sessions to disk, but in an undocumented incremental-patch format. A background
  file-watcher + a zsh `preexec` hook feeding `--from generic` is the only path, and
  it's fragile. Not planned; use `--from generic` manually.

## Development

```bash
python -m unittest discover -s tests -v
ruff check . && ruff format --check .
```

Stdlib only. Tests build fake transcripts in the real Claude Code JSONL shape and assert
on the findings.

## License

MIT
