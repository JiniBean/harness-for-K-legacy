# -*- coding: utf-8 -*-
"""Guard cases for db_mcp_guard (D8'/D9' Cursor+Claude shapes). Run from module tests dir or any cwd."""
from __future__ import print_function

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
MOD = HOOKS.parent
# Resolve kit core/hook_io.py from this file: .../modules/db-mcp/hooks/tests -> repo root
KIT_HOOK_IO = Path(__file__).resolve().parents[4] / "core" / "hook_io.py"


def _build():
    root = Path(tempfile.mkdtemp(prefix="dbmcp_guard_"))
    h = root / ".agents" / "hooks"
    h.mkdir(parents=True)
    shutil.copy(KIT_HOOK_IO, h / "hook_io.py")
    for name in ("db_sql_policy.py", "db_mcp_guard.py"):
        shutil.copy(HOOKS / name, h / name)
    (root / ".agents" / "harness.toml").write_text(
        'name = "t"\n[guard.db]\napprovals = { dev = "go", test = "gotest", kr = "gokr" }\n'
        'session_envs = ["dev"]\nprod_envs = ["kr"]\n',
        encoding="utf-8",
    )
    s = root / ".agents" / "mcp-servers" / "singleton"
    s.mkdir(parents=True)
    (s / "ports.json").write_text(
        json.dumps(
            {
                "bind": "127.0.0.1",
                "servers": {
                    "db-dev": {"port": 18761},
                    "db-kr": {"port": 18763},
                    "proj-ftp": {"port": 18766},
                },
            }
        ),
        encoding="utf-8",
    )
    # installed layout: hooks next to mcp-servers under .agents
    # guard looks ../mcp-servers/singleton from hooks — so put mcp-servers under .agents
    return root


CLA = {"session_id": "s", "hook_event_name": "PreToolUse"}
WS = ["/c:/proj/GSABIS"]
CUR = {
    "cursor_version": "3.20.21",
    "conversation_id": "x",
    "hook_event_name": "beforeMCPExecution",
    "workspace_roots": WS,
}


def cur(name, sql, url=None, tool="execute_sql"):
    p = dict(CUR, tool_name=tool, tool_input=json.dumps({"query": sql}), mcp_server_name=name)
    if url:
        p.update(mcp_server_url=url, url=url)
    else:
        p["command"] = name
    return p


CASES = [
    ("claude db-dev SELECT", dict(CLA, tool_name="mcp__db-dev__execute_sql", tool_input={"query": "SELECT 1 FROM DUAL"}), "allow"),
    ("claude db-kr INSERT", dict(CLA, tool_name="mcp__db-kr__execute_sql", tool_input={"query": "INSERT INTO T VALUES (1)"}), "block"),
    ("claude db-xx unknown", dict(CLA, tool_name="mcp__db-xx__execute_sql", tool_input={"query": "SELECT 1 FROM DUAL"}), "block"),
    ("SQL literal no pick", dict(CLA, tool_name="mcp__db-xx__execute_sql", tool_input={"query": "SELECT 'db-dev' FROM DUAL"}), "block"),
    ("url db-dev SELECT", cur("db-dev", "SELECT 1 FROM DUAL", "http://127.0.0.1:18761/mcp"), "allow"),
    ("url db-kr INSERT", cur("db-kr", "INSERT INTO T VALUES (1)", "http://127.0.0.1:18763/mcp"), "block"),
    ("url db-xx unknown", cur("db-xx", "SELECT 1 FROM DUAL", "http://127.0.0.1:18799/mcp"), "block"),
    ("stdio project-0-GSABIS-db-kr INSERT", cur("project-0-GSABIS-db-kr", "INSERT INTO T VALUES (1)"), "block"),
    ("stdio project-0-GSABIS-db-dev UPDATE no WHERE", cur("project-0-GSABIS-db-dev", "UPDATE T SET A=1"), "block"),
    ("stdio foreign postgres-db-prod", cur("project-0-GSABIS-postgres-db-prod", "UPDATE T SET A=1 WHERE B=2"), "allow"),
    ("foreign mongodb-dev execute_sql", dict(CLA, tool_name="mcp__mongodb-dev__execute_sql", tool_input={"query": "UPDATE T SET A=1 WHERE B=2"}), "allow"),
    ("foreign sqlite-db-local", dict(CLA, tool_name="mcp__sqlite-db-local__list_tables", tool_input={}), "allow"),
    ("foreign url postgres-db-prod", cur("mongodb-dev", "UPDATE T SET A=1 WHERE B=2", "https://mcp.example.com/postgres-db-prod/mcp"), "allow"),
    ("url jetbrains", cur("jetbrains", "", "http://localhost:64342/sse", tool="search_in_files_by_text"), "allow"),
    ("ftp url", cur("proj-ftp", "", "http://127.0.0.1:18766/mcp", tool="ftp_list"), "allow"),
]


def run(root, payload):
    # guard resolves ports relative to hooks/../mcp-servers — need layout .agents/hooks and .agents/mcp-servers
    # policy parents[2] = project root from .agents/hooks -> need harness at project/.agents/harness.toml
    # Move: our root IS project with .agents/
    p = subprocess.run(
        [sys.executable, str(root / ".agents" / "hooks" / "db_mcp_guard.py")],
        input=json.dumps(payload).encode(),
        capture_output=True,
        cwd=str(root),
    )
    return "block" if (p.returncode == 2 or b'"deny"' in p.stdout) else "allow"


def main():
    # Patch guard ports path: installed copy uses hooks under .agents/hooks and singleton under .agents/mcp-servers/singleton
    # Source guard uses ../mcp-servers from hooks dir = .agents/mcp-servers — correct for install layout.
    root = _build()
    # symlink/copy singleton to where guard expects: hooks/../mcp-servers = .agents/mcp-servers — already there
    fail = 0
    print("== test_db_mcp_guard")
    for label, payload, expect in CASES:
        got = run(root, payload)
        ok = got == expect
        fail += 0 if ok else 1
        print("%s %-48s got=%s" % ("PASS" if ok else "FAIL", label, got))
    shutil.rmtree(root, ignore_errors=True)
    print("FAIL=%d" % fail)
    return fail


if __name__ == "__main__":
    raise SystemExit(main())
