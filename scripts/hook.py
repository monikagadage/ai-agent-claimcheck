#!/usr/bin/env python3
"""Hook shim: put the repo root on sys.path, then run the CLI.

Kept tiny and dependency-free on purpose. All logic lives in `claimcheck/`.
The CLI always exits 0, so a hook problem can never wedge a session.

Claude Code (no args needed):
    python3 /path/scripts/hook.py
Cursor:
    python3 /path/scripts/hook.py --from cursor
Any other arg is forwarded to `claimcheck.cli` as-is.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from claimcheck.cli import main

if __name__ == "__main__":
    argv = sys.argv[1:] or ["--from", "claude-code"]
    raise SystemExit(main(argv))
