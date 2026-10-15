# -*- coding: utf-8 -*-
"""file_write / file_read guard: protected hook scripts, hook state, secrets, hook registrations."""
from __future__ import print_function

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hook_io
from hook_io import (
    HOOK_EDIT_STATE,
    collect_paths,
    emit_allow,
    emit_deny,
    extract_path_candidates,
    hook_registry,
    is_write_like,
    log_error,
    protected_hook_basenames,
    read_stdin_json,
    required_hook_names,
    tool_name,
)

# Derived from hooks.toml (required = true) plus the core guards; core only if hooks.toml is unreadable.
REQUIRED_HOOKS_JSON_NAMES = required_hook_names()
# Core hook scripts plus hooks.toml entries with protected = true.
_PROTECTED_HOOK_BASENAMES = protected_hook_basenames()


# Project root = parent of .agents/ (this file lives in .agents/hooks). The
# hook-config structural check applies only to this project's files; user-level
# ~/.cursor/hooks.json and ~/.claude/settings.json register no project guards.
# Tool folders (.cursor/.claude/.codex) stay protected too, so a stale copy of a
# hook script there cannot be recreated as a bypass.
_HOOK_DIRS = (".agents/hooks/", ".cursor/hooks/", ".claude/hooks/", ".codex/hooks/")
_PROJECT_ROOT = (
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    .replace("\\", "/")
    .lower()
    .rstrip("/")
    + "/"
)


def _in_project(slash):
    if len(slash) > 3 and slash[0] == "/" and slash[2] == "/" and slash[1].isalpha():
        slash = slash[1] + ":" + slash[2:]  # Git Bash /c/... form
    if not (slash[1:3] == ":/" or slash.startswith("/")):
        return True  # relative path: resolved against the project workspace
    return slash.startswith(_PROJECT_ROOT)


def _is_hooks_toml(path):
    slash = (path or "").replace("\\", "/").lower()
    return slash.endswith("/hooks.toml") and ".agents/hooks/" in slash and _in_project(slash)


def _is_hooks_json(path):
    """Hook registration files with the required-hook-names structural check:
    .cursor/hooks.json, .codex/hooks.json and the tool-neutral list .agents/hooks/hooks.toml."""
    if not path:
        return False
    slash = path.replace("\\", "/").lower()
    if not _in_project(slash):
        return False
    if slash.endswith("hooks.json") and any(d in slash for d in (".cursor/", ".claude/", ".codex/")):
        return True
    return _is_hooks_toml(path)


def _is_claude_settings_json(path):
    """Claude Code's project settings.json (holds generated hooks) — same structural check as hooks.json."""
    if not path:
        return False
    slash = path.replace("\\", "/").lower()
    return ".claude/" in slash and slash.rsplit("/", 1)[-1] == "settings.json" and _in_project(slash)


def _is_claude_settings_local(path):
    """Claude Code's settings.local.json: holds no hooks; only adding hooks or
    the disableAllHooks switch is blocked (that switch is the user's alone)."""
    if not path:
        return False
    slash = path.replace("\\", "/").lower()
    return ".claude/" in slash and slash.rsplit("/", 1)[-1] == "settings.local.json" and _in_project(slash)


def _hook_edit_approved():
    return os.path.isfile(HOOK_EDIT_STATE)


_HOME = os.path.expanduser("~").replace("\\", "/").lower().rstrip("/")
_HARNESS_CONFIG = _HOME + "/.agents/scripts/harness_config.py"
_GLOBAL_HARNESS_TOML = _HOME + "/.agents/harness.toml"
_READ_TOOLS = ("read", "grep", "glob", "notebookread")


def _norm_abs(path):
    slash = path.replace("\\", "/").lower()
    if len(slash) > 3 and slash[0] == "/" and slash[2] == "/" and slash[1].isalpha():
        slash = slash[1] + ":" + slash[2:]  # Git Bash /c/... form
    if slash.startswith("~/"):
        slash = _HOME + slash[1:]
    return slash


def _secret_dirs():
    """Default secrets dir plus the configured one (both stay protected if the setting moves)."""
    dirs = {_HOME + "/.agents/secrets/"}
    try:
        sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".agents", "scripts"))
        import harness_config

        dirs.add(str(harness_config.secrets_dir()).replace("\\", "/").lower().rstrip("/") + "/")
    except Exception as exc:  # loader missing or bad toml: default dir is still protected
        log_error("path_guard secrets_dir fallback: %s" % exc)
    return dirs


def _is_secret(path):
    """Secret store paths: no agent read, no overwrite (credentials.env kept as a legacy secret name)."""
    if not path:
        return False
    slash = _norm_abs(path)
    base = slash.rsplit("/", 1)[-1]
    if base == "cred" + "entials.env" and any(d in slash for d in (".agents/", ".cursor/", ".claude/", ".codex/")):
        return True
    return any(slash.startswith(d) or slash + "/" == d for d in _secret_dirs())


_UNPARSEABLE = object()


def _guard_section(text):
    """[guard] table of a harness.toml text ({} if absent); _UNPARSEABLE counts as a change."""
    try:
        import tomllib

        return tomllib.loads(text or "").get("guard") or {}
    except Exception:
        return _UNPARSEABLE


def _secrets_dir_lines(text):
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip().startswith("secrets_dir")]


def _is_read_like(data):
    tool = tool_name(data).lower()
    if tool:
        return tool in _READ_TOOLS
    # Cursor beforeReadFile carries file_path and no tool name
    return str(data.get("hook_event_name") or "").lower() == "beforereadfile"


def _is_hook_state(slash):
    """Approval/state files the hooks write themselves (hooks/state/...): never agent-writable."""
    return any((d + "state/") in slash for d in _HOOK_DIRS)


def _is_protected(path, approved=False):
    """True if Agent Write to this path must be denied (except hooks.json/settings.json structural allow).
    approved (user sent "gohook" this turn) opens hook scripts only, never state or credentials."""
    if not path:
        return False
    slash = path.replace("\\", "/").lower()
    base = slash.rsplit("/", 1)[-1]

    if _is_hooks_json(path) or _is_claude_settings_json(path) or _is_claude_settings_local(path):
        # Handled separately: structural checks, not blanket deny.
        return False

    if _is_hook_state(slash) or base == "hook_edit_" + "approved.json":
        return True
    if _is_secret(path) and (base == "cred" + "entials.env" or os.path.exists(path)):
        return True  # new empty secret files may be created; existing ones are never overwritten

    if approved:
        return False
    if _norm_abs(path) == _HARNESS_CONFIG:
        return True
    if any(d in slash or slash.startswith(d) for d in _HOOK_DIRS):
        if base in _PROTECTED_HOOK_BASENAMES:
            return True
    return False


def _proposed_hooks_json_text(data, tool):
    """Best-effort proposed file body from Write contents or StrReplace (None = unknown, e.g. apply_patch)."""
    tool_input = data.get("tool_input")
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except Exception:
            tool_input = {}
    if not isinstance(tool_input, dict):
        tool_input = {}

    if "write" in tool:
        contents = tool_input.get("contents")
        if not isinstance(contents, str):
            contents = tool_input.get("content")
        if isinstance(contents, str):
            return contents
    if "strreplace" in tool or "edit" in tool:
        full = tool_input.get("content")
        if isinstance(full, str):
            return full
        path = None
        for key in ("path", "file_path", "filePath"):
            val = tool_input.get(key) or data.get(key)
            if isinstance(val, str) and val.strip():
                path = val.strip()
                break
        old = tool_input.get("old_string")
        new = tool_input.get("new_string")
        if path and isinstance(old, str) and isinstance(new, str) and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                if old not in text:
                    return None
                return text.replace(old, new, 1)
            except Exception:
                return None
    if "delete" in tool:
        return ""
    return None


def _hooks_json_required_names_ok(text):
    if not isinstance(text, str) or not text.strip():
        return False
    lower = text.lower()
    for name in REQUIRED_HOOKS_JSON_NAMES:
        if name.lower() not in lower:
            return False
    return True


def _hooks_toml_required_kept(text):
    """Proposed hooks.toml must parse and keep every currently required guard as a
    [[hook]] entry (names in comments do not count) still marked required."""
    try:
        hooks = hook_registry(text)
    except Exception:
        return False
    scripts = {os.path.basename(str(h.get("script") or "")) for h in hooks}
    required = set(REQUIRED_HOOKS_JSON_NAMES)
    return required <= scripts and required <= set(required_hook_names(hooks))


def main():
    data = read_stdin_json(strict=True)
    if data is None:
        # Cursor on Korean Windows corrupts non-ASCII payloads (CP949 re-read), so
        # a parse failure is common for ordinary edits. Soft-allow only when none
        # of the path values that can still be pulled out of the raw text is a
        # protected file or a hook-config file. Claude Code / Codex send valid UTF-8
        # JSON, so a parse failure there stays a hard deny (emit_deny exits 2).
        paths = extract_path_candidates(hook_io._LAST_STDIN_TEXT or "")
        risky = [p for p in paths if _is_protected(p) or _is_hooks_json(p) or _is_claude_settings_json(p)
                 or _is_claude_settings_local(p)]
        if risky or hook_io.is_claude_code():
            log_error("path_guard soft-parse: deny paths=%s" % (paths,))
            emit_deny(
                "훅 stdin JSON 파싱 실패로 차단했습니다.",
                "protected_path_guard: stdin unparseable and target is a protected or hook-config file.",
            )
            return 0
        log_error("path_guard soft-parse: allow paths=%s" % (paths,))
        emit_allow()
        return 0

    if _is_read_like(data):
        if any(_is_secret(p) for p in collect_paths(data)):
            emit_deny(
                "비밀 파일은 에이전트가 읽을 수 없습니다. 값은 스크립트가 harness_config.secret()으로 읽습니다.",
                "Blocked read of secret store path.",
            )
            return 0
        emit_allow()
        return 0

    if not is_write_like(data):
        emit_allow()
        return 0

    tool = tool_name(data).lower()
    paths = collect_paths(data)

    # secrets_dir moves only by the user's own edit of the global harness.toml
    if any(_norm_abs(p) == _GLOBAL_HARNESS_TOML for p in paths):
        proposed = _proposed_hooks_json_text(data, tool)
        try:
            with open(os.path.expanduser("~/.agents/harness.toml"), "r", encoding="utf-8") as f:
                current = f.read()
        except Exception:
            current = ""
        if proposed is None or _secrets_dir_lines(proposed) != _secrets_dir_lines(current):
            emit_deny(
                "전역 harness.toml의 secrets_dir는 사용자만 바꿀 수 있습니다.",
                "Blocked global harness.toml write touching secrets_dir.",
            )
            return 0

    # [guard] (hook policy: blocked hosts, shell patterns, module approvals) changes only in a "gohook" turn
    toml_paths = [p for p in paths if _norm_abs(p).rsplit("/", 1)[-1] == "harness.toml"]
    if toml_paths and not _hook_edit_approved():
        proposed = _proposed_hooks_json_text(data, tool)
        for p in toml_paths:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    current = f.read()
            except Exception:
                current = ""
            before = _guard_section(current)
            after = _guard_section(proposed) if proposed is not None else _UNPARSEABLE
            if after is _UNPARSEABLE or after != before:
                emit_deny(
                    "harness.toml의 [guard] 절은 사용자가 %s을(를) 단독 입력한 턴에만 바꿀 수 있습니다." % hook_io.hook_approval_word(),
                    "Blocked harness.toml write changing [guard] without hook approval word.",
                )
                return 0

    # hooks.json / hooks.toml / .claude/settings.json: allow only if required hook
    # script names remain present in the proposed body (prevents disabling guards
    # by editing the hook config file itself, on any harness). Applies even
    # under "gohook" approval.
    hooks_paths = [p for p in paths if _is_hooks_json(p) or _is_claude_settings_json(p)]
    if hooks_paths:
        proposed = _proposed_hooks_json_text(data, tool)
        ok = proposed is not None and _hooks_json_required_names_ok(proposed)
        if ok and any(_is_hooks_toml(p) for p in hooks_paths):
            ok = _hooks_toml_required_kept(proposed)
        if not ok:
            emit_deny(
                "훅 등록 파일(hooks.json/hooks.toml/settings.json)에서 필수 가드(%s)를 빼는 수정은 차단됩니다."
                % ", ".join(REQUIRED_HOOKS_JSON_NAMES),
                "Blocked hook-config write: missing required hook basenames or required flags.",
            )
            return 0
        # Other paths in same call still checked below.

    if any(_is_claude_settings_local(p) for p in paths):
        proposed = _proposed_hooks_json_text(data, tool)
        if proposed is None or '"hooks"' in proposed or "disableallhooks" in proposed.lower():
            emit_deny(
                "settings.local.json에 hooks·disableAllHooks를 넣는 수정은 사용자만 할 수 있습니다.",
                "Blocked settings.local.json write: hooks or disableAllHooks.",
            )
            return 0

    approved = _hook_edit_approved()
    if any(_is_protected(p, approved) for p in paths):
        emit_deny(
            "보호된 훅 스크립트·훅 상태·비밀 파일입니다. 훅 스크립트 수정은 사용자가 %s을(를) 단독 입력한 턴에만 가능합니다." % hook_io.hook_approval_word(),
            "Blocked write to protected path.",
        )
        return 0

    emit_allow()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main() or 0)
    except SystemExit:
        raise
    except Exception as exc:
        emit_deny("path guard error", str(exc))
        raise SystemExit(0)
