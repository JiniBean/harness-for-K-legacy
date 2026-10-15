# -*- coding: utf-8 -*-
"""shell (beforeShellExecution / PreToolUse Bash): generic shell bypass guard.

Built-in rules: python -c, secrets dir, hook script/state writes, hook registration
writes, blocked hosts, FTP uploads. Module-specific regexes come from harness.toml
[guard] shell_block_patterns (set-up-harness merges each module's fragment there).
"""
from __future__ import print_function

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hook_io import (
    command_from,
    emit_allow,
    emit_deny,
    guard_config,
    log_error,
    protected_hook_basenames,
    run_guard,
)

_GUARD = guard_config()
# Hosts the shell may not reach directly (DB, servers reachable through MCP tools only)
BLOCK_HOSTS = tuple(str(h) for h in _GUARD.get("block_hosts") or ())

# Protected hook scripts may be neither named under a hook dir nor written. The
# generator may be run (it re-checks required guards) but not overwritten.
_HOOK_NAMES = sorted(
    re.escape(n[:-3] if n.endswith(".py") else n)
    for n in protected_hook_basenames()
    if n != "gen_hook_configs.py"
)

BLOCK_RES = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\.agents[\\/]+secrets\b",  # default harness secrets_dir; configured dir added below
        r"harness_config\.py[^\n]*\b(?:secret|secret_path)\b",
        r"hook_edit_approved\.json",
        r"(?:^|[\s\\/\"'=])\.(?:agents|cursor|claude|codex)[\\/]hooks[\\/](?:%s)" % "|".join(_HOOK_NAMES),
        r"(?:>|\b(?:cp|mv|copy|move|Copy-Item|Move-Item|Set-Content|Out-File|Add-Content|tee|sed\s+-i)\b[^\n]*)gen_hook_configs\.py",
    )
]


def _extra_patterns():
    """[guard] shell_block_patterns: module regexes (bad entries are logged and skipped)."""
    out = []
    for p in _GUARD.get("shell_block_patterns") or ():
        try:
            out.append(re.compile(str(p), re.IGNORECASE))
        except re.error as exc:
            log_error("shell_guard bad shell_block_patterns entry %r: %s" % (p, exc))
    return out


BLOCK_RES.extend(_extra_patterns())


def _configured_secrets_re():
    try:
        sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".agents", "scripts"))
        import harness_config

        parts = [p for p in re.split(r"[\\/]+", str(harness_config.secrets_dir())) if p]
        return re.compile(r"[\\/]+".join(re.escape(p) for p in parts), re.IGNORECASE)
    except Exception:
        return None


_SECRETS_RE = _configured_secrets_re()
if _SECRETS_RE is not None:
    BLOCK_RES.append(_SECRETS_RE)

# FTP hosts: write-like shell commands naming them are denied
FTP_HOSTS = tuple(str(h) for h in _GUARD.get("ftp_hosts") or ())

WRITE_RES = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bftp\b[\s\S]{0,200}\b(put|send|rename|delete|mkdir|rmdir|mput)\b",
        r"\b(put|send|rename|delete|mkdir|rmdir|mput)\b[\s\S]{0,200}\bftp\b",
        r"curl\s+[^\n]*(-T|--upload-file)\b",
        r"\bwinscp\b[\s\S]{0,300}\b(put|mv|rm|mkdir)\b",
    )
]

# python/py/pythonw -c: PowerShell 5.1 parses the string before Python.
PYTHON_C_RE = re.compile(
    r"(?i)\b(?:py|pythonw|python(?:\d+(?:\.\d+)*)?)(?:\.exe)?\s+-c\b"
)

# Redirect/cmdlet must target the path — not bare ">" elsewhere (e.g. chcp > $null).
_REDIR_TO = (
    r"(?i)(?:^|[^0-9<>])>{1,2}\s*(?:['\"]|\./|\\.\\|/|[A-Za-z]:\\)?"
    r"[^'\"\n;|&<>]*%s"
)
_CMDLET_TO = (
    r"(?i)\b(?:set-content|out-file|add-content)\b[\s\S]{0,240}%s"
)


def _shell_writes_path(command, path_regex_fragment):
    """True if Shell redirects or Set-Content/Out-File/Add-Content targets path."""
    if not command:
        return False
    if re.search(_REDIR_TO % path_regex_fragment, command):
        return True
    if re.search(_CMDLET_TO % path_regex_fragment, command):
        return True
    return False


def _mentions_ftp_host(command):
    for host in FTP_HOSTS:
        if host in command:
            return host
    return None


def guard(data):
    command = command_from(data) or ""
    lower = command.lower()

    if PYTHON_C_RE.search(command):
        emit_deny(
            "Write로 .py를 만든 뒤 python path\\to\\file.py만 실행하세요.",
            "Shell blocked: python/py/pythonw -c.",
        )
        return None

    for host in BLOCK_HOSTS:
        if host in command:
            emit_deny(
                "차단 호스트(DB 등)에 Shell로 직접 접속할 수 없습니다. MCP 도구만 사용하세요.",
                "Shell blocked: blocked host %s in command." % host,
            )
            return None

    for rx in BLOCK_RES:
        if rx.search(command):
            emit_deny(
                "비밀·훅 상태·직접 접속 우회 Shell은 차단됩니다. 해당 MCP 도구나 스크립트를 사용하세요.",
                "Shell blocked by shell_guard pattern: %s" % rx.pattern,
            )
            return None

    if _shell_writes_path(command, r"[\\/]hooks[\\/]state[\\/]"):
        emit_deny(
            "훅/승인 상태 파일에 대한 Shell 쓰기는 차단됩니다.",
            "Shell blocked: attempt to write hook state.",
        )
        return None

    if _shell_writes_path(command, r"hooks\.(?:json|toml)"):
        emit_deny(
            "hooks.json/hooks.toml Shell 쓰기는 차단됩니다. Write 도구 + path_guard 이름 검사를 사용하세요.",
            "Shell blocked: hooks.json/hooks.toml write.",
        )
        return None

    if _shell_writes_path(command, r"[\\/]\.claude[\\/]settings(?:\.local)?\.json"):
        emit_deny(
            ".claude/settings.json Shell 쓰기는 차단됩니다. Write 도구 + path_guard 이름 검사를 사용하세요.",
            "Shell blocked: .claude/settings(.local).json write.",
        )
        return None

    for rx in WRITE_RES:
        if rx.search(command):
            host = _mentions_ftp_host(command)
            emit_deny(
                "Agent Shell에서 FTP 업로드/변경은 차단됩니다. 로그는 FTP MCP(읽기)만 사용하세요.",
                "ftp shell_guard blocked pattern=%s host=%s" % (rx.pattern, host),
            )
            return None

    host = _mentions_ftp_host(command)
    if host and (
        ("-t " in lower)
        or ("--upload-file" in lower)
        or re.search(r"\bput\b", lower)
    ):
        emit_deny(
            "운영/참고 FTP 호스트로의 Shell 업로드는 차단됩니다.",
            "ftp shell_guard blocked upload toward host %s" % host,
        )
        return None

    emit_allow()
    return None


if __name__ == "__main__":
    # strict_stdin=True: empty/BOM-corrupt payload must deny, not soft-allow.
    raise SystemExit(run_guard(guard, strict_stdin=True) or 0)
