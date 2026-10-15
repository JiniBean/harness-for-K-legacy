# -*- coding: utf-8 -*-
"""Approval-keyword prompt hook test. Run inside an installed project:
python .agents/hooks/tests/test_dml_prompt.py

Runs a copy of the hook in a temp project with a known [guard.db] config, so
the live approval state file is never created or deleted.
"""
from __future__ import print_function

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path as _P

HOOKS = str(_P(__file__).resolve().parents[1])  # <root>/.agents/hooks
PY = sys.executable

_ROOT = tempfile.mkdtemp(prefix="dml_prompt_test_")
_TMP = os.path.join(_ROOT, ".agents", "hooks")
os.makedirs(_TMP)
with open(os.path.join(_ROOT, ".agents", "harness.toml"), "w", encoding="utf-8") as _f:
    _f.write('name = "prompttest"\n[guard.db]\napprovals = { dev = "go", test = "gotest" }\nsession_envs = ["dev"]\n')
for _f in ("db_dml_approve.py", "db_sql_policy.py", "hook_io.py"):
    shutil.copy(os.path.join(HOOKS, _f), _TMP)
SCRIPT = os.path.join(_TMP, "db_dml_approve.py")
STATE = os.path.join(_TMP, "state", "dml_" + "approved.json")


def run_case(name, payload_bytes):
    if os.path.isfile(STATE):
        os.remove(STATE)
    p = subprocess.Popen([PY, SCRIPT], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(payload_bytes)
    created = os.path.isfile(STATE)
    print("%s: created=%s stdout=%s" % (name, created, out.decode("utf-8", "replace").strip()))
    if err:
        print("  stderr: %s" % err.decode("utf-8", "replace").strip()[:200])
    return created


def mojibake_cp949(s):
    raw = s.encode("utf-8")
    return raw.decode("cp949", errors="replace")


def main():
    ok = fail = 0
    cases = []
    cases.append(("exact_utf8", json.dumps({"prompt": "go"}, ensure_ascii=False).encode("utf-8"), True))
    body = json.dumps({"prompt": "go"}, ensure_ascii=False).encode("utf-8")
    cases.append(("bom2_exact", b"\xef\xbb\xbf\xef\xbb\xbf" + body, True))
    cases.append(("codex_prompt", json.dumps({"session_id": "s", "hook_event_name": "UserPromptSubmit", "model": "m", "prompt": "gotest"}).encode("utf-8"), True))
    bad = mojibake_cp949("진행")
    cases.append(("mojibake_cp949", json.dumps({"prompt": bad}, ensure_ascii=False).encode("utf-8"), False))
    user_text = "이게 가장 유력한거아니야?\n너가 테스트 한번해봐\n\n진행"
    cases.append(("multiline_text", json.dumps({"prompt": user_text}, ensure_ascii=False).encode("utf-8"), False))
    cases.append(("empty_stdin", b"", False))
    cases.append(("no_prompt_key", json.dumps({"conversation_id": "test"}).encode("utf-8"), False))
    for name, raw, expect in cases:
        got = run_case(name, raw)
        if got == expect:
            ok += 1
            print("  -> PASS")
        else:
            fail += 1
            print("  -> FAIL expected created=%s" % expect)
    print("summary ok=%s fail=%s" % (ok, fail))
    shutil.rmtree(_ROOT, ignore_errors=True)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
