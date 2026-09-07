# Contributing to receipts

Thanks for taking a look. This is a small, focused plugin and it should stay that way.

## Design rules (please read before opening a PR)

1. **Deterministic core.** `receipts/` makes no network calls and loads no models. The
   optional LLM layer (roadmap v1.1) will live behind a clear opt-in and never be the default.
2. **A false alarm is worse than a miss.** If a check isn't confident a claim is unbacked,
   it stays silent. We would rather let three real problems through than cry wolf once.
3. **Warn, don't block, by default.** Blocking is opt-in via `strict`.
4. **A hook must never wedge a session.** `main()` always exits 0. Wrap anything that can
   throw. If in doubt, print `{}` and move on.
5. **Stdlib only.** No runtime dependencies. Tests use `unittest`.

## Getting set up

```bash
git clone https://github.com/monikagadage/claude-code-receipts
cd claude-code-receipts
python -m unittest discover -s tests -v      # 3.9+
```

Try it live in another project:

```bash
claude --plugin-dir /path/to/claude-code-receipts
```

## Adding or improving a check

Each check is a function in [`receipts/checks.py`](receipts/checks.py) taking
`(session, claims, ...)` and returning `list[Finding]`. To add one:

1. Add a claim pattern + `Claim` kind in [`receipts/claims.py`](receipts/claims.py).
   Add **positive and negative** examples to `TestClaims` — negatives (questions,
   "make sure X", "if X") matter as much as positives.
2. Add the check function and wire it into `run_all_checks`, gated by an `ignore` name.
3. Add fixture-based tests. Use the `Transcript` builder in `tests/_build.py` — it emits
   the real Claude Code JSONL shape.
4. Run against a real transcript (`~/.claude/projects/<...>/*.jsonl`) and sanity-check
   for false positives before opening the PR.

## Pull requests

- One change per PR.
- `python -m unittest discover -s tests` must pass; `ruff check .` must be clean.
- Note any new false-positive risk in the PR description.
- Update `CHANGELOG.md` under the unreleased heading.

## Reporting bugs

Open an issue with the claim text, what `receipts` reported, and what you expected.
A redacted snippet of the relevant transcript lines helps a lot.
