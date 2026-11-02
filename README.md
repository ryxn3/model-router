# model-router

A Claude Code skill that stops you paying Opus prices for work Haiku or Sonnet can do.

You select a model, ask for a task, and the skill breaks the task into parts. For each part it says which model is the cheapest one that can do it well. When a part needs a different model, it tells you to switch with `/model` and waits for you to say continue. When you ask how much you've saved, it builds a chart.

- [Why](#why)
- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Choosing a tier](#choosing-a-tier)
- [Example session](#example-session)
- [Savings report](#savings-report)
- [Command reference](#command-reference)
- [Plan file format](#plan-file-format)
- [Files and data](#files-and-data)
- [Pricing](#pricing)
- [How accurate is it?](#how-accurate-is-it)
- [Limitations](#limitations)
- [Project layout](#project-layout)
- [Contributing](#contributing)
- [Changelog](#changelog)

Installation is in [INSTALL.md](INSTALL.md).

---

## Why

Opus costs several times more per token than Sonnet, and Sonnet costs several times more than Haiku. Most requests have a few hard steps and many easy ones: designing a change is hard, renaming things across files is easy, and writing tests for a spec you already wrote is medium. Running all of it on the biggest model wastes money. Running all of it on the smallest model risks bad output on the hard parts.

`model-router` splits the difference. Each part goes to the cheapest tier that can handle it, with a pause at each switch so you stay in control.

## Quick start

1. Install it (see [INSTALL.md](INSTALL.md)). For this repo, nothing to install.
2. Start Claude Code and select a model, for example `/model opus`.
3. Ask for a task with routing:

   ```
   Route this: add rate limiting to the API, then write tests for it.
   ```

4. Claude replies with a plan:

   ```
   Task: Add rate limiting to API  (id d79b962b)
   Current model: opus   Baseline: opus

    #  part                         tier       tokens   baseline     routed  why
    1  design the limiter           opus        2,800      $0.09      $0.09  trade-offs across routes
    2  implement middleware         sonnet      2,500      $0.10      $0.02  clear spec
    3  write tests                  haiku       1,125      $0.04    $0.0021  spec given

   Total: baseline $0.23  routed $0.11  saved $0.12 (51%)
   Tokens: 6,425 total, 3,625 moved to cheaper tiers

   Switch plan:
     opus    part 1
     sonnet  part 2
     haiku   part 3
   Next: Run part 1 on opus now.
   ```

   The numbers above are real output from `route.py` for this plan.

5. Follow the switch prompts. When it says `/model sonnet`, run that command, then reply `continue`.

## How it works

```
   your request
        │
        ▼
 ┌──────────────┐   1. Split into 2–6 parts (in order)
 │  model-router│   2. Tier each part: haiku | sonnet | opus
 └──────┬───────┘   3. Price the plan (route.py)
        │           4. Show the plan and the next step
        ▼
  run parts on the current model if the tier matches
        │
        ├── tier change? ──► PAUSE: "/model <tier>, then say continue"
        │                         │
        │                         ▼
        │                    you switch, reply continue
        ▼
  next run ... until every part is done
```

Key behaviors:

- **Pauses only at tier changes.** Consecutive parts on the same tier run without stopping.
- **Never runs a part on a model below its tier** to save money. If you insist, it runs the part and states the risk in one line.
- **Escalates on failure.** If a cheap part's output fails checks (tests, spec mismatch, unclear output), it stops and asks for a switch up for that part only.
- **Doesn't nag.** If the whole task already fits the model you're on, it says so and doesn't suggest a switch.

## Choosing a tier

The tier is set by the hardest thing a part needs.

| Tier | Good for | Examples |
|---|---|---|
| **haiku** | Mechanical, fully specified, or lookup work | Rename, reformat, JSON↔CSV, explain a short snippet, commit message, lint fixes, docstrings, summarize short text, fill a template |
| **sonnet** | Standard engineering with a clear spec | Implement a feature in a known codebase, fix a bug with repro steps, tests for existing code, refactor 2–5 files toward a stated goal, review a moderate diff |
| **opus** | Judgment, ambiguity, hard reasoning | Architecture and trade-offs, root-causing an unknown bug across files, auth/crypto/permissions, concurrency and performance, interpreting vague requirements, long agent runs where early mistakes compound |

**Raise a tier** when the spec is vague, the part must decide something unspecified, it touches security, it spans many interdependent files, a wrong answer is costly, or the result can't be checked.

**Lower a tier** when the output is determined by the input, an existing pattern can be copied, or tests, a type checker, or a diff can verify it.

**Good default split:** Opus plans, Sonnet builds, Haiku does the mechanical follow-up.

When torn between two tiers, the router picks the higher one. A failed cheap attempt costs more than one extra switch.

## Example session

Illustrative only. The dollar figures here are made up to show the flow. Real numbers come from `route.py`.

```
You:    /model opus
You:    Route this: rename the `user_id` column to `account_id` everywhere,
        then add an index for lookups by account, then design the migration
        plan for production with zero downtime.

Claude: Plan (3 parts):
          1 rename column        haiku   mechanical, exact spec
          2 add lookup index     sonnet  standard migration file
          3 zero-downtime plan   opus    trade-offs, production risk
        Cost: baseline $0.31 → routed $0.12 (saved $0.19, 61%)

        Next: switch to haiku for part 1:
              /model haiku     then reply continue

You:    /model haiku
You:    continue

Claude: Part 1 done: 14 references renamed across 6 files. Tests pass.
        Next: switch to sonnet for part 2:
              /model sonnet    then reply continue

You:    /model sonnet
You:    continue

Claude: Part 2 done: migration 0042_add_account_index.sql added.
        Next: switch to opus for part 3:
              /model opus      then reply continue
...
```

## Savings report

Ask *"how much did I save?"* or *"show my savings chart"*. Claude runs `report.py` and sends `savings-report.html`. Open it in any browser. It is a single file with no external requests.

The report shows:

- **Money saved**: baseline cost minus routed cost, across all logged tasks.
- **Savings %**: the saving as a share of the baseline.
- **Tokens moved down**: tokens that ran on a cheaper tier than the baseline.
- **Cost per task**: baseline and routed bars for the most recent tasks.
- **Token share by tier**: a donut chart of Haiku, Sonnet and Opus usage.
- **Recent tasks**: a table with tier chips per task.

It follows your system light/dark setting.

Run it yourself:

```bash
python3 .claude/skills/model-router/scripts/report.py            # from a project folder
python3 .claude/skills/model-router/scripts/report.py --last 25  # chart more tasks
```

## Command reference

### `route.py`: price and log a plan

```bash
python3 scripts/route.py PLAN.json [--current MODEL] [--dry-run]
cat PLAN.json | python3 scripts/route.py - --dry-run
```

| Option | Meaning |
|---|---|
| `PLAN.json` | Plan file path, or `-` to read from stdin |
| `--current MODEL` | Override `current_model` in the plan. Use `haiku`, `sonnet` or `opus` |
| `--dry-run` | Print the plan and totals, don't write to the ledger |

Exit codes: `0` on success. Errors such as a bad tier or unreadable file print a message starting with `route.py:` and exit non-zero.

### `report.py`: build the savings report

```bash
python3 scripts/report.py [--ledger PATH] [--out PATH] [--last N]
```

| Option | Default | Meaning |
|---|---|---|
| `--ledger` | `./.claude/model-router/ledger.jsonl` | Which ledger to read |
| `--out` | `savings-report.html` next to the ledger | Where to write the HTML |
| `--last` | `12` | Most recent tasks to chart |

## Plan file format

```json
{
  "task": "short label shown in the report",
  "current_model": "opus",
  "baseline_model": "opus",
  "segments": [
    {
      "name": "design the cache",
      "tier": "opus",
      "why": "trade-offs across services",
      "input_tokens": 2000,
      "output_tokens": 800
    },
    {
      "name": "write the tests",
      "tier": "haiku",
      "why": "spec is written",
      "input_chars": 6000,
      "output_chars": 2500
    }
  ]
}
```

| Field | Required | Notes |
|---|---|---|
| `task` | No | Defaults to `untitled task` |
| `current_model` | No | The model you have selected. Defaults to `sonnet` |
| `baseline_model` | No | What you'd otherwise run on. Defaults to `current_model`. Set to `opus` to measure savings against Opus |
| `segments` | Yes | Ordered list of parts. At least one |
| `segments[].name` | No | Shown in the table |
| `segments[].tier` | Yes | `haiku`, `sonnet` or `opus` |
| `segments[].why` | No | Short reason, shown in the table |
| `segments[].input_tokens` / `output_tokens` | One of each form | Token counts |
| `segments[].input_chars` / `output_chars` | Alternative to tokens | Converted at 4 characters per token |

Use one unit form per part. If a part has both `input_tokens` and `input_chars`, the token value wins. If it has neither, its size counts as zero.

## Files and data

| Path | What it is | Shared? |
|---|---|---|
| `.claude/skills/model-router/SKILL.md` | Instructions Claude follows | Yes, commit it |
| `.claude/skills/model-router/pricing.json` | Per-model prices | Yes, but set your own values |
| `.claude/skills/model-router/scripts/` | `route.py` and `report.py` | Yes |
| `.claude/model-router/ledger.jsonl` | One JSON line per logged plan | No. Git-ignored |
| `.claude/model-router/savings-report.html` | Generated report | No. Git-ignored |

The ledger is append-only. Each line is one plan, with timestamp, tiers, token counts, and costs. You can delete it to reset your history.

Override the ledger location with an environment variable:

```bash
export MODEL_ROUTER_LEDGER=~/notes/model-router-ledger.jsonl
```

## Pricing

Prices are in `pricing.json`, in USD per million tokens:

```json
{
  "haiku":  {"input": 0.80, "output": 4.00},
  "sonnet": {"input": 3.00, "output": 15.00},
  "opus":   {"input": 15.00, "output": 75.00}
}
```

**These defaults are placeholders, not verified current Anthropic rates.** Update them from Anthropic's pricing page before relying on the dollar figures. Relative savings (percent, tokens moved) depend on the ratios between tiers, so they hold up better than absolute dollars.

## How accurate is it?

- **Tokens are estimates.** Characters divided by 4. Real tokenizer counts vary by language and content, and code often tokenizes differently from prose.
- **Costs are list-price math** on those estimates. They don't include prompt caching, batch discounts, or the context Claude Code adds on its own.
- **Savings assume the switches happen.** The ledger records plans. If you skipped a switch and ran everything on Opus, the report still counts the plan as routed. Treat the report as an estimate of what routing would save.
- **Tier choice is a judgment call** made by Claude from the rubric. It can be wrong. The router leans toward the higher tier when unsure.

## Limitations

- **Claude can't change your model.** You run `/model`. The skill pauses and waits for you.
- **Your current model comes from you or the session.** If Claude can't tell which model you've selected, it asks.
- **Routing adds steps.** Each tier change costs a `/model` command and a reply. It pays off on larger tasks and matters less for a one-line question.
- **It won't route tasks you ask it not to.** Use `/model` directly for those.
- **No automatic verification.** The router relies on you or the tests to catch a cheap model's mistake.

## Project layout

```
.
├── README.md                     ← you are here
├── INSTALL.md                    ← install, update, uninstall
├── CHANGELOG.md                  ← version history
├── .gitignore                    ← ignores .claude/model-router/
└── .claude/
    └── skills/
        └── model-router/
            ├── SKILL.md          ← skill instructions for Claude
            ├── pricing.json      ← per-model prices
            └── scripts/
                ├── route.py      ← price, log, and plan a split task
                └── report.py     ← build the HTML savings report
```

## Contributing

1. Fork and create a branch.
2. Keep scripts to the Python standard library so the skill installs with no dependencies.
3. Test both scripts before opening a pull request:

   ```bash
   python3 .claude/skills/model-router/scripts/route.py --help
   MODEL_ROUTER_LEDGER=/tmp/test-ledger.jsonl python3 .claude/skills/model-router/scripts/route.py /path/to/plan.json
   MODEL_ROUTER_LEDGER=/tmp/test-ledger.jsonl python3 .claude/skills/model-router/scripts/report.py
   ```

4. If you change the tier rubric or pause rules, update `SKILL.md` and the matching sections here together.
5. Add a line to `CHANGELOG.md`.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
