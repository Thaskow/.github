#!/usr/bin/env python3
"""Report MEASURED token usage from local Claude Code and Codex session logs.

Reads ~/.claude/projects/**/*.jsonl (Claude Code) and ~/.codex/sessions/**/*.jsonl
(Codex). Every number is read from the usage fields the tools record; the dollar
column is an API-price equivalent (a subscription bills differently), computed
from the PRICES table below.

Usage:
    python usage_report.py [--since YYYY-MM-DD] [--json] [--top N]
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

HOME = Path.home()
# $ per million tokens: input, output, cache write (5 min = 1.25 x input), cache read.
# Source: Anthropic price list, cached 2026-10-06. Update when prices change.
PRICES = {
    "opus": (4.00, 20.00, 5.00, 0.20),
    "sonnet": (2.00, 10.00, 2.50, 0.20),
    "haiku": (0.10, 0.50, 0.125, 0.01),
    "fable": (10.00, 50.00, 12.50, 0.25),
}


def family(model: str) -> str:
    for name in PRICES:
        if name in model:
            return name
    return "other"


def cost(model: str, u: dict) -> float:
    p = PRICES.get(family(model))
    if not p:
        return 0.0
    return (
        u.get("input_tokens", 0) * p[0]
        + u.get("output_tokens", 0) * p[1]
        + u.get("cache_creation_input_tokens", 0) * p[2]
        + u.get("cache_read_input_tokens", 0) * p[3]
    ) / 1e6


def claude_sessions(since: str | None):
    root = HOME / ".claude" / "projects"
    by_session: dict[str, dict] = {}
    for path in root.rglob("*.jsonl"):
        seen: set[str] = set()
        for line in path.open(encoding="utf-8", errors="replace"):
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = rec.get("timestamp", "")
            if since and ts and ts[:10] < since:
                continue
            sid = rec.get("sessionId") or path.stem
            s = by_session.setdefault(sid, {
                "session": sid, "project": path.parent.name if path.parent != root else "", "start": ts,
                "models": collections.Counter(), "usage": collections.Counter(), "cost": 0.0,
                "tools": collections.Counter(), "tool_result_chars": collections.Counter(),
                "subagent_requests": 0, "requests": 0, "first_context": None,
            })
            if ts and (not s["start"] or ts < s["start"]):
                s["start"] = ts
            msg = rec.get("message") or {}
            if rec.get("type") == "assistant" and isinstance(msg, dict) and msg.get("usage"):
                # One API response is logged as one record per content block, each
                # repeating the same usage: count usage once, but scan every block.
                mid = msg.get("id")
                if mid not in seen:
                    seen.add(mid)
                    u = msg["usage"]
                    model = msg.get("model", "?")
                    s["requests"] += 1
                    s["models"][model] += 1
                    if rec.get("isSidechain"):
                        s["subagent_requests"] += 1
                    for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
                        s["usage"][k] += u.get(k, 0) or 0
                    s["cost"] += cost(model, u)
                    if s["first_context"] is None and not rec.get("isSidechain"):
                        s["first_context"] = sum(u.get(k, 0) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                for block in msg.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        s["tools"][block.get("name", "?")] += 1
            elif rec.get("type") == "user" and isinstance(msg, dict):
                for block in msg.get("content") or [] if isinstance(msg.get("content"), list) else []:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        c = block.get("content")
                        size = len(json.dumps(c, ensure_ascii=False)) if not isinstance(c, str) else len(c)
                        name = (rec.get("toolUseResult") or {}).get("type", "") if isinstance(rec.get("toolUseResult"), dict) else ""
                        s["tool_result_chars"][name or "result"] += size
    return [s for s in by_session.values() if s["requests"]]


def codex_sessions(since: str | None):
    out = []
    for root in (HOME / ".codex" / "sessions", HOME / ".codex" / "archived_sessions"):
        for path in root.rglob("*.jsonl"):
            last, first, start, model, calls = None, None, "", "", collections.Counter()
            for line in path.open(encoding="utf-8", errors="replace"):
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                start = start or rec.get("timestamp", "")
                p = rec.get("payload") or {}
                if rec.get("type") == "turn_context":
                    model = p.get("model", model)
                if p.get("type") == "token_count" and p.get("info"):
                    last = p["info"]["total_token_usage"]
                    first = first or p["info"]["last_token_usage"]
                if p.get("type") in ("function_call", "custom_tool_call", "local_shell_call"):
                    calls[p.get("name", p.get("type"))] += 1
            if last and not (since and start[:10] < since):
                out.append({"session": path.stem[-36:], "start": start, "model": model, "usage": last,
                            "first_context": first.get("input_tokens") if first else None, "tools": calls})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()
    cl = claude_sessions(a.since)
    cx = codex_sessions(a.since)
    if a.json:
        print(json.dumps({"claude": cl, "codex": cx}, default=dict, ensure_ascii=False, indent=1))
        return 0

    tot = collections.Counter()
    models = collections.Counter()
    tools = collections.Counter()
    results = collections.Counter()
    total_cost = sub = req = 0
    for s in cl:
        tot.update(s["usage"])
        models.update(s["models"])
        tools.update(s["tools"])
        results.update(s["tool_result_chars"])
        total_cost += s["cost"]
        sub += s["subagent_requests"]
        req += s["requests"]
    print(f"CLAUDE CODE — {len(cl)} sessions, {req} model requests ({sub} by subagents)")
    print(f"  input {tot['input_tokens']:,} · cache write {tot['cache_creation_input_tokens']:,} · cache read {tot['cache_read_input_tokens']:,} · output {tot['output_tokens']:,}")
    print(f"  API-equivalent cost ${total_cost:,.2f}")
    print("  requests per model: " + ", ".join(f"{m} {n}" for m, n in models.most_common()))
    print("  tool calls: " + ", ".join(f"{t} {n}" for t, n in tools.most_common(12)))
    fc = sorted(s["first_context"] for s in cl if s["first_context"])
    if fc:
        print(f"  context at first request (tokens): min {fc[0]:,} · median {fc[len(fc)//2]:,} · max {fc[-1]:,}")
    print(f"  tool output returned to the model: {sum(results.values())/1e6:.2f} M chars (~{sum(results.values())/3.6/1e3:,.0f}k tokens est.)")
    print(f"\n  top {a.top} sessions by cost:")
    for s in sorted(cl, key=lambda s: -s["cost"])[: a.top]:
        u = s["usage"]
        print(f"   {s['start'][:10]} {s['session'][:8]} ${s['cost']:7.2f}  req {s['requests']:4} (sub {s['subagent_requests']:3})  "
              f"read {u['cache_read_input_tokens']/1e6:6.2f}M  out {u['output_tokens']/1e3:6.0f}k  {dict(s['models'].most_common(2))}")

    if cx:
        ctot = collections.Counter()
        for s in cx:
            ctot.update({k: v for k, v in s["usage"].items() if isinstance(v, int)})
        print(f"\nCODEX — {len(cx)} sessions (models: {collections.Counter(s['model'] for s in cx)})")
        print(f"  input {ctot['input_tokens']:,} (cached {ctot['cached_input_tokens']:,}) · output {ctot['output_tokens']:,} (reasoning {ctot['reasoning_output_tokens']:,})")
        fc = sorted(s["first_context"] for s in cx if s["first_context"])
        if fc:
            print(f"  context at first request (tokens): min {fc[0]:,} · median {fc[len(fc)//2]:,} · max {fc[-1]:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
