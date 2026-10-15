# -*- coding: utf-8 -*-
"""prompt_submit: the approval word alone opens protected hook-script edits for this turn.

The word is [guard] hook_approval in harness.toml (default "gohook").

Any other user prompt removes the approval, so it lasts exactly one turn.
Only real user prompts fire this event; agents cannot create the state file
(protected_path_guard.py blocks writes to it).
"""
from __future__ import print_function

import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hook_io import HOOK_EDIT_STATE, emit_prompt_ok, extract_prompt, hook_approval_word, read_stdin_json


def main():
    data = read_stdin_json(strict=False) or {}
    approve_re = re.compile(r"^\s*" + re.escape(hook_approval_word()) + r"\s*[.!！。]?\s*$", re.IGNORECASE)
    if approve_re.match(extract_prompt(data)):
        os.makedirs(os.path.dirname(HOOK_EDIT_STATE), exist_ok=True)
        with open(HOOK_EDIT_STATE, "w", encoding="utf-8") as f:
            json.dump({"approved_at": time.time(), "source": "user_prompt_gohook"}, f)
    elif os.path.isfile(HOOK_EDIT_STATE):
        os.remove(HOOK_EDIT_STATE)
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
