---
name: model-router
description: Split a task into parts, assign each part to the cheapest Claude model (Haiku, Sonnet or Opus) that can do it well, and pause for the user to switch models at each tier change. Use when the user asks which model should do a task, wants to save tokens or money, or asks how much they saved (this also builds a savings chart).
---

# Model router

You cannot change the model yourself. The user switches with `/model`. Your job is to plan the split, say exactly when to switch, pause at each switch, and keep score.

Scripts live in `.claude/skills/model-router/scripts/` and need only Python 3.

## 0. Find the current model

Use the model the user says they have selected ("I'm on opus"), or the model named in your environment. If you can't tell, ask once and continue after they answer. Call it `current`.

## 1. Split the request

Break the request into 2 to 6 parts, in execution order. A part is a unit one model can finish without needing another part's reasoning. Don't split finer than that: every tier change costs the user a `/model` switch.

Put decision-making parts first. A common good split is Opus plans, then Haiku executes the mechanical parts.

## 2. Assign a tier to each part

Tier by the hardest thing the part needs, not the average.

| Tier | Use for | Examples |
|---|---|---|
| **haiku** | Mechanical, fully specified, or lookup work | rename, reformat, JSON/CSV conversion, explain a short snippet, commit message, fix a lint error, add docstrings, summarize short text, fill a clear template |
| **sonnet** | Standard engineering with a clear spec | implement a feature in a known codebase, fix a bug with reproduction steps, write tests for existing code, refactor 2 to 5 files toward a stated goal, review a moderate diff, write substantive docs |
| **opus** | Judgment, ambiguity, or hard reasoning | architecture and trade-offs, root-causing an unknown bug across many files, auth/crypto/permission logic, concurrency or performance deep dives, interpreting vague requirements, long multi-step agent work where early mistakes compound |

**Raise the tier** when: the spec is vague; the part has to decide something nobody specified; it touches security; it spans many interdependent files; a wrong answer is costly; or it can't be checked afterward.

**Lower the tier** when: the output is fully determined by the input; an existing pattern can be copied; or tests, a type checker, or a diff can verify the result mechanically.

When torn between two tiers, pick the higher one and say so. A cheap model that fails costs more than one switch.

## 3. Price the plan

Estimate each part's input and output size (about 4 characters per token). Write the plan to the scratchpad, then run:

```bash
python3 .claude/skills/model-router/scripts/route.py PLAN.json
```

```json
{
  "task": "short label",
  "current_model": "opus",
  "segments": [
    {"name": "design the cache", "tier": "opus", "why": "trade-offs",
     "input_chars": 8000, "output_chars": 3000},
    {"name": "write the tests", "tier": "haiku", "why": "mechanical, spec given",
     "input_chars": 4000, "output_chars": 2000}
  ]
}
```

Use `--dry-run` for a quick "should I" question, which doesn't log. Otherwise leave it off so the task is logged for the savings report.

## 4. Tell the user the plan

Lead with the switch plan, short:

- Each part: tier, and one line on why.
- Cost: all on the current model vs routed, the dollars saved, and the percent.
- The next step: either "run part N on <current> now" or "switch to `<tier>` with `/model <tier>`, then say `continue`".

If the whole task already fits the current model, say so briefly and don't push a switch.

## 5. Run with pauses

- Run only the parts that are on the current model's tier. Run them now.
- At every tier change, stop. Name the model to switch to (`/model haiku`, `/model sonnet`, or `/model opus`) and wait for the user to say continue.
- Never run a part on a model below its tier to save money. If the user insists, run it, and say the risk in one line.
- If a cheap part's output fails verification (tests fail, output is off-spec, something is unclear), stop, say so, and ask for a switch up for that part only.
- After a bigger-model part finishes, if the next part fits a smaller tier, stop and ask for the switch down.
- Keep each stop short: what just finished, what's next, the exact `/model` command.

## 6. Savings report

When the user asks for their savings, a chart, or "how much did I save", run:

```bash
python3 .claude/skills/model-router/scripts/report.py
```

Send the generated `.claude/model-router/savings-report.html` to the user with SendUserFile (`display: "render"`). In chat, give three numbers: dollars saved, percent saved, and tokens moved to cheaper tiers.

## Honesty rules

- Dollar figures use `pricing.json`. Those values are placeholder list prices, not verified current rates. Say so when quoting dollars, and tell the user to update the file.
- Token counts are estimates (about 4 characters per token), not billed usage.
- The ledger records plans, not executed switches. If the user skipped a switch, the savings were not realized. Say so if it matters.
- Don't claim a model was used unless it was. You can only see what the user has selected, so ask when unsure.
