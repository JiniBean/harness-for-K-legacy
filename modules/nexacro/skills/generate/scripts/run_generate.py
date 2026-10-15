# -*- coding: utf-8 -*-
"""Nexacro generate CLI wrapper. No Studio / nexacro.exe.

Paths come from <project>/.agents/harness.toml [paths] (loader ~/.agents/scripts/harness_config.py):
  required: nexacro_generator, nexacro_adl, nexacro_src, nexacro_out_parent, nexacro_out
  optional: nexacro_project   generator -P value (default: folder name of nexacro_out)
            nexacro_exploded  app folder inside the war exploded copy
                              (default: {war_exploded}/<project folder name>_war_exploded/{nexacro_project})
            webapp_app_link   webapp junction checked for status only
Project root = --project-root, else the current directory.
"""
import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".agents", "scripts"))
import harness_config  # noqa: E402

SRC_EXTS = (".xfdl", ".xjs")
GEN_EXTS = tuple(e + ".js" for e in SRC_EXTS)

# Set by configure()
PROJECT_ROOT = GEN_EXE = ADL = SRC_ROOT = OUT_PARENT = PROJECT = OUT_ROOT = None
LOG_PATH = EXPLODED_ROOT = WEBAPP_APP_LINK = None


def configure(project_root):
    global PROJECT_ROOT, GEN_EXE, ADL, SRC_ROOT, OUT_PARENT, PROJECT, OUT_ROOT
    global LOG_PATH, EXPLODED_ROOT, WEBAPP_APP_LINK
    PROJECT_ROOT = os.path.abspath(project_root)
    paths = harness_config.load(PROJECT_ROOT).get("paths") or {}

    def cfg_path(key, required=True):
        """[paths] value: expand "~", resolve relative to PROJECT_ROOT."""
        val = paths.get(key)
        if not val:
            if required:
                raise SystemExit("harness.toml [paths] %s missing" % key)
            return None
        p = os.path.expanduser(val)
        return os.path.normpath(p if os.path.isabs(p) else os.path.join(PROJECT_ROOT, p))

    GEN_EXE = cfg_path("nexacro_generator")
    ADL = cfg_path("nexacro_adl")
    SRC_ROOT = cfg_path("nexacro_src")
    OUT_PARENT = cfg_path("nexacro_out_parent")
    OUT_ROOT = cfg_path("nexacro_out")
    PROJECT = paths.get("nexacro_project") or os.path.basename(OUT_ROOT)
    LOG_PATH = os.path.join(PROJECT_ROOT, ".agents", "tmp", "nexacro_gen.log")
    EXPLODED_ROOT = cfg_path("nexacro_exploded", required=False)
    if EXPLODED_ROOT is None:
        war = cfg_path("war_exploded", required=False)
        if war:
            artifact = os.path.basename(PROJECT_ROOT) + "_war_exploded"
            EXPLODED_ROOT = os.path.join(war, artifact, PROJECT)
    WEBAPP_APP_LINK = cfg_path("webapp_app_link", required=False)


def ensure_log_dir():
    d = os.path.dirname(LOG_PATH)
    if not os.path.isdir(d):
        os.makedirs(d)


def find_src(token):
    """Return absolute .xfdl/.xjs path for basename token (.xfdl first)."""
    if token.lower().endswith(SRC_EXTS):
        return _find_name(token)
    for ext in SRC_EXTS:
        p = _find_name(token + ext)
        if p:
            return p
    return None


def _find_name(name):
    direct = os.path.join(SRC_ROOT, name)
    if os.path.isfile(direct):
        return os.path.normpath(direct)
    matches = []
    for root, _dirs, files in os.walk(SRC_ROOT):
        if name in files:
            matches.append(os.path.normpath(os.path.join(root, name)))
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    matches.sort(key=lambda p: (len(p), p))
    return matches[0]


def is_service(token):
    return os.path.isdir(os.path.join(SRC_ROOT, token))


def expected_js(xfdl_path):
    rel = os.path.relpath(xfdl_path, SRC_ROOT)
    return os.path.normpath(os.path.join(OUT_ROOT, rel + ".js"))


def exploded_js(gen_js_path):
    rel = os.path.relpath(gen_js_path, OUT_ROOT)
    return os.path.normpath(os.path.join(EXPLODED_ROOT, rel))


def junction_status():
    link = WEBAPP_APP_LINK
    if not link:
        return "n/a"
    if not os.path.exists(link):
        return "missing"
    try:
        import ctypes
        from ctypes import wintypes

        FILE_ATTRIBUTE_REPARSE_POINT = 0x400
        GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
        GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
        GetFileAttributesW.restype = wintypes.DWORD
        attrs = GetFileAttributesW(link)
        if attrs == 0xFFFFFFFF:
            return "unknown"
        if attrs & FILE_ATTRIBUTE_REPARSE_POINT:
            return "linked"
    except Exception:
        pass
    return "real_dir"


def build_cmd(mode, targets):
    cmd = [
        GEN_EXE,
        "-A",
        ADL,
        "-O",
        OUT_PARENT,
        "-P",
        PROJECT,
        "-L",
        LOG_PATH,
    ]
    if mode == "all":
        return cmd
    if mode == "service":
        cmd.extend(["-S", targets[0]])
        return cmd
    paths = []
    for t in targets:
        p = find_src(t)
        if not p:
            raise SystemExit("source not found: %s" % t)
        paths.append(p)
    cmd.extend(["-F", ",".join(paths)])
    return cmd


def _walk_gen(prefix):
    """Generated *.xfdl.js / *.xjs.js under OUT_ROOT (limited to prefix folder if given)."""
    for root, _dirs, files in os.walk(OUT_ROOT):
        if prefix and not (root == prefix or root.startswith(prefix + os.sep)):
            continue
        for name in files:
            if name.endswith(GEN_EXTS):
                yield os.path.normpath(os.path.join(root, name))


def _service_prefix(mode, targets):
    if mode == "service":
        return os.path.normpath(os.path.join(OUT_ROOT, targets[0]))
    return None


def collect_sync_sources(mode, targets, before_mtimes):
    """Paths under OUT_ROOT to copy into exploded: new or newer than before the run."""
    if mode == "file":
        return [expected_js(find_src(t)) for t in targets]
    out = []
    for path in _walk_gen(_service_prefix(mode, targets)):
        prev = before_mtimes.get(path)
        cur = os.path.getmtime(path) if os.path.isfile(path) else None
        if cur is None:
            continue
        if prev is None or cur > prev:
            out.append(path)
    return out


def snapshot_mtimes(mode, targets):
    snap = {}
    if mode == "file":
        for t in targets:
            p = expected_js(find_src(t))
            snap[p] = os.path.getmtime(p) if os.path.isfile(p) else None
        return snap
    for path in _walk_gen(_service_prefix(mode, targets)):
        snap[path] = os.path.getmtime(path)
    return snap


def sync_to_exploded(gen_paths):
    if not EXPLODED_ROOT or not os.path.isdir(EXPLODED_ROOT):
        print("exploded missing (skip sync): %s" % EXPLODED_ROOT, file=sys.stderr)
        return 1
    n = 0
    for src in gen_paths:
        if not os.path.isfile(src):
            print("sync skip missing:", src, file=sys.stderr)
            continue
        dst = exploded_js(src)
        ddir = os.path.dirname(dst)
        if not os.path.isdir(ddir):
            os.makedirs(ddir)
        shutil.copy2(src, dst)
        print("synced:", dst)
        n += 1
    print("sync_count:", n)
    return 0 if n > 0 or not gen_paths else 1


def _print_log_tail(size):
    if not os.path.isfile(LOG_PATH):
        return
    with open(LOG_PATH, "rb") as f:
        tail = f.read()[-size:]
    # Generator writes the log in the system ANSI code page on Korean Windows.
    print(tail.decode("cp949", "replace"))


def main(argv):
    ap = argparse.ArgumentParser(description="Nexacro generate wrapper")
    ap.add_argument("--dry", action="store_true", help="print command only")
    ap.add_argument(
        "--sync-exploded",
        dest="sync_exploded",
        action="store_true",
        default=True,
        help="copy Generate outputs into war exploded (default on)",
    )
    ap.add_argument(
        "--no-sync-exploded",
        dest="sync_exploded",
        action="store_false",
        help="skip war exploded copy",
    )
    ap.add_argument("--project-root", default=os.getcwd(), help="project root (default: cwd)")
    ap.add_argument("tokens", nargs="+", help="form name(s), service folder, or 'all'")
    args = ap.parse_args(argv)

    configure(args.project_root)

    if not os.path.isfile(GEN_EXE):
        print("generator missing: %s" % GEN_EXE, file=sys.stderr)
        return 2
    if not os.path.isfile(ADL):
        print("ADL missing: %s" % ADL, file=sys.stderr)
        return 2

    tokens = args.tokens
    if len(tokens) == 1 and tokens[0].lower() == "all":
        mode, targets = "all", []
    elif len(tokens) == 1 and is_service(tokens[0]):
        mode, targets = "service", tokens
    else:
        mode, targets = "file", tokens

    ensure_log_dir()
    cmd = build_cmd(mode, targets)
    print("CMD:", subprocess.list2cmdline(cmd))
    print("junction:", junction_status())
    print("mode:", mode)
    print("sync_exploded:", args.sync_exploded)
    print("exploded:", EXPLODED_ROOT)

    expected = []
    if mode == "file":
        for t in targets:
            expected.append(expected_js(find_src(t)))
            print("expect:", expected[-1])

    if args.dry:
        return 0

    before = snapshot_mtimes(mode, targets)

    t0 = datetime.now()
    proc = subprocess.call(cmd)
    t1 = datetime.now()
    print("exit:", proc)
    print("elapsed_sec:", (t1 - t0).total_seconds())

    if proc != 0:
        _print_log_tail(2000)
        return proc

    for p in expected:
        if not os.path.isfile(p):
            print("MISSING output:", p, file=sys.stderr)
            return 1
        mtime = os.path.getmtime(p)
        size = os.path.getsize(p)
        print("ok:", p, "size=%s" % size, "mtime=%s" % datetime.fromtimestamp(mtime))
        if before.get(p) is not None and mtime <= before[p]:
            print("WARN: mtime not newer than before", p, file=sys.stderr)

    if mode in ("all", "service"):
        print("log:", LOG_PATH)
        _print_log_tail(800)

    if args.sync_exploded:
        sources = expected if mode == "file" else collect_sync_sources(mode, targets, before)
        rc = sync_to_exploded(sources)
        if rc != 0 and mode == "file":
            return rc

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
