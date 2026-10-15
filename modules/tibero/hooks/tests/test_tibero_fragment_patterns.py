# -*- coding: utf-8 -*-
"""Source-repo check for this module's harness.fragment.toml shell_block_patterns.

Run from the harness repo (not an installed project):
python modules/<module>/hooks/tests/test_<module>_fragment_patterns.py

Every pattern line must carry a trailing "# sample: <command>" comment. The test loads the
fragment with tomllib, compiles each pattern the way shell_guard.py does (re.IGNORECASE)
and asserts it matches its sample. In an installed project the fragment is already merged
into harness.toml, so the test prints SKIP there.
"""
import re
import sys
import tomllib
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
FRAG = Path(__file__).resolve().parents[2] / "harness.fragment.toml"
if not FRAG.is_file():
    print("SKIP no harness.fragment.toml at %s (installed copy)" % FRAG)
    sys.exit(0)

text = FRAG.read_text(encoding="utf-8")
patterns = tomllib.loads(text)["guard"]["shell_block_patterns"]

# Pattern lines inside the shell_block_patterns array: <toml string>, # sample: <command>
LINE_RE = re.compile(r"^\s*('''.*?'''|'[^']*'|\"(?:[^\"\\]|\\.)*\")\s*,?\s*(?:#\s*sample:\s*(.*?))?\s*$")
body = text.split("shell_block_patterns = [", 1)[1].split("\n]", 1)[0]
samples = {}
for line in body.splitlines():
    if not line.strip() or line.strip().startswith("#"):
        continue
    m = LINE_RE.match(line)
    if not m:
        continue
    pattern = tomllib.loads("p = " + m.group(1))["p"]
    samples[pattern] = m.group(2)

fail = 0
for p in patterns:
    sample = samples.get(p)
    if not sample:
        ok, why = False, "no '# sample:' comment"
    else:
        try:
            ok = bool(re.compile(p, re.IGNORECASE).search(sample))
            why = "matches" if ok else "does not match sample %r" % sample
        except re.error as exc:
            ok, why = False, "compile error: %s" % exc
    fail += 0 if ok else 1
    print("%s %-40s %s" % ("PASS" if ok else "FAIL", p[:40], why))
print("FAIL=%d" % fail)
sys.exit(1 if fail else 0)
