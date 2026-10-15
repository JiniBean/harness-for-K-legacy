# -*- coding: utf-8 -*-
"""OZ ozr/odi guard: file_write deny Write-like edits; after_file_edit header warn; CLI check.

Usage:
  --pretooluse          file_write hook (deny Write/StrReplace/apply_patch on .ozr/.odi)
  (no args)             after_file_edit hook (warn when the header is broken)
  file.ozr [file2...]   CLI integrity check (exit 1 on any issue)
"""
from __future__ import print_function

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hook_io
from hook_io import (
    collect_paths,
    emit_allow,
    emit_context,
    emit_deny,
    extract_path_candidates,
    is_write_like,
    read_stdin_json,
)

MSG_BROKEN = (
    "OZ file integrity failed. Header missing or XML not after the 24-byte OZR prefix. "
    "git checkout -- <file> then byte-patch (rb insert wb). Do not Write/StrReplace .ozr/.odi."
)


def _is_oz_path(path):
    lower = path.replace("\\", "/").lower()
    return lower.endswith(".ozr") or lower.endswith(".odi")


def check_file(path):
    """Return issue string or None if OK / skip."""
    if not _is_oz_path(path):
        return None
    if not os.path.isfile(path):
        return "missing file: %s" % path
    with open(path, "rb") as f:
        raw = f.read(4096)
    if not raw:
        return "empty: %s" % path
    lower = path.replace("\\", "/").lower()
    if lower.endswith(".ozr"):
        if raw.startswith(b"\xef\xbb\xbf") or raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
            return "BOM at start (header stripped?): %s" % path
        if raw[:3] != b"OZR":
            return "OZR magic missing: %s" % path
        xml_at = raw.find(b"<?xml")
        if xml_at < 0:
            return "<?xml not found: %s" % path
        if xml_at == 0:
            return "XML at offset 0 (24-byte header missing): %s" % path
        if xml_at != 24:
            return "<?xml at offset %s (expected 24): %s" % (xml_at, path)
    else:
        xml_at = raw.find(b"<?xml")
        if xml_at < 0:
            return "<?xml not found: %s" % path
    return None


def _run_pretooluse():
    data = read_stdin_json(strict=False) or {}
    if not data:
        # Parse failure (Cursor CP949-corrupted payload): tool name is unknown,
        # but this hook is only registered on write-like matchers. Pull path
        # values out of the raw text so .ozr/.odi writes stay blocked.
        oz_paths = [p for p in extract_path_candidates(hook_io._LAST_STDIN_TEXT or "") if _is_oz_path(p)]
        if oz_paths:
            emit_deny(
                "rb/wb 바이트 패치만. Write/StrReplace로 .ozr/.odi 저장 금지.",
                "oz_file_guard: blocked Write-like on %s (stdin parse failed)" % ", ".join(oz_paths),
            )
            return 0
        emit_allow()
        return 0
    if not is_write_like(data):
        emit_allow()
        return 0
    oz_paths = [p for p in collect_paths(data) if _is_oz_path(p)]
    if oz_paths:
        emit_deny(
            "rb/wb 바이트 패치만. Write/StrReplace로 .ozr/.odi 저장 금지.",
            "oz_file_guard: blocked Write-like on %s" % ", ".join(oz_paths),
        )
        return 0
    emit_allow()
    return 0


def _run_after_or_default():
    data = read_stdin_json(strict=False) or {}
    issues = []
    for path in collect_paths(data):
        issue = check_file(path)
        if issue:
            issues.append(issue)
    if issues:
        emit_context(MSG_BROKEN + " " + "; ".join(issues))
    return 0


def main():
    argv = [a for a in sys.argv[1:] if a]
    if "--pretooluse" in argv:
        return _run_pretooluse()

    # CLI: python oz_file_guard.py file.ozr [file2...]
    file_args = [a for a in argv if not a.startswith("-")]
    if file_args:
        failed = 0
        for path in file_args:
            issue = check_file(path)
            if issue:
                sys.stderr.write(issue + "\n")
                failed = 1
            else:
                sys.stdout.write("OK %s\n" % path)
        raise SystemExit(failed)

    return _run_after_or_default()


if __name__ == "__main__":
    try:
        raise SystemExit(main() or 0)
    except SystemExit:
        raise
    except Exception as exc:
        if "--pretooluse" in sys.argv:
            emit_allow()
        else:
            emit_context("oz_file_guard error: %s" % exc)
        raise SystemExit(0)
