# -*- coding: utf-8 -*-
"""Generate per-tool hook registrations from the neutral list hooks.toml.

--scope project (default; run from <root>/.agents/hooks, root = parent of .agents/):
  reads  <root>/.agents/hooks/hooks.toml
  writes .cursor/hooks.json (whole file), .claude/settings.json "hooks" key
         (other keys preserved), .codex/hooks.json (whole file)
--scope global:
  reads  ~/.agents/hooks/hooks.toml
  merges into ~/.cursor/hooks.json and the "hooks" key of ~/.claude/settings.json:
         only entries whose command points into ~/.agents/hooks/ are replaced,
         every other entry and key is kept. No Codex output.

Refuses to write when a required guard is missing (hooks.toml required = true; in
project scope also the core shell_guard.py / protected_path_guard.py), because this
script bypasses the Write-tool path guard.

Usage: python gen_hook_configs.py [--scope project|global] [--check] [--tools claude,cursor,codex]
  --scope  project (default) or global
  --check  diff only, write nothing
  --tools  outputs to generate (default: all; codex is ignored in global scope)
"""
from __future__ import print_function

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from hook_io import required_hook_names  # noqa: E402

ALL_TOOLS = ("claude", "cursor", "codex")

CURSOR_EVENT = {
    "session_start": ("sessionStart", None),
    "prompt_submit": ("beforeSubmitPrompt", None),
    "shell": ("beforeShellExecution", None),
    "file_write": ("preToolUse", "Write|Delete|StrReplace|EditNotebook|ApplyPatch"),
    "file_write_full": ("preToolUse", "Write|ApplyPatch"),
    "after_file_edit": ("afterFileEdit", None),
    "mcp": ("beforeMCPExecution", None),
    "file_read": ("beforeReadFile", None),
    "shell_input": ("preToolUse", "Shell"),
}
CLAUDE_EVENT = {
    "session_start": ("SessionStart", None),
    "prompt_submit": ("UserPromptSubmit", None),
    "shell": ("PreToolUse", "Bash|PowerShell"),
    "file_write": ("PreToolUse", "Write|Edit|NotebookEdit"),
    "file_write_full": ("PreToolUse", "Write"),
    "after_file_edit": ("PostToolUse", "Write|Edit|NotebookEdit"),
    "mcp": ("PreToolUse", None),  # claude_matcher required
    "file_read": ("PreToolUse", "Read|Grep|Glob|NotebookRead"),
    "shell_input": ("PreToolUse", "Bash|PowerShell"),
}
# None = no Codex event (file_read: Codex has no read hook).
CODEX_EVENT = {
    "session_start": ("SessionStart", None),
    "prompt_submit": ("UserPromptSubmit", None),
    "shell": ("PreToolUse", "^Bash$"),
    "file_write": ("PreToolUse", "^apply_patch$"),
    "file_write_full": ("PreToolUse", "^apply_patch$"),
    "after_file_edit": ("PostToolUse", "apply_patch|Edit|Write"),
    "mcp": ("PreToolUse", None),  # claude_matcher reused
    "file_read": None,
    "shell_input": None,  # Codex shell input rewrite: unverified, not registered
}


class Target(object):
    """Where hooks.toml is read from and where registrations go, per scope."""

    def __init__(self, scope):
        self.scope = scope
        if scope == "global":
            self.base = str(Path.home())  # honors USERPROFILE / HOME
            self.config_root = None  # harness_config.load(None): global settings only
        else:
            self.base = os.path.dirname(os.path.dirname(HERE))  # parent of .agents/
            self.config_root = self.base
        self.hooks_dir = os.path.join(self.base, ".agents", "hooks")
        self.hooks_toml = os.path.join(self.hooks_dir, "hooks.toml")
        self.cursor_out = os.path.join(self.base, ".cursor", "hooks.json")
        self.claude_out = os.path.join(self.base, ".claude", "settings.json")
        self.codex_out = os.path.join(self.base, ".codex", "hooks.json")


def _python(target):
    """[tools] python of the harness settings: hook command interpreter."""
    # Project copy of the loader (sibling scripts/) first, then the global one.
    sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".agents", "scripts"))
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
    import harness_config

    py = (harness_config.load(target.config_root).get("tools") or {}).get("python")
    if not py:
        raise SystemExit("harness.toml [tools] python is not set; refusing to generate hook registrations")
    return str(py).replace("\\", "/")


def load(path):
    with open(path, "rb") as f:
        hooks = tomllib.load(f).get("hook", [])
    for h in hooks:
        for ev in h["events"]:
            if ev not in CURSOR_EVENT:
                raise SystemExit("unknown event %r in %s" % (ev, h["script"]))
            if ev == "mcp" and (_for_tool(h, "claude") or _for_tool(h, "codex")) and not h.get("claude_matcher"):
                raise SystemExit("mcp hook %s needs claude_matcher" % h["script"])
    return hooks


def _for_tool(h, tool):
    """only = "cursor" | "claude" | "codex" (or a list of them) limits a hook to those tools."""
    only = h.get("only")
    if not only:
        return True
    return tool in (only if isinstance(only, list) else [only])


def _quote(arg):
    return '"%s"' % arg if " " in arg else arg


def cursor_config(hooks, py, hooks_dir):
    out = {}
    for h in hooks:
        if not _for_tool(h, "cursor"):
            continue
        path = os.path.join(hooks_dir, h["script"]).replace("/", "\\")
        cmd = " ".join([py.replace("/", "\\"), path] + h.get("args", []))
        for ev in h["events"]:
            name, default_matcher = CURSOR_EVENT[ev]
            entry = {"command": cmd}
            matcher = h.get("cursor_matcher") if ev == "file_write" else None
            matcher = matcher or default_matcher
            if matcher:
                entry["matcher"] = matcher
            entry["timeout"] = 10
            if ev not in ("session_start", "prompt_submit", "after_file_edit"):
                entry["failClosed"] = bool(h.get("fail_closed", False))
            elif ev == "session_start":
                entry["failClosed"] = False
            out.setdefault(name, []).append(entry)
    return {"version": 1, "hooks": out}


def _grouped(hooks, tool, events, script_cmd):
    """Claude Code / Codex shape: {Event: [{"matcher": m, "hooks": [{"type": "command", ...}]}]}."""
    out = {}
    for h in hooks:
        if not _for_tool(h, tool):
            continue
        cmd = " ".join([script_cmd(h["script"])] + h.get("args", []))
        for ev in h["events"]:
            mapped = events[ev]
            if mapped is None:
                continue
            name, matcher = mapped
            # claude_matcher: required for mcp (reused by Codex); for Claude it overrides any event's matcher.
            if ev == "mcp" or (tool == "claude" and h.get("claude_matcher")):
                matcher = h["claude_matcher"]
            groups = out.setdefault(name, [])
            group = next((g for g in groups if g.get("matcher") == matcher), None)
            if group is None:
                group = {"matcher": matcher, "hooks": []} if matcher else {"hooks": []}
                groups.append(group)
            group["hooks"].append({"type": "command", "command": cmd, "timeout": 10})
    return out


def claude_hooks(hooks, py, target):
    if target.scope == "global":
        # Absolute path: $CLAUDE_PROJECT_DIR would point at whatever project is open.
        hooks_dir = target.hooks_dir.replace("\\", "/")
        return _grouped(hooks, "claude", CLAUDE_EVENT,
                        lambda s: _quote(py) + " " + _quote(hooks_dir + "/" + s))
    return _grouped(hooks, "claude", CLAUDE_EVENT,
                    lambda s: py + " $CLAUDE_PROJECT_DIR/.agents/hooks/" + s)


def codex_config(hooks, py, target):
    # Codex has no project-dir variable in hook commands: use absolute paths.
    hooks_dir = target.hooks_dir.replace("\\", "/")
    return {"hooks": _grouped(hooks, "codex", CODEX_EVENT,
                              lambda s: _quote(py) + " " + _quote(hooks_dir + "/" + s))}


# ---- global merge: replace only harness-owned entries ----

def _owned_markers(target):
    """Command substrings that mark an entry as ours (lowercase, forward slashes)."""
    return (target.hooks_dir.replace("\\", "/").lower() + "/", "~/.agents/hooks/")


def _is_owned(cmd, markers):
    c = str(cmd or "").replace("\\", "/").lower()
    return any(m in c for m in markers)


def merge_cursor(old, new, markers):
    out = dict(old) if isinstance(old, dict) else {}
    out.setdefault("version", 1)
    events = {}
    for name, entries in (out.get("hooks") or {}).items():
        kept = [e for e in entries or [] if not (isinstance(e, dict) and _is_owned(e.get("command"), markers))]
        if kept:
            events[name] = kept
    for name, entries in new["hooks"].items():
        events.setdefault(name, []).extend(entries)
    out["hooks"] = events
    return out


def merge_claude(old_hooks, new_hooks, markers):
    events = {}
    for name, groups in (old_hooks or {}).items():
        kept_groups = []
        for g in groups or []:
            if not isinstance(g, dict):
                kept_groups.append(g)
                continue
            inner = [x for x in g.get("hooks") or []
                     if not (isinstance(x, dict) and _is_owned(x.get("command"), markers))]
            if inner:
                kept_groups.append(dict(g, hooks=inner))
        if kept_groups:
            events[name] = kept_groups
    for name, groups in new_hooks.items():
        events.setdefault(name, []).extend(groups)
    return events


def check_required(text, label, required):
    missing = [n for n in required if n not in text]
    if missing:
        raise SystemExit("refusing to write %s: missing required hooks %s" % (label, missing))


def read_json(path):
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj, check_only):
    text = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    old = open(path, encoding="utf-8").read() if os.path.isfile(path) else ""
    if old == text:
        print("unchanged", path)
        return
    print(("would change " if check_only else "write ") + path)
    if not check_only:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)


def _tools(val):
    if val is None:
        return ALL_TOOLS
    tools = tuple(t.strip().lower() for t in val.split(",") if t.strip())
    bad = [t for t in tools if t not in ALL_TOOLS]
    if bad or not tools:
        raise SystemExit("--tools takes a comma list of %s (got %r)" % (",".join(ALL_TOOLS), val))
    return tools


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gen_hook_configs.py",
                                 description="Generate hook registrations from hooks.toml.")
    ap.add_argument("--scope", choices=("project", "global"), default="project")
    ap.add_argument("--check", action="store_true", help="diff only, write nothing")
    ap.add_argument("--tools", help="comma list of " + ",".join(ALL_TOOLS) + " (default: all)")
    a = ap.parse_args(argv)
    target = Target(a.scope)
    tools = _tools(a.tools)
    if not os.path.isfile(target.hooks_toml):
        raise SystemExit("hooks.toml not found: %s" % target.hooks_toml)
    hooks = load(target.hooks_toml)
    py = _python(target)
    if a.scope == "global":
        # Core project guards are not installed globally; only hooks.toml required = true counts.
        required = [os.path.basename(str(h.get("script") or "")) for h in hooks if h.get("required")]
    else:
        required = required_hook_names(hooks)
    markers = _owned_markers(target)
    outputs = []
    if "cursor" in tools:
        cursor = cursor_config(hooks, py, target.hooks_dir)
        if a.scope == "global":
            cursor = merge_cursor(read_json(target.cursor_out), cursor, markers)
        check_required(json.dumps(cursor), target.cursor_out, required)
        outputs.append((target.cursor_out, cursor))
    if "claude" in tools:
        settings = read_json(target.claude_out)
        new = claude_hooks(hooks, py, target)
        settings["hooks"] = merge_claude(settings.get("hooks"), new, markers) if a.scope == "global" else new
        check_required(json.dumps(settings), target.claude_out, required)
        outputs.append((target.claude_out, settings))
    if "codex" in tools:
        if a.scope == "global":
            print("skip codex: global scope writes no ~/.codex/hooks.json")
        else:
            codex = codex_config(hooks, py, target)
            check_required(json.dumps(codex), target.codex_out, required)
            outputs.append((target.codex_out, codex))
    # Check every output before writing any, so a refusal leaves all files untouched.
    for path, obj in outputs:
        write_json(path, obj, a.check)
    return 0


if __name__ == "__main__":
    sys.exit(main())
