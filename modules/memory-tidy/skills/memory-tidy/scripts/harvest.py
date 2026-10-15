#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Harvest likely user corrections from agent transcripts (memory-tidy skill).

Usage:
  python harvest.py --project ROOT [--since YYYY-MM-DD]   # write candidates json
  python harvest.py --mark YYYY-MM-DD                     # record harvest date
  python harvest.py selftest

Sources: ~/.claude/projects/<slug>/*.jsonl (main sessions, not subagents) and
~/.cursor/projects/<slug>/agent-transcripts/*/*.jsonl. A regex pre-filter picks
candidate user messages; the model decides which are real corrections.
--since defaults to the last harvest date, else 60 days back (Claude cleanupPeriodDays).
The marker (~/.agents/state/memory-tidy_last_harvest) gates garbage-collector:
transcripts older than it may be deleted, so mark only after the candidates were reviewed.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import tempfile
from pathlib import Path

# Strong cues are corrections on their own. Weak cues ("아니야", "잖아") are mostly domain
# talk, so they count only together with words about how the agent works or answers.
STRONG = re.compile(
    r"이해가 ?안|뭔 ?소리|뭔소린|장황|이렇게 말해야|이렇게 말하면|쉽게 설명|다시 설명|너만 아는"
    r"|분명히|했잖아|말했잖아|하지 ?마|하지말|앞으로|항상|절대|기억해")
WEAK = re.compile(r"아니야|아니잖아|아니라|잖아|말고|틀렸|잘못|왜 .{0,20}(했|안|하지|해)|다시 해")
META = re.compile(r"규칙|스킬|지시|메모리|훅|설명|답변|말해|말하|물어|묻|보고|확인하고|추측|단정"
                  r"|마음대로|임의로|멋대로|너는|네가|니가|에이전트|서브에이전트|계획")
CUES = re.compile(STRONG.pattern + "|" + WEAK.pattern)


def is_candidate(t: str) -> bool:
    return bool(STRONG.search(t) or (WEAK.search(t) and META.search(t)))
NOISE = re.compile(r"^\s*<(local-command|command-name|command-message|system-reminder|task-notification)")
SYS_BLOCK = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
USER_QUERY = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.S)
DEFAULT_LOOKBACK = 60


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def slug_dir(parent: Path, root: Path) -> Path | None:
    if parent.is_dir():
        for d in parent.iterdir():
            if d.is_dir() and norm(d.name) == norm(str(root)):
                return d
    return None


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # tool_result blocks carry no user words
        return "\n".join(c.get("text", "") for c in content
                         if isinstance(c, dict) and c.get("type") == "text")
    return ""


def turns(path: Path, kind: str):
    """Yield (role, text, iso_ts) per line; kind is 'claude' or 'cursor'."""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if kind == "claude":
            if o.get("type") not in ("user", "assistant") or o.get("isMeta") or o.get("isSidechain"):
                continue
            role, ts = o["type"], o.get("timestamp", "")
        else:
            role, ts = o.get("role"), ""
        t = SYS_BLOCK.sub("", text_of((o.get("message") or {}).get("content"))).strip()
        if kind == "cursor" and role == "user":
            m = USER_QUERY.search(t)
            t = m.group(1) if m else t
        if t:
            yield role, t, ts


def harvest(root: Path, home: Path, since: dt.date) -> dict:
    srcs = []
    c = slug_dir(home / ".claude" / "projects", root)
    if c:
        srcs += [(p, "claude") for p in c.glob("*.jsonl")]
    c = slug_dir(home / ".cursor" / "projects", root)
    if c:
        srcs += [(p, "cursor") for p in (c / "agent-transcripts").glob("*/*.jsonl")]
    cut = since.isoformat()
    out, scanned, seen = [], 0, set()
    for path, kind in sorted(srcs):
        mdate = dt.date.fromtimestamp(path.stat().st_mtime).isoformat()
        if mdate < cut:
            continue
        scanned += 1
        prev = ""
        for role, t, ts in turns(path, kind):
            if role == "assistant":
                prev = t
                continue
            if NOISE.match(t) or (ts and ts[:10] < cut) or not is_candidate(t) or t in seen:
                continue
            seen.add(t)  # resent / duplicated prompts
            out.append({"source": kind, "session": path.stem, "date": (ts or mdate)[:10],
                        "user": t[:400], "prev_assistant": prev[-300:]})
    return {"project": str(root), "since": cut, "scanned_at": dt.date.today().isoformat(),
            "sessions_scanned": scanned, "candidates": out}


def marker(home: Path) -> Path:
    return home / ".agents" / "state" / "memory-tidy_last_harvest"


def selftest() -> None:
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        root, home = t / "C" / "Proj", t / "home"
        cl = home / ".claude" / "projects" / re.sub(r"[\\/:]", "-", str(root))
        cl.mkdir(parents=True)
        today = dt.date.today().isoformat()
        rows = [
            {"type": "user", "message": {"content": "<command-name>/clear</command-name> 아니야"}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "A안으로 했습니다"}]}},
            {"type": "user", "timestamp": today + "T01:00:00Z",
             "message": {"content": "전역스킬이라고 했잖아 분명히"}},
            {"type": "user", "timestamp": today + "T01:01:00Z", "message": {"content": "좋아 진행해"}},
            {"type": "user", "timestamp": "2020-01-01T00:00:00Z", "message": {"content": "그거 아니야"}},
            {"type": "user", "isSidechain": True, "message": {"content": "왜 그렇게 했어"}},
        ]
        (cl / "s1.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                                     encoding="utf-8")
        cu = home / ".cursor" / "projects" / re.sub(r"[\\/:]+", "-", str(root)).lower()
        (cu / "agent-transcripts" / "x").mkdir(parents=True)
        (cu / "agent-transcripts" / "x" / "x.jsonl").write_text(json.dumps(
            {"role": "user", "message": {"content": [{"type": "text", "text":
             "<timestamp>t</timestamp>\n<user_query>\n장황해 다시 설명해\n</user_query>"}]}},
            ensure_ascii=False), encoding="utf-8")
        r = harvest(root, home, dt.date.today() - dt.timedelta(days=1))
        got = sorted(c["user"] for c in r["candidates"])
        assert got == ["장황해 다시 설명해", "전역스킬이라고 했잖아 분명히"], got
        cl_c = [c for c in r["candidates"] if c["source"] == "claude"][0]
        assert cl_c["prev_assistant"] == "A안으로 했습니다", cl_c
        main(["x", "--mark", today], home=home)
        assert marker(home).read_text(encoding="utf-8") == today
        assert since_default(home) == dt.date.today()
    print("selftest ok")


def since_default(home: Path) -> dt.date:
    m = marker(home)
    if m.is_file():
        return dt.date.fromisoformat(m.read_text(encoding="utf-8").strip()[:10])
    return dt.date.today() - dt.timedelta(days=DEFAULT_LOOKBACK)


def main(argv: list[str], home: Path | None = None) -> int:
    home = home or Path.home()
    if argv[1:2] == ["selftest"]:
        selftest()
        return 0
    if argv[1:2] == ["--mark"] and len(argv) == 3:
        d = dt.date.fromisoformat(argv[2])
        marker(home).parent.mkdir(parents=True, exist_ok=True)
        marker(home).write_text(d.isoformat(), encoding="utf-8")
        print("marked %s" % d)
        return 0
    if argv[1:2] != ["--project"] or len(argv) not in (3, 5) or (len(argv) == 5 and argv[3] != "--since"):
        sys.stderr.write(__doc__)
        return 2
    root = Path(argv[2]).resolve()
    since = dt.date.fromisoformat(argv[4]) if len(argv) == 5 else since_default(home)
    r = harvest(root, home, since)
    out = root / ".agents" / "tmp" / ("%s_harvest.json" % dt.date.today().strftime("%Y%m%d"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    # one line per candidate for cheap first-pass reading; look up prev_assistant in json by index
    brief = ["%d. %s %s | %s" % (i, c["date"], c["source"], " ".join(c["user"].split())[:200])
             for i, c in enumerate(r["candidates"])]
    out.with_suffix(".txt").write_text("\n".join(brief) + "\n", encoding="utf-8")
    print("since %s, sessions %d, candidates %d" % (r["since"], r["sessions_scanned"], len(r["candidates"])))
    print("out: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
