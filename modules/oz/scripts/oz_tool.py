# -*- coding: utf-8 -*-
"""OZ report (.ozr/.odi) byte-safe helper: library + CLI.

Replaces per-task patch scripts that each re-implemented header split, tag
lookup and self-checks. Never parses and
re-serializes XML for writing: patches are byte splices, so the 24-byte OZR
header, mixed CRLF/LF and attribute order stay exactly as Designer saved them.

CLI
  python .agents/scripts/oz_tool.py check FILE...        # post-patch self-check (oz module rules.md)
  python .agents/scripts/oz_tool.py dump FILE [--name N] [--grep REGEX]
  python .agents/scripts/oz_tool.py selftest

Library (task patch scripts import this instead of copying helpers)
  sys.path.insert(0, r"<project root>\\.agents\\scripts"); import oz_tool as oz
  header, body = oz.read(path)
  body = oz.set_attr(body, b"FixedTableLabel12", b"COLNAME", b"P_HEADER1")
  body = oz.set_attr(body, name, b"SCRIPTCODE", oz.escape_script(script_text))
  body = oz.delete_element(body, name)
  oz.write(path, header, body)          # then: oz_tool.py check path
To compare with an older revision: git show REV:path > .agents/tmp/old.ozr, then dump both.
"""
from __future__ import print_function

import re
import sys
from collections import Counter
from html import unescape
from xml.parsers import expat

OZR_MAGIC = b"OZR"
OZR_HEADER_LEN = 24


# ---------------------------------------------------------------- read / write

def read(path):
    """Return (header, body). .ozr must be OZR magic + XML at byte 24; .odi has no header."""
    with open(path, "rb") as f:
        raw = f.read()
    if path.lower().endswith(".ozr"):
        if raw[:3] != OZR_MAGIC or raw.find(b"<?xml") != OZR_HEADER_LEN:
            raise SystemExit("bad OZR header in %s (magic=%r, xml@%d)" % (path, raw[:3], raw.find(b"<?xml")))
        return raw[:OZR_HEADER_LEN], raw[OZR_HEADER_LEN:]
    return b"", raw


def write(path, header, body):
    """Write bytes and report the size change. Header bytes are written unchanged."""
    with open(path, "rb") as f:
        old = f.read()
    if path.lower().endswith(".ozr") and old[:OZR_HEADER_LEN] != header:
        raise SystemExit("refusing to write %s: header differs from file on disk" % path)
    new = header + body
    with open(path, "wb") as f:
        f.write(new)
    print("wrote %s: %d -> %d bytes (%+d)" % (path, len(old), len(new), len(new) - len(old)))


# ---------------------------------------------------------------- tag lookup

def _tag_end(body, start):
    """Index just past the '>' closing the tag that starts at body[start] == '<' (quote-aware)."""
    in_quote = False
    i = start + 1
    while i < len(body):
        c = body[i:i + 1]
        if c == b'"':
            in_quote = not in_quote
        elif c == b">" and not in_quote:
            return i + 1
        i += 1
    raise ValueError("unterminated tag at %d" % start)


def find_tag(body, name, tags=None):
    """(start, end, self_closing, tag) of the first open tag whose NAME attribute equals name."""
    needle = b'NAME="' + name + b'"'
    for m in re.finditer(br"<([A-Z][A-Z0-9_]*)[\s>/]", body):
        tag = m.group(1)
        if tags and tag not in tags:
            continue
        start = m.start()
        end = _tag_end(body, start)
        text = body[start:end]
        if re.search(br"(?:^|\s)" + re.escape(needle), text[len(tag) + 1:]):
            return start, end, text.endswith(b"/>"), tag
    return None


def get_attr(body, name, attr, tags=None):
    hit = find_tag(body, name, tags)
    if not hit:
        return None
    m = re.search(br"\s" + re.escape(attr) + br'="([^"]*)"', body[hit[0]:hit[1]])
    return m.group(1) if m else None


def set_attr(body, name, attr, value, tags=None):
    """Replace attr's value, or insert it before '>' / '/>' (keeps self-closing tags valid)."""
    hit = find_tag(body, name, tags)
    if not hit:
        raise KeyError("NAME=%r not found" % name)
    start, end, self_closing, _ = hit
    tag_text = body[start:end]
    pat = re.compile(br"(\s" + re.escape(attr) + br'=")[^"]*(")')
    if pat.search(tag_text):
        new_tag = pat.sub(lambda m: m.group(1) + value + m.group(2), tag_text, count=1)
    else:
        cut = len(tag_text) - (2 if self_closing else 1)
        new_tag = tag_text[:cut].rstrip() + b" " + attr + b'="' + value + b'"' + tag_text[cut:]
    return body[:start] + new_tag + body[end:]


def delete_element(body, name, tags=None):
    """Remove the element (self-closing, or open tag through its matching close tag)."""
    hit = find_tag(body, name, tags)
    if not hit:
        raise KeyError("NAME=%r not found" % name)
    start, end, self_closing, tag = hit
    if self_closing:
        return body[:start] + body[end:]
    depth, pos = 1, end
    tok = re.compile(br"<(/?)" + re.escape(tag) + br"[\s>/]")
    while depth:
        m = tok.search(body, pos)
        if not m:
            raise ValueError("no closing </%s> for %r" % (tag.decode(), name))
        close_end = _tag_end(body, m.start())
        if m.group(1):
            depth -= 1
        elif not body[m.start():close_end].endswith(b"/>"):
            depth += 1
        pos = close_end
    return body[:start] + body[pos:]


# ---------------------------------------------------------------- SCRIPTCODE text

def unescape_script(value):
    """SCRIPTCODE attribute bytes -> readable text."""
    text = value.decode("utf-8") if isinstance(value, bytes) else value
    return unescape(text.replace("~OZ#CRLF", "\n").replace("~OZ#TAB", "\t"))


def escape_script(text):
    """Readable text -> SCRIPTCODE attribute bytes (Designer encoding)."""
    text = text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("\r\n", "~OZ#CRLF").replace("\n", "~OZ#CRLF").replace("\t", "~OZ#TAB")
    return text.encode("utf-8")


# ---------------------------------------------------------------- check

def check(path):
    """Return a list of problems (empty = PASS). Covers the post-patch self-check list."""
    problems = []
    with open(path, "rb") as f:
        raw = f.read()
    is_ozr = path.lower().endswith(".ozr")
    if is_ozr:
        if raw[:3] != OZR_MAGIC:
            problems.append("header: magic %r (expected OZR)" % raw[:3])
        if raw.find(b"<?xml") != OZR_HEADER_LEN:
            problems.append("header: <?xml at %d (expected %d)" % (raw.find(b"<?xml"), OZR_HEADER_LEN))
        if b"\r\r\n" in raw:
            problems.append("eol: %d x \\r\\r\\n (double CR)" % raw.count(b"\r\r\n"))
    else:
        bare_lf = len(re.findall(br"(?<!\r)\n", raw))
        if bare_lf:
            problems.append("eol: %d bare LF in .odi (expected CRLF only)" % bare_lf)
    body = raw[raw.find(b"<?xml"):] if b"<?xml" in raw else raw

    stack, orphans, names, seq = [], [], Counter(), [0]
    parser = expat.ParserCreate()

    def start(tag, attrs):
        # A pasted component left twice sits under the same parent with the same tag
        # and identical attributes. Copies on other pages/parents are normal.
        seq[0] += 1
        parent_id = stack[-1][1] if stack else 0
        if is_ozr and tag.startswith("OZ") and attrs.get("NAME"):
            names[(parent_id, tag, tuple(sorted(attrs.items())))] += 1
        if tag == "OZTABLELABEL" and "TABLEINDEX" in attrs and (not stack or stack[-1][0] != "OZTABLESTATIC"):
            orphans.append("%s (parent %s)" % (attrs.get("NAME"), stack[-1][0] if stack else "-"))
        stack.append((tag, seq[0]))

    parser.StartElementHandler = start
    parser.EndElementHandler = lambda tag: stack.pop()
    try:
        parser.Parse(body, True)
    except expat.ExpatError as exc:
        problems.append("xml: %s" % exc)
    if orphans:
        problems.append("OZTABLELABEL with TABLEINDEX outside OZTABLESTATIC: %s" % ", ".join(orphans[:20]))
    dups = [dict(k[2])["NAME"] for k, c in names.items() if c > 1]
    if dups:
        problems.append("identical duplicate component: %s" % ", ".join(dups[:20]))
    return problems


# ---------------------------------------------------------------- dump

def dump(path, name=None, grep=None):
    _, body = read(path)
    stack = []
    parser = expat.ParserCreate()
    rx = re.compile(grep) if grep else None
    keys = ("COLNAME", "DATASETNAME", "FONTNAME", "TABLEINDEX", "X", "Y", "WIDTH", "HEIGHT")

    def start(tag, attrs):
        band = next((n for t, n in reversed(stack) if t.endswith("BAND") and n), "-")
        stack.append((tag, attrs.get("NAME")))
        if "NAME" not in attrs or (name and attrs["NAME"] != name):
            return
        script = unescape_script(attrs.get("SCRIPTCODE", ""))
        line = "%s %s band=%s %s" % (tag, attrs["NAME"], band,
                                    " ".join("%s=%s" % (k, attrs[k]) for k in keys if k in attrs))
        if rx and not (rx.search(line) or rx.search(script)):
            return
        print(line)
        if script:
            print("    " + script.replace("\n", "\n    "))

    parser.StartElementHandler = start
    parser.EndElementHandler = lambda tag: stack.pop()
    parser.Parse(body, True)


# ---------------------------------------------------------------- selftest

def _selftest():
    body = (b'<?xml version="1.0" encoding="UTF-8"?><R><OZBAND NAME="B1"><OZTABLESTATIC NAME="S1">'
            b'<OZTABLELABEL NAME="L1" TABLEINDEX="0" COLNAME="A"/>'
            b'<OZTABLELABEL NAME="L2" TABLEINDEX="1"><X/></OZTABLELABEL></OZTABLESTATIC></OZBAND></R>')
    # Regression: inserting into a self-closing tag must keep it well-formed.
    out = set_attr(body, b"L1", b"DATASETNAME", b"OZPARAMS")
    assert b'<OZTABLELABEL NAME="L1" TABLEINDEX="0" COLNAME="A" DATASETNAME="OZPARAMS"/>' in out, out
    out = set_attr(out, b"L1", b"COLNAME", b"B")
    assert get_attr(out, b"L1", b"COLNAME") == b"B"
    expat.ParserCreate().Parse(out, True)
    out2 = delete_element(out, b"L2")
    assert b"L2" not in out2 and b"</OZTABLESTATIC>" in out2
    expat.ParserCreate().Parse(out2, True)
    text = 'if (a < b) {\n\tsetattr("fontname", x);\n}'
    assert unescape_script(escape_script(text)) == text
    assert find_tag(body, b"NOPE") is None
    print("selftest OK")


def main(argv):
    if not argv or argv[0] not in ("check", "dump", "selftest"):
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd == "selftest":
        _selftest()
        return 0
    if cmd == "check":
        failed = 0
        for path in args:
            problems = check(path)
            print("%s %s" % ("FAIL" if problems else "PASS", path))
            for p in problems:
                print("  - " + p)
            failed |= bool(problems)
        return 1 if failed else 0
    opts = {"--name": None, "--grep": None}
    files = []
    it = iter(args)
    for a in it:
        if a in opts:
            opts[a] = next(it)
        else:
            files.append(a)
    for path in files:
        dump(path, name=opts["--name"], grep=opts["--grep"])
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
