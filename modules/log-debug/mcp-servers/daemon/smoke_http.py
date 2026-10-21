# -*- coding: utf-8 -*-
"""Smoke-test Streamable HTTP MCP: two clients share one server process.

Does not touch secrets. Calls tools/list only. httpx comes with the mcp package.

  python smoke_http.py http://127.0.0.1:<port>/mcp
"""
from __future__ import print_function

import json
import sys
import uuid

import httpx


def _session(url):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "daemon-smoke", "version": "0.1"},
        },
    }
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, headers=headers, json=init)
        sid = r.headers.get("mcp-session-id")
        if r.status_code >= 400:
            raise SystemExit("initialize failed %s: %s" % (r.status_code, r.text[:500]))
        nheaders = dict(headers)
        if sid:
            nheaders["mcp-session-id"] = sid
        client.post(url, headers=nheaders, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        r2 = client.post(url, headers=nheaders, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        return {
            "client_id": str(uuid.uuid4())[:8],
            "http_status": r2.status_code,
            "session_id": sid,
            "tools_body_head": r2.text[:400],
        }


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__.strip())
    url = sys.argv[1]
    a = _session(url)
    b = _session(url)
    out = {
        "url": url,
        "client_a": a,
        "client_b": b,
        "shared_ok": a["http_status"] < 400 and b["http_status"] < 400,
        "distinct_sessions": a.get("session_id") != b.get("session_id"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["shared_ok"] else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
