# -*- coding: utf-8 -*-
"""Read-only FTP MCP server for remote WAS logs (log-debug module).

Tools: ftp_servers, ftp_list, ftp_get, ftp_download, ftp_slice. No put/rename/delete.
Settings: project .agents/harness.toml [ftp] (port_default) and [[ftp.servers]];
MCP server name: [guard.ftp] server_name (same name the ftp_mcp_guard hook matches).
Accounts: secret "ftp" (<secrets_dir>/<project>/ftp.env), FTP_USER[_<ALIAS>] / FTP_PASSWORD[_<ALIAS>].
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
from ftplib import FTP, error_perm
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path.home() / ".agents" / "scripts"))
import harness_config  # noqa: E402


def _find_project_root(start: Path) -> Path:
    """Parent of the nearest enclosing .agents folder; cwd when not installed under one."""
    for parent in start.parents:
        if parent.name == ".agents":
            return parent.parent
    return Path.cwd()


PROJECT_ROOT = _find_project_root(Path(__file__).resolve())
# One-off files live under <project>/.agents/tmp so garbage-collector retention covers them
DOWNLOAD_ROOT = PROJECT_ROOT / ".agents" / "tmp" / "ftp"
DEFAULT_MAX_BYTES = 2 * 1024 * 1024
DEFAULT_DOWNLOAD_MAX = 512 * 1024 * 1024
HARD_DOWNLOAD_MAX = 2 * 1024 * 1024 * 1024
DEFAULT_PORT = 21

_CFG = harness_config.load(PROJECT_ROOT)
SERVER_NAME = str(((_CFG.get("guard") or {}).get("ftp") or {}).get("server_name") or "ftp")

# Singleton daemon (mcp-servers/singleton) sets GSABIS_MCP_HOST/PORT/TRANSPORT; unset = stdio.
mcp = FastMCP(
    SERVER_NAME,
    host=os.environ.get("GSABIS_MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("GSABIS_MCP_PORT", "8000")),
)


def _load_config() -> Dict[str, Any]:
    """[ftp] of the project harness.toml: port_default, servers[] (alias, host, region, log_* hints)."""
    return harness_config.load(PROJECT_ROOT).get("ftp") or {}


def _server_map() -> Dict[str, Dict[str, Any]]:
    out = {}
    for row in _load_config().get("servers") or []:
        alias = str(row.get("alias") or "").strip().lower()
        if alias:
            out[alias] = row
    return out


def _resolve(server: str) -> Dict[str, Any]:
    alias = (server or "").strip().lower()
    servers = _server_map()
    row = servers.get(alias)
    if not row:
        raise ValueError("Unknown server alias %r. Known: %s" % (server, ", ".join(sorted(servers)) or "(none)"))
    cfg = _load_config()
    creds = harness_config.secret("ftp", project_root=PROJECT_ROOT)
    key = alias.upper()
    return {
        "alias": alias,
        "host": row["host"],
        "port": int(row.get("port") or cfg.get("port_default") or DEFAULT_PORT),
        "user": creds.get("FTP_USER_" + key) or creds.get("FTP_USER") or "",
        "password": creds.get("FTP_PASSWORD_" + key) or creds.get("FTP_PASSWORD") or "",
        "region": row.get("region"),
        "log_cwd_current": row.get("log_cwd_current"),
        "log_cwd_backup": row.get("log_cwd_backup"),
        "log_name_hint": row.get("log_name_hint"),
    }


def _connect(info: Dict[str, Any]) -> FTP:
    ftp = FTP()
    ftp.connect(info["host"], info["port"], timeout=30)
    ftp.login(info["user"], info["password"])
    ftp.set_pasv(True)
    return ftp


def _close(ftp: FTP) -> None:
    try:
        ftp.quit()
    except Exception:
        ftp.close()


def _list_dir(ftp: FTP, path: str) -> List[str]:
    lines: List[str] = []
    # Prefer LIST; fall back to NLST
    try:
        ftp.cwd(path)
        try:
            ftp.retrlines("LIST", lines.append)
        except error_perm:
            return sorted(ftp.nlst())
    except error_perm as exc:
        raise ValueError("FTP list failed for %s: %s" % (path, exc))
    return lines


def _require_abs(path: str, label: str) -> None:
    if not path or not str(path).startswith("/"):
        raise ValueError("%s must be an absolute remote path starting with /" % label)


@mcp.tool()
def ftp_servers() -> str:
    """List registered FTP log server aliases with region and path hints (read-only config)."""
    cfg = _load_config()
    keys = ("alias", "host", "region", "log_cwd_current", "log_cwd_backup", "log_name_hint")
    rows = [{k: row.get(k) for k in keys} for row in cfg.get("servers") or []]
    return json.dumps(
        {
            "port_default": cfg.get("port_default") or DEFAULT_PORT,
            "servers": rows,
            "policy": "read-only: ftp_servers/ftp_list/ftp_get/ftp_download/ftp_slice; no put/rename/delete",
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def ftp_list(server: str, path: str) -> str:
    """List files on an FTP log host (READ). server=alias from ftp_servers, path=absolute remote dir."""
    info = _resolve(server)
    _require_abs(path, "path")
    ftp = _connect(info)
    try:
        lines = _list_dir(ftp, path)
    finally:
        _close(ftp)
    return json.dumps(
        {"server": info["alias"], "host": info["host"], "path": path, "entries": lines, "count": len(lines)},
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def ftp_get(
    server: str,
    remote_path: str,
    max_bytes: int = DEFAULT_MAX_BYTES,
    tail_lines: Optional[int] = None,
) -> str:
    """Read a remote file (READ/RETR) as a preview. Caps size with max_bytes (default 2MB). Optional tail_lines for text."""
    info = _resolve(server)
    _require_abs(remote_path, "remote_path")
    if max_bytes is None or int(max_bytes) <= 0:
        max_bytes = DEFAULT_MAX_BYTES
    max_bytes = int(max_bytes)
    if max_bytes > 8 * 1024 * 1024:
        raise ValueError("max_bytes cap is 8MB for agent safety")

    ftp = _connect(info)
    buf = io.BytesIO()
    truncated = False
    try:
        ftp.cwd(os.path.dirname(remote_path) or "/")
        name = os.path.basename(remote_path)

        def _writer(chunk):
            if buf.tell() + len(chunk) > max_bytes:
                remain = max_bytes - buf.tell()
                if remain > 0:
                    buf.write(chunk[:remain])
                raise StopIteration("max_bytes")
            buf.write(chunk)

        try:
            ftp.retrbinary("RETR " + name, _writer, blocksize=8192)
        except StopIteration:
            truncated = True
        except error_perm as exc:
            raise ValueError("FTP get failed for %s: %s" % (remote_path, exc))
    finally:
        _close(ftp)

    raw = buf.getvalue()
    text = None
    for enc in ("utf-8", "cp949", "euc-kr", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    if text is None:
        return json.dumps(
            {
                "server": info["alias"],
                "remote_path": remote_path,
                "bytes": len(raw),
                "truncated": truncated,
                "binary": True,
                "note": "Could not decode as text; binary payload omitted",
            },
            ensure_ascii=False,
            indent=2,
        )

    if tail_lines is not None and int(tail_lines) > 0:
        lines = text.splitlines()
        n = int(tail_lines)
        text = "\n".join(lines[-n:])
        if len(lines) > n:
            truncated = True

    return json.dumps(
        {
            "server": info["alias"],
            "remote_path": remote_path,
            "bytes_read": len(raw),
            "truncated": truncated,
            "content": text,
        },
        ensure_ascii=False,
        indent=2,
    )


def _safe_basename(remote_path: str) -> str:
    name = os.path.basename(str(remote_path).replace("\\", "/"))
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise ValueError("invalid remote filename")
    return name


def _download_cap(max_bytes: Optional[int]) -> int:
    if max_bytes is None or int(max_bytes) <= 0:
        return DEFAULT_DOWNLOAD_MAX
    cap = int(max_bytes)
    if cap > HARD_DOWNLOAD_MAX:
        raise ValueError("max_bytes cap is 2GB for ftp_download")
    return cap


@mcp.tool()
def ftp_download(
    server: str,
    remote_path: str,
    max_bytes: int = DEFAULT_DOWNLOAD_MAX,
) -> str:
    """RETR a remote log/zip to .agents/tmp/ftp/<alias>/. Returns local path and size only (no file content)."""
    info = _resolve(server)
    _require_abs(remote_path, "remote_path")
    name = _safe_basename(remote_path)
    cap = _download_cap(max_bytes)

    dest_dir = DOWNLOAD_ROOT / info["alias"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    local_path = dest_dir / name
    tmp_path = dest_dir / (name + ".part")

    ftp = _connect(info)
    written = 0
    remote_size = None
    try:
        ftp.cwd(os.path.dirname(remote_path) or "/")
        try:
            remote_size = ftp.size(name)
        except Exception:
            remote_size = None
        if remote_size is not None and int(remote_size) > cap:
            raise ValueError(
                "remote file is %s bytes, over max_bytes=%s; raise max_bytes or narrow the time range"
                % (remote_size, cap)
            )

        exceeded = []
        with tmp_path.open("wb") as out:
            holder = [0]

            def _writer(chunk):
                if holder[0] + len(chunk) > cap:
                    remain = cap - holder[0]
                    if remain > 0:
                        out.write(chunk[:remain])
                        holder[0] += remain
                    exceeded.append(True)
                    raise StopIteration("max_bytes")
                out.write(chunk)
                holder[0] += len(chunk)

            try:
                ftp.retrbinary("RETR " + name, _writer, blocksize=65536)
            except StopIteration:
                pass
            except error_perm as exc:
                raise ValueError("FTP download failed for %s: %s" % (remote_path, exc))
            written = holder[0]

        if exceeded:
            raise ValueError(
                "download stopped at max_bytes=%s (incomplete file discarded). remote_size=%s"
                % (cap, remote_size)
            )
        tmp_path.replace(local_path)
    finally:
        _close(ftp)
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return json.dumps(
        {
            "server": info["alias"],
            "host": info["host"],
            "remote_path": remote_path,
            "local_path": str(local_path),
            "bytes": written,
            "remote_size": remote_size,
            "content_inlined": False,
        },
        ensure_ascii=False,
        indent=2,
    )


SLICE_TS_ARG = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d(:\d\d)?$")
LOG_TS = re.compile(rb"(?m)^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")
PROBE_BYTES = 256 * 1024
SLICE_TOLERANCE = 1024 * 1024


def _retr_range(info: Dict[str, Any], parent: str, name: str, offset: int, length: int, sink) -> int:
    """RETR length bytes from offset (REST). Drops the connection afterwards so the 226/426 reply
    of the aborted RETR cannot get out of step with the next command."""
    ftp = _connect(info)
    got = 0
    try:
        ftp.cwd(parent or "/")
        ftp.voidcmd("TYPE I")
        conn = ftp.transfercmd("RETR " + name, rest=offset)
        try:
            while got < length:
                chunk = conn.recv(min(65536, length - got))
                if not chunk:
                    break
                sink(chunk)
                got += len(chunk)
        finally:
            conn.close()
    finally:
        ftp.close()
    return got


def _probe_ts(info: Dict[str, Any], parent: str, name: str, offset: int) -> Optional[str]:
    """First log timestamp after the first complete line past offset. None when none within PROBE_BYTES."""
    buf = bytearray()
    _retr_range(info, parent, name, offset, PROBE_BYTES, buf.extend)
    if offset > 0:
        nl = buf.find(b"\n")
        buf = buf[nl + 1:] if nl >= 0 else bytearray()
    m = LOG_TS.search(bytes(buf))
    return m.group(1).decode("ascii") if m else None


def _find_offset(info: Dict[str, Any], parent: str, name: str, size: int, ts: str, side: str) -> int:
    """Binary search for the ts boundary. start returns an offset at or before it, end at or after it
    (both widen the range). Probes without a timestamp (long multi-line dumps) also move the widening way."""
    lo, hi = 0, size
    while hi - lo > SLICE_TOLERANCE:
        mid = (lo + hi) // 2
        found = _probe_ts(info, parent, name, mid)
        earlier = (side == "end") if found is None else found < ts
        if earlier:
            lo = mid
        else:
            hi = mid
    return lo if side == "start" else hi


@mcp.tool()
def ftp_slice(
    server: str,
    remote_path: str,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
    max_bytes: int = DEFAULT_DOWNLOAD_MAX,
) -> str:
    """Download only a time range of a large text log (REST + binary search on log timestamps) to .agents/tmp/ftp/.
    from_ts/to_ts: 'YYYY-MM-DD HH:mm[:ss]' as printed in the log, range is from_ts <= t < to_ts; at least one required.
    Not for .zip/.gz (use ftp_download). Returns local path, size and offsets only (no file content)."""
    info = _resolve(server)
    _require_abs(remote_path, "remote_path")
    name = _safe_basename(remote_path)
    if name.lower().endswith((".zip", ".gz")):
        raise ValueError("compressed files cannot be sliced; use ftp_download")
    if not from_ts and not to_ts:
        raise ValueError("from_ts or to_ts required")
    for ts in (from_ts, to_ts):
        if ts and not SLICE_TS_ARG.match(ts):
            raise ValueError("timestamp must be 'YYYY-MM-DD HH:mm[:ss]': %r" % ts)
    cap = _download_cap(max_bytes)
    parent = os.path.dirname(remote_path)

    ftp = _connect(info)
    try:
        ftp.cwd(parent or "/")
        ftp.voidcmd("TYPE I")
        size = int(ftp.size(name))
    except error_perm as exc:
        raise ValueError("FTP size failed for %s: %s" % (remote_path, exc))
    finally:
        _close(ftp)

    # Fix the range to the size at search start (a live file keeps growing)
    start = _find_offset(info, parent, name, size, from_ts, "start") if from_ts else 0
    end = _find_offset(info, parent, name, size, to_ts, "end") if to_ts else size
    if end <= start:
        raise ValueError("no data in range (offset_start=%s offset_end=%s)" % (start, end))
    if end - start > cap:
        raise ValueError("range is %s bytes, over max_bytes=%s; narrow the time range" % (end - start, cap))

    def _hhmm(ts, default):
        return ts[11:16].replace(":", "") if ts else default

    dest_dir = DOWNLOAD_ROOT / info["alias"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    local_path = dest_dir / ("%s.%s-%s.log" % (name, _hhmm(from_ts, "0000"), _hhmm(to_ts, "2400")))
    tmp_path = dest_dir / (local_path.name + ".part")
    try:
        with tmp_path.open("wb") as out:
            written = _retr_range(info, parent, name, start, end - start, out.write)
        tmp_path.replace(local_path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return json.dumps(
        {
            "server": info["alias"],
            "host": info["host"],
            "remote_path": remote_path,
            "local_path": str(local_path),
            "bytes": written,
            "remote_size": size,
            "offset_start": start,
            "offset_end": end,
            "content_inlined": False,
        },
        ensure_ascii=False,
        indent=2,
    )


if __name__ == "__main__":
    # stdio (default) | streamable-http | sse
    _transport = (os.environ.get("GSABIS_MCP_TRANSPORT") or "stdio").strip().lower()
    if _transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport="streamable-http" if _transport == "http" else _transport)
