# -*- coding: utf-8 -*-
"""Search Cursor and Claude Code chat transcripts (jsonl) by regex.

Replaces the per-campaign scanners (explanation pushback, CS English translation,
session audits) that each re-implemented the same jsonl parsing.

Usage:
  python .agents/scripts/transcript_grep.py REGEX [--role user|assistant] [--since YYYY-MM-DD]
         [--project SUBSTR] [--tool cursor|claude] [--include-subagents] [--context N]

Default roots: ~/.cursor/projects/*/agent-transcripts and ~/.claude/projects/*.
Output: one JSON object per hit {tool, file, ts, role, text} (text trimmed to --context chars
around the first match; default 300). Pipe to a file under .agents/tmp for follow-up analysis.
"""
from __future__ import print_function

import datetime
import glob
import json
import os
import re
import sys


def extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            item if isinstance(item, str) else str(item.get("text") or "")
            for item in content
            if isinstance(item, (str, dict)) and (isinstance(item, str) or item.get("type", "text") == "text")
        )
    if isinstance(content, dict):
        return str(content.get("text") or "")
    return ""


def unwrap_user_query(text):
    m = re.search(r"<user_query>\s*(.*?)\s*</user_query>", text, re.S)
    return m.group(1).strip() if m else re.sub(r"<timestamp>.*?</timestamp>", "", text, flags=re.S).strip()


def messages(path):
    """Yield (role, text, ts, is_sidechain) for user/assistant turns in one jsonl file."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
            role = obj.get("role") or msg.get("role") or ""
            role = {"human": "user", "ai": "assistant", "model": "assistant"}.get(role, role)
            if role not in ("user", "assistant"):
                continue
            text = extract_text(obj.get("content") if obj.get("content") is not None else msg.get("content"))
            if role == "user":
                text = unwrap_user_query(text)
            if text:
                yield role, text, obj.get("timestamp") or obj.get("createdAt") or "", bool(obj.get("isSidechain"))


def transcript_files(tool, project):
    home = os.path.expanduser("~")
    roots = []
    if tool in (None, "cursor"):
        roots += [("cursor", p) for p in glob.glob(os.path.join(home, ".cursor", "projects", "*", "agent-transcripts"))]
    if tool in (None, "claude"):
        roots += [("claude", p) for p in glob.glob(os.path.join(home, ".claude", "projects", "*"))]
    for name, root in roots:
        if project and project.lower() not in root.lower():
            continue
        for path in glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True):
            yield name, path


def main(argv):
    if not argv or argv[0].startswith("--"):
        print(__doc__)
        return 2
    rx = re.compile(argv[0], re.I)
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    role, project, tool = opt("--role"), opt("--project"), opt("--tool")
    since = opt("--since")
    since_ts = datetime.datetime.strptime(since, "%Y-%m-%d").timestamp() if since else 0
    ctx = int(opt("--context", 300))
    subagents = "--include-subagents" in argv
    hits = 0
    for name, path in transcript_files(tool, project):
        if os.path.getmtime(path) < since_ts:
            continue
        if not subagents and ("subagents" in path.replace("\\", "/").split("/") or os.path.basename(path).startswith("agent-")):
            continue
        for r, text, ts, side in messages(path):
            if (role and r != role) or (side and not subagents):
                continue
            m = rx.search(text)
            if not m:
                continue
            lo = max(0, m.start() - ctx // 2)
            print(json.dumps({"tool": name, "file": path, "ts": ts, "role": r, "text": text[lo:lo + ctx]}, ensure_ascii=False))
            hits += 1
    sys.stderr.write("hits=%d\n" % hits)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
