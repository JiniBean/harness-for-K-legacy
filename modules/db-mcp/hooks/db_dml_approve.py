# -*- coding: utf-8 -*-
"""prompt_submit: record DML approval when the user sends an approval keyword alone
(keywords per env from harness.toml [guard.db] approvals, e.g. go / gotest)."""
from __future__ import print_function

import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hook_io import emit_prompt_ok, extract_prompt, read_stdin_json
from db_sql_policy import (
    APPROVAL_KEYWORDS,
    BUNDLE_MAX_WRITES,
    BUNDLE_TTL_SEC,
    DEFAULT_SESSION_TTL_SEC,
    STATE_FILE,
    is_session_env,
)

# Whole-message match, so length order does not matter; session envs come from [guard.db].
APPROVE_MAP = tuple(
    (re.compile(r"^\s*" + re.escape(kw) + r"\s*[.!！。]?\s*$"), env, "session" if is_session_env(env) else "bundle")
    for env, kw in APPROVAL_KEYWORDS.items()
)


def _match_approval(prompt):
    text = prompt or ""
    for pattern, env, mode in APPROVE_MAP:
        if pattern.match(text):
            return env, mode
    return None, None


def main():
    data = read_stdin_json(strict=False)
    if not data:
        emit_prompt_ok()
        return 0

    env, mode = _match_approval(extract_prompt(data))
    if env and mode:
        payload = {
            "mode": mode,
            "env": env,
            "approved_at": time.time(),
            "source": "user_prompt_%s" % env,
        }
        if mode == "session":
            payload["ttl_sec"] = DEFAULT_SESSION_TTL_SEC
        else:
            payload["ttl_sec"] = BUNDLE_TTL_SEC
            payload["max_writes"] = BUNDLE_MAX_WRITES
            payload["writes_used"] = 0
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    emit_prompt_ok()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main() or 0)
    except SystemExit:
        raise
    except Exception:
        emit_prompt_ok()
        raise SystemExit(0)
