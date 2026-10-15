# -*- coding: utf-8 -*-
"""Harness settings and secrets loader (stdlib only, Python 3.11+ for tomllib).

Settings (not secret):
  ~/.agents/harness.toml                 global (fixed location)
  <harness_dir>/harness.toml             project, overrides global keys
  harness_dir defaults to <project_root>/.agents; override in the global file:
    [projects."C:/path/to/project"]
    harness_dir = "D:/elsewhere/.agents"

Secrets:
  <secrets_dir>/<project name>/<secret name>.env   KEY=VALUE lines
  secrets_dir defaults to ~/.agents/secrets; override with secrets_dir in the global file.
  project name = project harness.toml "name", else the project folder name (lowercase).
  Environment variable HARNESS_SECRET_<NAME>_<KEY> overrides one key
  (NAME/KEY uppercased, non-alphanumerics -> "_").
  Agents never read secret files; only launchers and scripts call secret().

Usage:
  import harness_config as hc
  cfg = hc.load(project_root)
  creds = hc.secret("tibero", project_root=project_root)
  python harness_config.py [project_root]   prints resolved paths (no secret values)
"""
from __future__ import annotations

import os
import re
import sys
import tomllib
from pathlib import Path

GLOBAL_DIR = Path.home() / ".agents"
GLOBAL_FILE = GLOBAL_DIR / "harness.toml"
DEFAULT_SECRETS_DIR = GLOBAL_DIR / "secrets"


def _read_toml(path):
    if not path.is_file():
        return {}
    # utf-8-sig: PowerShell 5.1 and Notepad may write a BOM, which tomllib rejects.
    return tomllib.loads(path.read_text(encoding="utf-8-sig"))


def _merge(base, over):
    out = dict(base)
    for key, val in over.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], val)
        else:
            out[key] = val
    return out


def _norm(path):
    return str(Path(path).resolve()).replace("\\", "/").rstrip("/").lower()


def global_config():
    return _read_toml(GLOBAL_FILE)


def project_dir(project_root):
    root = Path(project_root).resolve()
    projects = global_config().get("projects") or {}
    for key, val in projects.items():
        if _norm(key) == _norm(root) and isinstance(val, dict) and val.get("harness_dir"):
            return Path(val["harness_dir"]).expanduser()
    return root / ".agents"


def load(project_root=None):
    cfg = global_config()
    cfg.pop("projects", None)
    if project_root is not None:
        cfg = _merge(cfg, _read_toml(project_dir(project_root) / "harness.toml"))
    return cfg


def secrets_dir():
    val = global_config().get("secrets_dir")
    return Path(val).expanduser() if val else DEFAULT_SECRETS_DIR


def project_name(project_root):
    name = _read_toml(project_dir(project_root) / "harness.toml").get("name")
    return str(name or Path(project_root).resolve().name).lower()


def _env_key(*parts):
    return "_".join(re.sub(r"[^A-Za-z0-9]", "_", p).upper() for p in parts)


def secret(name, project_root=None, project=None):
    """Return {KEY: VALUE} for one secret; env HARNESS_SECRET_<NAME>_<KEY> wins per key."""
    folder = project or (project_name(project_root) if project_root is not None else "global")
    path = secrets_dir() / folder / ("%s.env" % name)
    values = {}
    if path.is_file():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip()
    prefix = _env_key("HARNESS_SECRET", name) + "_"
    for env_name, env_val in os.environ.items():
        if env_name.upper().startswith(prefix):
            values[env_name[len(prefix):].upper()] = env_val
    return values


def secret_path(name, project_root=None, project=None):
    folder = project or (project_name(project_root) if project_root is not None else "global")
    return secrets_dir() / folder / ("%s.env" % name)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else None
    print("global_file:", GLOBAL_FILE, "(exists)" if GLOBAL_FILE.is_file() else "(missing)")
    print("secrets_dir:", secrets_dir())
    if root:
        print("project_dir:", project_dir(root))
        print("project_name:", project_name(root))
        print("project_keys:", sorted(load(root).keys()))
