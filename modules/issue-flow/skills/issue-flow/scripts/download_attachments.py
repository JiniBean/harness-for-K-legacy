#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Save Jira issue attachments to <project>/.agents/tmp. Never prints the token.

Settings come from harness.toml via ~/.agents/scripts/harness_config.py:
  [tracker] site               e.g. https://example.atlassian.net
  [paths]   jira_token_file    line 1 = Atlassian login email, line 2 = API token

Usage: python download_attachments.py KEY-1234
Exit: 0 ok / 2 token file missing or malformed, or settings missing / 1 HTTP or other error
"""
from __future__ import annotations

import base64
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# <project>/.agents, located from this file without assuming folder depth
AGENTS_DIR = next((p for p in Path(__file__).resolve().parents if p.name == ".agents"), None)
WIN_BAD = re.compile(r'[\\/:*?"<>|]')
KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d+$", re.I)
USAGE = "usage: download_attachments.py KEY-1234\n"


def load_settings():
    """Return (site, token_file) from harness.toml; exit 2 when missing."""
    if AGENTS_DIR is None:
        sys.stderr.write("<project>/.agents/skills/issue-flow/scripts 에 설치된 상태에서 실행하세요\n")
        sys.exit(2)
    sys.path.insert(0, str(Path.home() / ".agents" / "scripts"))
    try:
        import harness_config
    except ImportError:
        sys.stderr.write("harness_config.py 없음: ~/.agents/scripts 를 확인하세요\n")
        sys.exit(2)
    cfg = harness_config.load(AGENTS_DIR.parent)
    site = (cfg.get("tracker") or {}).get("site") or ""
    token_file = (cfg.get("paths") or {}).get("jira_token_file") or ""
    if not site or not token_file:
        sys.stderr.write("harness.toml 에 [tracker] site 와 [paths] jira_token_file 이 필요합니다\n")
        sys.exit(2)
    return site.rstrip("/"), Path(token_file).expanduser()


def token_path(token_file):
    for p in (token_file, token_file.with_name(token_file.name + ".txt")):
        if p.is_file():
            return p
    return token_file


def load_creds(token_file):
    path = token_path(token_file)
    if not path.is_file():
        sys.stderr.write("토큰 파일 없음: %s\n" % path)
        sys.exit(2)
    lines = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    if len(lines) < 2:
        sys.stderr.write("토큰 파일 형식 오류: 1행 이메일, 2행 API 토큰\n")
        sys.exit(2)
    return lines[0], lines[1]


def request(email, token, url, timeout=60, accept="application/json"):
    raw = ("%s:%s" % (email, token)).encode("utf-8")
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Basic " + base64.b64encode(raw).decode("ascii"))
    if accept:
        req.add_header("Accept", accept)
    return urllib.request.urlopen(req, timeout=timeout)


def safe_name(name):
    cleaned = WIN_BAD.sub("_", name).strip() or "attachment"
    return cleaned[:180]


def main(argv):
    if len(argv) == 2 and argv[1] in ("-h", "--help"):
        sys.stdout.write(__doc__)
        return 0
    if len(argv) != 2 or not KEY_RE.match(argv[1]):
        sys.stderr.write(USAGE)
        return 1
    key = argv[1].upper()
    site, token_file = load_settings()
    email, token = load_creds(token_file)
    url = "%s/rest/api/3/issue/%s?fields=attachment" % (site, key)
    try:
        with request(email, token, url, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        sys.stderr.write("issue GET HTTP %s\n" % err.code)
        return 1
    attachments = data.get("fields", {}).get("attachment") or []
    dest_dir = AGENTS_DIR / "tmp"
    dest_dir.mkdir(parents=True, exist_ok=True)
    if not attachments:
        sys.stdout.write("0\n")
        return 0
    saved = []
    for att in attachments:
        aid = att.get("id")
        fname = safe_name("%s_%s" % (key, att.get("filename") or aid))
        dest = dest_dir / fname
        content_url = "%s/rest/api/3/attachment/content/%s" % (site, aid)
        try:
            with request(email, token, content_url, timeout=120, accept="*/*") as resp:
                dest.write_bytes(resp.read())
        except urllib.error.HTTPError as err:
            sys.stderr.write("attachment %s HTTP %s\n" % (aid, err.code))
            return 1
        saved.append(str(dest))
    sys.stdout.write("%d\n%s\n" % (len(saved), "\n".join(saved)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
