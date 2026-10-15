# -*- coding: utf-8 -*-
"""protected_path_guard regression checks. Run inside an installed project:
python .agents/hooks/tests/test_path_guard.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path as _P

HOOKS = str(_P(__file__).resolve().parents[1])  # <root>/.agents/hooks
ROOT = str(_P(__file__).resolve().parents[3])  # .agents/hooks/tests -> project root
HOME = str(_P.home())

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, HOOKS)
from hook_io import CORE_REQUIRED, required_hook_names  # noqa: E402

PY = sys.executable
G = os.path.join(HOOKS, "protected_path_guard.py")
CLA = {"session_id": "s", "hook_event_name": "PreToolUse"}
CUR = {"cursor_version": "1", "conversation_id": "x", "hook_event_name": "preToolUse"}
FULL = " ".join(required_hook_names())


def j(*parts):
    return os.path.join(*parts)


def w(base, tool, path, content):
    d = dict(base, tool_name=tool, tool_input={"file_path": path, "content": content})
    return json.dumps(d).encode("utf-8")


def r(base, tool, path):
    key = "path" if tool in ("Grep", "Glob") else "file_path"
    return json.dumps(dict(base, tool_name=tool, tool_input={key: path})).encode("utf-8")


def gitbash(path):
    p = path.replace("\\", "/")
    return "/" + p[0].lower() + p[2:] if len(p) > 2 and p[1] == ":" else p


def _secrets_dir():
    try:
        sys.path.insert(0, j(HOME, ".agents", "scripts"))
        import harness_config

        return str(harness_config.secrets_dir())
    except Exception:
        return j(HOME, ".agents", "secrets")


SEC = _secrets_dir()
EXISTING_SECRET = next((j(d, f) for d, _, fs in os.walk(SEC) for f in fs), None)

with open(j(HOOKS, "hooks.toml"), encoding="utf-8") as _f:
    HOOKS_TOML_TEXT = _f.read()
_blocks = HOOKS_TOML_TEXT.split("[[hook]]")
TOML_NO_SHELL = "[[hook]]".join(b for b in _blocks if 'script = "shell_guard.py"' not in b)
TOML_NO_FLAGS = "\n".join(ln for ln in HOOKS_TOML_TEXT.splitlines() if ln.strip() != "required = true")
# Dropping required flags matters only when a module marked its own guard required (core two are fixed).
NO_FLAGS_EXPECT = "block" if set(required_hook_names()) - set(CORE_REQUIRED) else "allow"

CASES = [
    # (name, stdin bytes, expect: "block" | "allow")
    ("claude Write project settings w/o names", w(CLA, "Write", j(ROOT, ".claude", "settings.json"), "{}"), "block"),
    ("claude Write project settings w/ names", w(CLA, "Write", j(ROOT, ".claude", "settings.json"), FULL), "allow"),
    ("cursor Write project hooks.json w/o names", w(CUR, "Write", j(ROOT, ".cursor", "hooks.json"), "{}"), "block"),
    ("claude Write project .codex/hooks.json w/o names", w(CLA, "Write", j(ROOT, ".codex", "hooks.json"), "{}"), "block"),
    ("claude Write project settings.local plain", w(CLA, "Write", j(ROOT, ".claude", "settings.local.json"), "{}"), "allow"),
    ("claude Write settings.local w/ disableAllHooks", w(CLA, "Write", j(ROOT, ".claude", "settings.local.json"), '{"disableAllHooks": true}'), "block"),
    ("claude Write settings.local w/ hooks", w(CLA, "Write", j(ROOT, ".claude", "settings.local.json"), '{"hooks": {}}'), "block"),
    ("gitbash path project settings w/o names", w(CLA, "Write", gitbash(j(ROOT, ".claude", "settings.json")), "{}"), "block"),
    ("relative .claude/settings.json w/o names", w(CLA, "Write", ".claude/settings.json", "{}"), "block"),
    ("claude Write GLOBAL ~/.claude/settings.json", w(CLA, "Write", j(HOME, ".claude", "settings.json"), "{}"), "allow"),
    ("cursor Write GLOBAL ~/.cursor/hooks.json", w(CUR, "Write", j(HOME, ".cursor", "hooks.json"), "{}"), "allow"),
    ("claude Write .cursor/hooks/hook_io.py", w(CLA, "Write", j(ROOT, ".cursor", "hooks", "hook_io.py"), "x"), "block"),
    ("claude Write .claude/hooks/shell_guard.py", w(CLA, "Write", j(ROOT, ".claude", "hooks", "shell_guard.py"), "x"), "block"),
    ("claude Write hook state file", w(CLA, "Write", j(ROOT, ".cursor", "hooks", "state", "x_approved.json"), "x"), "block"),
    ("claude Write legacy credentials.env", w(CLA, "Write", j(ROOT, ".cursor", "db", "credentials.env"), "x"), "block"),
    ("claude Write normal file", w(CLA, "Write", j(ROOT, "src", "a.java"), "x"), "allow"),
    ("claude broken JSON -> exit 2", b'{"session_id":"s","hook_event_name":"PreToolUse","tool_name":"Write","tool_input":{"file_path":"x\\q"', "block"),
    ("claude Write .agents/hooks/hook_io.py", w(CLA, "Write", j(HOOKS, "hook_io.py"), "x"), "block"),
    ("claude Write gen_hook_configs.py", w(CLA, "Write", j(HOOKS, "gen_hook_configs.py"), "x"), "block"),
    ("claude Write hook_edit_approve.py", w(CLA, "Write", j(HOOKS, "hook_edit_approve.py"), "x"), "block"),
    ("claude Write hooks.toml garbage", w(CLA, "Write", j(HOOKS, "hooks.toml"), "x"), "block"),
    ("claude Write hooks.toml unchanged", w(CLA, "Write", j(HOOKS, "hooks.toml"), HOOKS_TOML_TEXT), "allow"),
    ("claude Write hooks.toml w/o shell_guard", w(CLA, "Write", j(HOOKS, "hooks.toml"), TOML_NO_SHELL), "block"),
    ("claude Write hooks.toml w/o required flags", w(CLA, "Write", j(HOOKS, "hooks.toml"), TOML_NO_FLAGS), NO_FLAGS_EXPECT),
    ("claude Write custom hook (not protected)", w(CLA, "Write", j(HOOKS, "my_custom_hook.py"), "x"), "allow"),
    ("claude Read secret file", r(CLA, "Read", j(SEC, "proj", "ftp.env")), "block"),
    ("claude Read secret file gitbash path", r(CLA, "Read", gitbash(j(SEC, "proj", "ftp.env"))), "block"),
    ("claude Grep secret dir", r(CLA, "Grep", SEC), "block"),
    ("claude Read legacy credentials.env", r(CLA, "Read", j(ROOT, ".agents", "mcp-servers", "db", "credentials.env")), "block"),
    ("cursor beforeReadFile secret file", json.dumps({"cursor_version": "1", "conversation_id": "x", "hook_event_name": "beforeReadFile", "file_path": j(SEC, "proj", "ftp.env"), "content": "x"}).encode("utf-8"), "block"),
    ("cursor beforeReadFile normal file", json.dumps({"cursor_version": "1", "conversation_id": "x", "hook_event_name": "beforeReadFile", "file_path": j(ROOT, "AGENTS.md"), "content": "x"}).encode("utf-8"), "allow"),
    ("claude Read normal file", r(CLA, "Read", j(ROOT, "AGENTS.md")), "allow"),
    ("claude Read credentials example", r(CLA, "Read", j(ROOT, ".agents", "mcp-servers", "db", "credentials.env.example")), "allow"),
    ("claude Write new empty secret file", w(CLA, "Write", j(SEC, "proj", "new-test-only.env"), ""), "allow"),
    ("claude Write harness_config.py", w(CLA, "Write", j(HOME, ".agents", "scripts", "harness_config.py"), "x"), "block"),
    ("claude Write global harness.toml secrets_dir", w(CLA, "Write", j(HOME, ".agents", "harness.toml"), 'secrets_dir = "D:/x"'), "block"),
]
if EXISTING_SECRET:
    CASES.append(("claude Write existing secret file", w(CLA, "Write", EXISTING_SECRET, "x"), "block"))
else:
    print("SKIP claude Write existing secret file (no file under %s)" % SEC)

fail = 0
for name, payload, expect in CASES:
    p = subprocess.run([PY, G], input=payload, capture_output=True)
    out = p.stdout.decode("utf-8", "replace")
    got = "block" if (p.returncode == 2 or '"deny"' in out) else "allow"
    fail += 0 if got == expect else 1
    print("%s %-48s rc=%s got=%s" % ("PASS" if got == expect else "FAIL", name, p.returncode, got))

# "gohook" approval: run copies in a temp dir so the live approval state is never touched.
_tmp = tempfile.mkdtemp(prefix="hook_edit_test_")
for _f in ("protected_path_guard.py", "hook_io.py", "hook_edit_approve.py"):
    shutil.copy(j(HOOKS, _f), _tmp)
TG, TA = j(_tmp, "protected_path_guard.py"), j(_tmp, "hook_edit_approve.py")
HOOK_PY = j(HOOKS, "shell_guard.py")


def prompt(text):
    subprocess.run([PY, TA], input=json.dumps(dict(CLA, prompt=text)).encode("utf-8"), capture_output=True)


def guard(path, content="x"):
    p = subprocess.run([PY, TG], input=w(CLA, "Write", path, content), capture_output=True)
    return "block" if (p.returncode == 2 or '"deny"' in p.stdout.decode("utf-8", "replace")) else "allow"


# harness.toml [guard]: changes need a "gohook" turn; other keys stay editable
HT = j(_tmp, "harness.toml")
GUARD_TOML = 'name = "p"\n[guard]\nblock_hosts = ["10.0.0.1"]\n'
with open(HT, "w", encoding="utf-8") as _f:
    _f.write(GUARD_TOML)
for name, content, expect in [
    ("no approval: harness.toml other key", GUARD_TOML + '[person]\nauthor = "a"\n', "allow"),
    ("no approval: harness.toml [guard] change", 'name = "p"\n[guard]\nblock_hosts = []\n', "block"),
    ("no approval: harness.toml [guard] removed", 'name = "p"\n', "block"),
    ("no approval: harness.toml unparseable", "[guard\n", "block"),
]:
    got = guard(HT, content)
    fail += 0 if got == expect else 1
    print("%s %-48s got=%s" % ("PASS" if got == expect else "FAIL", name, got))

steps = [
    ("no approval: hook script", None, HOOK_PY, "block"),
    ("gohook: hook script", "gohook", HOOK_PY, "allow"),
    ("gohook: hook state stays blocked", None, j(HOOKS, "state", "x_approved.json"), "block"),
    ("gohook: approval state file stays blocked", None, j(_tmp, "state", "hook_edit_approved.json"), "block"),
    ("gohook: credentials stay blocked", None, j(ROOT, ".agents", "mcp-servers", "db", "credentials.env"), "block"),
    ("next prompt expires approval", "next turn", HOOK_PY, "block"),
]
for name, text, path, expect in steps:
    if text is not None:
        prompt(text)
    got = guard(path)
    fail += 0 if got == expect else 1
    print("%s %-48s got=%s" % ("PASS" if got == expect else "FAIL", name, got))
    if name == "gohook: hook script":
        got = guard(HT, 'name = "p"\n[guard]\nblock_hosts = []\n')
        fail += 0 if got == "allow" else 1
        print("%s %-48s got=%s" % ("PASS" if got == "allow" else "FAIL", "gohook: harness.toml [guard] change", got))
shutil.rmtree(_tmp, ignore_errors=True)
print("TOTAL FAIL=%d" % fail)
sys.exit(1 if fail else 0)
