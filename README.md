# ai-agent-claimcheck

[![ci](https://github.com/monikagadage/ai-agent-claimcheck/actions/workflows/test.yml/badge.svg)](https://github.com/monikagadage/ai-agent-claimcheck/actions/workflows/test.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![python: 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![status: alpha](https://img.shields.io/badge/status-alpha-orange)

**Your AI coding agent says "Done ✅". `claimcheck` checks whether it actually did the thing.**

> Repo & plugin: `ai-agent-claimcheck`. Short name and Python import path: `claimcheck`.

When the agent finishes a turn, `claimcheck` reads what it *claimed* and compares it to
what the session actually *shows*:

- "all tests pass" — but no test command ran this session
- "I removed the obsolete `bun.lockb`" — but nothing deleted it and `git status` doesn't show it
- "as we agreed, switching to GraphQL" — but you never said that

Deterministic — no LLM, no network, no API cost. It reads the transcript your agent
already writes. **Warn-only by default**: it surfaces the unbacked claims and lets you decide.

```
⚠️  claimcheck — 2 claims not backed by this session:
  • "All tests pass."          → no test command ran this session
  • "I refactored auth.py."    → nothing in the session or git modified `auth.py`
```

If nothing is wrong — no claims, or every claim checks out — it stays completely silent.

---

## Why

"The agent said it was done and it wasn't" is one of the loudest complaints about AI
coding agents in 2026 — false "done", summaries that don't match the diff, invented
agreements ([r/ClaudeAI](https://www.reddit.com/r/ClaudeAI/comments/1v2ssw4/)). The usual
answers are a habit ("always ask for receipts"), a hook that runs one *fixed* command, or
a fresh session that reviews the work — one model grading another.

`claimcheck` is the deterministic, external one: it reads the **specific claims** the
agent made and checks each against what the transcript (and `git`) actually show —
automatically, at the moment the claim is made, whether the agent cooperates or not.

It is **not** a replacement for review or CI. It's a cheap tripwire for the specific
class of "it narrated something that didn't happen."

## Status

Alpha. Heavily dogfooded — the claim extractor has ~12 false-positive guards tuned against
a **1,600-turn sweep of real Claude Code history** (`scripts/sweep.py`), on which it now
produces zero false positives. Whether it catches enough *real* misfires to earn its place
is exactly what this alpha is meant to find out — [feedback welcome](#feedback).

## Platforms

| Surface | Status |
| --- | --- |
| **Claude Code** — CLI, IDE extensions, desktop "Code" tab | ✅ supported — a `Stop`-hook plugin, or a `settings.json` hook |
| **Cursor** | ✅ `stop`-hook adapter (`--from cursor`); transcript parsing is defensive — [verify against a real session](#install-cursor) |
| **Any agent** | ✅ `--from generic` — pipe it a small JSON of the turn |
| **Cowork** (Claude Desktop) | ⚠️ user `settings.json` hooks don't fire there |
| Codex CLI, VS Code Copilot | planned ([details](#roadmap)) |

The claim logic and checks are platform-neutral (`claimcheck/claims.py`,
`claimcheck/checks.py`) — every platform is one small file in `claimcheck/adapters/`.
[Adapters welcome.](CONTRIBUTING.md#adding-a-platform-adapter)

## Install — Claude Code

```bash
/plugin marketplace add monikagadage/ai-agent-claimcheck
/plugin install ai-agent-claimcheck@monikagadage
```

Requires `python3` on your `PATH` (3.9+). No pip packages. To try it without installing:

```bash
git clone https://github.com/monikagadage/ai-agent-claimcheck
claude --plugin-dir ./ai-agent-claimcheck
```

To see a ✅ line when claims check out (not just ⚠️ on problems), add
`CLAIMCHECK_CONFIRM=1` to the hook command, or `{"confirm": true}` to `.claimcheck.json`.

## Install — Cursor

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

Cursor's `stop` hook can't show a passive message, so in warn mode findings go to the
**log only** — set `CLAIMCHECK_LOG` (below). Or set `{"strict": true}` and it sends the
agent a follow-up. The Cursor transcript format is undocumented and parsed defensively;
if it misses commands/edits on your machine, open an issue with a redacted snippet from
`~/.cursor/projects/.../agent-transcripts/`.

## Any other agent — `generic`

```bash
echo '{
  "final_message": "All tests pass. I updated auth.py.",
  "user_messages": ["fix the login bug"],
  "commands": [{"text": "pytest -q", "ok": true, "exit_code": 0}],
  "edits": [{"path": "src/routes.py"}]
}' | python -m claimcheck.cli --from generic --text
```

Wire that into whatever end-of-turn mechanism your agent has.

## What it checks

| Claim in the final message | Backed by | Flagged when |
| --- | --- | --- |
| "tests pass", "12 tests green", "all passing" | a test-runner command ran **and** exited 0 (pytest, jest/vitest, `go test`, `cargo test`, `mvn`/`gradle`/`sbt`, rspec, `dotnet test`, `make test`, …) | no test command ran, or the only one failed |
| "builds", "compiles cleanly", "no type errors" | a build/typecheck command ran and exited 0 (`tsc`, `mypy`, `go build`, `cargo`, `javac`, `python -c "import …"`, `node --check`, …) | none ran, or the only one failed |
| "I updated / created / deleted `path`", "Created `X.kt`", "`Y` has been created" | an edit / `rm` / `mv` touched that path this session, **or** `git status` / recent commits show it changed | nothing in the session or git touched it |
| "as we agreed / decided / you asked, X" | X's keywords appear in one of **your** earlier messages | X appears only in the agent's own messages |

Every check stays silent unless it's confident. A missed claim is fine; a false alarm
is not. The extractor skips ~12 shapes that *look* like claims but aren't — quotes and
code blocks, hypotheticals ("for example…"), questions, instructions ("re-run and
confirm…"), restated goals ("you asked me to…"), coverage inventory ("45 pytest tests"),
reported speech ("the README says…"), and more.

## Configuration

Optional `.claimcheck.json` in the project root:

```json
{
  "strict": false,
  "confirm": false,
  "git": true,
  "ignore": [],
  "test_patterns": [],
  "build_patterns": []
}
```

| key | default | meaning |
| --- | --- | --- |
| `strict` | `false` | `true` → **block** the turn and send the agent back, instead of just warning |
| `confirm` | `false` | `true` → also show `✅ claimcheck — N claims check out` when everything verifies |
| `git` | `true` | `false` → skip the read-only `git` fallback in the file-edit check |
| `ignore` | `[]` | checks to skip: `tests`, `build`, `edits`, `agreements` |
| `test_patterns` / `build_patterns` | `[]` | extra regexes for project-specific commands |

`strict` and `confirm` also read `CLAIMCHECK_STRICT=1` / `CLAIMCHECK_CONFIRM=1` from the
environment (for a global default in the hook command); a project's `.claimcheck.json` wins.

## Keep a findings log

Set `CLAIMCHECK_LOG` to a file path and every flagged turn is appended as one JSON line —
timestamp, project, the final message, each finding. In the hook command:

```
CLAIMCHECK_LOG="$HOME/.claude/claimcheck-log.jsonl" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/hook.py"
```

## CI / pre-commit

The CLI reads a platform payload on stdin and exits non-zero (with `--strict-exit`) when
claims don't check out:

```bash
cat stop-hook-payload.json | python -m claimcheck.cli --from claude-code --text --strict-exit
```

## Sweep your own history

Before trusting it, run it over your past sessions:

```bash
python3 scripts/sweep.py             # each session's final turn
python3 scripts/sweep.py --strict    # every turn, against only what preceded it
```

Read-only. Prints every turn it would have flagged, plus a per-claim-kind breakdown.

## How it works

The agent's `Stop` / `stop` hook fires when it tries to end a turn. The adapter reads the
final message + the session transcript (commands and their exit status, file edits, your
messages) into a neutral `AgentTurn`. The core extracts claims (regex), runs the four
checks, and prints the platform's hook result. Any internal error → prints nothing, exits
0. **The only subprocess it ever runs is read-only `git`** (fixed argv, never a shell) —
see [SECURITY.md](SECURITY.md).

```
claimcheck/
├── model.py           # AgentTurn — the neutral shape every adapter produces
├── claims.py          # extract claims from the final message      (platform-neutral)
├── checks.py          # the four checks (+ read-only git for edits) (platform-neutral)
├── run.py             # AgentTurn + config -> Result(claims, findings)
├── report.py          # findings / confirmation -> text
├── cli.py             # stdin -> adapter -> run -> stdout
└── adapters/
    ├── claude_code.py # Stop-hook payload + transcript JSONL -> AgentTurn
    ├── cursor.py      # stop-hook payload + agent transcript -> AgentTurn
    └── generic.py     # a plain JSON turn description -> AgentTurn
```

## Limitations

Deliberately narrow and deterministic. It does **not**:

- diff a code change against the prose summary (needs an LLM — planned, opt-in)
- tell test runners apart — if *any* suite passed, "tests pass" counts as backed
- understand paraphrase or real negation ("as we discussed, Postgres" vs an earlier "not Postgres")
- verify claims in a session that ran no commands and made no edits (nothing to check against)

## Roadmap

- Opt-in LLM layer — on `Stop`, a subagent cites the tool call behind each claim or retracts it (the semantic cases regex can't reach).
- `PostToolUse` companion — catch "I ran the tests" mid-turn.
- Diff-vs-summary check.
- **Codex CLI** adapter (`notify` hooks + `~/.codex/` session logs).
- **VS Code Copilot** — no agent-lifecycle API, but VS Code persists chat sessions to
  `chatSessions/*.jsonl` (a patch stream that replays to the prose + tool calls + edits).
  Path: a `replay` module + `copilot` adapter + a `claimcheck watch` poller.

## Feedback

Tried it? Two things help most:

1. **False positives** — a `⚠️` that was wrong. Open an issue with the claim text and why
   (or turn on `CLAIMCHECK_LOG` and attach the file).
2. **Real catches** — a time it flagged something the agent genuinely didn't do. Those are
   the whole point; tell me.

## Development

```bash
python -m unittest discover -s tests -v
ruff check . && ruff format --check .
```

Stdlib only. Tests build fake transcripts in the real JSONL shapes and assert on the findings.

## License

MIT
