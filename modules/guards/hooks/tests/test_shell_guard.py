# -*- coding: utf-8 -*-
"""shell_guard regression checks. Run inside an installed project:
python .agents/hooks/tests/test_shell_guard.py

The guard runs from a temp project copy with a known [guard] config, so results
do not depend on this machine's harness.toml.
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

ROOT = tempfile.mkdtemp(prefix="shell_guard_test_")
_TH = os.path.join(ROOT, ".agents", "hooks")
os.makedirs(_TH)
for _f in ("hook_io.py", "shell_guard.py", "hooks.toml"):
    shutil.copy(os.path.join(HOOKS, _f), _TH)
with open(os.path.join(ROOT, ".agents", "harness.toml"), "w", encoding="utf-8") as _f:
    _f.write(
        'name = "shelltest"\n[guard]\nblock_hosts = ["10.9.9.9"]\nftp_hosts = ["ftp.example.test"]\n'
        'shell_block_patterns = ["forbidden_tool_x", "[unclosed"]\n'
    )
G = os.path.join(_TH, "shell_guard.py")
R = ROOT.replace("\\", "/")
GB = "/" + R[0].lower() + R[2:] if R[1:2] == ":" else R  # Git Bash form
CLA = {"session_id": "s", "hook_event_name": "PreToolUse", "tool_name": "Bash"}
CDX = {"session_id": "s", "hook_event_name": "PreToolUse", "model": "m", "cwd": R, "tool_name": "Bash"}
CUR = {"cursor_version": "1", "conversation_id": "x", "hook_event_name": "beforeShellExecution"}


def claude(cmd):
    return dict(CLA, tool_input={"command": cmd})


CASES = [
    ("write hook_io via shell", claude("echo x > " + R + "/.agents/hooks/hook_io.py"), True),
    ("cp onto protected_path_guard", claude("cp a " + GB + "/.agents/hooks/protected_path_guard.py"), True),
    ("write hooks.toml via shell", claude("echo x > .agents/hooks/hooks.toml"), True),
    ("write .codex/hooks.json via shell", claude("echo {} > .codex/hooks.json"), True),
    ("write hook state via shell", claude("echo {} > .agents/hooks/state/x_approved.json"), True),
    ("write claude settings via shell", claude("echo {} > ./.claude/settings.json"), True),
    ("read default secrets dir", claude("cat ~/.agents/secrets/p/ftp.env"), True),
    ("python -c", claude("python -c 'print(1)'"), True),
    ("plain ls", claude("ls .agents/hooks"), False),
    ("run a test script", claude("python .agents/hooks/tests/test_path_guard.py"), False),
    ("run generator", claude("python .agents/hooks/gen_hook_configs.py --check"), False),
    ("overwrite generator", claude("cp x .agents/hooks/gen_hook_configs.py"), True),
    ("sed -i generator", claude("sed -i s/a/b/ .agents/hooks/gen_hook_configs.py"), True),
    ("blocked host", claude("ssh admin@10.9.9.9"), True),
    ("curl upload", claude("curl -T a.txt ftp://ftp.example.test/"), True),
    ("ftp host put", claude("lftp ftp.example.test -e 'put a.txt'"), True),
    ("ftp host read", claude("curl ftp://ftp.example.test/a.log -o a.log"), False),
    ("shell_block_patterns entry", claude("forbidden_tool_x --run"), True),
    ("bad pattern entry is skipped", claude("echo [unclosed"), False),
    ("cursor python -c", dict(CUR, command="py -c 1"), True),
    ("cursor plain", dict(CUR, command="git status"), False),
    ("codex python -c", dict(CDX, tool_input={"command": "python -c 1"}), True),
    ("codex argv list python -c", dict(CDX, tool_input={"command": ["bash", "-lc", "python -c 1"]}), True),
    ("codex plain", dict(CDX, tool_input={"command": "git status"}), False),
]
fail = 0
for name, payload, expect_block in CASES:
    p = subprocess.run([sys.executable, G], input=json.dumps(payload).encode(), capture_output=True)
    blocked = p.returncode == 2 or b'"deny"' in p.stdout
    ok = blocked == expect_block
    fail += 0 if ok else 1
    print("%s %-40s blocked=%s" % ("PASS" if ok else "FAIL", name, blocked))
p = subprocess.run([sys.executable, G], input=b"", capture_output=True)
ok = p.returncode == 2 or b'"deny"' in p.stdout
fail += 0 if ok else 1
print("%s %-40s blocked=%s" % ("PASS" if ok else "FAIL", "empty stdin (strict)", ok))
shutil.rmtree(ROOT, ignore_errors=True)
print("FAIL=%d" % fail)
sys.exit(1 if fail else 0)
