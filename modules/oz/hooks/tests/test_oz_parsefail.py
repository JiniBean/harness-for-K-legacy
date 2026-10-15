# -*- coding: utf-8 -*-
"""oz_file_guard --pretooluse checks (broken Cursor JSON, Codex apply_patch).
Run inside an installed project: python .agents/hooks/tests/test_oz_parsefail.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path as _P

HOOKS = str(_P(__file__).resolve().parents[1])  # <root>/.agents/hooks
sys.stdout.reconfigure(encoding="utf-8")
PY = sys.executable
G = os.path.join(HOOKS, "oz_file_guard.py")
BROKEN_OZ = b'\xef\xbb\xbf{"conversation_id":"x","cursor_version":"1","tool_name":"Write","tool_input":{"file_path":"C:\\\\a\\\\r.ozr","contents":"\xed\x95\x9c\\q broken"'
BROKEN_TXT = BROKEN_OZ.replace(b"r.ozr", b"r.txt")
GOOD_OZ = json.dumps({"cursor_version": "1", "tool_name": "Write", "tool_input": {"file_path": r"C:\a\r.ozr"}}).encode()
GOOD_TXT = json.dumps({"cursor_version": "1", "tool_name": "Write", "tool_input": {"file_path": r"C:\a\r.txt"}}).encode()
CDX = {"session_id": "s", "hook_event_name": "PreToolUse", "model": "m", "cwd": "C:/a", "tool_name": "apply_patch"}
CODEX_OZ = json.dumps(dict(CDX, tool_input="*** Begin Patch\n*** Update File: rpt/r.odi\n+x\n*** End Patch\n")).encode()
CODEX_TXT = json.dumps(dict(CDX, tool_input="*** Begin Patch\n*** Update File: rpt/r.txt\n+x\n*** End Patch\n")).encode()
fail = 0
for name, payload, expect in [("broken ozr", BROKEN_OZ, "deny"), ("broken txt", BROKEN_TXT, "allow"),
                              ("good ozr", GOOD_OZ, "deny"), ("good txt", GOOD_TXT, "allow"),
                              ("codex patch odi", CODEX_OZ, "deny"), ("codex patch txt", CODEX_TXT, "allow")]:
    p = subprocess.run([PY, G, "--pretooluse"], input=payload, capture_output=True)
    out = p.stdout.decode("utf-8", "replace")
    got = "deny" if (p.returncode == 2 or '"deny"' in out) else "allow"
    ok = got == expect
    fail += 0 if ok else 1
    print("%s %-16s rc=%s got=%s" % ("PASS" if ok else "FAIL", name, p.returncode, got))
print("FAIL=%d" % fail)
sys.exit(1 if fail else 0)
