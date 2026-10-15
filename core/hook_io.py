# -*- coding: utf-8 -*-
"""Shared stdin/stdout JSON I/O for Cursor, Claude Code and Codex hooks (Windows-safe).

Output protocol:
- Cursor: JSON on stdout ({"permission": "allow"|"deny", ...}).
- Claude Code and Codex: allow = no output + exit 0; deny = reason on stderr + exit 2.
"""
from __future__ import print_function

import json
import os
import re
import sys
import tomllib
import traceback
from datetime import datetime

UTF8_BOM = b"\xef\xbb\xbf"
UTF16_LE_BOM = b"\xff\xfe"
UTF16_BE_BOM = b"\xfe\xff"

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
# Project root = parent of .agents/ (this file lives in <root>/.agents/hooks or ~/.agents/hooks).
PROJECT_ROOT = os.path.dirname(os.path.dirname(HOOKS_DIR))
HOOKS_TOML = os.path.join(HOOKS_DIR, "hooks.toml")

# Guards every hook registration must keep, whatever hooks.toml says.
CORE_REQUIRED = ("shell_guard.py", "protected_path_guard.py")
# Hook scripts agents may edit only in a "gohook" turn. gen_hook_configs.py writes
# the registration files directly (not through the Write tool), so it must not be
# editable into a bypass either.
CORE_PROTECTED = (
    "hook_io.py",
    "shell_guard.py",
    "gen_hook_configs.py",
    "protected_path_guard.py",
    "hook_edit_approve.py",
)

# Last stdin snapshot, so guards can still extract paths when JSON parse fails.
_LAST_STDIN_TEXT = ""

# Last parsed stdin dict, used to auto-detect which harness invoked this hook
# so the same script/emit_* calls work for all of them.
_LAST_DATA = None

_CURSOR_KEYS = ("cursor_version", "conversation_id", "generation_id")

# Strict guards (shell/MCP) show this when stdin JSON cannot be parsed.
PARSE_FAIL_USER_MESSAGE = (
    "훅 stdin JSON 파싱 실패로 차단했습니다. "
    "Cursor(Windows)가 한글 등 비ASCII가 든 payload를 CP949로 깨뜨려 전달한 경우입니다. "
    "명령/입력에서 한글을 제거하거나 한글 내용은 파일로 옮긴 뒤 다시 실행하세요."
)

# Path keys only — never scan full blob for protected filenames (plan-body false positive).
_PATH_KEY_RE = re.compile(
    r'"(?:path|file_path|filePath)"\s*:\s*"((?:[^"\\]|\\.)*)"',
    re.IGNORECASE,
)

# Codex apply_patch file headers.
_PATCH_PATH_RE = re.compile(
    r"^\*\*\* (?:Update File|Add File|Delete File|Move to):[ \t]*(.+?)[ \t]*$",
    re.MULTILINE,
)


def _state_dir():
    return os.path.join(HOOKS_DIR, "state")


# Written by hook_edit_approve.py when the user sends "gohook"; removed on the
# next user prompt. protected_path_guard.py reads it to allow hook-script edits.
HOOK_EDIT_STATE = os.path.join(_state_dir(), "hook_edit_" + "approved.json")


def hook_registry(text=None):
    """[[hook]] entries of hooks.toml (or of the given TOML text). Raises on read/parse error."""
    if text is None:
        with open(HOOKS_TOML, "rb") as f:
            return tomllib.load(f).get("hook", [])
    return tomllib.loads(text).get("hook", [])


def required_hook_names(hooks=None):
    """Core guards plus every hooks.toml entry with required = true (core only if hooks.toml is unreadable)."""
    names = list(CORE_REQUIRED)
    try:
        hooks = hook_registry() if hooks is None else hooks
    except Exception as exc:
        log_error("required_hook_names fallback to core: %s" % exc)
        return tuple(names)
    for h in hooks:
        script = os.path.basename(str(h.get("script") or ""))
        if h.get("required") and script and script not in names:
            names.append(script)
    return tuple(names)


def protected_hook_basenames(hooks=None):
    """Core hook scripts plus hooks.toml entries with protected = true (and their 'protects' helpers)."""
    names = set(CORE_PROTECTED)
    try:
        hooks = hook_registry() if hooks is None else hooks
    except Exception as exc:
        log_error("protected_hook_basenames fallback to core: %s" % exc)
        return frozenset(names)
    for h in hooks:
        if not h.get("protected"):
            continue
        names.add(os.path.basename(str(h.get("script") or "")))
        names.update(os.path.basename(str(p)) for p in h.get("protects") or ())
    names.discard("")
    return frozenset(names)


def _same_dir(a, b):
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def is_global_install():
    """True when this file sits in ~/.agents/hooks (global hooks), not in a project."""
    return _same_dir(HOOKS_DIR, os.path.join(os.path.expanduser("~"), ".agents", "hooks"))


def guard_config():
    """[guard] of the harness settings: global only for global hooks, else global + project; {} when missing or broken."""
    try:
        # Loader next to this hooks dir (<.agents>/scripts: project copy or ~/.agents/scripts), then the global one.
        sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".agents", "scripts"))
        sys.path.insert(0, os.path.join(os.path.dirname(HOOKS_DIR), "scripts"))
        import harness_config

        root = None if is_global_install() else PROJECT_ROOT
        return harness_config.load(root).get("guard") or {}
    except Exception as exc:
        log_error("guard_config: %s" % exc)
        return {}


def hook_approval_word():
    """Word the user sends alone to open protected edits for one turn ([guard] hook_approval)."""
    return str(guard_config().get("hook_approval") or "gohook").strip() or "gohook"


def extract_prompt(data):
    """User prompt text from a prompt-submit payload (Cursor / Claude / Codex key names)."""
    for key in ("prompt", "content", "message", "text", "user_message"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val
    for key in ("input", "payload"):
        nested = data.get(key)
        if isinstance(nested, dict):
            found = extract_prompt(nested)
            if found:
                return found
    return ""


def log_error(message):
    """Append error to state/hook_errors.log; never write to stdout."""
    try:
        d = _state_dir()
        if not os.path.isdir(d):
            os.makedirs(d)
        path = os.path.join(d, "hook_errors.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (datetime.utcnow().isoformat() + "Z", message))
    except Exception:
        try:
            sys.stderr.write(str(message) + "\n")
            sys.stderr.flush()
        except Exception:
            pass


def _hex_prefix(raw, n=32):
    if not raw:
        return "(empty)"
    return " ".join("%02x" % b for b in bytearray(raw[:n]))


def _parse_error_offset(exc):
    """Best-effort character offset from json.JSONDecodeError / ValueError message."""
    pos = getattr(exc, "pos", None)
    if isinstance(pos, int) and pos >= 0:
        return pos
    msg = str(exc)
    m = re.search(r"\(char (\d+)\)", msg)
    if m:
        return int(m.group(1))
    m = re.search(r"column (\d+)", msg)
    if m:
        # column is 1-based on a single-line payload; treat as approx offset
        return max(0, int(m.group(1)) - 1)
    return None


def log_stdin_parse_fail(exc, text, raw):
    """
    Log parse failure with length, offset, and ~64-char surroundings only.
    Never dumps full stdin (commands / secrets).
    """
    offset = _parse_error_offset(exc)
    length = len(text or "")
    surround = ""
    if text and offset is not None:
        start = max(0, offset - 32)
        end = min(length, offset + 32)
        chunk = text[start:end]
        # single-line log: collapse whitespace/newlines in snippet
        chunk = chunk.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
        surround = " surround=%r" % (chunk,)
    log_error(
        "read_stdin_json parse_fail: %s len=%s offset=%s hex=%s%s"
        % (exc, length, offset, _hex_prefix(raw), surround)
    )


def read_stdin_bytes():
    """Read raw stdin bytes (binary preferred)."""
    try:
        return sys.stdin.buffer.read()
    except Exception:
        raw = sys.stdin.read()
        if isinstance(raw, str):
            return raw.encode("utf-8", "replace")
        return raw or b""


def normalize_stdin_bytes(raw):
    """
    Strip repeated UTF-8 BOMs; convert UTF-16 BOM payloads to UTF-8 bytes.
    Cursor on Windows may pipe one or more UTF-8 BOMs via PowerShell 5.1.
    """
    if not raw:
        return b""
    while raw.startswith(UTF8_BOM):
        raw = raw[len(UTF8_BOM) :]
    if raw.startswith(UTF16_LE_BOM):
        try:
            return raw.decode("utf-16-le").encode("utf-8")
        except Exception as exc:
            log_error("normalize_stdin_bytes utf-16-le: %s hex=%s" % (exc, _hex_prefix(raw)))
            raise
    if raw.startswith(UTF16_BE_BOM):
        try:
            return raw.decode("utf-16-be").encode("utf-8")
        except Exception as exc:
            log_error("normalize_stdin_bytes utf-16-be: %s hex=%s" % (exc, _hex_prefix(raw)))
            raise
    return raw


def decode_stdin_text(raw):
    """Decode normalized stdin bytes to text; log hex on total failure."""
    raw = normalize_stdin_bytes(raw or b"")
    if not raw:
        return ""
    for enc in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    log_error(
        "decode_stdin_text failed hex=%s len=%s" % (_hex_prefix(raw), len(raw))
    )
    raise UnicodeDecodeError("utf-8", raw, 0, 1, "hook stdin decode failed")


def emit(payload):
    """Write one JSON object to stdout and flush."""
    # ASCII-escaped JSON is safer across Windows console code pages.
    sys.stdout.write(json.dumps(payload, ensure_ascii=True))
    sys.stdout.flush()


def is_claude_code():
    """
    True if the current hook invocation uses the Claude Code output protocol
    (Claude Code itself, or Codex, which uses the same protocol) rather than
    Cursor's.

    Cursor payloads carry cursor_version / conversation_id / generation_id
    (and, since recent versions, hook_event_name too). Claude Code and Codex
    payloads carry session_id / hook_event_name but none of the Cursor-only
    keys. So Cursor-only keys win; hook_event_name alone is not enough.
    Misdetecting Cursor as Claude Code makes emit_allow() print nothing,
    which failClosed treats as a block ("returned no output").
    """
    d = _LAST_DATA
    if not isinstance(d, dict):
        # stdin JSON failed to parse: judge from the raw text so a Claude Code
        # deny still goes out as stderr + exit 2 (a Cursor-style JSON deny on
        # stdout with exit 0 would be treated as allow by Claude Code).
        text = _LAST_STDIN_TEXT or ""
        for key in _CURSOR_KEYS:
            if '"%s"' % key in text:
                return False
        return '"hook_event_name"' in text or '"session_id"' in text
    for key in _CURSOR_KEYS:
        if key in d:
            return False
    return ("hook_event_name" in d) or ("session_id" in d)


def is_codex():
    """
    True if the payload has the Codex shape: hook_event_name + session_id +
    model/cwd and no Cursor keys. Claude Code payloads can match too (they
    carry cwd); that is harmless because both use the same output protocol.
    Only a hint: apply_patch handling keys off the payload, not this.
    """
    d = _LAST_DATA
    if not isinstance(d, dict) or any(k in d for k in _CURSOR_KEYS):
        return False
    return "hook_event_name" in d and "session_id" in d and ("model" in d or "cwd" in d)


def emit_allow():
    if is_claude_code():
        # PreToolUse/UserPromptSubmit: no output, exit 0 = allow.
        return
    emit({"permission": "allow"})


def emit_prompt_ok():
    """UserPromptSubmit 'continue normally' response, harness-aware."""
    if is_claude_code():
        return
    emit({"continue": True})


def emit_context(text):
    """Non-blocking advisory context/warning, harness-aware (never denies)."""
    if not text:
        return
    if is_claude_code():
        sys.stderr.write(text + "\n")
        sys.stderr.flush()
        return
    emit({"additional_context": text, "agent_message": text})


def extract_path_candidates(text):
    """Pull path/file_path/filePath string values from possibly-broken JSON text."""
    if not text:
        return []
    out = []
    for m in _PATH_KEY_RE.finditer(text):
        raw = m.group(1)
        try:
            path = json.loads('"' + raw + '"')
        except Exception:
            path = raw.replace("\\\\", "\\").replace("\\/", "/")
        if isinstance(path, str) and path.strip():
            out.append(path.strip())
    return out


WRITE_LIKE_TOOLS = (
    "write", "delete", "strreplace", "editnotebook", "notebookedit", "applypatch", "apply_patch", "edit",
)


def tool_name(data):
    """Raw tool name from the payload (Cursor, Claude Code and Codex key variants)."""
    for key in ("tool_name", "toolName", "name", "tool"):
        val = data.get(key) if isinstance(data, dict) else None
        if isinstance(val, str) and val.strip():
            return val
    return ""


def is_write_like(data):
    tool = tool_name(data).lower()
    return any(t in tool for t in WRITE_LIKE_TOOLS)


def patch_text(tool_input):
    """
    apply_patch body from a tool_input value, or "".
    Codex apply_patch schema is unverified, so accept a raw string or a dict
    holding the patch under input / patch / command (string or argv list).
    """
    if isinstance(tool_input, str):
        return tool_input if _PATCH_PATH_RE.search(tool_input) else ""
    if isinstance(tool_input, dict):
        for key in ("input", "patch", "command"):
            val = tool_input.get(key)
            if isinstance(val, list):
                val = "\n".join(str(v) for v in val)
            if isinstance(val, str) and _PATCH_PATH_RE.search(val):
                return val
    return ""


def patch_paths(text):
    """Target paths named by apply_patch file headers (Update/Add/Delete File, Move to)."""
    return [m.group(1) for m in _PATCH_PATH_RE.finditer(text or "")]


def collect_paths(data):
    """Every target path in a file-tool payload (path keys, files[] lists, apply_patch headers)."""
    paths = []
    if not isinstance(data, dict):
        return paths
    tool_input = data.get("tool_input") or data.get("input") or {}
    patch = patch_text(tool_input)
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except Exception:
            tool_input = {} if patch else {"path": tool_input}
    patch = patch or patch_text(tool_input)
    if patch:
        paths.extend(patch_paths(patch))
    if not isinstance(tool_input, dict):
        tool_input = {}
    for key in ("path", "file_path", "filePath", "target_notebook", "notebook_path"):
        for src in (tool_input, data):
            val = src.get(key)
            if isinstance(val, str) and val.strip():
                paths.append(val.strip())
    files = data.get("files") or tool_input.get("files")
    if isinstance(files, list):
        for item in files:
            if isinstance(item, dict):
                item = item.get("path") or item.get("file_path")
            if isinstance(item, str) and item.strip():
                paths.append(item.strip())
    return paths


def emit_deny(user_message, agent_message=None):
    """
    Emit deny in the caller's protocol.

    Harness-aware: under Claude Code and Codex, PreToolUse/UserPromptSubmit
    hooks block via stderr + exit code 2 (not a Cursor-style permission JSON
    blob), so this raises SystemExit(2) immediately after printing the reason.
    """
    if is_claude_code():
        sys.stderr.write((agent_message or user_message or "denied") + "\n")
        sys.stderr.flush()
        sys.exit(2)
    payload = {
        "permission": "deny",
        "user_message": user_message,
    }
    if agent_message:
        payload["agent_message"] = agent_message
    emit(payload)


def read_stdin_json(strict=False):
    """
    Read UTF-8/BOM/UTF-16 stdin JSON.

    On json.loads failure, log offset + ~64 chars of context (no full dump).
    Known cause on Korean Windows: Cursor pipes the UTF-8 payload through
    PowerShell 5.1, which re-reads it as CP949; a trailing odd byte swallows
    the closing quote and the JSON structure breaks. Not recoverable here.

    strict=False: return {} on empty/failure (non-security hooks).
    strict=True: return None on empty/failure (caller should deny).
    """
    global _LAST_STDIN_TEXT, _LAST_DATA
    try:
        raw = read_stdin_bytes()
    except Exception as exc:
        log_error("read_stdin_json read: %s" % exc)
        _LAST_STDIN_TEXT = ""
        return None if strict else {}

    if not raw or not raw.strip():
        _LAST_STDIN_TEXT = ""
        if strict:
            log_error("read_stdin_json: empty stdin")
            return None
        return {}

    text = ""
    try:
        text = decode_stdin_text(raw)
        text = text.lstrip("\ufeff").strip()
        _LAST_STDIN_TEXT = text
        if not text:
            if strict:
                log_error("read_stdin_json: empty after decode hex=%s" % _hex_prefix(raw))
                return None
            return {}
        try:
            data = json.loads(text)
        except Exception as exc:
            log_stdin_parse_fail(exc, text, raw)
            raise
        if isinstance(data, dict):
            _LAST_DATA = data
            return data
        log_error("read_stdin_json: JSON root is not object type=%s" % type(data).__name__)
    except Exception as exc:
        _LAST_STDIN_TEXT = text or ""
        # parse errors already logged with offset/surround by log_stdin_parse_fail
        if not isinstance(exc, ValueError):
            log_error("read_stdin_json: %s hex=%s" % (exc, _hex_prefix(raw)))

    return None if strict else {}


def command_from(data):
    """Extract shell command string from hook payload shapes."""
    if not isinstance(data, dict):
        return ""
    for key in ("command", "cmd", "shell_command"):
        val = data.get(key)
        if isinstance(val, list):
            # Codex may pass argv lists (unverified); join so patterns still see every word.
            val = " ".join(str(v) for v in val)
        if isinstance(val, str) and val.strip():
            return val
    # Claude Code / Codex Bash PreToolUse payload nests it under tool_input.command.
    nested = data.get("tool_input") or data.get("input") or data.get("payload")
    if isinstance(nested, dict):
        return command_from(nested)
    return ""


def run_guard(fn, strict_stdin=True):
    """
    Run guard callable(data); the callable emits its own allow/deny.
    Always emits JSON on any failure to avoid failClosed no-output.

    strict_stdin=True (default for security guards): empty/unparseable
    stdin yields deny instead of soft-allow via {}.
    """
    try:
        data = read_stdin_json(strict=strict_stdin)
        if strict_stdin and data is None:
            emit_deny(
                PARSE_FAIL_USER_MESSAGE,
                "hook_io.run_guard: stdin empty or unparseable (strict). "
                "Likely CP949 corruption of non-ASCII payload by Cursor/PowerShell pipe.",
            )
            return 0
        if data is None:
            data = {}
        fn(data)
    except SystemExit:
        raise
    except Exception as exc:
        log_error("run_guard: %s\n%s" % (exc, traceback.format_exc()))
        emit_deny(
            "훅 가드 오류로 차단했습니다.",
            "hook_io.run_guard error: %s" % exc,
        )
    return 0
