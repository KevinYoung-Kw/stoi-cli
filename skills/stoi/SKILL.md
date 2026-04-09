---
name: stoi
description: >
  Use this skill whenever the user mentions token efficiency, cache misses,
  wasted tokens, prompt caching, /compact workflows, Claude Code cost optimization,
  session analysis, "含屎量", or anything related to measuring or improving
  Claude Code token economy—even if they do not explicitly say "stoi".
---

# STOI Skill

`stoi` (Shit Token On Investment) is a CLI tool and MCP server that analyzes
Claude Code session token efficiency. It treats cache stability as king and
surfaces concrete, user-actionable fixes instead of vague advice.

## When to use

- The user asks about token efficiency, cache hits, or prompt caching in Claude Code.
- The user mentions high token usage, "wasted" tokens, or session bloat.
- The user brings up `/compact`, session splitting, or `CLAUDE.md` optimization.
- The user references "含屎量" (shit-token ratio) or cost per session.
- The user wants to compare two sessions or workflows A/B style.
- The user asks how to make Claude Code cheaper or faster.

## How to use

### Using the CLI

Suggest CLI commands based on what the user needs:

| Command | When to suggest |
|---------|-----------------|
| `stoi report` | User wants a quick post-session breakdown. |
| `stoi dashboard` | User wants an interactive HTML view with per-turn analysis. |
| `stoi start` | User wants to start a real-time monitoring proxy before a session. |
| `stoi compare <session_a> <session_b>` | User wants an A/B comparison of two sessions or workflows. |
| `stoi repl` then `/insights` or `/blame` | User is already in the stoi REPL and wants deep dives. |

### Using the MCP Server

If the user has the stoi MCP server configured, prefer calling tools directly
instead of asking the user to run CLI commands. Available tools:

- `stoi_latest` — fetch the most recent session summary.
- `stoi_report` — run a full analysis on a specific session.
- `stoi_insights` — get high-level insights and trends.
- `stoi_overview` — list recent sessions with metadata.
- `stoi_blame` — identify which turns or patterns are the biggest token wasters.

Use `stoi_latest` or `stoi_report` first, then follow up with `stoi_insights` or
`stoi_blame` if the user wants deeper diagnostics.

## Analysis Workflow

1. **Check installation.** Run `which stoi` or `uv tool list | grep stoi`. If it
   is missing, suggest installing with `uv tool install stoi-cli` (or the
   equivalent for their package manager).
2. **Choose entry point.** If MCP is available, call the MCP tools. Otherwise,
   run the CLI commands listed above.
3. **Run analysis.** Execute the appropriate command(s) and capture the output.
4. **Interpret results using the 3-layer model:**
   - **L1 Cache** — prefix stability. High cache misses here are the most expensive.
   - **L2 Validity** — whether loaded context actually gets used. Unused context is waste.
   - **L3 Cost** — absolute token spend. Cheapest to fix only after L1 and L2 are solid.
5. **Formulate actionable recommendations.** Every suggestion must be concrete:
   - "Move X to `CLAUDE.md`" instead of "optimize your system prompt."
   - "Run `/compact` after turn 15" instead of "keep sessions short."
   - "Split this 200-turn session at turn 90" instead of "avoid long sessions."

## Response Format

Present results in this structure:

```markdown
### Session Summary
- **Session ID:** `<id>`
- **Total Tokens:** `<number>`
- **Cache Hit Rate:** `<percentage>`
- **Shit-Token Ratio (含屎量):** `<percentage>`

### 3-Layer Diagnosis
- **L1 Cache:** <emoji> <one-line verdict>
- **L2 Validity:** <emoji> <one-line verdict>
- **L3 Cost:** <emoji> <one-line verdict>

### Actionable Fixes
- [ ] <concrete fix 1>
- [ ] <concrete fix 2>
- [ ] <concrete fix 3>
```

Use emojis to signal severity:
- Green / acceptable
- Yellow / warning
- Red / critical

## Copy-paste Quick Reference

### Install
```bash
uv tool install stoi-cli
```

### Top 5 CLI Commands
```bash
stoi report          # latest session breakdown
stoi dashboard       # interactive HTML dashboard
stoi start           # real-time monitoring proxy
stoi compare A B     # A/B session comparison
stoi repl            # enter the stoi REPL
```

### Top 5 MCP Tools
- `stoi_latest`   — most recent session summary
- `stoi_report`   — full analysis for a session
- `stoi_insights` — trends and high-level insights
- `stoi_overview` — list of recent sessions
- `stoi_blame`    — pinpoint biggest token wasters
