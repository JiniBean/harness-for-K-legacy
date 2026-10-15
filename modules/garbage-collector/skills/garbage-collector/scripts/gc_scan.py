#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scan and delete agent leftovers for one project (garbage-collector skill).

Usage:
  python gc_scan.py [--project ROOT]          # dry run: print summary, write plan json
  python gc_scan.py --apply PLAN.json [--only CAT[,CAT]] [--include-review]
  python gc_scan.py selftest

Targets (all age-based, default 30 days, override in <ROOT>/.agents/gc.toml):
  tmp                 <ROOT>/.agents/tmp/**                  (minus `keep` globs)
  claude_temp         %TEMP%/claude/<slug>/<session>/
  claude_sessions     ~/.claude/projects/<slug>/<id>.jsonl + <id>/   (harvest-gated)
  cursor_tools        ~/.cursor/projects/<slug>/agent-tools/*
  cursor_transcripts  ~/.cursor/projects/<slug>/agent-transcripts/*  (harvest-gated)
  extra               [[extra]] entries in gc.toml (inside ROOT only)
  untracked (review)  `git status` untracked files, never deleted without --include-review
Harvest gate: a session is deletable only if older than the date in
~/.agents/state/memory-tidy_last_harvest (written by memory-tidy). No marker = keep all.
Deletion is permanent. --apply re-validates every path against the allowed roots.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

DAY = 86400
CONFIG_KEYS = {"retention_days", "keep", "ignore_untracked", "extra"}
EXTRA_KEYS = {"path", "glob", "days"}
HARVEST_GATED = {"claude_sessions", "cursor_transcripts"}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def find_slug_dir(parent: Path, root: Path) -> Path | None:
    """Claude uses C--A-B, Cursor uses c-A-B; compare alphanumerics only."""
    if not parent.is_dir():
        return None
    key = norm(str(root))
    for d in parent.iterdir():
        if d.is_dir() and norm(d.name) == key:
            return d
    return None


def newest_mtime(p: Path) -> float:
    if p.is_symlink() or not p.is_dir():
        return p.lstat().st_mtime
    # newest file inside; directory mtimes are ignored (they change on unrelated listing ops)
    m = 0.0
    for dirpath, _dirs, files in os.walk(p):
        for f in files:
            try:
                m = max(m, os.lstat(os.path.join(dirpath, f)).st_mtime)
            except OSError:
                pass
    return m or p.lstat().st_mtime


def size_of(p: Path) -> int:
    if p.is_symlink() or not p.is_dir():
        return p.lstat().st_size
    total = 0
    for dirpath, _dirs, files in os.walk(p):
        for f in files:
            try:
                total += os.lstat(os.path.join(dirpath, f)).st_size
            except OSError:
                pass
    return total


def load_config(root: Path) -> dict:
    cfg = {"retention_days": 30, "keep": [], "ignore_untracked": [], "extra": []}
    f = root / ".agents" / "gc.toml"
    if not f.is_file():
        return cfg
    data = tomllib.loads(f.read_text(encoding="utf-8"))
    bad = set(data) - CONFIG_KEYS
    if bad:
        raise SystemExit("gc.toml: unknown keys %s" % sorted(bad))
    for e in data.get("extra", []):
        bad = set(e) - EXTRA_KEYS
        if bad or "path" not in e:
            raise SystemExit("gc.toml [[extra]]: bad entry %r" % e)
        target = (root / e["path"]).resolve()
        if not target.is_relative_to(root.resolve()) or target == root.resolve():
            raise SystemExit("gc.toml [[extra]]: path must be inside project root: %s" % e["path"])
    cfg.update(data)
    return cfg


def env_paths(home: Path | None = None, temp: Path | None = None) -> dict:
    home = home or Path.home()
    temp = temp or Path(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp")
    return {
        "claude_projects": home / ".claude" / "projects",
        "cursor_projects": home / ".cursor" / "projects",
        "claude_temp": temp / "claude",
        "harvest": home / ".agents" / "state" / "memory-tidy_last_harvest",
    }


def allowed_roots(root: Path, env: dict, cfg: dict) -> dict:
    roots = {"tmp": root / ".agents" / "tmp"}
    c = find_slug_dir(env["claude_temp"], root)
    if c:
        roots["claude_temp"] = c
    c = find_slug_dir(env["claude_projects"], root)
    if c:
        roots["claude_sessions"] = c
    c = find_slug_dir(env["cursor_projects"], root)
    if c:
        roots["cursor_tools"] = c / "agent-tools"
        roots["cursor_transcripts"] = c / "agent-transcripts"
    for i, e in enumerate(cfg["extra"]):
        roots["extra%d" % i] = root / e["path"]
    return roots


def read_harvest(env: dict) -> float | None:
    f = env["harvest"]
    if not f.is_file():
        return None
    d = dt.date.fromisoformat(f.read_text(encoding="utf-8").strip()[:10])
    return time.mktime(d.timetuple())


def scan(root: Path, env: dict, now: float | None = None) -> dict:
    now = now or time.time()
    root = root.resolve()
    cfg = load_config(root)
    days = int(cfg["retention_days"])
    cutoff = now - days * DAY
    harvest = read_harvest(env)
    roots = allowed_roots(root, env, cfg)
    items, notes = [], []

    def add(cat: str, p: Path, review: bool = False):
        items.append({"cat": cat, "path": str(p), "bytes": size_of(p),
                      "mtime": dt.date.fromtimestamp(newest_mtime(p)).isoformat(),
                      "review": review})

    tmp = roots["tmp"]
    if tmp.is_dir():
        for p in sorted(tmp.rglob("*")):
            rel = p.relative_to(tmp).as_posix()
            if p.is_file() and not any(fnmatch.fnmatch(rel, k) for k in cfg["keep"]) \
                    and p.lstat().st_mtime < cutoff:
                add("tmp", p)

    for cat in ("claude_temp", "cursor_tools", "cursor_transcripts"):
        base = roots.get(cat)
        if not base or not base.is_dir():
            continue
        for p in sorted(base.iterdir()):
            if newest_mtime(p) >= cutoff:
                continue
            if cat in HARVEST_GATED and (harvest is None or newest_mtime(p) >= harvest):
                continue
            add(cat, p)

    base = roots.get("claude_sessions")
    if base:
        for j in sorted(base.glob("*.jsonl")):
            m = newest_mtime(j)
            if m < cutoff and harvest is not None and m < harvest:
                add("claude_sessions", j)
                side = base / j.stem
                if side.is_dir():
                    add("claude_sessions", side)
        mem = base / "memory"
        if mem.is_dir():
            notes.append("memory files: %d (cleanup is memory-tidy's job)"
                         % len([f for f in mem.glob("*.md") if f.name != "MEMORY.md"]))
    if harvest is None:
        notes.append("no harvest marker: session transcripts are kept until memory-tidy runs")

    for i, e in enumerate(cfg["extra"]):
        base = roots["extra%d" % i]
        if not base.is_dir():
            continue
        ecut = now - int(e.get("days", days)) * DAY
        for p in sorted(base.rglob(e.get("glob", "*"))):
            if p.is_file() and p.lstat().st_mtime < ecut:
                add("extra:" + e["path"], p)

    try:
        out = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "-uall"],
                             capture_output=True, text=True, encoding="utf-8", check=True).stdout
        for line in out.splitlines():
            if line.startswith("?? "):
                rel = line[3:].strip('"')
                if rel.startswith("../"):  # root is a subfolder of a larger repo
                    continue
                if not any(fnmatch.fnmatch(Path(rel).name, g) for g in cfg["ignore_untracked"]):
                    add("untracked", root / rel, review=True)
    except (OSError, subprocess.CalledProcessError):
        notes.append("not a git repo or git missing: untracked check skipped")

    return {"project": str(root), "created": dt.date.fromtimestamp(now).isoformat(),
            "retention_days": days, "items": items, "notes": notes}


def under(p: Path, base: Path) -> bool:
    try:
        return p.resolve().is_relative_to(base.resolve())
    except OSError:
        return False


def apply(plan: dict, env: dict, include_review: bool) -> dict:
    root = Path(plan["project"])
    # review items may be anywhere in the project; everything else only inside its target roots
    roots = list(allowed_roots(root, env, load_config(root)).values())
    done, failed = [], []
    for it in plan["items"]:
        if it["review"] and not include_review:
            continue
        p = Path(it["path"])
        if p.is_symlink() or not p.exists():
            failed.append((it["path"], "missing or symlink"))
            continue
        bases = [root] if it["review"] else roots
        if not any(under(p, b) and p.resolve() != b.resolve() for b in bases):
            failed.append((it["path"], "outside allowed roots"))
            continue
        try:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
            done.append(it["path"])
        except OSError as e:
            failed.append((it["path"], str(e)))
    return {"deleted": len(done), "failed": failed}


def summary(plan: dict) -> str:
    by = {}
    for it in plan["items"]:
        c = by.setdefault(it["cat"], [0, 0, it["review"]])
        c[0] += 1
        c[1] += it["bytes"]
    lines = ["%-28s %6s %10s" % ("category", "count", "MB")]
    for cat, (n, b, rv) in sorted(by.items()):
        lines.append("%-28s %6d %10.1f%s" % (cat, n, b / 1e6, "  (review only)" if rv else ""))
    lines += ["note: " + n for n in plan["notes"]]
    return "\n".join(lines)


def selftest() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        root, home, temp = t / "C" / "Proj", t / "home", t / "temp"
        old = time.time() - 40 * DAY
        def mk(p: Path, aged=True):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")
            if aged:
                os.utime(p, (old, old))
            return p
        mk(root / ".agents" / "tmp" / "a_old.py")
        mk(root / ".agents" / "tmp" / "b_new.py", aged=False)
        mk(root / ".agents" / "tmp" / "_keep" / "k.txt")
        mk(root / "log" / "w_1.log")
        (root / ".agents" / "gc.toml").write_text(
            'keep = ["_keep/**"]\n[[extra]]\npath = "log"\nglob = "w_*.log"\ndays = 1\n',
            encoding="utf-8")
        cp = home / ".claude" / "projects" / re.sub(r"[\\/:]", "-", str(root))
        mk(cp / "s1.jsonl")
        mk(cp / "s1" / "tool-results" / "r.txt")
        mk(cp / "memory" / "m.md")
        mk(temp / "claude" / re.sub(r"[\\/:]", "-", str(root)) / "sess" / "scratchpad" / "x.py")
        cur = home / ".cursor" / "projects" / re.sub(r"[\\/:]+", "-", str(root)).lower()
        mk(cur / "agent-tools" / "t.txt")
        mk(cur / "agent-transcripts" / "tr" / "a.jsonl")
        env = env_paths(home, temp)

        plan = scan(root, env)
        cats = sorted({i["cat"] for i in plan["items"]})
        assert cats == ["claude_temp", "cursor_tools", "extra:log", "tmp"], cats
        paths = [i["path"] for i in plan["items"]]
        assert not any("b_new" in p or "_keep" in p for p in paths), paths

        env["harvest"].parent.mkdir(parents=True)
        env["harvest"].write_text(dt.date.today().isoformat(), encoding="utf-8")
        plan = scan(root, env)
        cats = {i["cat"] for i in plan["items"]}
        assert {"claude_sessions", "cursor_transcripts"} <= cats, cats
        assert not any("memory" in i["path"] for i in plan["items"])

        outside, src = mk(t / "outside.txt"), mk(root / "src" / "Main.java")
        for p in (outside, src):
            plan["items"].append({"cat": "tmp", "path": str(p), "bytes": 1,
                                  "mtime": "", "review": False})
        res = apply(plan, env, include_review=False)
        assert [f[0] for f in res["failed"]] == [str(outside), str(src)], res
        assert outside.exists() and src.exists() and (root / ".agents" / "tmp" / "b_new.py").exists()
        assert not (root / ".agents" / "tmp" / "a_old.py").exists()
        assert not (cp / "s1.jsonl").exists() and (cp / "memory" / "m.md").exists()

        (root / ".agents" / "gc.toml").write_text('[[extra]]\npath = ".."\n', encoding="utf-8")
        try:
            scan(root, env)
            raise AssertionError("extra outside root accepted")
        except SystemExit:
            pass
        (root / ".agents" / "gc.toml").write_text('kep = []\n', encoding="utf-8")
        try:
            scan(root, env)
            raise AssertionError("unknown key accepted")
        except SystemExit:
            pass
    print("selftest ok")


def main(argv: list[str]) -> int:
    if argv[1:2] == ["selftest"]:
        selftest()
        return 0
    flags = {"--project": 1, "--apply": 1, "--only": 1, "--include-review": 0}
    i = 1
    while i < len(argv):  # reject anything unknown (e.g. --help) instead of scanning cwd
        if argv[i] not in flags or i + flags[argv[i]] >= len(argv) + (flags[argv[i]] == 0):
            sys.stderr.write(__doc__)
            return 2
        i += 1 + flags[argv[i]]
    env = env_paths()
    if "--apply" in argv:
        plan = json.loads(Path(argv[argv.index("--apply") + 1]).read_text(encoding="utf-8"))
        if "--only" in argv:  # e.g. --only tmp,extra:log  (category names from the summary)
            keep = set(argv[argv.index("--only") + 1].split(","))
            plan["items"] = [it for it in plan["items"] if it["cat"] in keep]
        res = apply(plan, env, "--include-review" in argv)
        print(json.dumps(res, ensure_ascii=True, indent=1))
        return 1 if res["failed"] else 0
    root = Path(argv[argv.index("--project") + 1]) if "--project" in argv else Path.cwd()
    plan = scan(root, env)
    out = root / ".agents" / "tmp" / ("%s_gc_plan.json" % dt.date.today().strftime("%Y%m%d"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(summary(plan))
    print("plan: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
