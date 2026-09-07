"""Parse the Stop-hook payload + the session transcript into a plain Session model.

Claude Code transcript lines (JSONL) look like:

    {"type":"user","message":{"role":"user","content":"build X"}, ...}
    {"type":"assistant","message":{"role":"assistant","content":[
        {"type":"thinking", ...},
        {"type":"text","text":"I'll do X"},
        {"type":"tool_use","id":"toolu_1","name":"Bash","input":{"command":"pytest"}}
    ]}, ...}
    {"type":"user","toolUseResult":{...},"message":{"role":"user","content":[
        {"type":"tool_result","tool_use_id":"toolu_1","content":[...],"is_error":true}
    ]}, ...}

A failed Bash call is marked by `is_error: true` and a tool_result whose text starts
with "Exit code N". Successful calls have no `is_error`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

EDIT_TOOLS = {"Edit": "file_path", "Write": "file_path", "MultiEdit": "file_path",
              "NotebookEdit": "notebook_path", "Update": "file_path"}


@dataclass
class Command:
    text: str
    ok: bool
    exit_code: int | None
    output: str
    sidechain: bool = False


@dataclass
class FileEdit:
    path: str
    tool: str
    sidechain: bool = False


@dataclass
class Session:
    final_message: str = ""
    user_messages: list[str] = field(default_factory=list)
    commands: list[Command] = field(default_factory=list)
    edits: list[FileEdit] = field(default_factory=list)
    cwd: str = ""
    transcript_found: bool = False

    # ---- construction ---------------------------------------------------------

    @classmethod
    def from_hook_input(cls, data: dict) -> "Session":
        s = cls(final_message=(data.get("last_assistant_message") or "").strip(),
                cwd=data.get("cwd", "") or "")
        tpath = data.get("transcript_path")
        if tpath and Path(tpath).expanduser().is_file():
            s.transcript_found = True
            s._load_transcript(Path(tpath).expanduser())
        return s

    def _load_transcript(self, path: Path) -> None:
        pending: dict[str, tuple[str, dict, bool]] = {}   # tool_use_id -> (name, input, sidechain)
        last_assistant_text = ""

        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except ValueError:
                continue

            typ = o.get("type")
            if typ not in ("user", "assistant"):
                continue
            sidechain = bool(o.get("isSidechain"))
            msg = o.get("message") or {}
            content = msg.get("content")

            if typ == "assistant":
                for item in _as_items(content):
                    it = item.get("type")
                    if it == "text" and not sidechain:
                        txt = item.get("text", "").strip()
                        if txt:
                            last_assistant_text = txt
                    elif it == "tool_use":
                        name = item.get("name", "")
                        tinput = item.get("input") or {}
                        tid = item.get("id", "")
                        if tid:
                            pending[tid] = (name, tinput, sidechain)
                        if name in EDIT_TOOLS:
                            p = tinput.get(EDIT_TOOLS[name])
                            if p:
                                self.edits.append(FileEdit(str(p), name, sidechain))
                        if name == "Bash":
                            self.edits.extend(_edits_from_bash(tinput.get("command", ""), sidechain))
                continue

            # typ == "user"
            tool_results = [i for i in _as_items(content) if i.get("type") == "tool_result"]
            if not tool_results and "toolUseResult" not in o:
                text = _plain_text(content)
                if text:
                    self.user_messages.append(text)
                continue

            for tr in tool_results:
                tid = tr.get("tool_use_id", "")
                name, tinput, sc = pending.get(tid, ("", {}, sidechain))
                if name != "Bash":
                    continue
                body = _result_text(tr.get("content"))
                is_error = bool(tr.get("is_error"))
                exit_code = _exit_code(body)
                ok = not is_error and (exit_code in (0, None))
                if exit_code not in (0, None):
                    ok = False
                self.commands.append(Command(
                    text=tinput.get("command", "").strip(),
                    ok=ok,
                    exit_code=exit_code,
                    output=body[:4000],
                    sidechain=sc,
                ))

        if not self.final_message:
            self.final_message = last_assistant_text


# ---- helpers ----------------------------------------------------------------

def _as_items(content) -> list[dict]:
    if isinstance(content, list):
        return [c for c in content if isinstance(c, dict)]
    return []


def _plain_text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    parts = [c.get("text", "") for c in _as_items(content) if c.get("type") == "text"]
    return " ".join(p for p in parts if p).strip()


def _result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            c.get("text", "") if isinstance(c, dict) else str(c)
            for c in content
        )
    return ""


def _exit_code(body: str) -> int | None:
    head = body.lstrip()[:40]
    if head.startswith("Exit code "):
        digits = head[len("Exit code "):].split()[0].strip().rstrip(".")
        if digits.isdigit():
            return int(digits)
    return None


def _edits_from_bash(command: str, sidechain: bool) -> list[FileEdit]:
    """Best-effort: catch obvious file mutations done via shell."""
    import re
    out: list[FileEdit] = []

    def clean(t: str) -> str | None:
        t = t.strip().strip("\"'")
        if not t or t.startswith("-") or any(ch in t for ch in "{}$*?()`"):
            return None
        return t

    for m in re.finditer(r"\b(rm|mv|cp|touch|dd)\s+((?:-\S+\s+)*)(\S+)", command):
        target = clean(m.group(3))
        if target:
            out.append(FileEdit(target, f"bash:{m.group(1)}", sidechain))
    for m in re.finditer(r"(?<![0-9])>>?\s*([^\s;|&<>]+)", command):
        target = clean(m.group(1))
        if target:
            out.append(FileEdit(target, "bash:redirect", sidechain))
    return out
