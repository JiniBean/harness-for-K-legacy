# -*- coding: utf-8 -*-
"""
Cursor beforeShellExecution hook / Claude Code PreToolUse hook (matcher: PowerShell).
Denies high-risk Hangul source generation via Set-Content/Out-File here-strings.
"""
from __future__ import annotations

import json
import re
import sys

HANGUL_RE = re.compile(r"[가-힣]")
WRITE_CMD_RE = re.compile(
    r"(?i)\b(Set-Content|Add-Content|Out-File|Set-Content\s+-Path)\b"
)
HERE_STRING_RE = re.compile(r"@['\"]|@\$['\"]|'@|\"@")


def is_high_risk(command: str) -> bool:
    if not HANGUL_RE.search(command):
        return False
    if not WRITE_CMD_RE.search(command):
        return False
    # here-string or multi-line script body markers
    if HERE_STRING_RE.search(command) or "\n" in command:
        return True
    # short one-liners still risky if writing .py/.ps1 with Hangul
    if re.search(r"(?i)\.(py|ps1|js|ts|java|xml|sql)\b", command):
        return True
    return False


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        print(json.dumps({"permission": "allow"}))
        return 0
    if not isinstance(data, dict):
        data = {}

    # Cursor also sends hook_event_name; Cursor-only keys win.
    is_claude = ("hook_event_name" in data or "session_id" in data) and not any(
        k in data for k in ("cursor_version", "conversation_id", "generation_id")
    )

    tool_input = data.get("tool_input") or data.get("input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    command = tool_input.get("command") or data.get("command") or ""
    if not isinstance(command, str):
        command = str(command)

    if is_high_risk(command):
        msg = (
            "Blocked: creating Hangul-containing source via Set-Content/Out-File in Shell "
            "often corrupts encoding on Windows PowerShell 5.1. "
            "Use the Write tool to create the UTF-8 file, then run it with Shell "
            "(UTF-8 preamble is auto-injected)."
        )
        if is_claude:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": msg,
                        }
                    },
                    ensure_ascii=True,
                )
            )
        else:
            print(
                json.dumps(
                    {
                        "permission": "deny",
                        "user_message": msg,
                        "agent_message": msg,
                    },
                    ensure_ascii=True,
                )
            )
        return 0

    if not is_claude:
        print(json.dumps({"permission": "allow"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
