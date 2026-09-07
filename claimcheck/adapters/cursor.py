"""Cursor adapter — the `stop` hook.

Hook payload (documented, https://cursor.com/docs/hooks):
    {
      "hook_event_name": "stop",
      "conversation_id": "...", "generation_id": "...",
      "workspace_roots": ["/abs/path"],
      "transcript_path": "/abs/path/to/transcript"   # nullable
      "status": "completed" | "aborted" | "error",
      "loop_count": 0
    }

Hook output: `{"followup_message": "..."}` auto-submits as the next user message.
Cursor hooks CANNOT show a passive message and CANNOT block, so:
  - warn mode  -> return {} (findings go to CLAIMCHECK_LOG / stderr only)
  - strict mode -> return a followup_message asking the agent to fix or restate

Transcript format: NOT documented by Cursor as of this writing. `_load_transcript`
below is defensive (JSONL or JSON array; common key names). Verify against a real
file at ~/.cursor/projects/.../agent-transcripts/ and tighten as needed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..model import AgentTurn, Command, FileEdit

SOURCE = "cursor"

_SHELL_KEYS = ("command", "cmd", "shell_command", "script")
_PATH_KEYS = ("path", "file_path", "target_file", "uri", "file")


def parse(payload: dict) -> AgentTurn:
    roots = payload.get("workspace_roots") or []
    turn = AgentTurn(
        project_dir=str(roots[0]) if roots else "",
        source=SOURCE,
    )
    tpath = payload.get("transcript_path")
    if tpath and Path(tpath).expanduser().is_file():
        turn.observed = True
        _load_transcript(turn, Path(tpath).expanduser())
    return turn


def already_reprompted(payload: dict) -> bool:
    return bool(payload.get("loop_count"))


def to_hook_output(message: str, *, block: bool) -> dict:
    if not block:
        return {}  # Cursor can't surface a passive note; warn-mode findings are logged only
    return {
        "followup_message": message
        + "\n\nEither make each claim true (run the command, make the edit) "
        "or restate it accurately, then finish."
    }


# --------------------------------------------------------------------------- internals


def _load_transcript(turn: AgentTurn, path: Path) -> None:
    text = path.read_text(errors="replace")
    entries = _as_entries(text)
    last_assistant = ""

    for e in entries:
        if not isinstance(e, dict):
            continue
        role = (e.get("role") or e.get("type") or e.get("author") or "").lower()
        content = e.get("content", e.get("text", e.get("message")))

        if role in ("assistant", "ai", "model"):
            txt = _text_of(content)
            if txt:
                last_assistant = txt
            for call in _tool_calls(e, content):
                _absorb_call(turn, call)
        elif role in ("user", "human"):
            txt = _text_of(content)
            if txt and not _looks_like_tool_result(e):
                turn.user_messages.append(txt)
        elif role in ("tool", "tool_result", "function"):
            _absorb_result(turn, e, content)
        else:
            # unlabeled entry: still scavenge tool calls / results
            for call in _tool_calls(e, content):
                _absorb_call(turn, call)
            _absorb_result(turn, e, content)

    if not turn.final_message:
        turn.final_message = last_assistant


def _as_entries(text: str) -> list:
    text = text.strip()
    if not text:
        return []
    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            return obj
        if isinstance(obj, dict):
            for k in ("messages", "entries", "transcript", "events"):
                if isinstance(obj.get(k), list):
                    return obj[k]
            return [obj]
    except ValueError:
        pass
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _text_of(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, str):
                parts.append(c)
            elif isinstance(c, dict) and c.get("type") in (None, "text", "output_text"):
                parts.append(c.get("text", ""))
        return " ".join(p for p in parts if p).strip()
    if isinstance(content, dict):
        return str(content.get("text", "")).strip()
    return ""


def _tool_calls(entry: dict, content) -> list:
    for key in ("tool_calls", "toolCalls", "tools", "actions"):
        v = entry.get(key)
        if isinstance(v, list):
            return v
    if isinstance(content, list):
        return [
            c for c in content if isinstance(c, dict) and c.get("type") in ("tool_use", "tool_call")
        ]
    return []


def _first(d: dict, keys) -> str:
    for k in keys:
        if d.get(k):
            return str(d[k])
    args = d.get("input") or d.get("args") or d.get("arguments") or d.get("parameters") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {}
    if isinstance(args, dict):
        for k in keys:
            if args.get(k):
                return str(args[k])
    return ""


def _tool_name(call: dict) -> str:
    return str(call.get("name") or call.get("tool") or call.get("function", {}) or "").lower()


def _absorb_call(turn: AgentTurn, call: dict) -> None:
    if not isinstance(call, dict):
        return
    name = _tool_name(call)
    shell = _first(call, _SHELL_KEYS)
    if shell:
        turn.commands.append(Command(text=shell.strip(), ok=True))
        return
    if any(k in name for k in ("shell", "terminal", "bash", "run_")):
        return
    path = _first(call, _PATH_KEYS)
    if path:
        turn.edits.append(FileEdit(path=path.strip(), how=name or "edit"))


def _absorb_result(turn: AgentTurn, entry: dict, content) -> None:
    if not turn.commands:
        return
    body = _text_of(content) or _text_of(entry.get("output"))
    is_error = bool(entry.get("is_error") or entry.get("error") or entry.get("exit_code"))
    m = re.match(r"\s*(?:exit code|exited with)\s+(\d+)", body, re.I)
    code = (
        int(m.group(1))
        if m
        else (entry.get("exit_code") if isinstance(entry.get("exit_code"), int) else None)
    )
    last = turn.commands[-1]
    if last.output:
        return
    last.output = body[:4000]
    last.exit_code = code
    last.ok = not is_error and code in (0, None)


def _looks_like_tool_result(entry: dict) -> bool:
    return any(k in entry for k in ("tool_call_id", "toolCallId", "tool_use_id", "tool_result"))
