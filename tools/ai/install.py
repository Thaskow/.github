#!/usr/bin/env python3
"""Install the shared agent configuration on this machine (idempotent).

Simulation by default: prints what would change. `--apply` writes, and keeps a
timestamped `.bak-*` copy of every file it replaces. `--uninstall` restores the
most recent backups (or removes files that did not exist before).

Installs, from this repo:
  ai/AGENTS.md (+ optional ~/.ai-local.md)  -> ~/.claude/CLAUDE.md, ~/.codex/AGENTS.md
  ai/claude/agents/*.md                     -> ~/.claude/agents/
  ai/skills/*/SKILL.md                      -> ~/.claude/skills/, ~/.codex/skills/
  ai/codex/*.config.toml                    -> ~/.codex/ (profiles: codex -p <name>)
  ai/claude/settings.json (keys only)       -> merged into ~/.claude/settings.json
`{{TOOLS}}` in those files is replaced by the absolute path of tools/ai.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOLS = (REPO / "tools" / "ai").as_posix()
HOME = Path.home()
LOCAL = HOME / ".ai-local.md"
MARK = "<!-- installé par Thaskow/.github/tools/ai/install.py : modifier la source, pas ce fichier -->\n"


def render(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("{{TOOLS}}", TOOLS)


def plan() -> list[tuple[Path, str]]:
    glob = render(REPO / "ai" / "AGENTS.md")
    if LOCAL.is_file():
        glob += "\n## Machine locale (~/.ai-local.md)\n\n" + LOCAL.read_text(encoding="utf-8")
    out = [(HOME / ".claude" / "CLAUDE.md", MARK + glob), (HOME / ".codex" / "AGENTS.md", MARK + glob)]
    for f in sorted((REPO / "ai" / "claude" / "agents").glob("*.md")):
        out.append((HOME / ".claude" / "agents" / f.name, render(f)))
    for f in sorted((REPO / "ai" / "skills").glob("*/SKILL.md")):
        for root in (HOME / ".claude" / "skills", HOME / ".codex" / "skills"):
            out.append((root / f.parent.name / "SKILL.md", render(f)))
    for f in sorted((REPO / "ai" / "codex").glob("*.config.toml")):
        out.append((HOME / ".codex" / f.name, render(f)))
    settings = HOME / ".claude" / "settings.json"
    wanted = json.loads((REPO / "ai" / "claude" / "settings.json").read_text(encoding="utf-8"))
    current = json.loads(settings.read_text(encoding="utf-8")) if settings.is_file() else {}
    merged = json.loads(json.dumps(current))
    for key, value in wanted.items():
        if isinstance(value, dict):
            merged.setdefault(key, {}).update(value)
        else:
            merged[key] = value
    out.append((settings, json.dumps(merged, ensure_ascii=False, indent=2) + "\n"))
    return out


def backups(path: Path) -> list[Path]:
    return sorted(path.parent.glob(path.name + ".bak-*"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    changed = 0
    for path, content in plan():
        if a.uninstall:
            prev = backups(path)
            if prev:
                print(f"restore {path} <- {prev[-1].name}")
                if a.apply:
                    shutil.copy2(prev[-1], path)
            elif path.is_file() and path.name != "settings.json":
                print(f"remove  {path}")
                if a.apply:
                    path.unlink()
            continue
        old = path.read_text(encoding="utf-8") if path.is_file() else None
        if old == content:
            continue
        changed += 1
        print(f"{'update' if old is not None else 'create'} {path}")
        if a.apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            if old is not None:
                shutil.copy2(path, path.with_name(f"{path.name}.bak-{stamp}"))
            path.write_text(content, encoding="utf-8", newline="\n")
    if not a.uninstall:
        print(f"{changed} file(s) {'written' if a.apply else 'to write (simulation, add --apply)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
