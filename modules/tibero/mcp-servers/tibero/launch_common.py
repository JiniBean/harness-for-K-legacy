# -*- coding: utf-8 -*-
"""Shared launcher for Tibero MCP servers (one process per env profile).

Each env gets a two-line launch_<env>.py next to this file (see README). The env name comes
from that file name, so the MCP command line carries "launch_<env>" for the tibero hooks.
Settings: project .agents/harness.toml [tibero] (jdbc_jar, profiles.<env>) and [java]
(tool_jdk_home, tool_jdk_fallbacks). Accounts: secret "tibero" (<secrets_dir>/<project>/tibero.env).
The MCP server (modified fork, see README) lives under ./tibero-mcp-server/src.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

TIBERO_DIR = Path(__file__).resolve().parent
SERVER_SRC = TIBERO_DIR / "tibero-mcp-server" / "src"

sys.path.insert(0, str(Path.home() / ".agents" / "scripts"))
import harness_config  # noqa: E402


def _find_project_root(start: Path) -> Path:
    """Parent of the nearest enclosing .agents folder; cwd when not installed under one."""
    for parent in start.parents:
        if parent.name == ".agents":
            return parent.parent
    return Path.cwd()


PROJECT_ROOT = _find_project_root(TIBERO_DIR / "launch_common.py")
_CFG = harness_config.load(PROJECT_ROOT)
_TIBERO = _CFG.get("tibero") or {}
_JAVA = _CFG.get("java") or {}

# JPype needs a 64-bit JDK matching the 64-bit Python (JDK 9+, 17 recommended)
DEFAULT_JAVA_HOME = Path(_JAVA["tool_jdk_home"]) if _JAVA.get("tool_jdk_home") else None
FALLBACK_JAVA_HOMES = [Path(p) for p in _JAVA.get("tool_jdk_fallbacks") or []]

PROFILES = {
    name: {
        "host": str(p["host"]),
        "port": str(p["port"]),
        "sid": str(p["sid"]),
        "user_key": "TIBERO_USER_" + name.upper(),
        "password_key": "TIBERO_PASSWORD_" + name.upper(),
    }
    for name, p in (_TIBERO.get("profiles") or {}).items()
}


def _jdbc_jar():
    rel = _TIBERO.get("jdbc_jar")
    if not rel:
        raise SystemExit("[tibero] jdbc_jar is not set in .agents/harness.toml")
    path = Path(rel)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _resolve_java_home():
    current = os.environ.get("JAVA_HOME", "").strip()
    if current and Path(current).is_dir():
        current_path = Path(current)
        # An app-server JDK 1.x (often 32-bit) cannot host JPype; prefer the tool JDK when set
        if "jdk1." in str(current_path).lower() and DEFAULT_JAVA_HOME and DEFAULT_JAVA_HOME.is_dir():
            return DEFAULT_JAVA_HOME
        return current_path
    for candidate in [DEFAULT_JAVA_HOME] + FALLBACK_JAVA_HOMES:
        if candidate and candidate.is_dir():
            return candidate
    return None


def _ensure_java_home():
    java_home = _resolve_java_home()
    if java_home is None:
        return None
    os.environ["JAVA_HOME"] = str(java_home)
    # Put the tool JDK ahead of stale PATH entries (old JREs)
    os.environ["PATH"] = os.pathsep.join(
        [str(java_home / "bin"), str(java_home / "jre" / "bin"), os.environ.get("PATH", "")]
    )
    return java_home


def _find_jvm_lib(java_home):
    if java_home is None:
        return None
    names = ("jvm.dll", "libjvm.so", "libjvm.dylib")
    for sub in ("bin/server", "bin/client", "jre/bin/server", "jre/bin/client", "lib/server", "jre/lib/server"):
        for name in names:
            path = java_home / sub / name
            if path.is_file():
                return path
    return None


def _start_jvm(jdbc_jar):
    """Start the JPype JVM with an explicit JVM library so a PATH JRE is not picked."""
    import jpype

    if jpype.isJVMStarted():
        return
    java_home = _ensure_java_home()
    jvm_lib = _find_jvm_lib(java_home)
    if jvm_lib is None:
        raise SystemExit(
            "JVM library not found under JAVA_HOME=%s. Install a 64-bit JDK 9+ "
            "and set [java] tool_jdk_home." % java_home
        )
    jpype.startJVM(str(jvm_lib), "-Djava.class.path=%s" % jdbc_jar, convertStrings=False)


def launch(profile):
    if profile not in PROFILES:
        raise SystemExit("Unknown Tibero profile %r. Known: %s" % (profile, ", ".join(sorted(PROFILES)) or "(none)"))
    jdbc_jar = _jdbc_jar()
    if not jdbc_jar.is_file():
        raise SystemExit("JDBC jar not found: %s" % jdbc_jar)
    if not SERVER_SRC.is_dir():
        raise SystemExit("Tibero MCP server source not found: %s (install it separately, see README)" % SERVER_SRC)

    creds = harness_config.secret("tibero", project_root=PROJECT_ROOT)
    cfg = PROFILES[profile]
    user = creds.get(cfg["user_key"]) or creds.get("TIBERO_USER")
    password = creds.get(cfg["password_key"]) or creds.get("TIBERO_PASSWORD")
    if not user or not password:
        raise SystemExit(
            "Missing account for profile '%s'. Fill %s (keys: see tibero.env.example)."
            % (profile, harness_config.secret_path("tibero", project_root=PROJECT_ROOT))
        )

    if _ensure_java_home() is None:
        raise SystemExit("JAVA_HOME not set and [java] tool_jdk_home not found.")

    os.environ["TIBERO_HOST"] = cfg["host"]
    os.environ["TIBERO_PORT"] = cfg["port"]
    os.environ["TIBERO_SID"] = cfg["sid"]
    os.environ["TIBERO_USER"] = user
    os.environ["TIBERO_PASSWORD"] = password
    os.environ["CLASSPATH"] = str(jdbc_jar)
    os.environ["TIBERO_MCP_PROFILE"] = profile

    _start_jvm(str(jdbc_jar))

    sys.path.insert(0, str(SERVER_SRC))
    from tibero_mcp_server.server import main

    asyncio.run(main())


def main():
    """Entry for launch_<env>.py: env = file name after 'launch_'."""
    stem = Path(sys.argv[0]).stem
    if not stem.startswith("launch_") or stem == "launch_common":
        raise SystemExit("Run through launch_<env>.py (got %s)" % stem)
    launch(stem[len("launch_"):])
