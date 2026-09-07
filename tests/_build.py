"""Tiny builder for fake Claude Code transcripts in the real JSONL shape."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

_ids = itertools.count(1)


class Transcript:
    def __init__(self) -> None:
        self.lines: list[dict] = []

    def user(self, text: str) -> "Transcript":
        self.lines.append({"type": "user", "isSidechain": False,
                           "message": {"role": "user", "content": text}})
        return self

    def say(self, text: str, sidechain: bool = False) -> "Transcript":
        self.lines.append({"type": "assistant", "isSidechain": sidechain,
                           "message": {"role": "assistant",
                                       "content": [{"type": "text", "text": text}]}})
        return self

    def _tool(self, name: str, tinput: dict, sidechain: bool) -> str:
        tid = f"toolu_{next(_ids)}"
        self.lines.append({"type": "assistant", "isSidechain": sidechain,
                           "message": {"role": "assistant", "content": [
                               {"type": "tool_use", "id": tid, "name": name, "input": tinput}]}})
        return tid

    def _result(self, tid: str, body: str, is_error: bool) -> None:
        self.lines.append({"type": "user", "isSidechain": False,
                           "toolUseResult": {"stdout": body, "stderr": ""},
                           "message": {"role": "user", "content": [
                               {"type": "tool_result", "tool_use_id": tid,
                                "content": [{"type": "text", "text": body}],
                                "is_error": is_error}]}})

    def bash(self, cmd: str, out: str = "", exit_code: int = 0, sidechain: bool = False) -> "Transcript":
        tid = self._tool("Bash", {"command": cmd}, sidechain)
        body = out if exit_code == 0 else f"Exit code {exit_code}\n{out}"
        self._result(tid, body, is_error=exit_code != 0)
        return self

    def edit(self, path: str, tool: str = "Edit") -> "Transcript":
        key = "notebook_path" if tool == "NotebookEdit" else "file_path"
        tid = self._tool(tool, {key: path}, False)
        self._result(tid, f"Updated {path}", is_error=False)
        return self

    def write(self, path: str) -> "Transcript":
        return self.edit(path, "Write")

    def raw(self, obj: dict) -> "Transcript":
        self.lines.append(obj)
        return self

    def dump(self, path: Path) -> str:
        path.write_text("\n".join(json.dumps(o) for o in self.lines) + "\n")
        return str(path)


def hook_input(final_message: str, transcript_path: str, cwd: str = "/proj",
               stop_hook_active: bool = False) -> dict:
    return {
        "session_id": "test",
        "transcript_path": transcript_path,
        "cwd": cwd,
        "hook_event_name": "Stop",
        "last_assistant_message": final_message,
        "stop_hook_active": stop_hook_active,
        "stop_reason": "end_turn",
    }
