# -*- coding: utf-8 -*-
"""mcp guard for the read-only FTP log MCP server.

Policy:
- Only ftp_servers / ftp_list / ftp_get / ftp_download / ftp_stat / ftp_slice allowed
- No temporary approval path; WRITE tools always denied
- Non-FTP MCP calls pass through
Server name: harness.toml [guard.ftp] server_name (tool names starting with ftp are caught without it).
"""
from __future__ import print_function

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hook_io import emit_allow, emit_deny, guard_config, read_stdin_json

SERVER_NAME = str((guard_config().get("ftp") or {}).get("server_name") or "").lower()

ALLOWED_TOOLS = ("ftp_servers", "ftp_list", "ftp_get", "ftp_download", "ftp_stat", "ftp_slice")
DENY_NAME_FRAGMENTS = (
    "put",
    "upload",
    "store",
    "rename",
    "delete",
    "mkdir",
    "rmdir",
    "rm_",
    "remove",
    "write",
    "append",
    "chmod",
    "send",
)


def _deny(user_message, agent_message):
    emit_deny(user_message, agent_message)
    return 0


def _tool_name(payload):
    name = str(payload.get("tool_name") or payload.get("toolName") or payload.get("name") or "")
    lower = name.lower()
    # Claude Code / Codex MCP tool names: mcp__<server>__<tool> (e.g. mcp__log-ftp__ftp_get).
    if "__" in lower:
        return lower.rsplit("__", 1)[-1].strip()
    # strip server prefixes like log-ftp.ftp_list
    if "." in lower:
        lower = lower.split(".")[-1]
    if "-" in lower and lower.rsplit("-", 1)[-1].startswith("ftp"):
        lower = lower.rsplit("-", 1)[-1]
    return lower.strip()


def tool_looks_ftp(tool):
    t = (tool or "").lower()
    return t.startswith("ftp")


def _is_ftp_mcp(payload):
    blob = " ".join(
        [
            str(payload.get("command") or ""),
            str(payload.get("url") or ""),
            str(payload.get("server") or ""),
            str(payload.get("serverName") or ""),
            str(payload.get("tool_name") or ""),
            json.dumps(payload.get("tool_input") or "", ensure_ascii=False),
        ]
    ).lower()
    return (
        (bool(SERVER_NAME) and SERVER_NAME in blob)
        or ("mcp-ftp" in blob)
        or ("ftp_list" in blob)
        or ("ftp_get" in blob)
        or ("ftp_servers" in blob)
        or ("ftp_download" in blob)
        or ("ftp_put" in blob)
        or ("ftp_upload" in blob)
        or tool_looks_ftp(_tool_name(payload))
    )


def main():
    payload = read_stdin_json(strict=True)
    if payload is None:
        return _deny(
            "FTP MCP 훅 입력 파싱 실패",
            "ftp_mcp_guard stdin JSON parse failed (empty or unparseable).",
        )

    if not _is_ftp_mcp(payload):
        emit_allow()
        return 0

    tool = _tool_name(payload)
    if tool in ALLOWED_TOOLS:
        emit_allow()
        return 0

    for frag in DENY_NAME_FRAGMENTS:
        if frag in tool:
            return _deny(
                "FTP MCP는 읽기만 허용됩니다. 업로드/변경은 차단됩니다 (일시 승인 없음).",
                "ftp_mcp_guard denied tool=%s (write-like). No approval bypass." % tool,
            )

    if tool_looks_ftp(tool):
        return _deny(
            "허용되지 않은 FTP MCP 도구입니다. ftp_servers / ftp_list / ftp_get / ftp_download / ftp_stat / ftp_slice만 사용하세요.",
            "ftp_mcp_guard denied unknown ftp tool=%s" % tool,
        )

    # Identified as FTP MCP but tool name unclear → fail closed for safety
    return _deny(
        "FTP MCP 도구를 판별할 수 없어 차단했습니다.",
        "ftp_mcp_guard fail-closed: unrecognized tool on %s: %r" % (SERVER_NAME or "ftp", tool),
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main() or 0)
    except SystemExit:
        raise
    except Exception as exc:
        emit_deny(
            "FTP MCP 훅 오류로 차단했습니다.",
            "ftp_mcp_guard error: %s" % exc,
        )
        raise SystemExit(0)
