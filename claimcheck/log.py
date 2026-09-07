"""Optional findings log.

When the CLAIMCHECK_LOG env var points at a file, every turn that produces findings
appends one JSON line there — timestamp, project, the final message, and each finding.
Useful for reviewing false positives and tuning the claim patterns.

Best-effort: any failure to write is swallowed. Never breaks the hook.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .checks import Finding
from .model import AgentTurn

ENV_VAR = "CLAIMCHECK_LOG"


def append(turn: AgentTurn, findings: list[Finding]) -> None:
    dest = os.environ.get(ENV_VAR)
    if not dest or not findings:
        return
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source": turn.source,
        "project_dir": turn.project_dir,
        "final_message": turn.final_message,
        "findings": [
            {"kind": f.kind, "claim": f.claim, "reason": f.reason, "evidence": f.evidence}
            for f in findings
        ],
    }
    try:
        p = Path(dest).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass
