# -*- coding: utf-8 -*-
"""Smoke test for the read-only FTP log MCP server (direct calls, no MCP client).

Run inside an installed project with the MCP server's Python:
  python .agents/mcp-servers/ftp/smoke_test.py
Servers come from harness.toml [[ftp.servers]]. Remote checks are skipped when none are
configured, or per server when log_cwd_current is empty. Hook policy has its own tests
(.agents/hooks/tests/test_ftp_mcp_guard.py).
"""
from __future__ import annotations

import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from server import ftp_download, ftp_get, ftp_list, ftp_servers, ftp_slice  # noqa: E402

TS = re.compile(r"(?m)^(\d{4}-\d\d-\d\d \d\d:\d\d)")


def _entry_name(line):
    """File name from a LIST line (last field) or an NLST name; '' for directories."""
    parts = line.split()
    if not parts or line.startswith("d"):
        return ""
    return parts[-1]


def _check_server(row, results):
    alias = row["alias"]
    cwd = row.get("log_cwd_current")
    if not cwd:
        results.append(("SKIP", "%s list" % alias, "log_cwd_current not set"))
        return
    try:
        listing = json.loads(ftp_list(alias, cwd))
    except Exception as exc:
        results.append(("FAIL", "%s list %s" % (alias, cwd), str(exc)))
        return
    results.append(("PASS", "%s list %s" % (alias, cwd), "count=%s" % listing["count"]))

    names = [n for n in (_entry_name(e) for e in listing["entries"]) if n and not n.lower().endswith((".zip", ".gz"))]
    if not names:
        results.append(("SKIP", "%s get/download/slice" % alias, "no plain file in %s" % cwd))
        return
    target = cwd.rstrip("/") + "/" + names[0]

    try:
        got = json.loads(ftp_get(alias, target, max_bytes=4096, tail_lines=5))
        results.append(("PASS" if "content" in got or got.get("binary") else "FAIL",
                        "%s get tail %s" % (alias, target), "bytes_read=%s" % got.get("bytes_read", got.get("bytes"))))
    except Exception as exc:
        results.append(("FAIL", "%s get tail %s" % (alias, target), str(exc)))
        return

    # Cap check: max_bytes=1 must refuse (size check) or discard the partial file
    try:
        ftp_download(alias, target, max_bytes=1)
        results.append(("SKIP", "%s download cap" % alias, "file is 1 byte or smaller"))
    except ValueError as exc:
        results.append(("PASS" if "max_bytes" in str(exc) else "FAIL", "%s download cap" % alias, str(exc)))
    except Exception as exc:
        results.append(("FAIL", "%s download cap" % alias, str(exc)))

    try:
        head = json.loads(ftp_get(alias, target, max_bytes=4096)).get("content") or ""
        m = TS.search(head)
        first = m.group(1) if m else None
    except Exception as exc:
        results.append(("FAIL", "%s slice probe" % alias, str(exc)))
        return
    if not first:
        results.append(("SKIP", "%s slice 1h" % alias, "no 'YYYY-MM-DD HH:mm' timestamp at file start"))
        return
    until = (datetime.datetime.strptime(first, "%Y-%m-%d %H:%M") + datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
    try:
        sl = json.loads(ftp_slice(alias, target, first, until))
        body = Path(sl["local_path"]).read_bytes()
        stamps = re.findall(rb"(?m)^(\d{4}-\d\d-\d\d \d\d:\d\d)", body)
        ok = sl["bytes"] > 0 and bool(stamps) and stamps[0].decode() <= until
        results.append(("PASS" if ok else "FAIL", "%s slice 1h" % alias,
                        {k: sl[k] for k in ("bytes", "offset_start", "offset_end", "local_path")}))
    except Exception as exc:
        results.append(("FAIL", "%s slice 1h" % alias, str(exc)))


def main():
    results = []
    cfg = json.loads(ftp_servers())
    rows = [r for r in cfg["servers"] if r.get("alias")]
    results.append(("PASS", "ftp_servers", [r["alias"] for r in rows]))
    if not rows:
        results.append(("SKIP", "remote checks", "no [[ftp.servers]] in .agents/harness.toml"))
    for row in rows:
        _check_server(row, results)

    failed = 0
    for status, name, detail in results:
        failed += status == "FAIL"
        print("[%s] %s :: %s" % (status, name, detail))
    print("SUMMARY failed=%s / %s" % (failed, len(results)))
    return 1 if failed else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
