# Security Policy

## Threat model

`claimcheck` runs as a Claude Code `Stop` hook. It:

- reads the hook payload on stdin and the session transcript file named in it
- reads an optional `.claimcheck.json` from the project directory
- writes a JSON result to stdout and diagnostics to stderr
- makes **no** network calls and loads **no** models
- runs exactly one kind of subprocess: **read-only `git`** (`rev-parse`, `status
  --porcelain`, `log --name-only`) in the project directory, for the file-edit check.
  A fixed argv — never a shell, never values from the transcript or config. ~10s
  timeout, any failure is swallowed. Disable with `.claimcheck.json` `{"git": false}`.

It never executes commands from the transcript or from config. A malicious transcript
or config can at worst cause `claimcheck` to print nothing (it catches all exceptions and
exits 0).

## Reporting a vulnerability

Please report suspected vulnerabilities through GitHub's
[private vulnerability reporting](https://github.com/monikagadage/ai-agent-claimcheck/security/advisories/new)
rather than a public issue.

You can expect an initial response within 7 days.

## Supported versions

Only the latest `0.x` release receives fixes while the project is pre-1.0.
