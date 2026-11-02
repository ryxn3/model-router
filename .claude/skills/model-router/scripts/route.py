#!/usr/bin/env python3
"""Price a routed task plan, print the switch plan, and log it for the savings report.

Usage:
  route.py PLAN.json [--current MODEL] [--dry-run]
  cat PLAN.json | route.py - [--dry-run]

PLAN.json:
  {
    "task": "short label",
    "current_model": "opus",        # what the user has selected right now
    "baseline_model": "opus",       # optional: what they would otherwise run on
    "segments": [
      {"name": "design the cache", "tier": "opus", "why": "trade-offs",
       "input_tokens": 2000, "output_tokens": 800},
      {"name": "write the tests", "tier": "haiku", "why": "mechanical",
       "input_chars": 6000, "output_chars": 3000}   # chars are converted at ~4 chars/token
    ]
  }

Set MODEL_ROUTER_LEDGER to change where plans are logged.
Default: ./.claude/model-router/ledger.jsonl (relative to the working directory).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PRICING_FILE = SKILL_DIR / "pricing.json"
DEFAULT_LEDGER = Path(os.environ.get("MODEL_ROUTER_LEDGER") or Path.cwd() / ".claude" / "model-router" / "ledger.jsonl")
TIERS = ["haiku", "sonnet", "opus"]  # cheapest -> most capable
RANK = {t: i for i, t in enumerate(TIERS)}
CHARS_PER_TOKEN = 4


def die(msg: str) -> None:
    sys.exit(f"route.py: {msg}")


def load_pricing() -> dict:
    try:
        data = json.loads(PRICING_FILE.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        die(f"cannot read {PRICING_FILE}: {exc}")
    missing = [t for t in TIERS if t not in data]
    if missing:
        die(f"pricing.json is missing {missing}")
    return data


def model_name(value, field: str) -> str:
    name = str(value).strip().lower()
    if name not in RANK:
        die(f"{field}: {value!r} is not one of {TIERS}")
    return name


def tokens(seg: dict, kind: str) -> int:
    if f"{kind}_tokens" in seg:
        return max(0, int(seg[f"{kind}_tokens"]))
    if f"{kind}_chars" in seg:
        return max(0, round(int(seg[f"{kind}_chars"]) / CHARS_PER_TOKEN))
    return 0


def cost(tier: str, tin: int, tout: int, pricing: dict) -> float:
    p = pricing[tier]
    return (tin * p["input"] + tout * p["output"]) / 1_000_000


def label(parts: list[int]) -> str:
    """1-based part numbers as '2' or '2-4'."""
    return f"{parts[0] + 1}" if len(parts) == 1 else f"{parts[0] + 1}-{parts[-1] + 1}"


def analyse(plan: dict, pricing: dict, current_override: str | None) -> dict:
    current = model_name(current_override or plan.get("current_model", "sonnet"), "current_model")
    baseline = model_name(plan.get("baseline_model", current), "baseline_model")
    raw = plan.get("segments") or []
    if not raw:
        die("plan has no segments")

    segments = []
    for i, s in enumerate(raw, 1):
        tier = model_name(s.get("tier", ""), f"segment {i} tier")
        tin, tout = tokens(s, "input"), tokens(s, "output")
        segments.append({
            "name": s.get("name") or f"part {i}",
            "why": s.get("why", ""),
            "tier": tier,
            "input_tokens": tin,
            "output_tokens": tout,
            "baseline_cost": cost(baseline, tin, tout, pricing),
            "routed_cost": cost(tier, tin, tout, pricing),
        })

    # A run is a block of consecutive parts on the same tier. Every boundary is a model switch.
    runs: list[dict] = []
    for idx, seg in enumerate(segments):
        if runs and runs[-1]["tier"] == seg["tier"]:
            runs[-1]["parts"].append(idx)
        else:
            runs.append({"tier": seg["tier"], "parts": [idx]})

    first = runs[0]
    if first["tier"] == current:
        next_step = f"Run part {label(first['parts'])} on {current} now."
    else:
        next_step = (f"PAUSE: switch to {first['tier']} (/model {first['tier']}) for part "
                     f"{label(first['parts'])}, then say continue.")

    baseline_cost = sum(s["baseline_cost"] for s in segments)
    routed_cost = sum(s["routed_cost"] for s in segments)
    tokens_total = sum(s["input_tokens"] + s["output_tokens"] for s in segments)
    tokens_down = sum(s["input_tokens"] + s["output_tokens"]
                      for s in segments if RANK[s["tier"]] < RANK[baseline])

    return {
        "id": uuid.uuid4().hex[:8],
        "ts": int(time.time()),
        "task": plan.get("task") or "untitled task",
        "current_model": current,
        "baseline_model": baseline,
        "segments": segments,
        "runs": [{"tier": r["tier"], "parts": [p + 1 for p in r["parts"]]} for r in runs],
        "next_step": next_step,
        "baseline_cost": baseline_cost,
        "routed_cost": routed_cost,
        "saved": baseline_cost - routed_cost,
        "tokens_total": tokens_total,
        "tokens_downgraded": tokens_down,
    }


def money(x: float) -> str:
    if x == 0:
        return "$0.00"
    return f"${x:,.2f}" if abs(x) >= 0.01 else f"${x:,.4f}"


def print_summary(rec: dict) -> None:
    pct = (rec["saved"] / rec["baseline_cost"] * 100) if rec["baseline_cost"] else 0.0
    print(f"Task: {rec['task']}  (id {rec['id']})")
    print(f"Current model: {rec['current_model']}   Baseline: {rec['baseline_model']}")
    print()
    print(f"{'#':>2}  {'part':<28} {'tier':<7} {'tokens':>9} {'baseline':>10} {'routed':>10}  why")
    for i, s in enumerate(rec["segments"], 1):
        toks = s["input_tokens"] + s["output_tokens"]
        print(f"{i:>2}  {s['name'][:28]:<28} {s['tier']:<7} {toks:>9,} "
              f"{money(s['baseline_cost']):>10} {money(s['routed_cost']):>10}  {s['why']}")
    print()
    print(f"Total: baseline {money(rec['baseline_cost'])}  routed {money(rec['routed_cost'])}  "
          f"saved {money(rec['saved'])} ({pct:.0f}%)")
    print(f"Tokens: {rec['tokens_total']:,} total, {rec['tokens_downgraded']:,} moved to cheaper tiers")
    print()
    print("Switch plan:")
    for r in rec["runs"]:
        print(f"  {r['tier']:<7} part {label([p - 1 for p in r['parts']])}")
    print(f"Next: {rec['next_step']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Price a routed task plan and log it.")
    ap.add_argument("plan", help="plan JSON file, or - for stdin")
    ap.add_argument("--current", help="override current_model from the plan")
    ap.add_argument("--dry-run", action="store_true", help="print only; do not write the ledger")
    args = ap.parse_args()

    try:
        raw = sys.stdin.read() if args.plan == "-" else Path(args.plan).read_text()
        plan = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        die(f"cannot read plan: {exc}")

    rec = analyse(plan, load_pricing(), args.current)
    print_summary(rec)

    if not args.dry_run:
        DEFAULT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with DEFAULT_LEDGER.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(f"\nLogged to {DEFAULT_LEDGER}")


if __name__ == "__main__":
    main()
