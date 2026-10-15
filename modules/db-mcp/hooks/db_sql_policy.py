# -*- coding: utf-8 -*-
"""Shared DB MCP SQL classification and approval-session checks.

Settings: harness.toml [guard.db] (approvals, session_envs, ttl, prod_envs, ...).
Missing config means no approval keywords, so every write stays denied.
"""
from __future__ import print_function

import json
import os
import re
import sys
import time
from pathlib import Path


def _guard_config():
    """[guard.db] of the project harness.toml. Missing/broken config -> {} (no approvals = no writes)."""
    try:
        sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".agents", "scripts"))
        import harness_config

        root = Path(__file__).resolve().parents[2]  # .agents/hooks -> project root
        return (harness_config.load(root).get("guard") or {}).get("db") or {}
    except Exception:
        return {}


_CFG = _guard_config()
DEFAULT_SESSION_TTL_SEC = int(_CFG.get("session_ttl_sec", 600))
BUNDLE_TTL_SEC = int(_CFG.get("bundle_ttl_sec", 180))
BUNDLE_MAX_WRITES = int(_CFG.get("bundle_max_writes", 10))

# Without config every env counts as prod, so INSERT/MERGE/CREATE stay denied.
PROD_ENVS = tuple(_CFG.get("prod_envs") or ()) if _CFG else None
PROD_MUTATION_DENY_KEYWORDS = tuple(_CFG.get("prod_deny_keywords") or ("INSERT", "MERGE", "CREATE"))

# Single source for env -> approval keyword (empty when config is missing: writes need an approval that cannot exist).
APPROVAL_KEYWORDS = dict(_CFG.get("approvals") or {})
SESSION_ENVS = tuple(_CFG.get("session_envs") or ())
ENVS = tuple(APPROVAL_KEYWORDS)

# Approval state written by db_dml_approve.py, read by db_mcp_guard.py
# and the DB MCP adapter server.
STATE_FILE = Path(__file__).resolve().parent / "state" / ("dml_" + "approved.json")

READ_PREFIXES = (
    "SELECT",
    "WITH",
    "SHOW",
    "DESC",
    "DESCRIBE",
    "EXPLAIN",
)

WRITE_KEYWORDS = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "TRUNCATE",
    "CREATE",
    "ALTER",
    "DROP",
    "GRANT",
    "REVOKE",
    "COMMENT",
    "RENAME",
    "CALL",
    "BEGIN",
    "DECLARE",
    "EXECUTE",
)

# Always denied even with a valid approval session.
HARD_DENY_KEYWORDS = (
    "DROP",
    "TRUNCATE",
)

WRITE_KEYWORD_RE = re.compile(
    r"\b(" + "|".join(WRITE_KEYWORDS) + r")\b",
    re.IGNORECASE,
)
HARD_DENY_RE = re.compile(
    r"\b(" + "|".join(HARD_DENY_KEYWORDS) + r")\b",
    re.IGNORECASE,
)
WHERE_RE = re.compile(r"\bWHERE\b", re.IGNORECASE)
UPDATE_OR_DELETE_RE = re.compile(r"\b(UPDATE|DELETE)\b", re.IGNORECASE)
PROD_MUTATION_DENY_RE = re.compile(
    r"\b(" + "|".join(PROD_MUTATION_DENY_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def strip_sql_comments(sql):
    no_block = re.sub(r"/\*.*?\*/", " ", sql or "", flags=re.DOTALL)
    lines = []
    for line in no_block.splitlines():
        if "--" in line:
            line = line.split("--", 1)[0]
        lines.append(line)
    return "\n".join(lines)


def has_multiple_statements(cleaned):
    """True if there is a non-trailing statement separator."""
    text = (cleaned or "").strip()
    if not text:
        return False
    # Allow a single trailing semicolon.
    if text.endswith(";"):
        text = text[:-1].rstrip()
    return ";" in text


def first_token(cleaned):
    token = re.split(r"\s+", cleaned.strip(), maxsplit=1)[0].upper()
    return token.lstrip("(")


def classify_sql(sql):
    """Return kind: empty|multi|hard_deny|read|write|unknown.

    write covers DML/DDL that needs approval (except hard_deny which is never allowed).
    """
    cleaned = strip_sql_comments(sql).strip()
    if not cleaned:
        return "empty"
    if has_multiple_statements(cleaned):
        return "multi"
    if HARD_DENY_RE.search(cleaned):
        return "hard_deny"
    # Body keyword scan blocks WITH ... UPDATE/DELETE bypass.
    if WRITE_KEYWORD_RE.search(cleaned):
        return "write"
    token = first_token(cleaned)
    if token in READ_PREFIXES:
        return "read"
    if token in WRITE_KEYWORDS:
        return "write"
    return "unknown"


def requires_where(sql):
    """UPDATE/DELETE must include WHERE (hard rule for approved writes)."""
    return bool(UPDATE_OR_DELETE_RE.search(strip_sql_comments(sql)))


def has_where_clause(sql):
    cleaned = strip_sql_comments(sql)
    return bool(WHERE_RE.search(cleaned))


def validate_write_sql(sql, env=None):
    """Return (ok, reason_code) for the hard rules that apply before any approval check.

    ok=True with reason "read" needs nothing more; "write" still needs an approval session.
    Deny reasons: empty, multi, hard_deny, unknown, prod_mutation, no_where.
    """
    kind = classify_sql(sql)
    if kind in ("empty", "multi", "hard_deny", "unknown"):
        return False, kind
    if kind == "read":
        return True, "read"
    if prod_mutation_denied(env, sql):
        return False, "prod_mutation"
    if requires_where(sql) and not has_where_clause(sql):
        return False, "no_where"
    return True, "write"


def approval_keyword_for_env(env):
    return APPROVAL_KEYWORDS.get(env)


def is_session_env(env):
    return env in SESSION_ENVS


def is_prod_env(env):
    return True if PROD_ENVS is None else env in PROD_ENVS


def prod_mutation_denied(env, sql):
    """True when env is a prod env and the SQL body contains a prod_deny_keywords word."""
    if not is_prod_env(env):
        return False
    cleaned = strip_sql_comments(sql)
    return bool(PROD_MUTATION_DENY_RE.search(cleaned))


def session_allows_write(session):
    """Return True if session dict still permits one more write."""
    if not session:
        return False
    mode = session.get("mode") or "session"
    if mode == "session":
        return True
    if mode == "bundle":
        try:
            used = int(session.get("writes_used", 0))
            limit = int(session.get("max_writes", BUNDLE_MAX_WRITES))
        except (TypeError, ValueError):
            return False
        return used < limit
    return False


def consume_write(state_file, expected_env=None):
    """Increment bundle writes_used after a successful write commit."""
    path = Path(state_file)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        env = data.get("env") or "dev"
        if expected_env is not None and env != expected_env:
            return False
        mode = data.get("mode") or "session"
        if mode != "bundle":
            return True
        used = int(data.get("writes_used", 0)) + 1
        limit = int(data.get("max_writes", BUNDLE_MAX_WRITES))
        data["writes_used"] = used
        if used >= limit:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            return True
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


def load_session(state_file, expected_env=None, default_ttl=DEFAULT_SESSION_TTL_SEC):
    """Return session dict if valid, else None. Deletes expired file when possible."""
    path = Path(state_file)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ts = float(data.get("approved_at", 0))
        ttl = data.get("ttl_sec")
        try:
            ttl_sec = float(ttl) if ttl is not None else float(default_ttl)
        except (TypeError, ValueError):
            ttl_sec = float(default_ttl)
        if time.time() - ts > ttl_sec:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            return None
        env = data.get("env") or "dev"
        if expected_env is not None and env != expected_env:
            return None
        return data
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def sql_preview(sql, limit=200):
    text = re.sub(r"\s+", " ", (sql or "").strip())
    if len(text) > limit:
        return text[:limit] + "..."
    return text
