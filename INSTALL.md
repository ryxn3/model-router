# Install guide: model-router

This guide covers installing the `model-router` skill for Claude Code. It takes about two minutes.

- [Requirements](#requirements)
- [Option A: use it in this repo (no install)](#option-a-use-it-in-this-repo-no-install)
- [Option B: install for every project](#option-b-install-for-every-project)
- [Option C: copy it into another project](#option-c-copy-it-into-another-project)
- [Verify the install](#verify-the-install)
- [Set your prices](#set-your-prices)
- [Update](#update)
- [Uninstall](#uninstall)
- [Troubleshooting](#troubleshooting)

---

## Requirements

| Requirement | Why | Check |
|---|---|---|
| Claude Code | Runs the skill | `claude --version` |
| Python 3.9 or newer | Runs the scripts. Standard library only, nothing to `pip install` | `python3 --version` (Windows: `python --version`) |
| Git (optional) | To clone or update the repo | `git --version` |

The scripts use no third-party packages.

Claude Code finds project skills in `.claude/skills/` and personal skills in `~/.claude/skills/`. The skill folder must contain `SKILL.md`.

---

## Option A: use it in this repo (no install)

If you're working inside this repository, the skill is already in place:

```
.claude/skills/model-router/
```

1. Open Claude Code in the repo root:

   ```bash
   cd claude-model-calculator
   claude
   ```

2. Ask for a routing plan. For example: *"Route this: add rate limiting to the API, then write tests for it."*

That's it. Skip to [Verify the install](#verify-the-install) to confirm it works.

---

## Option B: install for every project

Use this to make the skill available in all your projects.

### macOS and Linux

```bash
# 1. Get the skill
git clone https://github.com/ryxn3/claude-model-calculator.git /tmp/model-router-src

# 2. Copy the skill folder into your personal skills directory
mkdir -p ~/.claude/skills
cp -R /tmp/model-router-src/.claude/skills/model-router ~/.claude/skills/

# 3. Clean up
rm -rf /tmp/model-router-src
```

### Windows (PowerShell)

```powershell
git clone https://github.com/ryxn3/claude-model-calculator.git "$env:TEMP\model-router-src"

New-Item -ItemType Directory -Force "$HOME\.claude\skills" | Out-Null
Copy-Item -Recurse "$env:TEMP\model-router-src\.claude\skills\model-router" "$HOME\.claude\skills\"

Remove-Item -Recurse -Force "$env:TEMP\model-router-src"
```

After copying, the skill lives at:

- macOS/Linux: `~/.claude/skills/model-router/`
- Windows: `%USERPROFILE%\.claude\skills\model-router\`

Start a new Claude Code session so it picks up the skill.

> In the commands below, `SKILL_DIR` means the path to the `model-router` folder. For a personal install it is `~/.claude/skills/model-router`. The scripts find their own location, so you can run them from any project.

---

## Option C: copy it into another project

To add the skill to a specific project:

```bash
mkdir -p /path/to/your-project/.claude/skills
cp -R /path/to/model-router /path/to/your-project/.claude/skills/
```

The skill is then available only in that project. Commit `.claude/skills/model-router/` if your team should share it. Add `.claude/model-router/` to that project's `.gitignore`, since it holds your personal ledger and reports.

---

## Verify the install

Run these from any project folder. Replace `SKILL_DIR` with your install path.

**1. Scripts run:**

```bash
python3 SKILL_DIR/scripts/route.py --help
python3 SKILL_DIR/scripts/report.py --help
```

Both should print usage text.

**2. A dry-run plan prices correctly:**

```bash
cat > /tmp/mr-test.json <<'EOF'
{"task": "smoke test", "current_model": "opus",
 "segments": [{"name": "rename", "tier": "haiku", "input_chars": 400, "output_chars": 100}]}
EOF
python3 SKILL_DIR/scripts/route.py /tmp/mr-test.json --dry-run
```

You should see a table, a total, and `Next: PAUSE: switch to haiku (/model haiku) for part 1, then say continue.`

**3. The skill is listed:** start Claude Code and type `/` or ask *"what skills do you have?"*. `model-router` should appear.

**4. End to end:** ask Claude *"Route this: fix a typo in the README, then redesign the auth flow."* It should split the work into parts, give each a tier, and tell you when to run `/model`.

---

## Set your prices

The dollar figures come from `pricing.json` in the skill folder:

```json
{
  "haiku":  {"input": 0.80, "output": 4.00},
  "sonnet": {"input": 3.00, "output": 15.00},
  "opus":   {"input": 15.00, "output": 75.00}
}
```

These are USD per million tokens and are **placeholder values**. Check Anthropic's current pricing page and edit the numbers. Savings are only as accurate as these figures.

---

## Update

For a personal install, pull the repo and copy again:

```bash
cd /path/to/claude-model-calculator && git pull
rm -rf ~/.claude/skills/model-router
cp -R .claude/skills/model-router ~/.claude/skills/
```

Re-copying overwrites `pricing.json`. Save your edited prices first, or re-apply them afterward.

Your ledger lives in each project's `.claude/model-router/` folder, not in the skill folder, so updates don't delete your history.

---

## Uninstall

```bash
rm -rf ~/.claude/skills/model-router          # personal install
rm -rf .claude/skills/model-router            # project install
rm -rf .claude/model-router                   # optional: delete logged history and reports
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python3: command not found` on Windows | Use `python` instead of `python3` in every command. |
| Claude doesn't mention `model-router` | Start a new session. Check that `SKILL.md` is directly inside `model-router/`, not one level deeper. |
| `route.py: segment 1 tier: 'Haiku' is not one of [...]` | Tiers must be lowercase: `haiku`, `sonnet`, `opus`. (Input is case-insensitive, so check the spelling.) |
| `route.py: cannot read plan` | Check the path to the JSON file, and that the file is valid JSON. |
| `route.py: pricing.json is missing [...]` | Restore `pricing.json` with all three tiers. |
| `report.py` says `Tasks: 0` | No plans logged yet. Run `route.py` without `--dry-run`. Check that you're in the same project folder, since the ledger is per folder. |
| The report shows `$0.0000` costs | Token counts are small. Real tasks are larger. Also check `pricing.json` isn't all zeros. |
| Chart is missing or empty | Open `savings-report.html` in a browser. It is a static file with no network calls. |
| Permission prompts on every script | Allow the commands in your Claude Code settings, or approve them once. |

Still stuck? Open an issue at https://github.com/ryxn3/claude-model-calculator/issues with your OS, Python version, and the full error text.
