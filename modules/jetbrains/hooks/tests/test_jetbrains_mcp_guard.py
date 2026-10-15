# -*- coding: utf-8 -*-
"""jetbrains_mcp_guard checks (jetbrains module). Run inside an installed project:
python .agents/hooks/tests/test_jetbrains_mcp_guard.py

Runs the installed guard from a temp project copy (hook_io.py next to it).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path as _P

HOOKS = str(_P(__file__).resolve().parents[1])  # <root>/.agents/hooks
sys.stdout.reconfigure(encoding="utf-8")
PY = sys.executable

ROOT = tempfile.mkdtemp(prefix="jetbrains_guard_test_")
_TH = os.path.join(ROOT, ".agents", "hooks")
os.makedirs(_TH)
for _f in ("hook_io.py", "jetbrains_mcp_guard.py", "hooks.toml"):
    shutil.copy(os.path.join(HOOKS, _f), _TH)
with open(os.path.join(ROOT, ".agents", "harness.toml"), "w", encoding="utf-8") as _f:
    _f.write('name = "jbtest"\n')

CLA = {"session_id": "s", "hook_event_name": "PreToolUse", "cwd": ROOT}
CUR = {"cursor_version": "1", "conversation_id": "x", "hook_event_name": "beforeMCPExecution"}
JG = "jetbrains_mcp_guard.py"


def mcp(tool, base=CLA):
    return json.dumps(dict(base, tool_name=tool, tool_input={"pathInProject": "src/A.java"})).encode()


def run(stdin):
    p = subprocess.run([PY, os.path.join(_TH, JG)], input=stdin, capture_output=True)
    return "block" if (p.returncode == 2 or b'"deny"' in p.stdout) else "allow"


CASES = [
    ("claude plugin replace_text_in_file", mcp("mcp__plugin_agents-global_jetbrains__replace_text_in_file"), "block"),
    ("claude execute_terminal_command", mcp("mcp__jetbrains__execute_terminal_command"), "block"),
    ("claude execute_run_configuration", mcp("mcp__jetbrains__execute_run_configuration"), "block"),
    ("claude search_in_files_by_text", mcp("mcp__plugin_agents-global_jetbrains__search_in_files_by_text"), "allow"),
    ("claude get_file_text_by_path", mcp("mcp__jetbrains__get_file_text_by_path"), "allow"),
    ("cursor create_new_file", mcp("create_new_file", CUR), "block"),
    ("cursor find_files_by_glob", mcp("find_files_by_glob", CUR), "allow"),
    ("cursor other MCP tool", mcp("searchJiraIssuesUsingJql", CUR), "allow"),
    ("empty stdin (strict)", b"", "block"),
]
fail = 0
for name, stdin, expect in CASES:
    got = run(stdin)
    fail += 0 if got == expect else 1
    print("%s %-40s got=%s" % ("PASS" if got == expect else "FAIL", name, got))
shutil.rmtree(ROOT, ignore_errors=True)
print("FAIL=%d" % fail)
sys.exit(1 if fail else 0)
