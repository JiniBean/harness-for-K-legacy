# -*- coding: utf-8 -*-
"""Kill stdio MCP python processes that are NOT singleton port listeners.

Keeps PIDs listening on exactly ports.json bind:port (and their venv parent). Kills other
python.exe whose command line runs one of the ports.json server scripts (left over from
stdio-mode sessions). Windows only.

Usage:
  python cleanup_stdio_dupes.py --dry-run
  python cleanup_stdio_dupes.py
"""
from __future__ import print_function

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORTS = json.loads((ROOT / "ports.json").read_text(encoding="utf-8"))
SCRIPTS = [str((ROOT / s["script"]).resolve()).lower() for s in PORTS["servers"].values()]


def _listener_pids():
    # Exact bind:port only (same rule as daemon._pid_listening_on); a foreign 0.0.0.0 listener is not ours.
    needles = {"%s:%s" % (PORTS["bind"], v["port"]) for v in PORTS["servers"].values()}
    keep = set()
    try:
        out = subprocess.check_output(["netstat", "-ano", "-p", "tcp"], text=True, errors="replace")
    except (OSError, subprocess.CalledProcessError):
        return keep
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        local, state, pid_s = parts[1], parts[3].upper(), parts[-1]
        if state == "LISTENING" and pid_s.isdigit() and local in needles:
            keep.add(int(pid_s))
    return keep


def _mcp_pythons():
    """Return list of {pid, ppid} for python.exe running a ports.json server script."""
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                "Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress",
            ],
            text=True,
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit("process list failed: %s" % exc)
    if not out.strip():
        return []
    data = json.loads(out)
    if isinstance(data, dict):
        data = [data]
    rows = []
    for row in data:
        cmd = (row.get("CommandLine") or "").lower().replace("/", "\\")
        if any(s in cmd for s in SCRIPTS):
            rows.append({"pid": int(row["ProcessId"]), "ppid": int(row.get("ParentProcessId") or 0)})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    keep = _listener_pids()
    procs = _mcp_pythons()
    by_pid = {p["pid"]: p for p in procs}
    for pid in list(keep):  # also keep parents of listeners (venv wrapper)
        parent = by_pid.get(pid, {}).get("ppid")
        if parent:
            keep.add(parent)

    victims = [p for p in procs if p["pid"] not in keep]
    report = {"keep_pids": sorted(keep), "victim_count": len(victims), "victims": victims,
              "dry_run": bool(args.dry_run)}
    if not args.dry_run:
        report["killed"] = [
            {"pid": v["pid"], "rc": subprocess.run(["taskkill", "/PID", str(v["pid"]), "/T", "/F"],
                                                   capture_output=True).returncode}
            for v in victims
        ]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
