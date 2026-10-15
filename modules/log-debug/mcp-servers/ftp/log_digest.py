# -*- coding: utf-8 -*-
"""WAS log digest for the log skill (operation mode). Stdlib only.

Summary mode: one line per target-company request that has DML / exception / key hits
  python log_digest.py --group <SCHEMA> --corp <CORP_ID> [--from "2026-01-02 08:30"] [--to ...] [--key VALUE] FILE...
Raw mode: kept records of one request (SELECT excluded)
  python log_digest.py --puuid <REQUEST_ID> FILE...
Self test:
  python log_digest.py --selftest

Input: text logs, .gz, .zip (streamed, never extracted to disk).
Line format (see README): record header
  "YYYY-MM-DD HH:mm:ss[,mmm] <thread or (thread)> LEVEL [logger] body"
request start line (logger = [log] interceptor of the project harness.toml)
  "============= Request URI : [<uri>] / PUUID : [<id>] / ... / IP : [<ip>] / Member : [... Group_ID=.., Corp_ID=.., User_ID=..]"
SQL lines from log4jdbc logger "jdbc.sqltiming", optional leading "/* Dao.method */" comment.
"""
from __future__ import annotations

import argparse
import gzip
import io
import re
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".agents" / "scripts"))
import harness_config  # noqa: E402


def _find_project_root(start: Path) -> Path:
    """Parent of the nearest enclosing .agents folder; cwd when not installed under one."""
    for parent in start.parents:
        if parent.name == ".agents":
            return parent.parent
    return Path.cwd()


HEAD = re.compile(
    r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)(?:,\d{3})? (\(.*?\)|\S+)\s+"
    r"(TRACE|DEBUG|INFO|WARN|ERROR) \[([^\]]+)\] ?"
)
# The only project value: logger class that prints the request start line
INTERCEPTOR = str((harness_config.load(_find_project_root(Path(__file__).resolve())).get("log") or {}).get("interceptor") or "")
SQLTIMING = "jdbc.sqltiming"
REQ = re.compile(r"Request URI : \[([^\]]*)\] / PUUID : \[([^\]]*)\]")
IP = re.compile(r" / IP : \[([^\]]*)\]")
MEMBER_FIELD = {k: re.compile(k + r"=([^,\]]*)") for k in ("Group_ID", "Corp_ID", "User_ID")}
LEAD_COMMENT = re.compile(r"^\s*/\*\s*(.*?)\s*\*/\s*", re.S)
FIRST_WORD = re.compile(r"[A-Za-z]+")
DML_KIND = {"INSERT": "INS", "UPDATE": "UPD", "DELETE": "DEL", "MERGE": "MRG"}
COLS = ("INS", "UPD", "DEL", "MRG", "ETC")
RAW_MAX_LINES = 200
RECORD_MAX_LINES = 10


def open_lines(path):
    """Open one file (or every member of a zip) as (name, line iterator) pairs."""
    low = path.lower()
    if low.endswith(".zip"):
        zf = zipfile.ZipFile(path)
        for name in zf.namelist():
            if not name.endswith("/"):
                yield path + "!" + name, io.TextIOWrapper(zf.open(name), encoding="utf-8", errors="replace")
    elif low.endswith(".gz"):
        yield path, gzip.open(path, "rt", encoding="utf-8", errors="replace")
    else:
        yield path, io.open(path, "r", encoding="utf-8", errors="replace")


def records(lines):
    """Group lines into records that start with a header line. (ts, thread, level, cls, body_lines)"""
    cur = None
    for line in lines:
        m = HEAD.match(line)
        if m:
            if cur:
                yield cur
            cur = (m.group(1), m.group(2), m.group(3), m.group(4), [line[m.end():].rstrip("\r\n")])
        elif cur:
            cur[4].append(line.rstrip("\r\n"))
    if cur:
        yield cur


def sql_kind(body):
    """sqltiming body -> (kind, Dao.method). kind: INS/UPD/DEL/MRG/ETC/SEL"""
    dao = ""
    m = LEAD_COMMENT.match(body)
    if m:
        dao = m.group(1)
        body = body[m.end():]
    w = FIRST_WORD.match(body.lstrip("( "))
    word = w.group(0).upper() if w else ""
    if word in ("SELECT", "WITH"):
        return "SEL", dao
    return DML_KIND.get(word, "ETC"), dao


class Req(object):
    def __init__(self, ts, uri, puuid, ip, group, corp, user):
        self.ts, self.uri, self.puuid, self.ip = ts, uri, puuid, ip
        self.group, self.corp, self.user = group, corp, user
        self.cnt = dict.fromkeys(COLS, 0)
        self.exc = 0
        self.keyhit = 0
        self.target_sql = False  # request without Member: SQL holds target schema + CORP_ID literal
        self.raw = []


def scan(sources, group, corp, keys, ts_from, ts_to, puuid):
    """sources: [(name, line iterator)]. Returns target requests and counters."""
    corp_re = re.compile(r"CORP_ID\s*=\s*'?%s'?\b" % re.escape(corp)) if corp else None
    schema = (group + ".") if group else None
    found = []
    total = 0
    outside_dml = 0
    for _name, lines in sources:
        by_thread = {}  # thread -> Req, or None when not a target. Reset per file
        for ts, thread, level, cls, body in records(lines):
            head = body[0]
            if cls == INTERCEPTOR:
                if level == "DEBUG" and head.startswith("============="):
                    m = REQ.search(head)
                    if not m:
                        continue
                    total += 1
                    ip = IP.search(head)
                    f = {}
                    for k, r in MEMBER_FIELD.items():
                        hit = r.search(head)
                        f[k] = hit.group(1) if hit else None
                    req = Req(ts, m.group(1), m.group(2), ip.group(1) if ip else "", f["Group_ID"], f["Corp_ID"], f["User_ID"])
                    keep = True
                    if puuid:
                        keep = req.puuid == puuid
                    else:
                        if req.corp is not None and (req.corp != corp or (group and req.group != group)):
                            keep = False
                        if ts_from and ts < ts_from or ts_to and ts >= ts_to:
                            keep = False
                    by_thread[thread] = req if keep else None
                    if keep:
                        found.append(req)
                continue  # other interceptor lines (e.g. session-expired reprint) are neither requests nor exceptions
            is_sql = cls == SQLTIMING
            is_err = level in ("ERROR", "WARN")
            text = "\n".join(body)
            if not (is_sql or is_err or "Exception" in text):
                continue  # drop dataset dumps, http wire logs, etc.
            req = by_thread.get(thread)
            if is_sql:
                kind, dao = sql_kind(text)
            else:
                kind, dao = None, ""
            if req is None:
                if thread not in by_thread and kind in DML_KIND.values() and schema and schema in text \
                        and corp_re and corp_re.search(text):
                    outside_dml += 1  # target-company DML before the thread's first request line
                continue
            if kind:
                if kind != "SEL":
                    req.cnt[kind] += 1
                if req.corp is None and schema and schema in text and corp_re.search(text):
                    req.target_sql = True
            else:
                req.exc += 1
            if keys:
                req.keyhit += sum(text.count(k) for k in keys)
            if puuid and kind != "SEL":
                req.raw.append((ts, level, cls, dao, body))
    if not puuid:
        found = [r for r in found if r.corp is not None or r.target_sql]
    return found, total, outside_dml


def print_summary(found, total, outside_dml, limit, elapsed, files):
    hit = [r for r in found if sum(r.cnt.values()) or r.exc or r.keyhit]
    shown = hit[:limit]
    print("[digest] files=%d requests_total=%d target_requests=%d hit=%d shown=%d outside_request_dml=%d elapsed=%.1fs"
          % (len(files), total, len(found), len(hit), len(shown), outside_dml, elapsed))
    if len(hit) > limit:
        print("[digest] %d rows omitted; narrow --from/--to or raise --limit" % (len(hit) - limit))
    print("ts | User_ID | URI | PUUID | " + " | ".join(COLS) + " | EXC | KEYHIT")
    for r in shown:
        user = r.user if r.corp is not None else "Corp_ID=?(SQL)"
        print(" | ".join([r.ts, user or "", r.uri, r.puuid] + [str(r.cnt[c]) for c in COLS] + [str(r.exc), str(r.keyhit)]))


def print_raw(found):
    if not found:
        print("[digest] PUUID not found")
        return
    r = found[0]
    print("[digest] %s | %s | %s | Group_ID=%s Corp_ID=%s User_ID=%s IP=%s"
          % (r.ts, r.uri, r.puuid, r.group, r.corp, r.user, r.ip))
    n = 0
    for ts, level, cls, dao, body in r.raw:
        cut = body[:RECORD_MAX_LINES]
        tag = (" <%s>" % dao) if dao else ""
        lines = ["%s %s [%s]%s %s" % (ts, level, cls, tag, cut[0])] + cut[1:]
        if len(body) > RECORD_MAX_LINES:
            lines.append("  ... (+%d lines)" % (len(body) - RECORD_MAX_LINES))
        for line in lines:
            if n >= RAW_MAX_LINES:
                print("[digest] raw output capped at %d lines" % RAW_MAX_LINES)
                return
            print(line)
            n += 1


def selftest():
    global INTERCEPTOR
    INTERCEPTOR = "app.web.RequestInterceptor"  # fixture value; independent of the project setting
    par = "(worker-pool(localhost:9000)-%d [was-%d])"  # parenthesized thread form (e.g. JEUS)
    lines = [
        # Tomcat form (millis), target company request p1
        "2026-01-02 09:06:34,625 http-exec-62 DEBUG [%s] ============= Request URI : [/M1/save.do] / PUUID : [p1] / SID : [s] / IP : [ip-a] / Member : [MemberVO [Group_ID=SCHEMA_A, Group_Name=null, Corp_ID=100, Corp_Name=null, User_ID=user1, User_PW=null]]" % INTERCEPTOR,
        "2026-01-02 09:06:34,700 http-exec-62  INFO [jdbc.sqltiming] /* M1_Order_Dao.updateOrder */ UPDATE SCHEMA_A.ORDER_TB SET X = 1 ",
        "WHERE CORP_ID = '100' AND JOB_NO = 'J1' ",
        " {executed in 2 msec}",
        "2026-01-02 09:06:34,701 http-exec-62  INFO [jdbc.sqltiming] /*M1_Order_Dao.mergeX*/ MERGE INTO SCHEMA_A.X USING DUAL ON (1=1) ",
        " {executed in 1 msec}",
        "2026-01-02 09:06:34,702 http-exec-62  INFO [jdbc.sqltiming] SELECT 1 FROM DUAL ",
        " {executed in 1 msec}",
        "2026-01-02 09:06:34,703 http-exec-62 DEBUG [app.comm.model.DataMap] dataset dump",
        "\t\t\t<Col id=\"JOB_NO\">J1</Col>",
        "2026-01-02 09:06:34,704 http-exec-62 ERROR [app.M1.X] save failed",
        "java.lang.RuntimeException: boom",
        "\tat a.b.C(C.java:1)",
        "2026-01-02 09:06:34,705 http-exec-62 ERROR [%s] ======== Not Login or Session expire => Request URI : [/M1/save.do] / PUUID : [p1]" % INTERCEPTOR,
        # parenthesized thread form (no millis), other company request p2
        "2026-01-02 09:06:35 %s DEBUG [%s] ============= Request URI : [/M1/save.do] / PUUID : [p2] / SID : [s] / IP : [ip-b] / Member : [MemberVO [Group_ID=SCHEMA_B, Corp_ID=200, User_ID=user2]]" % (par % (7, 4), INTERCEPTOR),
        "2026-01-02 09:06:35 %s  INFO [jdbc.sqltiming] INSERT INTO SCHEMA_B.T VALUES (1) " % (par % (7, 4)),
        # requests without Member: target company SQL p3 / other company SQL p4
        "2026-01-02 09:06:36 %s DEBUG [%s] ============= Request URI : [/auth/login.do] / PUUID : [p3] / SID : [s] / IP : [ip-c]" % (par % (8, 5), INTERCEPTOR),
        "2026-01-02 09:06:36 %s  INFO [jdbc.sqltiming] INSERT INTO SCHEMA_A.LOGIN_HIST (CORP_ID) VALUES (1) WHERE CORP_ID=100 " % (par % (8, 5)),
        "2026-01-02 09:06:37 %s DEBUG [%s] ============= Request URI : [/auth/login.do] / PUUID : [p4] / SID : [s] / IP : [ip-d]" % (par % (9, 6), INTERCEPTOR),
        "2026-01-02 09:06:37 %s  INFO [jdbc.sqltiming] INSERT INTO SCHEMA_B.LOGIN_HIST (CORP_ID) VALUES ('200') WHERE CORP_ID = '1000' " % (par % (9, 6)),
    ]
    assert HEAD.match(lines[14]).group(2) == par % (7, 4)
    assert HEAD.match(lines[1]).group(3) == "INFO"
    assert sql_kind("/* A.b */ SELECT(1)")[0] == "SEL" and sql_kind("/*A.b*/ MERGE INTO X") == ("MRG", "A.b")
    found, total, outside = scan([("t", iter(lines))], "SCHEMA_A", "100", ["J1"], None, None, None)
    by = dict((r.puuid, r) for r in found)
    assert total == 4, total
    assert sorted(by) == ["p1", "p3"], sorted(by)
    p1 = by["p1"]
    assert (p1.cnt["UPD"], p1.cnt["MRG"], p1.cnt["INS"], p1.exc, p1.keyhit) == (1, 1, 0, 1, 1), (p1.cnt, p1.exc, p1.keyhit)
    assert by["p3"].cnt["INS"] == 1 and by["p3"].target_sql
    raw, _, _ = scan([("t", iter(lines))], None, None, [], None, None, "p1")
    kinds = [rec[2] for rec in raw[0].raw]
    assert kinds.count("jdbc.sqltiming") == 2, kinds  # SELECT excluded
    only_late, _, _ = scan([("t", iter(lines))], "SCHEMA_A", "100", [], "2026-01-02 09:06:35", None, None)
    assert [r.puuid for r in only_late] == ["p3"]
    print("selftest ok")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--group", help="schema (Group_ID)")
    ap.add_argument("--corp", help="company id (Corp_ID)")
    ap.add_argument("--from", dest="ts_from", help="'YYYY-MM-DD HH:mm[:ss]' inclusive (as printed in the log)")
    ap.add_argument("--to", dest="ts_to", help="'YYYY-MM-DD HH:mm[:ss]' exclusive")
    ap.add_argument("--key", action="append", default=[], help="body search key (repeatable)")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--puuid", help="raw mode")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        selftest()
        return 0
    if not INTERCEPTOR:
        ap.error("[log] interceptor is not set in .agents/harness.toml (logger class of the request start line)")
    if not a.files:
        ap.error("FILE required")
    if not a.puuid and not (a.group and a.corp):
        ap.error("--group and --corp required (or --puuid)")
    t0 = time.time()
    sources = (src for f in a.files for src in open_lines(f))
    found, total, outside = scan(sources, a.group, a.corp, a.key, a.ts_from, a.ts_to, a.puuid)
    if a.puuid:
        print_raw(found)
    else:
        print_summary(found, total, outside, a.limit, time.time() - t0, a.files)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
