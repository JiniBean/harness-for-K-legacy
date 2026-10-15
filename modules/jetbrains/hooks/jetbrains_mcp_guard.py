# -*- coding: utf-8 -*-
"""Read-only guard for the IntelliJ IDEA built-in MCP server (jetbrains module).

Installed at <project>/.agents/hooks/ next to hook_io.py and registered from the
project hooks.toml (modules/jetbrains/hooks.toml fragment):
- Cursor beforeMCPExecution (failClosed); sees every MCP call, passes non-matching tools
- Claude Code / Codex PreToolUse with claude_matcher "mcp__.*jetbrains.*__.*"

Policy: write/execute tools are always denied, everything else passes.
Why: the IDE MCP server has no per-tool exposure setting, so
execute_terminal_command / execute_run_configuration would bypass shell guards
and DB approval hooks, and file-write tools would skip editor-side hooks.
"""
from __future__ import print_function

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hook_io import emit_allow, emit_deny, read_stdin_json
from hook_io import tool_name as raw_tool_name

# Tool names are unique to this server, so they are denied wherever they come from.
DENY_TOOLS = {
    "execute_terminal_command": "셸 명령은 셸 도구로 실행하세요. IntelliJ 터미널 경유는 셸 가드와 DB 승인 절차를 우회합니다.",
    "execute_run_configuration": "실행 구성 기동은 차단됩니다. 필요하면 사용자가 IDE에서 직접 실행하세요.",
    "create_new_file": "파일 생성은 편집 도구로 하세요. MCP 경유 생성은 차단됩니다.",
    "replace_text_in_file": "파일 수정은 편집 도구로 하세요. MCP 경유 수정은 차단됩니다.",
    "rename_refactoring": "이름 변경 리팩터링은 차단됩니다. 변경 범위가 훅 검사를 거치지 않습니다.",
    "reformat_file": "전체 포맷 변경은 차단됩니다. 불필요한 diff를 만듭니다.",
}


def bare_tool_name(payload):
    """Bare tool name: Claude mcp__<server>__<tool>, Cursor MCP:<tool> or <tool>."""
    name = raw_tool_name(payload).lower().strip()
    for sep in ("__", ":", "."):
        if sep in name:
            name = name.rsplit(sep, 1)[-1]
    return name.strip()


def main():
    data = read_stdin_json(strict=True)
    if data is None:
        emit_deny("JetBrains MCP 훅 입력 파싱 실패로 차단했습니다.",
                  "jetbrains_mcp_guard: stdin JSON parse failed (empty or unparseable).")
        return 0
    tool = bare_tool_name(data)
    if tool in DENY_TOOLS:
        emit_deny("JetBrains MCP의 쓰기·실행 도구는 차단됩니다. " + DENY_TOOLS[tool],
                  "jetbrains_mcp_guard denied tool=%s (write/execute)." % tool)
        return 0
    emit_allow()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main() or 0)
    except SystemExit:
        raise
    except Exception as exc:
        emit_deny("JetBrains MCP 훅 오류로 차단했습니다.", "jetbrains_mcp_guard error: %s" % exc)
        raise SystemExit(0)
