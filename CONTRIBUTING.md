# Contributing to claimcheck

Thanks for taking a look. This is a small, focused tool and it should stay that way.

## Design rules (please read before opening a PR)

1. **Deterministic core.** No network, no models. The only subprocess is read-only `git`
   in the file-edit check (fixed argv, never a shell) — anything heavier needs a strong
   case and probably a config gate. The LLM layer on the roadmap will be opt-in, never
   the default.
2. **The core is platform-neutral.** `claims.py` / `checks.py` / `run.py` only ever see an
   `AgentTurn` (`claimcheck/model.py`). Anything platform-specific — parsing a transcript,
   shaping hook output — lives in `claimcheck/adapters/<platform>.py`.
3. **A false alarm is worse than a miss.** If a check isn't confident a claim is unbacked,
   it stays silent. We would rather let three real problems through than cry wolf once.
4. **Warn, don't block, by default.** Blocking is opt-in via `strict`.
5. **A hook must never wedge a session.** The CLI always exits 0 (unless `--strict-exit`).
   Wrap anything that can throw.
6. **Stdlib only.** No runtime dependencies. Tests use `unittest`.

## Getting set up

```bash
git clone https://github.com/monikagadage/ai-agent-claimcheck
cd ai-agent-claimcheck
python -m unittest discover -s tests -v      # 3.9+
```

Try it live in another project:

```bash
claude --plugin-dir /path/to/ai-agent-claimcheck
```

## Adding or improving a check

Each check is a function in [`claimcheck/checks.py`](claimcheck/checks.py) taking
`(turn, claims, ...)` and returning `list[Finding]`. To add one:

1. Add a claim pattern + `Claim` kind in [`claimcheck/claims.py`](claimcheck/claims.py).
   Add **positive and negative** examples to `TestClaims` — negatives (questions,
   "make sure X", "if X") matter as much as positives.
2. Add the check function and wire it into `run_all_checks`, gated by an `ignore` name.
3. Add fixture-based tests. Use the `Transcript` builder in `tests/_build.py`.
4. Run against a real transcript (`~/.claude/projects/<...>/*.jsonl`) and sanity-check
   for false positives before opening the PR.

## Adding a platform adapter

1. Write `claimcheck/adapters/<name>.py` with `parse(payload: dict) -> AgentTurn`
   (and, if the platform has a hook-output format, `to_hook_output(...)`).
2. Register it in `claimcheck/adapters/__init__.py`.
3. `claims.py` / `checks.py` / `run.py` need **no** changes.

## Pull requests

- One change per PR.
- `python -m unittest discover -s tests` must pass; `ruff check .` and `ruff format --check .` must be clean.
- Note any new false-positive risk in the PR description.
- Update `CHANGELOG.md` under the unreleased heading.

## Reporting bugs

Open an issue with the claim text, what `claimcheck` reported, and what you expected.
A redacted snippet of the relevant transcript lines helps a lot.
