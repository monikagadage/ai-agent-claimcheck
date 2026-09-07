"""Generic adapter — for any agent without a dedicated adapter.

Feed it a JSON object on stdin describing the turn. Everything is optional except
`final_message`; unknown keys are ignored.

    {
      "final_message": "All tests pass. I updated auth.py.",
      "user_messages": ["fix the login bug"],
      "commands": [
        {"text": "pytest -q", "ok": true, "exit_code": 0},
        {"text": "npm run build", "ok": false, "exit_code": 1}
      ],
      "edits": [{"path": "src/routes.py"}, {"path": "config.toml"}],
      "project_dir": "/path/to/project"
    }

`commands` entries also accept `command`/`cmd` for the text and `output` for the
body; `edits` entries also accept a bare string path.
"""

from __future__ import annotations

from ..model import AgentTurn, Command, FileEdit

SOURCE = "generic"


def parse(payload: dict) -> AgentTurn:
    turn = AgentTurn(
        final_message=str(payload.get("final_message") or "").strip(),
        project_dir=str(payload.get("project_dir") or payload.get("cwd") or ""),
        source=SOURCE,
        observed=True,  # caller vouches for the data they passed
    )
    for m in payload.get("user_messages") or []:
        if isinstance(m, str) and m.strip():
            turn.user_messages.append(m.strip())

    for c in payload.get("commands") or []:
        if isinstance(c, str):
            turn.commands.append(Command(text=c.strip(), ok=True))
        elif isinstance(c, dict):
            code = c.get("exit_code")
            turn.commands.append(
                Command(
                    text=str(c.get("text") or c.get("command") or c.get("cmd") or "").strip(),
                    ok=bool(c.get("ok", code in (0, None))),
                    exit_code=code if isinstance(code, int) else None,
                    output=str(c.get("output") or "")[:4000],
                )
            )

    for e in payload.get("edits") or []:
        if isinstance(e, str):
            turn.edits.append(FileEdit(path=e))
        elif isinstance(e, dict) and e.get("path"):
            turn.edits.append(FileEdit(path=str(e["path"]), how=str(e.get("how") or "")))

    return turn
