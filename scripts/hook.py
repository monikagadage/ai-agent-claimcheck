#!/usr/bin/env python3
"""Stop-hook shim: put the plugin root on sys.path, then run receipts.verify.

Kept tiny and dependency-free on purpose. All real logic lives in `receipts/`.
Exit code is always 0 (receipts.main guarantees it) so a hook problem can never
wedge a Claude Code session.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from receipts.verify import main

if __name__ == "__main__":
    raise SystemExit(main())
