# -*- coding: utf-8 -*-
"""mcp guard for DB MCP servers (db-<env>).

Policy from harness.toml [guard.db]:
- SELECT-like free; writes need the env approval keyword alone
- session_envs / bundle / prod_envs as in db_sql_policy
Detection (D8'/D9'): Claude tool_name mcp__db-<env>__; Cursor mcp_server_name;
ports.json db-* fallback. No substring db-/launch_ gates.
"""
from __future__ import print_function

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hook_io import emit_allow, emit_deny, read_stdin_json
from db_sql_policy import (
    BUNDLE_TTL_SEC,
    DEFAULT_SESSION_TTL_SEC,
    ENVS,
    STATE_FILE,
    approval_keyword_for_env,
    is_session_env,
    load_session,
    session_allows_write,
    validate_write_sql,
)

DENY_MESSAGES = {
    "empty": ("빈 SQL은 실행할 수 없습니다.", "Empty SQL denied."),
    "multi": ("세미콜론으로 연결된 다중 SQL은 허용되지 않습니다.", "Multi-statement SQL denied."),
    "hard_deny": ("DROP/TRUNCATE는 승인 세션이어도 허용되지 않습니다.", "DROP/TRUNCATE hard-denied."),
    "unknown": ("알 수 없는 SQL 유형은 차단되었습니다.", "Unknown SQL kind denied."),
    "prod_mutation": (
        "운영(%s)에서는 INSERT/MERGE/CREATE가 허용되지 않습니다. UPDATE/DELETE만 가능합니다.",
        "Prod mutation denied on db-%s: prod_deny_keywords blocked.",
    ),
    "no_where": ("UPDATE/DELETE는 WHERE 절이 필수입니다.", "UPDATE/DELETE without WHERE denied."),
}


def _payload_blob(payload):
    meta = dict((k, v) for k, v in payload.items() if k != "tool_input")
    return json.dumps(meta, ensure_ascii=False).lower()


def _port_envs():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mcp-servers", "daemon", "ports.json")
    try:
        with open(path, encoding="utf-8") as f:
            servers = json.load(f).get("servers") or {}
    except (OSError, ValueError):
        return {}
    return dict((":%s/" % s.get("port"), name[len("db-"):])
                for name, s in servers.items() if name.startswith("db-"))


def _cursor_server(payload):
    name = str(payload.get("mcp_server_name") or "").lower()
    m = re.match(r"db-([a-z0-9]+)$", name)
    if m:
        return m.group(1)
    for root in payload.get("workspace_roots") or []:
        base = re.escape(str(root).rstrip("/\\").replace("\\", "/").split("/")[-1].lower())
        m = re.match(r"project-\d+-%s-db-([a-z0-9]+)$" % base, name)
        if m:
            return m.group(1)
    return None


def _detect_env(payload):
    tool = str(payload.get("tool_name") or "").lower()
    m = re.match(r"mcp__db-([a-z0-9]+)__", tool)
    if m:
        return m.group(1) if m.group(1) in ENVS else None
    cur = _cursor_server(payload)
    if cur is not None:
        return cur if cur in ENVS else None
    blob = _payload_blob(payload)
    for token, env in _port_envs().items():
        if token in blob and env in ENVS:
            return env
    return None


def _gate(payload, env):
    tool = str(payload.get("tool_name") or "").lower()
    if re.match(r"mcp__db-", tool):
        return True
    if _cursor_server(payload) is not None:
        return True
    return env is not None


def _tool_name(payload):
    name = str(payload.get("tool_name") or "")
    lower = name.lower()
    if "execute_sql" in lower:
        return "execute_sql"
    if "get_table_info" in lower:
        return "get_table_info"
    return lower.split(".")[-1].split("-")[-1].strip()


def _extract_query(payload):
    raw = payload.get("tool_input")
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            data = {"query": raw}
    if not isinstance(data, dict):
        return ""
    for key in ("query", "sql", "statement"):
        if data.get(key):
            return str(data.get(key))
    return ""


def _deny(user_message, agent_message):
    emit_deny(user_message, agent_message)
    return 0


def _default_ttl_for_env(env):
    if is_session_env(env):
        return DEFAULT_SESSION_TTL_SEC
    return BUNDLE_TTL_SEC


def main():
    payload = read_stdin_json(strict=True)
    if payload is None:
        return _deny(
            "DB MCP 훅 입력 파싱 실패",
            "DB MCP guard stdin JSON parse failed (empty or unparseable).",
        )

    env = _detect_env(payload)
    tool = _tool_name(payload)

    if not _gate(payload, env):
        emit_allow()
        return 0

    if env is None:
        return _deny(
            "DB MCP 환경을 판별할 수 없어 차단했습니다.",
            "Could not detect a db-<env> from [guard.db] approvals (%s). Denied." % ", ".join(ENVS),
        )

    if tool != "execute_sql":
        emit_allow()
        return 0

    query = _extract_query(payload)
    keyword = approval_keyword_for_env(env)

    ok, reason = validate_write_sql(query, env)
    if not ok:
        user_msg, agent_msg = DENY_MESSAGES[reason]
        if reason == "prod_mutation":
            user_msg, agent_msg = user_msg % env, agent_msg % env
        return _deny(user_msg, agent_msg)

    if reason == "read":
        emit_allow()
        return 0

    session = load_session(
        STATE_FILE,
        expected_env=env,
        default_ttl=_default_ttl_for_env(env),
    )
    if keyword and session and session_allows_write(session):
        emit_allow()
        return 0

    return _deny(
        "DML/DDL은 채팅에 '%s'만 단독으로 입력한 뒤 다시 실행해야 합니다." % keyword,
        "Write blocked on db-%s until user sends exactly '%s'." % (env, keyword),
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main() or 0)
    except SystemExit:
        raise
    except Exception as exc:
        emit_deny(
            "DB MCP 훅 오류로 차단했습니다.",
            "Hook error: %s" % exc,
        )
        raise SystemExit(0)
