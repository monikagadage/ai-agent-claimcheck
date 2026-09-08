# demo

`demo.gif` in the project README is generated from `demo.tape` with
[vhs](https://github.com/charmbracelet/vhs):

```bash
brew install vhs        # or: go install github.com/charmbracelet/vhs@latest
vhs demo/demo.tape       # writes demo/demo.gif
```

The two fixtures are `generic`-adapter payloads:

- `turn-lie.json` — the agent claims "all tests pass" and "removed `bun.lockb`", but the
  session only edited `src/config.ts` and ran `ls` → **both claims flagged**.
- `turn-ok.json` — same message, but `npm test` ran and `git rm bun.lockb` happened →
  **both claims check out** (`✅` shown because `CLAIMCHECK_CONFIRM=1`).
