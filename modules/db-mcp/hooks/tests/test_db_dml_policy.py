# -*- coding: utf-8 -*-
"""Smoke tests for the DB DML approval policy (no DB). Run inside an installed project:
python .agents/hooks/tests/test_DB_dml_policy.py

Imports the hooks from a temp project copy with a known [guard.db] config.
"""
from __future__ import print_function

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path as _P

HOOKS = str(_P(__file__).resolve().parents[1])  # <root>/.agents/hooks
sys.stdout.reconfigure(encoding="utf-8")

DB_TOML = """name = "DBtest"
[guard.db]
approvals = { dev = "go", test = "gotest", kr = "gokr", vn = "govn", cn = "gocn" }
session_envs = ["dev"]
session_ttl_sec = 600
bundle_ttl_sec = 180
bundle_max_writes = 10
prod_envs = ["kr", "vn", "cn"]
prod_deny_keywords = ["INSERT", "MERGE", "CREATE"]
"""

_ROOT = tempfile.mkdtemp(prefix="DB_policy_test_")
_TH = os.path.join(_ROOT, ".agents", "hooks")
os.makedirs(_TH)
for _f in ("hook_io.py", "db_sql_policy.py", "db_dml_approve.py"):
    shutil.copy(os.path.join(HOOKS, _f), _TH)
with open(os.path.join(_ROOT, ".agents", "harness.toml"), "w", encoding="utf-8") as _f:
    _f.write(DB_TOML)
sys.path.insert(0, _TH)

from db_sql_policy import (  # noqa: E402
    BUNDLE_MAX_WRITES,
    classify_sql,
    consume_write,
    load_session,
    prod_mutation_denied,
    session_allows_write,
)
from db_dml_approve import _match_approval  # noqa: E402


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("OK:", msg)


def test_approval_keywords():
    ok(_match_approval("go") == ("dev", "session"), "go -> dev session")
    ok(_match_approval("gotest") == ("test", "bundle"), "gotest -> test bundle")
    ok(_match_approval("gokr") == ("kr", "bundle"), "gokr -> kr bundle")
    ok(_match_approval("govn") == ("vn", "bundle"), "govn -> vn bundle")
    ok(_match_approval("gocn") == ("cn", "bundle"), "gocn -> cn bundle")
    ok(_match_approval("go 해줘") == (None, None), "go 해줘 not approved")
    ok(_match_approval("gogo") == (None, None), "gogo not approved")


def test_prod_mutation():
    ok(prod_mutation_denied("kr", "INSERT INTO t VALUES (1)"), "kr INSERT denied")
    ok(prod_mutation_denied("kr", "MERGE INTO t USING s ON (1=1)"), "kr MERGE denied")
    ok(prod_mutation_denied("kr", "CREATE TABLE x (id NUMBER)"), "kr CREATE denied")
    ok(not prod_mutation_denied("kr", "DELETE FROM t WHERE id = 1"), "kr DELETE allowed check")
    ok(not prod_mutation_denied("test", "INSERT INTO t VALUES (1)"), "test INSERT allowed check")


def test_bundle_consume():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        payload = {
            "mode": "bundle",
            "env": "test",
            "max_writes": BUNDLE_MAX_WRITES,
            "writes_used": 0,
            "approved_at": time.time(),
            "ttl_sec": 180,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        session = load_session(path, expected_env="test")
        ok(session_allows_write(session), "bundle session allows first write")
        for i in range(BUNDLE_MAX_WRITES):
            ok(consume_write(path, expected_env="test"), "consume %d" % (i + 1))
        ok(not os.path.isfile(path), "state file removed after max writes")
    finally:
        if os.path.isfile(path):
            os.unlink(path)


def test_classify():
    ok(classify_sql("SELECT 1 FROM dual") == "read", "SELECT is read")
    ok(classify_sql("DELETE FROM t WHERE id = 1") == "write", "DELETE is write")
    ok(classify_sql("DROP TABLE t") == "hard_deny", "DROP hard deny")


def main():
    try:
        test_approval_keywords()
        test_prod_mutation()
        test_bundle_consume()
        test_classify()
    finally:
        shutil.rmtree(_ROOT, ignore_errors=True)
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
