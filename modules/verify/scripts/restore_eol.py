# -*- coding: utf-8 -*-
"""Restore a file's per-line EOL pattern (CRLF/LF) from a git revision, keeping current content.

Nexacro .xfdl files often mix CRLF and LF. Editors and some tools normalize every
line ending, which turns a few-line change into a whole-file diff (and /verify's
EOL check fails). This re-applies the old line ending to every unchanged line and
the neighbouring line's ending to inserted lines. Content bytes are never changed.

Usage:
  python .agents/scripts/restore_eol.py FILE [--rev HEAD] [--check]
    --check   report CRLF/LF counts before and after, write nothing
"""
from __future__ import print_function

import difflib
import os
import re
import subprocess
import sys


def split_lines(data):
    """[(text_bytes, eol_bytes)]; last item may have eol b''."""
    out = []
    for m in re.finditer(br"([^\r\n]*)(\r\n|\n|\r|$)", data):
        if m.group(0) == b"" and m.start() == len(data):
            break
        out.append((m.group(1), m.group(2)))
    return out


def count_eol(data):
    crlf = data.count(b"\r\n")
    return crlf, data.count(b"\n") - crlf


def restore(head, cur):
    old, new = split_lines(head), split_lines(cur)
    crlf, lf = count_eol(head)
    default = b"\r\n" if crlf >= lf else b"\n"
    sm = difflib.SequenceMatcher(None, [t for t, _ in old], [t for t, _ in new], autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out += [(new[j][0], old[i1 + k][1]) for k, j in enumerate(range(j1, j2))]
        elif op in ("replace", "insert"):
            near = old[i1][1] if i1 < len(old) and old[i1][1] else (old[i1 - 1][1] if i1 else default)
            out += [(new[j][0], near or default) for j in range(j1, j2)]
    if out and not new[-1][1]:
        out[-1] = (out[-1][0], b"")  # keep "no trailing newline" as in the current file
    return b"".join(t + e for t, e in out)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    path = argv[0]
    rev = argv[argv.index("--rev") + 1] if "--rev" in argv else "HEAD"
    top = subprocess.run(["git", "-C", os.path.dirname(os.path.abspath(path)), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True, check=True).stdout.strip()
    rel = os.path.relpath(os.path.abspath(path), top).replace("\\", "/")
    head = subprocess.run(["git", "-C", top, "show", "%s:%s" % (rev, rel)], capture_output=True, check=True).stdout
    with open(path, "rb") as f:
        cur = f.read()
    out = restore(head, cur)
    strip = lambda b: re.sub(br"\r\n|\r|\n", b"\n", b)
    assert strip(out) == strip(cur), "content changed; refusing to write"
    print("%s: %s CRLF/LF %s -> %s -> %s (current -> restored)" % (
        path, rev, count_eol(head), count_eol(cur), count_eol(out)))
    if "--check" not in argv and out != cur:
        with open(path, "wb") as f:
            f.write(out)
        print("written")
    return 0


def _selftest():
    head = b"a\r\nb\nc\r\nx\ny\r\n"
    cur = b"a\nB\nc\nx\ny\nd\n"  # every EOL normalized to LF, b->B changed, d inserted
    out = restore(head, cur)
    assert out == b"a\r\nB\nc\r\nx\ny\r\nd\r\n", out
    print("selftest OK")


if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        _selftest()
        sys.exit(0)
    sys.exit(main(sys.argv[1:]))
