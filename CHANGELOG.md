# Changelog

All notable changes to `model-router` are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-11-02

### Added
- `model-router` Claude Code skill (`.claude/skills/model-router/SKILL.md`): splits a task into parts, assigns each the cheapest sufficient tier (Haiku, Sonnet, Opus), and pauses for a `/model` switch at each tier change.
- `scripts/route.py`: prices a plan from token or character counts, prints the switch plan and next step, and appends the plan to a local ledger. Supports `--dry-run` and `--current`.
- `scripts/report.py`: builds a self-contained HTML savings report with inline SVG: money saved, percent saved, tokens moved to cheaper tiers, per-task cost bars, tier donut, and a recent-tasks table. Follows light and dark system themes.
- `pricing.json`: per-model USD prices per million tokens (placeholder defaults).
- `README.md`, `INSTALL.md`, and this changelog.
- `.gitignore` entry for `.claude/model-router/` (personal ledger and reports).

### Notes
- Dollar figures use placeholder prices. Update `pricing.json` before relying on them.
- Token counts are estimates at 4 characters per token.
