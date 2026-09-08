"""Config, lowest precedence first:

  1. defaults below
  2. env vars — CLAIMCHECK_CONFIRM / CLAIMCHECK_STRICT (truthy -> True), for a global
     default in the hook command
  3. `.claimcheck.json` in the project root:

     {
       "strict": false,              // true -> block the turn instead of just warning
       "confirm": false,             // true -> also show a ✅ line when claims check out
       "ignore": ["agreements"],     // checks to skip: tests | build | edits | agreements
       "test_patterns": ["\\bbazel test\\b"],
       "build_patterns": ["\\bbazel build\\b"]
     }

A project's `.claimcheck.json` always wins over an env var.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT = {
    "strict": False,
    "confirm": False,
    "git": True,
    "ignore": [],
    "test_patterns": [],
    "build_patterns": [],
}
FILENAMES = (".claimcheck.json", "claimcheck.config.json")
_TRUTHY = {"1", "true", "yes", "on"}


def load_config(project_dir: str | None) -> dict:
    cfg = dict(DEFAULT)

    for key, env in (("confirm", "CLAIMCHECK_CONFIRM"), ("strict", "CLAIMCHECK_STRICT")):
        val = os.environ.get(env)
        if val is not None:
            cfg[key] = val.strip().lower() in _TRUTHY

    if project_dir:
        base = Path(project_dir).expanduser()
        for name in FILENAMES:
            p = base / name
            if p.is_file():
                try:
                    data = json.loads(p.read_text())
                except ValueError:
                    break
                if isinstance(data, dict):
                    cfg.update({k: v for k, v in data.items() if k in DEFAULT})
                break
    return cfg
