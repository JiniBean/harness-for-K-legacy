#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aggregate a searchJiraIssuesUsingJql response JSON into the issue-flow skill's section 1/2 tables.

Usage:
  python aggregate_assigned.py <mcp-json> [--start-status NAME] [--status-order "A,B,C"] [--sort-field NAME]
  python aggregate_assigned.py            (no args: self-check)

  --start-status  status whose issues are start candidates (default: every issue)
  --status-order  workflow order of status names for the count table (default: name order)
  --sort-field    [tracker.fields] name from harness.toml, or a raw field id;
                  candidates sort by it, then duedate, then key (default: duedate, key)
Exit: 0 ok / 1 argument, file or JSON error
"""
from __future__ import print_function

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

MISSING = "*(미입력)*"


def resolve_field(name):
    """Map a [tracker.fields] name to its id; return the name unchanged if not configured."""
    if not name:
        return None
    sys.path.insert(0, str(Path.home() / ".agents" / "scripts"))
    try:
        import harness_config
    except ImportError:
        return name
    agents = next((p for p in Path(__file__).resolve().parents if p.name == ".agents"), None)
    cfg = harness_config.load(agents.parent if agents else None)
    fields = (cfg.get("tracker") or {}).get("fields") or {}
    return fields.get(name) or name


def status_rows(status_counts, order):
    """Yield (name, count) in the given order; unknown names last, A-Z."""
    known = set(order)
    for name in order:
        if name in status_counts:
            yield name, status_counts[name]
    for name in sorted(n for n in status_counts if n not in known):
        yield name, status_counts[name]


def sort_key(row):
    due = row["due"] if row["due"] else "9999-99-99"
    duedate = row["duedate"] if row["duedate"] else "9999-99-99"
    return (due, duedate, row["key"])


def mmdd(val):
    if val is None or val == "":
        return MISSING
    s = val.strip() if isinstance(val, str) else str(val)
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[5:10]
    return s


def page_info(data):
    """(issues, nextPageToken, isLast). Newer MCP responses use issues.nodes + issues.pageInfo."""
    issues = data.get("issues") or []
    if isinstance(issues, dict):
        page = issues.get("pageInfo") or {}
        has_next = page.get("hasNextPage")
        return (
            issues.get("nodes") or [],
            page.get("endCursor"),
            None if has_next is None else not has_next,
        )
    return issues, data.get("nextPageToken"), data.get("isLast")


def blank_to_none(val):
    if isinstance(val, dict):
        val = val.get("value") or val.get("name")
    if isinstance(val, str) and not val.strip():
        return None
    return val or None


def aggregate(data, start_status=None, sort_field=None):
    issues, next_page_token, is_last = page_info(data)
    status_counts = Counter()
    review = []
    for iss in issues:
        fields = iss.get("fields") or {}
        status = ((fields.get("status") or {}).get("name")) or ""
        status_counts[status] += 1
        if start_status and status != start_status:
            continue
        review.append(
            {
                "key": iss.get("key") or "",
                "summary": (fields.get("summary") or "").strip(),
                "reporter": (fields.get("reporter") or {}).get("displayName") or "",
                "due": blank_to_none(fields.get(sort_field)) if sort_field else None,
                "duedate": blank_to_none(fields.get("duedate")),
            }
        )
    review.sort(key=sort_key)
    return status_counts, review, len(issues), next_page_token, is_last


def emit(status_counts, review, total, next_page_token, is_last, order):
    print("TOTAL\t%s" % total)
    print("nextPageToken\t%s" % (next_page_token if next_page_token else ""))
    print("isLast\t%s" % is_last)
    print("---STATUS---")
    for name, count in status_rows(status_counts, order):
        print("%s\t%s" % (name, count))
    print("---REVIEW---")
    print("#\tkey\tsummary\treporter\tsort_field\tduedate")
    for i, row in enumerate(review, 1):
        print(
            "%s\t%s\t%s\t%s\t%s\t%s"
            % (
                i,
                row["key"],
                row["summary"].replace("\t", " "),
                row["reporter"].replace("\t", " "),
                mmdd(row["due"]),
                mmdd(row["duedate"]),
            )
        )
    print("---REVIEW_COUNT---")
    print(len(review))


def main(argv):
    parser = argparse.ArgumentParser(description="Aggregate assigned issues JSON")
    parser.add_argument("json_path", help="path to searchJiraIssuesUsingJql JSON file")
    parser.add_argument("--start-status", default=None)
    parser.add_argument("--status-order", default="")
    parser.add_argument("--sort-field", default=None)
    args = parser.parse_args(argv[1:])

    try:
        with open(args.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except IOError as err:
        sys.stderr.write("cannot read %s: %s\n" % (args.json_path, err))
        return 1
    except ValueError as err:
        sys.stderr.write("invalid JSON %s: %s\n" % (args.json_path, err))
        return 1

    order = [s.strip() for s in args.status_order.split(",") if s.strip()]
    result = aggregate(data, args.start_status, resolve_field(args.sort_field))
    emit(*result, order=order)
    return 0


def self_check():
    rows = list(status_rows(Counter({"Done": 9, "To Do": 5, "Review": 10, "Other": 1}),
                            ["To Do", "In Progress", "Review", "Done"]))
    assert [r[0] for r in rows] == ["To Do", "Review", "Done", "Other"], rows
    nodes = {"issues": {"nodes": [{"key": "K-1", "fields": {}}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None}}}
    assert page_info(nodes) == ([{"key": "K-1", "fields": {}}], None, True)
    assert mmdd("2026-10-28") == "10-28"
    assert mmdd(None) == MISSING
    data = {"issues": [
        {"key": "K-3", "fields": {"status": {"name": "To Do"}, "cf_due": "2026-10-29", "duedate": "2026-09-18"}},
        {"key": "K-2", "fields": {"status": {"name": "To Do"}, "cf_due": "2026-10-28", "duedate": "2026-09-18"}},
        {"key": "K-1", "fields": {"status": {"name": "To Do"}, "cf_due": "2026-10-29", "duedate": "2026-09-11"}},
        {"key": "K-9", "fields": {"status": {"name": "To Do"}, "cf_due": "", "duedate": None}},
        {"key": "K-5", "fields": {"status": {"name": "Done"}}},
    ]}
    counts, review, total, _, _ = aggregate(data, "To Do", "cf_due")
    assert total == 5 and counts["Done"] == 1
    assert [r["key"] for r in review] == ["K-2", "K-1", "K-3", "K-9"], review
    _, review_all, _, _, _ = aggregate(data)
    assert len(review_all) == 5
    sys.stdout.write("self-check ok\n")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        self_check()
        raise SystemExit(0)
    raise SystemExit(main(sys.argv) or 0)
