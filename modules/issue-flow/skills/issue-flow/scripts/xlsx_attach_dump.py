# -*- coding: utf-8 -*-
"""Dump everything an xlsx ticket attachment says: cells, text boxes, comments, images.

Request sheets often put the request body (menu name, report name) in a
drawing text box next to a screenshot, with empty cells, so reading cells only
misses it. Stdlib only (zipfile + ElementTree), no openpyxl.

Usage:
  python .agents/skills/issue-flow/scripts/xlsx_attach_dump.py FILE.xlsx [--media-out DIR] [--max-cells N]

Output sections: [sheet NAME] cells (coordinate=value, non-empty), merged ranges,
[textboxes] per drawing shape, [comments], [media] (extracted when --media-out is given).
"""
from __future__ import print_function

import os
import posixpath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
}
R_ID = "{%s}id" % NS["r"]


def _xml(z, name):
    return ET.fromstring(z.read(name)) if name in z.namelist() else None


def _rels(z, part):
    """Relationship Id -> absolute zip path for a part (e.g. xl/workbook.xml)."""
    folder, base = posixpath.split(part)
    root = _xml(z, posixpath.join(folder, "_rels", base + ".rels"))
    out = {}
    if root is not None:
        for r in root.findall("rel:Relationship", NS):
            out[r.get("Id")] = posixpath.normpath(posixpath.join(folder, r.get("Target")))
    return out


def shared_strings(z):
    root = _xml(z, "xl/sharedStrings.xml")
    if root is None:
        return []
    return ["".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])) for si in root.findall("m:si", NS)]


def sheets(z):
    """[(name, sheet part path)] in workbook order."""
    wb = _xml(z, "xl/workbook.xml")
    rels = _rels(z, "xl/workbook.xml")
    return [(s.get("name"), rels.get(s.get(R_ID))) for s in wb.find("m:sheets", NS)]


def cell_values(z, part, strings):
    root = _xml(z, part)
    for c in root.iter("{%s}c" % NS["m"]):
        t = c.get("t")
        if t == "inlineStr":
            v = "".join(x.text or "" for x in c.iter("{%s}t" % NS["m"]))
        else:
            node = c.find("m:v", NS)
            v = node.text if node is not None else None
            if v is not None and t == "s":
                v = strings[int(v)]
        if v not in (None, ""):
            yield c.get("r"), v
    merged = root.find("m:mergeCells", NS)
    if merged is not None:
        yield "merged", " ".join(m.get("ref") for m in merged)


def textboxes(z):
    for name in sorted(n for n in z.namelist() if re.match(r"xl/drawings/drawing\d+\.xml$", n)):
        root = _xml(z, name)
        for sp in root.iter("{%s}sp" % NS["xdr"]):
            paras = []
            for p in sp.iter("{%s}p" % NS["a"]):
                line = "".join(t.text or "" for t in p.iter("{%s}t" % NS["a"]))
                if line.strip():
                    paras.append(line)
            if paras:
                yield name, "\n".join(paras)


def comments(z):
    for name in sorted(n for n in z.namelist() if re.match(r"xl/comments\d*\.xml$", n)):
        root = _xml(z, name)
        for c in root.iter("{%s}comment" % NS["m"]):
            yield name, c.get("ref"), "".join(t.text or "" for t in c.iter("{%s}t" % NS["m"]))


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    path, media_out, max_cells = argv[0], None, 400
    if "--media-out" in argv:
        media_out = argv[argv.index("--media-out") + 1]
    if "--max-cells" in argv:
        max_cells = int(argv[argv.index("--max-cells") + 1])
    with zipfile.ZipFile(path) as z:
        strings = shared_strings(z)
        for name, part in sheets(z):
            print("[sheet %s]" % name)
            for i, (ref, v) in enumerate(cell_values(z, part, strings)):
                if i >= max_cells:
                    print("  ... (more cells, raise --max-cells)")
                    break
                print("  %s=%s" % (ref, str(v).replace("\n", " / ")))
        print("[textboxes]")
        for name, text in textboxes(z):
            print("  (%s)\n    %s" % (name, text.replace("\n", "\n    ")))
        print("[comments]")
        for name, ref, text in comments(z):
            print("  %s %s: %s" % (name, ref, text.replace("\n", " / ")))
        print("[media]")
        for name in (n for n in z.namelist() if n.startswith("xl/media/")):
            info = z.getinfo(name)
            if media_out:
                os.makedirs(media_out, exist_ok=True)
                dest = os.path.join(media_out, posixpath.basename(name))
                with open(dest, "wb") as f:
                    f.write(z.read(name))
                print("  %s %d bytes -> %s" % (name, info.file_size, dest))
            else:
                print("  %s %d bytes" % (name, info.file_size))
    return 0


def _selftest():
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", '<workbook xmlns="%s" xmlns:r="%s"><sheets><sheet name="S1" r:id="rId1"/></sheets></workbook>' % (NS["m"], NS["r"]))
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="%s"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>' % NS["rel"])
        z.writestr("xl/sharedStrings.xml", '<sst xmlns="%s"><si><t>메뉴</t></si></sst>' % NS["m"])
        z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="%s"><sheetData><row><c r="A1" t="s"><v>0</v></c><c r="B1"><v>3</v></c></row></sheetData></worksheet>' % NS["m"])
        z.writestr("xl/drawings/drawing1.xml", '<xdr:wsDr xmlns:xdr="%s" xmlns:a="%s"><xdr:sp><xdr:txBody><a:p><a:r><a:t>[G-SABIS] 메뉴명 : 지결확정(2.0)</a:t></a:r></a:p></xdr:txBody></xdr:sp></xdr:wsDr>' % (NS["xdr"], NS["a"]))
    with zipfile.ZipFile(buf) as z:
        assert list(cell_values(z, sheets(z)[0][1], shared_strings(z))) == [("A1", "메뉴"), ("B1", "3")]
        assert list(textboxes(z)) == [("xl/drawings/drawing1.xml", "[G-SABIS] 메뉴명 : 지결확정(2.0)")]
    print("selftest OK")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:] == ["selftest"]:
        _selftest()
        sys.exit(0)
    sys.exit(main(sys.argv[1:]))
