# -*- coding: utf-8 -*-
"""ftp_mcp_guard checks (log-debug module). Run inside an installed project:
python .agents/hooks/tests/test_ftp_mcp_guard.py

Runs from a temp project copy with [guard.ftp] server_name = "demo-ftp".
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

ROOT = tempfile.mkdtemp(prefix="ftp_guard_test_")
_TH = os.path.join(ROOT, ".agents", "hooks")
os.makedirs(_TH)
for _f in ("hook_io.py", "ftp_mcp_guard.py", "shell_guard.py", "protected_path_guard.py", "hooks.toml"):
    shutil.copy(os.path.join(HOOKS, _f), _TH)
with open(os.path.join(ROOT, ".agents", "harness.toml"), "w", encoding="utf-8") as _f:
    _f.write('name = "ftptest"\n[guard.ftp]\nserver_name = "demo-ftp"\n')

CLA = {"session_id": "s", "hook_event_name": "PreToolUse"}
CUR = {"cursor_version": "1", "conversation_id": "x", "hook_event_name": "beforeMCPExecution"}


def mcp(tool, base=CLA, **extra):
    return json.dumps(dict(base, tool_name=tool, tool_input={"path": "/logs"}, **extra)).encode()


def run(script, stdin):
    p = subprocess.run([PY, os.path.join(_TH, script)], input=stdin, capture_output=True)
    return "block" if (p.returncode == 2 or b'"deny"' in p.stdout) else "allow"


FG = "ftp_mcp_guard.py"
CASES = [
    ("claude ftp_list", FG, mcp("mcp__demo-ftp__ftp_list"), "allow"),
    ("claude ftp_slice", FG, mcp("mcp__demo-ftp__ftp_slice"), "allow"),
    ("claude ftp_put", FG, mcp("mcp__demo-ftp__ftp_put"), "block"),
    ("claude ftp_unknown", FG, mcp("mcp__demo-ftp__ftp_chown"), "block"),
    ("claude server tool w/o ftp prefix", FG, mcp("mcp__demo-ftp__listing"), "block"),
    ("claude upload on other server", FG, mcp("mcp__other__ftp_upload"), "block"),
    ("claude non-ftp MCP", FG, mcp("mcp__other__search"), "allow"),
    ("cursor ftp_get", FG, mcp("ftp_get", CUR, server="demo-ftp"), "allow"),
    ("cursor ftp_delete", FG, mcp("ftp_delete", CUR, server="demo-ftp"), "block"),
    ("empty stdin (strict)", FG, b"", "block"),
    ("write ftp_mcp_guard (protected)", "protected_path_guard.py",
     json.dumps(dict(CLA, tool_name="Write", tool_input={"file_path": os.path.join(_TH, FG), "content": "x"})).encode(), "block"),
    ("shell names ftp_mcp_guard", "shell_guard.py",
     json.dumps(dict(CLA, tool_name="Bash", tool_input={"command": "echo x > .agents/hooks/ftp_mcp_guard.py"})).encode(), "block"),
]
fail = 0
for name, script, stdin, expect in CASES:
    got = run(script, stdin)
    fail += 0 if got == expect else 1
    print("%s %-36s got=%s" % ("PASS" if got == expect else "FAIL", name, got))
shutil.rmtree(ROOT, ignore_errors=True)
print("FAIL=%d" % fail)
sys.exit(1 if fail else 0)
