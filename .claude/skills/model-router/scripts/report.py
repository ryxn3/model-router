#!/usr/bin/env python3
"""Render the model-router ledger as a self-contained HTML savings report (inline SVG, no JS).

Usage:
  report.py [--ledger PATH] [--out PATH] [--last N]
"""
from __future__ import annotations

import argparse
import html
import json
import math
import os
from pathlib import Path

TIERS = ["haiku", "sonnet", "opus"]
DEFAULT_LEDGER = Path(os.environ.get("MODEL_ROUTER_LEDGER") or Path.cwd() / ".claude" / "model-router" / "ledger.jsonl")

CSS = """
:root {
  --bg: #f7f6f2; --card: #ffffff; --fg: #1d1d1b; --muted: #6b6a64; --line: #e4e2da;
  --haiku: #2a9d8f; --sonnet: #e9a23b; --opus: #7b5cd6;
  --base: #cfcdc4; --saved: #2a9d8f;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #161614; --card: #212120; --fg: #ecebe6; --muted: #9b9a93; --line: #34332f;
    --haiku: #3fc1b1; --sonnet: #f2b74f; --opus: #9d82ef;
    --base: #4a4944; --saved: #3fc1b1;
  }
}
:root[data-theme="dark"] {
  --bg: #161614; --card: #212120; --fg: #ecebe6; --muted: #9b9a93; --line: #34332f;
  --haiku: #3fc1b1; --sonnet: #f2b74f; --opus: #9d82ef;
  --base: #4a4944; --saved: #3fc1b1;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
main { max-width: 880px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 15px; margin: 0 0 12px; font-weight: 600; }
.muted { color: var(--muted); }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 20px 0; }
.kpi, .card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px; }
.k-label { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
.k-val { font-size: 26px; font-weight: 650; margin: 4px 0; }
.k-val.good { color: var(--saved); }
.grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
@media (min-width: 720px) { .grid { grid-template-columns: 1.6fr 1fr; } }
.card svg { display: block; max-width: 100%; height: auto; }
.lbl { font-size: 13px; fill: var(--fg); }
.val { font-size: 12px; fill: var(--muted); }
.big { font-size: 22px; font-weight: 650; fill: var(--fg); }
.base { fill: var(--base); }
.saved { fill: var(--saved); }
.legend { list-style: none; padding: 0; margin: 12px 0 0; font-size: 14px; }
.legend li { margin: 6px 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dot { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
.donut { display: flex; flex-direction: column; align-items: center; }
.empty { color: var(--muted); margin: 8px 0; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--line); }
th { color: var(--muted); font-weight: 500; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.tier { display: inline-block; font-size: 12px; padding: 1px 8px; border-radius: 999px; color: #fff; }
.note { font-size: 12px; color: var(--muted); margin-top: 16px; }
"""


def money(x: float) -> str:
    if x == 0:
        return "$0.00"
    return f"${x:,.2f}" if abs(x) >= 0.01 else f"${x:,.4f}"


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # skip a corrupted line rather than failing the whole report
    return rows


def summarise(rows: list[dict]) -> dict:
    base = sum(r.get("baseline_cost", 0.0) for r in rows)
    routed = sum(r.get("routed_cost", 0.0) for r in rows)
    mix = {t: 0 for t in TIERS}
    for r in rows:
        for s in r.get("segments", []):
            mix[s["tier"]] = mix.get(s["tier"], 0) + s.get("input_tokens", 0) + s.get("output_tokens", 0)
    return {
        "tasks": len(rows),
        "base": base,
        "routed": routed,
        "saved": base - routed,
        "pct": (100 * (base - routed) / base) if base else 0.0,
        "tokens": sum(r.get("tokens_total", 0) for r in rows),
        "down": sum(r.get("tokens_downgraded", 0) for r in rows),
        "mix": mix,
    }


def kpi(label: str, value: str, sub: str = "", good: bool = False) -> str:
    cls = "k-val good" if good else "k-val"
    return (f'<div class="kpi"><div class="k-label">{html.escape(label)}</div>'
            f'<div class="{cls}">{html.escape(value)}</div>'
            f'<div class="muted">{html.escape(sub)}</div></div>')


def bar_chart(rows: list[dict]) -> str:
    if not rows:
        return '<p class="empty">No routed tasks yet. Route a task and this chart fills in.</p>'
    # Name on its own line, then a baseline bar and a routed bar. Full card width for the bars.
    width, bar_max, row_h = 560, 380, 64
    peak = max(max(r.get("baseline_cost", 0), r.get("routed_cost", 0)) for r in rows) or 1
    height = row_h * len(rows) + 4
    out = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Baseline versus routed cost per task">']
    for i, r in enumerate(rows):
        y = 4 + i * row_h
        b, o = r.get("baseline_cost", 0.0), r.get("routed_cost", 0.0)
        bw, ow = bar_max * b / peak, bar_max * o / peak
        name = html.escape(str(r.get("task", "task"))[:60])
        out.append(f'<text x="0" y="{y + 12}" class="lbl">{name}</text>')
        out.append(f'<rect x="0" y="{y + 20}" width="{bw:.1f}" height="14" rx="3" class="base"/>')
        out.append(f'<text x="{bw + 6:.1f}" y="{y + 31}" class="val">{money(b)} on baseline</text>')
        out.append(f'<rect x="0" y="{y + 40}" width="{ow:.1f}" height="14" rx="3" class="saved"/>')
        out.append(f'<text x="{ow + 6:.1f}" y="{y + 51}" class="val">{money(o)} routed</text>')
    out.append("</svg>")
    return "".join(out)


def donut(mix: dict) -> str:
    total = sum(mix.values())
    if total == 0:
        return '<p class="empty">No token data yet.</p>'
    radius, stroke = 70, 22
    circ = 2 * math.pi * radius
    arcs, offset = [], 0.0
    for t in TIERS:
        share = mix.get(t, 0) / total
        if share == 0:
            continue
        arcs.append(
            f'<circle cx="90" cy="90" r="{radius}" fill="none" stroke="var(--{t})" stroke-width="{stroke}" '
            f'stroke-dasharray="{share * circ:.2f} {circ:.2f}" stroke-dashoffset="{-offset * circ:.2f}" '
            f'transform="rotate(-90 90 90)"/>')
        offset += share
    legend = "".join(
        f'<li><span class="dot" style="background:var(--{t})"></span>'
        f'<b>{t.title()}</b> {mix.get(t, 0) / total * 100:.0f}% '
        f'<span class="muted">{mix.get(t, 0):,} tokens</span></li>'
        for t in TIERS)
    return (f'<div class="donut"><svg viewBox="0 0 180 180" width="180" height="180" role="img" '
            f'aria-label="Token share by tier"><circle cx="90" cy="90" r="{radius}" fill="none" '
            f'stroke="var(--line)" stroke-width="{stroke}"/>{"".join(arcs)}'
            f'<text x="90" y="88" text-anchor="middle" class="big">{total / 1000:,.1f}k</text>'
            f'<text x="90" y="106" text-anchor="middle" class="val">tokens</text></svg>'
            f'<ul class="legend">{legend}</ul></div>')


def table(rows: list[dict]) -> str:
    if not rows:
        return ""
    body = []
    for r in reversed(rows):
        base, routed = r.get("baseline_cost", 0.0), r.get("routed_cost", 0.0)
        saved = base - routed
        pct = (saved / base * 100) if base else 0.0
        tiers = sorted({s["tier"] for s in r.get("segments", [])}, key=TIERS.index)
        chips = " ".join(f'<span class="tier" style="background:var(--{t})">{t}</span>' for t in tiers)
        body.append(
            f'<tr><td>{html.escape(str(r.get("task", "task")))}<div class="muted">{chips}</div></td>'
            f'<td class="num">{money(base)}</td><td class="num">{money(routed)}</td>'
            f'<td class="num">{money(saved)}</td><td class="num">{pct:.0f}%</td></tr>')
    return ("<table><thead><tr><th>Task</th><th class=\"num\">Baseline</th><th class=\"num\">Routed</th>"
            "<th class=\"num\">Saved</th><th class=\"num\">%</th></tr></thead><tbody>"
            + "".join(body) + "</tbody></table>")


def render(rows: list[dict], last: int) -> str:
    s = summarise(rows)
    recent = rows[-last:]
    kpis = "".join([
        kpi("Money saved", money(s["saved"]), f"vs. running everything on the baseline model", good=s["saved"] > 0),
        kpi("Savings", f"{s['pct']:.0f}%", f"{money(s['base'])} → {money(s['routed'])}", good=s["pct"] > 0),
        kpi("Tokens moved down", f"{s['down']:,}", f"of {s['tokens']:,} routed tokens"),
        kpi("Tasks routed", str(s["tasks"]), "logged plans"),
    ])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model routing savings</title>
<style>{CSS}</style></head>
<body><main>
<h1>Model routing savings</h1>
<div class="muted">Each part of each task sent to the cheapest model that can do it. Token counts are estimates (about 4 characters per token). Dollar figures use the rates in pricing.json.</div>
<div class="kpis">{kpis}</div>
<div class="grid">
  <section class="card"><h2>Cost per task: baseline vs routed</h2>{bar_chart(recent)}</section>
  <section class="card"><h2>Token share by tier</h2>{donut(s["mix"])}</section>
</div>
<section class="card" style="margin-top:12px"><h2>Recent tasks</h2>{table(recent) or '<p class="empty">Nothing logged yet.</p>'}</section>
<div class="note">Plans are logged when routed. Savings only count if the user actually made the model switches.</div>
</main></body></html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the model-router savings report.")
    ap.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    ap.add_argument("--out", type=Path, default=None, help="default: savings-report.html next to the ledger")
    ap.add_argument("--last", type=int, default=12, help="how many recent tasks to chart")
    args = ap.parse_args()

    rows = load(args.ledger)
    out = args.out or args.ledger.parent / "savings-report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(rows, max(1, args.last)))

    s = summarise(rows)
    print(f"Wrote {out}")
    print(f"Tasks: {s['tasks']}  Baseline {money(s['base'])}  Routed {money(s['routed'])}  "
          f"Saved {money(s['saved'])} ({s['pct']:.0f}%)")
    print(f"Tokens: {s['tokens']:,} total, {s['down']:,} moved to cheaper tiers")


if __name__ == "__main__":
    main()
