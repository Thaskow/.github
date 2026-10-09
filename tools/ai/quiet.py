#!/usr/bin/env python3
"""Run a command, keep its full output in a log file, print only what matters.

An agent pays for every line of output it reads, on every following request.
This wrapper prints the exit code, the lines that look like errors or failures
(with a little context) and the last lines, and saves the full log for a
targeted read when needed. Nothing is hidden: when the command fails and no
error line is recognised, more of the tail is shown.

Usage:
    python quiet.py [--tail N] [--log FILE] -- <command> [args...]
Examples:
    python quiet.py -- npm run test
    python quiet.py --tail 40 -- npx vue-tsc --noEmit
The log goes to <git dir>/ai-logs/ (never committed) or the temp directory.
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ERROR = re.compile(
    r"(\berror\b|\bERR!|\bfail(ed|ure)?\b|\bFAIL\b|✗|×|\bexception\b|traceback|panic|"
    r"\bwarning TS|error TS\d+|AssertionError|Expected|Received|exit code [1-9])",
    re.IGNORECASE,
)
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
CONTEXT = 2
CONTEXT_AFTER = 8  # assertion diffs and stack frames follow the error line
MAX_ERROR_LINES = 80


def log_dir() -> Path:
    try:
        git = subprocess.run(["git", "rev-parse", "--absolute-git-dir"], capture_output=True, text=True, check=True).stdout.strip()
        d = Path(git) / "ai-logs"
    except (subprocess.CalledProcessError, FileNotFoundError):
        d = Path(tempfile.gettempdir()) / "ai-logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def main() -> int:
    argv = sys.argv[1:]
    if "--" not in argv:
        print(__doc__)
        return 2
    split = argv.index("--")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tail", type=int, default=15)
    ap.add_argument("--log", type=Path)
    a = ap.parse_args(argv[:split])
    cmd = argv[split + 1:]
    log = a.log or log_dir() / f"{time.strftime('%Y%m%d-%H%M%S')}-{re.sub(r'[^A-Za-z0-9]+', '-', ' '.join(cmd))[:40]}.log"

    start = time.time()
    # shell=True on Windows so that npm/npx (.cmd shims) resolve like in a terminal.
    proc = subprocess.run(
        subprocess.list2cmdline(cmd) if os.name == "nt" else cmd,
        shell=os.name == "nt", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "FORCE_COLOR": "0", "NO_COLOR": "1", "CI": os.environ.get("CI", "1")},
    )
    text = ANSI.sub("", proc.stdout.decode("utf-8", errors="replace"))
    log.write_text(text, encoding="utf-8")
    lines = text.splitlines()

    keep: set[int] = set()
    for i, line in enumerate(lines):
        if ERROR.search(line):
            keep.update(range(max(0, i - CONTEXT), min(len(lines), i + CONTEXT_AFTER + 1)))
    errors = sorted(keep)
    tail = a.tail if proc.returncode == 0 or errors else max(a.tail, 60)

    print(f"$ {shlex.join(cmd)}")
    print(f"exit {proc.returncode} · {len(lines)} lines · {time.time() - start:.1f}s · full log: {log}")
    if errors and proc.returncode != 0:
        shown = errors[:MAX_ERROR_LINES]
        print(f"--- error lines ({len(errors)} with context{', first ' + str(MAX_ERROR_LINES) if len(errors) > MAX_ERROR_LINES else ''})")
        prev = None
        for i in shown:
            if prev is not None and i != prev + 1:
                print("  …")
            print(lines[i])
            prev = i
    shown_until = errors[:MAX_ERROR_LINES][-1] if errors and proc.returncode != 0 else -1
    first_tail = max(len(lines) - tail, shown_until + 1)
    if first_tail < len(lines):
        print(f"--- last {len(lines) - first_tail} lines")
        print("\n".join(lines[first_tail:]))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
