# crescendo-agent-template-claude

A **self-contained, cloneable template** for running the Crescendo multi-agent
orchestration framework with Claude. Clone it, drop your project files into
`input/`, pick a domain profile, and Maestro coordinates a "crescendo" of
parallel role-based subagents — each isolated in its own git worktree — through
automated quality gates into a unified result.

Ported from the Antigravity/Gemini Crescendo template. Runs in the Claude for VS
Code extension, the Claude desktop app, or the `claude` CLI.

## Prerequisites

- `git`, `python3` (≥ 3.8), and [`just`](https://github.com/casey/just)
- [`gh`](https://cli.github.com/) (GitHub CLI) — for the GHI human-in-the-loop loop and PRs
- A GitHub token in your environment: `export GITHUB_PERSONAL_ACCESS_TOKEN=...`

## Quick start

```bash
# 1. Create your project from this template (or clone it directly)
gh repo create <your-org>/<project-name> --template <your-org>/crescendo-agent-template-claude --private --clone
cd <project-name>

# 2. Verify the engine
just preflight

# 3. Pick a domain profile (or let Maestro prompt you)
cp conductor/profiles/engineering.json conductor/profile.json

# 4. Drop your PRD / mockups / constraints into input/, then open the project in
#    Claude (VS Code extension, desktop app, or `claude`). Claude auto-loads
#    CLAUDE.md and becomes Maestro. Say:
#    "Sanitize the input folder and start the Crescendo workflow."
```

## How it works

`CLAUDE.md` is auto-loaded and turns Claude into **Maestro**. Maestro reads the
active `conductor/profile.json`, runs the pre-flight briefing, dispatches the
**Scribe** and role subagents (via the Task tool) into `.worktrees/`, runs
deterministic gates and contradiction detection, loops the
**adversarial-reviewer** to zero findings, and merges. Full architecture is in
`CRESCENDO.md`.

## Layout

```
CLAUDE.md            Auto-loaded: Maestro identity, 43 directives, file-resolution protocol
CRESCENDO.md         Full architecture guide
justfile             Cross-platform orchestration targets
.claude/
  settings.json      Permissions + plan-mode write-gating
  agents/            maestro, scribe, adversarial-reviewer
  skills/            9 workflow skills (conductor-*, worktree, init)
conductor/
  bin/               Cross-platform Python engine (gates, state, sanitize, worktree init, GHI)
  profiles/          5 domain profiles (engineering, legal, marketing, research, localization)
  schemas/           claims.schema.json (EAV contradiction detection)
  templates/         Setup templates + code style guides
  workflow.md        Execution protocols (TDD lifecycle, checkpoints, quality gates)
  product.md         Shared truth — your product definition (placeholder)
  tech-stack.md      Shared truth — your tech decisions (placeholder)
  tracks.md          Track registry
input/               Drop source material here (sanitized before use)
```

## Two ways to get the skills

This template is self-contained — `.claude/skills/` and `.claude/agents/` are
auto-discovered on clone, no install needed. Alternatively, install the
**`conductor-crescendo`** plugin once to get the same skills across every project
and every Claude surface. Both ship identical skill sources.

## Security

Never commit `.env` (git-ignored here). The `gh`/GitHub MCP token is read from
the environment. `conductor/` is copied **read-only** into every worktree so
agents cannot mutate shared config.
