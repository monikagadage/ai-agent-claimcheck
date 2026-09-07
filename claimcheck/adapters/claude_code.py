"""Claude Code adapter.

Turns a `Stop`-hook payload (+ the session transcript it points at) into an
`AgentTurn`. Also knows how to shape findings back into Claude Code's hook-output
JSON — the one place in the codebase that is Claude-Code-specific on the way out.

Transcript lines (JSONL):

    {"type":"user","message":{"role":"user","content":"build X"}}
    {"type":"assistant","message":{"role":"assistant","content":[
        {"type":"text","text":"I'll do X"},
        {"type":"tool_use","id":"toolu_1","name":"Bash","input":{"command":"pytest"}}]}}
    {"type":"user","toolUseResult":{...},"message":{"role":"user","content":[
        {"type":"tool_result","tool_use_id":"toolu_1","content":[...],"is_error":true}]}}

A failed Bash call is marked by `is_error: true` and a tool_result whose text
starts with "Exit code N". Successful calls carry no `is_error`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..model import AgentTurn, Command, FileEdit

SOURCE = "claude-code"

_EDIT_TOOLS = {
    "Edit": "file_path",
    "Write": "file_path",
    "MultiEdit": "file_path",
    "NotebookEdit": "notebook_path",
    "Update": "file_path",
}


def parse(payload: dict) -> AgentTurn:
    """`Stop`-hook payload -> AgentTurn."""
    turn = AgentTurn(
        final_message=(payload.get("last_assistant_message") or "").strip(),
        project_dir=payload.get("cwd", "") or "",
        source=SOURCE,
    )
    tpath = payload.get("transcript_path")
    if tpath and Path(tpath).expanduser().is_file():
        turn.observed = True
        _load_transcript(turn, Path(tpath).expanduser())
    return turn


def already_reprompted(payload: dict) -> bool:
    return bool(payload.get("stop_hook_active"))


def to_hook_output(message: str, *, block: bool) -> dict:
    out: dict = {"systemMessage": message, "hookSpecificOutput": {"hookEventName": "Stop"}}
    if block:
        out["hookSpecificOutput"]["decision"] = "block"
        out["hookSpecificOutput"]["additionalContext"] = (
            message + "\n\nEither make each claim true (run the command, make the edit) "
            "or restate it accurately, then finish."
        )
    return out


# --------------------------------------------------------------------------- internals


def _load_transcript(turn: AgentTurn, path: Path) -> None:
    pending: dict[str, tuple[str, dict, bool]] = {}
    last_assistant_text = ""

    for raw in path.read_text(errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            o = json.loads(raw)
        except ValueError:
            continue

        typ = o.get("type")
        if typ not in ("user", "assistant"):
            continue
        subagent = bool(o.get("isSidechain"))
        content = (o.get("message") or {}).get("content")

        if typ == "assistant":
            for item in _items(content):
                kind = item.get("type")
                if kind == "text" and not subagent:
                    txt = item.get("text", "").strip()
                    if txt:
                        last_assistant_text = txt
                elif kind == "tool_use":
                    name = item.get("name", "")
                    tinput = item.get("input") or {}
                    tid = item.get("id", "")
                    if tid:
                        pending[tid] = (name, tinput, subagent)
                    if name in _EDIT_TOOLS:
                        p = tinput.get(_EDIT_TOOLS[name])
                        if p:
                            turn.edits.append(FileEdit(str(p), name, subagent))
                    elif name == "Bash":
                        turn.edits.extend(_edits_from_shell(tinput.get("command", ""), subagent))
            continue

        # typ == "user"
        results = [i for i in _items(content) if i.get("type") == "tool_result"]
        if not results and "toolUseResult" not in o:
            text = _plain_text(content)
            if text:
                turn.user_messages.append(text)
            continue

        for tr in results:
            name, tinput, sub = pending.get(tr.get("tool_use_id", ""), ("", {}, subagent))
            if name != "Bash":
                continue
            body = _result_text(tr.get("content"))
            code = _exit_code(body)
            ok = not bool(tr.get("is_error")) and code in (0, None)
            turn.commands.append(
                Command(
                    text=tinput.get("command", "").strip(),
                    ok=ok,
                    exit_code=code,
                    output=body[:4000],
                    subagent=sub,
                )
            )

    if not turn.final_message:
        turn.final_message = last_assistant_text


def _items(content) -> list[dict]:
    return [c for c in content if isinstance(c, dict)] if isinstance(content, list) else []


def _plain_text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    parts = [c.get("text", "") for c in _items(content) if c.get("type") == "text"]
    return " ".join(p for p in parts if p).strip()


def _result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    return ""


def _exit_code(body: str) -> int | None:
    head = body.lstrip()[:40]
    if head.startswith("Exit code "):
        digits = head[len("Exit code ") :].split()[0].strip().rstrip(".")
        if digits.isdigit():
            return int(digits)
    return None


def _edits_from_shell(command: str, subagent: bool) -> list[FileEdit]:
    out: list[FileEdit] = []

    def clean(t: str) -> str | None:
        t = t.strip().strip("\"'")
        if not t or t.startswith("-") or any(ch in t for ch in "{}$*?()`"):
            return None
        return t

    for m in re.finditer(r"\b(rm|mv|cp|touch|dd)\s+((?:-\S+\s+)*)(\S+)", command):
        target = clean(m.group(3))
        if target:
            out.append(FileEdit(target, f"bash:{m.group(1)}", subagent))
    for m in re.finditer(r"(?<![0-9])>>?\s*([^\s;|&<>]+)", command):
        target = clean(m.group(1))
        if target:
            out.append(FileEdit(target, "bash:redirect", subagent))
    return out
