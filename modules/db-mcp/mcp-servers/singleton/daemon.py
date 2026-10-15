# -*- coding: utf-8 -*-
"""Start/stop/status for shared localhost MCP HTTP backends listed in ports.json.

One process per server for every Claude/Cursor session (mcp.json "url" entries) instead of
one stdio process per session. Servers read GSABIS_MCP_HOST/PORT/TRANSPORT.

  python daemon.py start|status|stop|restart [--only <name>]

ports.json (set-up-harness writes it from ports.example.json):
  bind     127.0.0.1 only
  python   absolute path of the Python that has the server requirements (venv)
  servers  name -> {port, script (relative to this folder), wait_sec?, disabled?}
Results also go to state/last_cmd.json (pythonw has no console).
"""
from __future__ import print_function

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORTS_FILE = ROOT / "ports.json"
STATE_DIR = ROOT / "state"


def _load_ports():
    return json.loads(PORTS_FILE.read_text(encoding="utf-8"))


def _pid_path(name):
    return STATE_DIR / ("%s.pid" % name)


def _log_path(name):
    return STATE_DIR / ("%s.log" % name)


def _script(info):
    return (ROOT / info["script"]).resolve()


def _read_pid(name):
    path = _pid_path(name)
    if not path.is_file():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _is_running(pid):
    if pid is None:
        return False
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _pid_listening_on(bind, port):
    """Return OS pid that listens on exactly bind:port, or None (Windows netstat)."""
    if sys.platform != "win32":
        return None
    try:
        out = subprocess.check_output(["netstat", "-ano", "-p", "tcp"], text=True, errors="replace")
    except (OSError, subprocess.CalledProcessError):
        return None
    needle = "%s:%s" % (bind, port)
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        local, state = parts[1], parts[3].upper()
        if local == needle and state == "LISTENING":
            try:
                return int(parts[-1])
            except ValueError:
                return None
    return None


def _emit_json(obj):
    """Print for interactive use; always write state/last_cmd.json (pythonw has no stdout)."""
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "last_cmd.json").write_text(text + "\n", encoding="utf-8")
    try:
        if sys.stdout is not None:
            print(text)
    except Exception:
        pass


def _alive(name, bind, port):
    # Alive = listening. A live process whose accept loop died (e.g. WinError 64) is stale, not alive.
    listen_pid = _pid_listening_on(bind, port)
    if listen_pid and _is_running(listen_pid):
        _pid_path(name).write_text(str(listen_pid), encoding="utf-8")
        return listen_pid
    return None


def _stale_pid(name, info):
    """PID from the pid file that still runs this server's script but does not listen.

    Command line must match: pid files survive reboot and the PID may now belong to another process.
    """
    pid = _read_pid(name)
    if not _is_running(pid) or sys.platform != "win32":
        return None
    try:
        cmd = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine" % pid],
            text=True, errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return pid if str(_script(info)).lower() in cmd.lower() else None


def _kill(pid):
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, capture_output=True)
    else:
        os.kill(pid, signal.SIGTERM)


def _url(bind, port):
    return "http://%s:%s/mcp" % (bind, port)


def cmd_status(names, cfg):
    bind = cfg["bind"]
    rows = []
    for name in names:
        info = cfg["servers"][name]
        pid = _alive(name, bind, info["port"])
        rows.append(
            {
                "name": name,
                "port": info["port"],
                "url": _url(bind, info["port"]),
                "pid": pid,
                "running": pid is not None,
                "disabled": bool(info.get("disabled")),
                "stale_pid": None if pid else _stale_pid(name, info),  # alive but not listening -> start replaces it
            }
        )
    _emit_json(rows)
    return 0


def _creationflags():
    if sys.platform != "win32":
        return 0
    # CREATE_NO_WINDOW: no extra conhost. NEW_PROCESS_GROUP: survives parent exit.
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def _spawn(name, python, script, bind, port):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    log_f = open(_log_path(name), "ab", buffering=0)
    env = os.environ.copy()
    env.update({
        "GSABIS_MCP_HOST": bind,
        "GSABIS_MCP_PORT": str(port),
        "GSABIS_MCP_TRANSPORT": "streamable-http",
        "PYTHONUNBUFFERED": "1",
    })
    proc = subprocess.Popen(
        [python, str(script)],
        cwd=str(script.parent),
        env=env,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=_creationflags(),
        close_fds=True,
    )
    _pid_path(name).write_text(str(proc.pid), encoding="utf-8")
    return proc.pid


def _wait_port(bind, port, timeout):
    import socket

    deadline = time.time() + timeout
    while time.time() < deadline:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            if sock.connect_ex((bind, port)) == 0:
                return True
        finally:
            sock.close()
        time.sleep(0.2)
    return False


def cmd_start(names, cfg):
    bind = cfg["bind"]
    python = cfg.get("python") or ""
    if not Path(python).is_file():
        raise SystemExit("ports.json python not found: %r" % python)
    started = []
    for name in names:
        info = cfg["servers"][name]
        existing = _alive(name, bind, info["port"])
        if existing:
            started.append({"name": name, "pid": existing, "action": "already-running"})
            continue
        if info.get("disabled"):  # "disabled": true -> never auto/manual start
            started.append({"name": name, "action": "skipped", "reason": "disabled"})
            continue
        script = _script(info)
        if not script.is_file():
            started.append({"name": name, "action": "skipped", "reason": "script missing: %s" % script})
            continue
        stale = _stale_pid(name, info)
        if stale:
            _kill(stale)
        pid = _spawn(name, python, script, bind, info["port"])
        ok = _wait_port(bind, info["port"], float(info.get("wait_sec") or 15))
        listen_pid = _pid_listening_on(bind, info["port"]) if ok else None
        if listen_pid:
            _pid_path(name).write_text(str(listen_pid), encoding="utf-8")
            pid = listen_pid
        started.append(
            {
                "name": name,
                "pid": pid,
                "action": "started" if ok else "started-port-not-ready",
                "url": _url(bind, info["port"]),
                "log": str(_log_path(name)),
            }
        )
    _emit_json(started)
    return 0


def cmd_stop(names, cfg):
    stopped = []
    for name in names:
        pid = _read_pid(name)
        if not _is_running(pid):
            if _pid_path(name).is_file():
                _pid_path(name).unlink()
            stopped.append({"name": name, "action": "not-running"})
            continue
        try:
            _kill(pid)
        except OSError as exc:
            stopped.append({"name": name, "pid": pid, "action": "error", "error": str(exc)})
            continue
        if _pid_path(name).is_file():
            _pid_path(name).unlink()
        stopped.append({"name": name, "pid": pid, "action": "stopped"})
    _emit_json(stopped)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="MCP singleton daemon")
    parser.add_argument("action", choices=["status", "start", "stop", "restart"])
    parser.add_argument("--only", action="append", dest="only", help="Limit to server name(s)")
    args = parser.parse_args(argv)
    cfg = _load_ports()
    all_names = list(cfg["servers"].keys())
    names = args.only or all_names
    for n in names:
        if n not in cfg["servers"]:
            raise SystemExit("unknown server: %s (known: %s)" % (n, ", ".join(all_names)))

    if args.action == "status":
        return cmd_status(names, cfg)
    if args.action == "start":
        return cmd_start(names, cfg)
    if args.action == "stop":
        return cmd_stop(names, cfg)
    cmd_stop(names, cfg)
    time.sleep(0.5)
    return cmd_start(names, cfg)


if __name__ == "__main__":
    sys.exit(main() or 0)
