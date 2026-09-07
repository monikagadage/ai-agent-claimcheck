#!/usr/bin/env python3
"""Claude Code `Stop`-hook shim: put the plugin root on sys.path, then run the CLI.

Kept tiny and dependency-free on purpose. All logic lives in `claimcheck/`.
The CLI always exits 0, so a hook problem can never wedge a Claude Code session.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from claimcheck.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["--from", "claude-code"]))
