"""Optional per-project config: `.claimcheck.json` in the project root.

{
  "strict": false,              // true -> block the turn instead of just warning
  "ignore": ["agreements"],     // checks to skip: tests | build | edits | agreements
  "test_patterns": ["\\bbazel test\\b"],
  "build_patterns": ["\\bbazel build\\b"]
}
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT = {"strict": False, "ignore": [], "test_patterns": [], "build_patterns": []}
FILENAMES = (".claimcheck.json", "claimcheck.config.json")


def load_config(project_dir: str | None) -> dict:
    cfg = dict(DEFAULT)
    if not project_dir:
        return cfg
    base = Path(project_dir).expanduser()
    for name in FILENAMES:
        p = base / name
        if p.is_file():
            try:
                data = json.loads(p.read_text())
            except ValueError:
                return cfg
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if k in DEFAULT})
            break
    return cfg
