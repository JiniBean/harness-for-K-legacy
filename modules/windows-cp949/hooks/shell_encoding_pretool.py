# -*- coding: utf-8 -*-
"""
Cursor preToolUse hook (matcher: Shell) / Claude Code PreToolUse hook (matcher: PowerShell).
Injects UTF-8 console preamble for Windows PowerShell 5.1 + CP949 hosts.
Reads JSON from stdin, writes JSON to stdout.
"""
from __future__ import annotations

import json
import re
import sys

PREAMBLE = (
    "chcp 65001 > $null; "
    "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
    "$OutputEncoding = [Console]::OutputEncoding; "
    "$env:PYTHONIOENCODING = 'utf-8'; "
)

# chcp alone is NOT sufficient — Agent/User Rule partial prefix must not skip injection.
PARTIAL_PREAMBLE_RE = re.compile(
    r"^(?:\s*chcp\s+65001\s*>\s*\$null\s*;\s*)+",
    re.IGNORECASE,
)


def already_wrapped(command: str) -> bool:
    """Skip only when the full UTF-8 console setup is already present."""
    return (
        "[Console]::OutputEncoding" in command
        and "$OutputEncoding = [Console]::OutputEncoding" in command
    )


def strip_partial_preamble(command: str) -> str:
    """Remove incomplete chcp-only prefix so we do not double-wrap."""
    stripped = PARTIAL_PREAMBLE_RE.sub("", command)
    return stripped.lstrip()


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        # fail open unless failClosed on the hook config
        print(json.dumps({"permission": "allow"}))
        return 0
    if not isinstance(data, dict):
        data = {}

    # Cursor also sends hook_event_name; Cursor-only keys win.
    is_claude = ("hook_event_name" in data or "session_id" in data) and not any(
        k in data for k in ("cursor_version", "conversation_id", "generation_id")
    )

    # preToolUse payload: tool_name / tool_input; be tolerant of field names
    tool_input = data.get("tool_input") or data.get("input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    command = tool_input.get("command") or data.get("command") or ""
    if not isinstance(command, str):
        command = str(command)

    if not command.strip() or already_wrapped(command):
        if not is_claude:
            print(json.dumps({"permission": "allow"}))
        return 0

    body = strip_partial_preamble(command)
    new_cmd = PREAMBLE + body
    updated = dict(tool_input)
    updated["command"] = new_cmd

    if is_claude:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "allow",
                        "updatedInput": updated,
                    }
                },
                ensure_ascii=True,
            )
        )
        return 0

    out = {
        "permission": "allow",
        "updated_input": updated,
        "agent_message": "Injected UTF-8 console preamble (chcp 65001 / OutputEncoding / PYTHONIOENCODING) for Shell.",
    }
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
