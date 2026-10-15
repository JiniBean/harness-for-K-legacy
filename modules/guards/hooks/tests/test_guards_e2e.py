# -*- coding: utf-8 -*-
"""End-to-end checks for protected_path_guard payload shapes (Cursor files[], broken
Cursor JSON, Codex apply_patch). No approval state is created.
Run inside an installed project: python .agents/hooks/tests/test_guards_e2e.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path as _P

HOOKS = str(_P(__file__).resolve().parents[1])  # <root>/.agents/hooks
ROOT = str(_P(__file__).resolve().parents[3])  # .agents/hooks/tests -> project root
PY = sys.executable
CLA = {"session_id": "s", "hook_event_name": "PreToolUse"}
CUR = {"cursor_version": "1", "conversation_id": "x", "hook_event_name": "preToolUse"}
CDX = {"session_id": "s", "hook_event_name": "PreToolUse", "model": "m", "cwd": ROOT}


def run(script, stdin):
    p = subprocess.run([PY, os.path.join(HOOKS, script)], input=stdin, capture_output=True)
    return "block" if (p.returncode == 2 or b'"deny"' in p.stdout) else "allow"


def write(path, base=CLA, content="x", files=None):
    ti = {"file_path": path, "content": content}
    if files is not None:
        ti = {"files": files}
    return json.dumps(dict(base, tool_name="Write", tool_input=ti)).encode()


def patch(*headers):
    return "*** Begin Patch\n" + "".join("%s\n+x\n" % h for h in headers) + "*** End Patch\n"


def codex(tool_input):
    return json.dumps(dict(CDX, tool_name="apply_patch", tool_input=tool_input)).encode()


P = ROOT
BROKEN = lambda path: ('{"conversation_id":"x","cursor_version":"1","tool_name":"Write","tool_input":{"file_path":"%s","contents":"\xed\x95\x9c\\q' % path.replace("\\", "\\\\")).encode("utf-8", "surrogateescape")
PG = "protected_path_guard.py"

CASES = [
    ("path files[] protected", PG, write(None, files=[{"path": os.path.join(HOOKS, "hook_io.py")}]), "block"),
    ("path files[] normal", PG, write(None, files=[os.path.join(P, "src", "a.java")]), "allow"),
    ("path broken JSON normal file", PG, BROKEN(os.path.join(P, "src", "a.java")), "allow"),
    ("path broken JSON hooks.json", PG, BROKEN(os.path.join(P, ".cursor", "hooks.json")), "block"),
    ("path broken JSON hook script", PG, BROKEN(os.path.join(HOOKS, "shell_guard.py")), "block"),
    ("path broken JSON hooks.toml", PG, BROKEN(os.path.join(HOOKS, "hooks.toml")), "block"),
    ("codex patch string normal", PG, codex(patch("*** Update File: src/a.java")), "allow"),
    ("codex patch string hook script", PG, codex(patch("*** Update File: .agents/hooks/hook_io.py")), "block"),
    ("codex patch add hook state", PG, codex(patch("*** Add File: .agents/hooks/state/x.json")), "block"),
    ("codex patch delete guard", PG, codex(patch("*** Delete File: .agents/hooks/shell_guard.py")), "block"),
    ("codex patch move onto guard", PG, codex(patch("*** Update File: src/a.py\n*** Move to: .agents/hooks/hook_io.py")), "block"),
    ("codex patch dict input", PG, codex({"input": patch("*** Update File: .agents/hooks/hook_io.py")}), "block"),
    ("codex patch dict command argv", PG, codex({"command": ["apply_patch", patch("*** Update File: .codex/hooks.json")]}), "block"),
    ("codex patch hooks.toml", PG, codex(patch("*** Update File: .agents/hooks/hooks.toml")), "block"),
    ("codex patch two normal files", PG, codex(patch("*** Update File: src/a.java", "*** Add File: src/b.java")), "allow"),
]

fail = 0
for name, script, stdin, expect in CASES:
    got = run(script, stdin)
    ok = got == expect
    fail += 0 if ok else 1
    print("%s %-34s got=%s" % ("PASS" if ok else "FAIL", name, got))
print("FAIL=%d" % fail)
sys.exit(1 if fail else 0)
