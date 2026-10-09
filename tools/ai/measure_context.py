#!/usr/bin/env python3
"""Measure the context that AI agents load automatically in each repository.

Lists every agent instruction file (AGENTS.md, CLAUDE.md, Copilot instructions,
agent and skill definitions), plus the @imports CLAUDE.md pulls in, and reports
bytes, lines and an ESTIMATED token count (characters / 3.6, a rough ratio for
mixed French/English Markdown; it is not a tokenizer measurement).

Usage:
    python measure_context.py <repo> [<repo> ...] [--json]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

CHARS_PER_TOKEN = 3.6
PATTERNS = re.compile(
    r"(^|/)(AGENTS|CLAUDE|GEMINI)(\.override)?\.md$"
    r"|(^|/)\.github/copilot-instructions\.md$"
    r"|\.instructions\.md$"
    r"|(^|/)\.claude/(agents|commands|skills|rules)/.+\.md$"
    r"|(^|/)\.agents/skills/.+\.md$"
    r"|(^|/)\.github/agents/.+\.md$"
)
IMPORT_RE = re.compile(r"(?m)^\s*@([\w./\\-]+\.md)\s*$")


def tracked_files(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(repo), "ls-files"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def stats(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "bytes": len(text.encode("utf-8")),
        "lines": text.count("\n") + 1,
        "est_tokens": round(len(text) / CHARS_PER_TOKEN),
        "imports": IMPORT_RE.findall(text),
    }


def classify(rel: str) -> str:
    """When the file enters the context: always at start, on demand, or per path."""
    name = rel.rsplit("/", 1)[-1]
    if "/" not in rel and name in ("AGENTS.md", "CLAUDE.md", "AGENTS.override.md"):
        return "startup"
    if rel == ".github/copilot-instructions.md":
        return "startup(copilot)"
    if name in ("AGENTS.md", "CLAUDE.md"):
        return "on-entering-dir"
    if "/skills/" in rel and name == "SKILL.md":
        return "on-demand(description at startup)"
    if "/agents/" in rel:
        return "subagent-only"
    return "on-demand"


def measure(repo: Path) -> dict:
    rows = []
    for rel in tracked_files(repo):
        if not PATTERNS.search(rel):
            continue
        s = stats(repo / rel)
        s.update(path=rel, load=classify(rel))
        rows.append(s)
        # CLAUDE.md @imports are expanded at startup: count them as startup cost.
        for imp in s["imports"]:
            target = (repo / Path(rel).parent / imp).resolve()
            if target.is_file():
                t = stats(target)
                t.update(path=f"{rel} -> @{imp}", load="startup(import)" if s["load"] == "startup" else s["load"])
                rows.append(t)
    startup_claude = sum(r["est_tokens"] for r in rows if r["path"] in ("CLAUDE.md",) or r["path"].startswith("CLAUDE.md -> "))
    startup_codex = sum(r["est_tokens"] for r in rows if r["path"] in ("AGENTS.md", "AGENTS.override.md"))
    return {
        "repo": repo.name if repo.name != ".github" else f"{repo.parent.name}/.github",
        "files": rows,
        "startup_est_tokens": {"claude": startup_claude, "codex": startup_codex},
    }


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    repos = [Path(a) for a in argv if a != "--json"]
    if not repos:
        print(__doc__)
        return 2
    results = [measure(r) for r in repos]
    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
        return 0
    print(f"{'repo':28} {'claude@start':>12} {'codex@start':>11}  files")
    for r in results:
        st = r["startup_est_tokens"]
        print(f"{r['repo']:28} {st['claude']:>12} {st['codex']:>11}  {len(r['files'])}")
        for f in r["files"]:
            print(f"    {f['est_tokens']:>6} tok  {f['lines']:>4} l  {f['load']:<34} {f['path']}")
    print("(token counts are ESTIMATES: characters / 3.6)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
