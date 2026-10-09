#!/usr/bin/env python3
"""Replay real Claude Code sessions under a lower auto-compaction window.

For every main-thread request of each recorded session, takes the measured
context size and the measured growth since the previous request, then replays
that growth with a context cap: when the context would pass the cap it is
compacted to the session's initial context plus a summary (SUMMARY tokens), and
the compaction itself is billed (reading the context once, writing the summary).
Output tokens and the number of requests are kept as measured.

This is a SIMULATION on measured data, not a measurement: it ignores that a
compacted session may need extra reads to recover lost detail (REREAD_PER_COMPACTION
models that cost, set it to taste).

Usage: python simulate_compaction.py [--windows 150000 200000 300000 400000]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PRICE_READ, PRICE_WRITE, PRICE_OUT = 0.20, 5.00, 20.00  # Opus 5.5, $ per MTok
SUMMARY = 12_000
REREAD_PER_COMPACTION = 30_000  # tokens of files read again after a compaction (assumption)


def sessions():
    for path in (Path.home() / ".claude" / "projects").rglob("*.jsonl"):
        seen, ctx = set(), []
        for line in path.open(encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            m = r.get("message") or {}
            if r.get("type") != "assistant" or r.get("isSidechain") or not isinstance(m, dict) or not m.get("usage"):
                continue
            if m.get("id") in seen:
                continue
            seen.add(m["id"])
            u = m["usage"]
            ctx.append((u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0), u.get("output_tokens", 0)))
        if len(ctx) > 2:
            yield path.stem[:8], ctx


def cost(ctx, window):
    base = ctx[0][0]
    cur, total, compactions = base, 0.0, 0
    prev = base
    for size, out in ctx:
        growth = size - prev if size >= prev else size - base  # a real compaction already happened
        prev = size
        new = cur + max(growth, 0)
        if window and new > window:
            total += new * PRICE_READ / 1e6 + SUMMARY * PRICE_OUT / 1e6  # compaction request
            compactions += 1
            new = base + SUMMARY + REREAD_PER_COMPACTION
            total += (SUMMARY + REREAD_PER_COMPACTION) * PRICE_WRITE / 1e6
        total += new * PRICE_READ / 1e6 + max(growth, 0) * (PRICE_WRITE - PRICE_READ) / 1e6 + out * PRICE_OUT / 1e6
        cur = new
    return total, compactions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", type=int, nargs="*", default=[150_000, 200_000, 300_000, 400_000])
    a = ap.parse_args()
    data = list(sessions())
    base_total = sum(cost(c, 0)[0] for _, c in data)
    print(f"{len(data)} sessions · model of current behaviour (no extra cap): ${base_total:,.2f}")
    for w in a.windows:
        t = sum(cost(c, w)[0] for _, c in data)
        n = sum(cost(c, w)[1] for _, c in data)
        print(f"window {w:>9,}: ${t:8,.2f}  ({(t - base_total) / base_total:+.0%})  compactions {n}")


if __name__ == "__main__":
    main()
