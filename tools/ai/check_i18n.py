#!/usr/bin/env python3
"""Check that JSON locale catalogs stay in sync, without any model call.

Compares every locale against a reference locale (default: fr) and reports:
  missing  keys present in the reference but not in the locale
  extra    keys present in the locale but not in the reference
  params   strings whose placeholders differ ({name}, {0}, @:linked, <tag>, ICU)
  empty    empty strings

Layouts supported: <dir>/<lang>/<namespace>.json (Nuxt i18n split) and <dir>/<lang>.json.

Usage:
    python check_i18n.py <locales-dir> [--ref fr] [--json] [--missing-only LANG]
`--missing-only LANG` prints {key: reference text} for the keys LANG lacks: the
minimal input to hand a translator, instead of whole catalogs.
Exit code 1 when a problem is found (usable in CI or a test).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PLACEHOLDER = re.compile(r"\{\s*[\w.]+\s*(?:,[^{}]*)?\}|@:[\w.]+|</?[a-zA-Z][\w-]*>|%[sd]")


def flatten(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from flatten(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from flatten(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def load(root: Path) -> dict[str, dict[str, object]]:
    catalogs: dict[str, dict[str, object]] = {}
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        cat = catalogs.setdefault(d.name, {})
        for f in sorted(d.rglob("*.json")):
            ns = f.relative_to(d).with_suffix("").as_posix()
            cat.update({f"{ns}:{k}": v for k, v in flatten(json.loads(f.read_text(encoding="utf-8")))})
    for f in sorted(root.glob("*.json")):
        catalogs[f.stem] = dict(flatten(json.loads(f.read_text(encoding="utf-8"))))
    return catalogs


def params(value) -> list[str]:
    return sorted(re.sub(r"\s+", "", m) for m in PLACEHOLDER.findall(value)) if isinstance(value, str) else []


def check(catalogs, ref: str) -> dict[str, dict[str, list[str]]]:
    base = catalogs[ref]
    report = {}
    for lang, cat in catalogs.items():
        r = {
            "missing": sorted(set(base) - set(cat)) if lang != ref else [],
            "extra": sorted(set(cat) - set(base)) if lang != ref else [],
            "params": sorted(k for k in set(base) & set(cat) if lang != ref and params(base[k]) != params(cat[k])),
            "empty": sorted(k for k, v in cat.items() if v == ""),
        }
        report[lang] = {k: v for k, v in r.items() if v}
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", type=Path)
    ap.add_argument("--ref", default="fr")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--missing-only", metavar="LANG")
    a = ap.parse_args()
    catalogs = load(a.dir)
    if a.ref not in catalogs:
        print(f"reference locale '{a.ref}' not found in {a.dir}", file=sys.stderr)
        return 2
    report = check(catalogs, a.ref)
    if a.missing_only:
        todo = report.get(a.missing_only, {})
        keys = todo.get("missing", []) + todo.get("params", [])
        print(json.dumps({k: catalogs[a.ref][k] for k in keys}, ensure_ascii=False, indent=1))
        return 0
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        total = {lang: len(c) for lang, c in catalogs.items()}
        print("keys: " + ", ".join(f"{k} {v}" for k, v in total.items()))
        for lang, r in report.items():
            for kind, keys in r.items():
                print(f"{lang} {kind} ({len(keys)}): " + ", ".join(keys[:20]) + (" …" if len(keys) > 20 else ""))
        if not any(report.values()):
            print("OK: catalogs in sync")
    return 1 if any(report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
