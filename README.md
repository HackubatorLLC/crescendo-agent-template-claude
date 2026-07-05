# Crescendo (Claude edition)

**A multi-agent orchestration framework for Claude.**

Crescendo scales AI work horizontally across any domain. The Coordinator Agent
(**Maestro**) dispatches parallel **Subagents** — each isolated in its own git
worktree, each focused on a specific role — then merges their work through
automated quality gates and contradiction detection. A dedicated **Scribe** Agent
(**Score**) runs alongside, maintaining a forensic log. The same orchestration
engine powers software engineering, legal analysis, marketing campaigns, academic
research, and localization.

This is the **Claude port** of the original Antigravity/Gemini Crescendo template —
same engine and directives, adapted to run on the **Claude for VS Code extension,
the Claude desktop app, and the `claude` CLI**.

📖 For the full guide, architecture details, and AI-ingestion instructions, see **[CRESCENDO.md](./CRESCENDO.md)**.

---

## Prerequisites

| Tool | Required | Install | Notes |
|------|:--------:|---------|-------|
| git | ✅ | [git-scm.com](https://git-scm.com) | |
| Python 3.9+ | ✅ | [python.org](https://python.org) | Runs the `conductor/` scripts |
| just | ✅ | [just.systems](https://just.systems) | Task runner (cross-platform) |
| Claude | ✅ | VS Code extension, desktop app, or `claude` CLI | AI orchestration |
| gh (GitHub CLI) | Optional | [cli.github.com](https://cli.github.com) | Needed for HITL via GitHub Issues + PRs |

---

## Quick Start

### 1. Create a project from this template
```bash
gh repo create <your-org>/my-project \
  --template HackubatorLLC/crescendo-agent-template-claude --private --clone
cd my-project
```

### 2. Verify infrastructure
```bash
just preflight
# or, without just:
python conductor/bin/preflight_check.py
```
This checks external tools, core files, conductor scripts, domain profiles, and
packaged skills. Fix any ❌ items before proceeding.

### 3. Drop project files
Place your project requirements in the `input/` folder at the project root:
```
my-project/
├── input/                ← Drop files here
│   ├── my-prd.md         # Product requirements
│   ├── architecture.png  # System diagrams
│   └── constraints.md    # Regulatory / compliance rules
└── ...
```
Then sanitize them:
```bash
just sanitize-inputs
```
> Binary files (PDF, DOCX, XLSX) require manual review — they cannot be auto-sanitized.

### 4. Start Maestro
Open the project in Claude (VS Code extension, desktop app, or `claude`). Claude
auto-loads `CLAUDE.md` and becomes **Maestro**. Then say:
> "Sanitize the input folder and start the Crescendo workflow."

Maestro will:
- Prompt you to select a domain profile (engineering, legal, marketing, research, or localization)
- Parse your sanitized inputs
- Break the work into **tracks** and tasks
- Present a **pre-flight briefing** for your approval (agent count, quota estimate, commit scope, autonomy level)
- Dispatch **Score** (Scribe) and domain agents in parallel phases once you approve

### 5. Monitor & resume
```bash
just git-status-condutree     # view all agent worktrees
```
If a run pauses (e.g., quota limits), start a new session and say: *"Resume the Crescendo run."* Maestro reads `orchestration_state.json` and picks up where it stopped.

---

## Domain Profiles

| Profile | Domain | Roles | Autonomy | Aggregation | Data Classification |
|---------|--------|:-----:|----------|-------------|---------------------|
| `engineering.json` | Software Engineering | 6 | Full | git_merge | internal |
| `legal.json` | Legal Analysis | 9 | Checkpoint | document_assembly | confidential |
| `marketing.json` | Marketing / Content | 8 | Full | editorial_merge | public |
| `research.json` | Academic Research | 11 | Full | matrix_assembly | internal |
| `localization.json` | Internationalization | 16 | Full | matrix_assembly | internal |

Maestro can also create new roles on the fly based on project needs — the profile
defines the starting roster, not a hard limit. New roles follow each domain's
themed naming convention.

---

## What's Inside

```
crescendo-agent-template-claude/       ← Fully self-contained
├── README.md                          # This file
├── LICENSE                            # Apache License, Version 2.0
├── NOTICE                             # Required attribution notices (preserved in derivatives)
├── CLAUDE.md                          # Auto-loaded: Maestro identity, 43 directives, file-resolution protocol
├── CRESCENDO.md                       # Full guide, architecture, AI-ingestion instructions
├── justfile                           # Cross-platform automation (preflight, sanitize, inspect, poll, worktree init)
├── .claude/                           # Project-level Claude config (auto-discovered)
│   ├── settings.json                  # Permissions + plan-mode write-gating
│   ├── agents/                        # maestro, scribe, adversarial-reviewer
│   └── skills/                        # 9 packaged skills (zero external dependencies)
│       ├── using-git-worktrees/       # Worktree isolation protocol
│       ├── conductor-worktree-hitl/   # Parallel execution + HITL via GitHub Issues
│       ├── crescendo-init/            # Project bootstrapper
│       ├── conductor-setup/           # Conductor scaffolding
│       ├── conductor-implement/       # Track execution engine
│       ├── conductor-new-track/       # Track creation
│       ├── conductor-review/          # Code review protocol
│       ├── conductor-status/          # Progress dashboard
│       └── conductor-revert/          # Git-aware revert assistant
├── input/                             # Drop project files here
├── .worktrees/                        # Agent workspaces (created at runtime)
└── conductor/                         # Orchestration brain
    ├── bin/                           # Cross-platform Python scripts
    │   ├── init_worktree.py           # Cross-platform worktree isolation (read-only copy)
    │   ├── preflight_check.py         # Infrastructure validator
    │   ├── orchestration_state.py     # State machine (crash recovery, resume)
    │   ├── run_deterministic_gates.py # Quality gates (tests, lint, scope)
    │   ├── cross_validate_outputs.py  # Contradiction detection
    │   ├── sanitize_inputs.py         # Input sanitization
    │   └── ...                        # (git status, inspector, GHI tools)
    ├── profiles/                      # 5 domain configurations
    ├── schemas/                       # Claims JSON schema (EAV format)
    ├── templates/                     # Setup templates (style guides)
    └── workflow.md                    # Execution protocols (TDD lifecycle, checkpoints, gates)
```

---

## Key Concepts

| Concept | Summary | Details |
|---------|---------|---------|
| Profiles | Domain-specific configs (roles, gates, autonomy) | CRESCENDO.md §5 |
| 43 Directives | Maestro's behavioral rules | CLAUDE.md / CRESCENDO.md §6 |
| Scribe Agent | Required observer — forensic log of every run | CRESCENDO.md §6 (Directive 43) |
| Approach Validation | Agents submit plans before coding — conflicts caught early | CRESCENDO.md §6 (Directive 37) |
| HITL Questions | Agents post questions to GitHub Issues for human answers | CRESCENDO.md §6 (Directive 39) |
| Quality Gates | Deterministic + heuristic checks before merge | CRESCENDO.md §7 |
| Autonomy Levels | Full / Checkpoint / Supervised | CRESCENDO.md §8 |
| Quota Recovery | 3-layer system (estimate → wait → stop) | CRESCENDO.md §10 |
| Contradiction Detection | Claims-based (EAV) + text extraction | CRESCENDO.md §14 |
| Self-Contained | All skills shipped, zero plugin dependencies | CRESCENDO.md §18 |

---

## Documentation

| Document | Purpose |
|----------|---------|
| [CLAUDE.md](./CLAUDE.md) | Auto-loaded context: Maestro identity, 43 directives, file-resolution protocol |
| [CRESCENDO.md](./CRESCENDO.md) | Full guide — architecture, usage, profiles, all sections |
| [conductor/workflow.md](./conductor/workflow.md) | Execution protocols, gate rules, aggregation strategies |
| [conductor/profiles/](./conductor/profiles) | Domain-specific JSON configurations |
| conductor/schemas/claims.schema.json | EAV claims format for contradiction detection |

---

## Two ways to get the skills

This template is **self-contained** — `.claude/skills/` and `.claude/agents/` are
auto-discovered on clone, no install needed. Alternatively, install the
[`conductor-crescendo`](https://github.com/HackubatorLLC/conductor-crescendo) plugin
once to get the same skills across every project and every Claude surface. Both
ship identical skill sources.

---

## GitHub identity (run as a dedicated account, isolated from your other logins)

Crescendo does its GitHub work — GHI human-in-the-loop, integration pushes, and PRs —
through the `gh` CLI, authenticated as a **project-local identity** that never disturbs
any other GitHub account you use in parallel.

`conductor-setup` prompts for a Personal Access Token and wires this up automatically.
Under the hood:

- The token is stored as `GH_TOKEN` in the git-ignored `.env`. `gh` honors `GH_TOKEN`
  and it takes precedence over your machine's `gh auth login` **without modifying it**.
- `just` targets auto-load `.env` and the `gh`-based scripts load it themselves, so the
  token reaches `gh` in any host — desktop app, VS Code, or CLI — with nothing to
  re-export each session.
- `git push` uses a repo-local credential helper, so it authenticates as the same
  identity without touching your global git config.
- The token stays at the main checkout only; `init_worktree.py` strips it from worktree
  copies so subagents can't act on GitHub.

Verify the active identity any time with `just gh-whoami`. **Never run `gh auth login`
for a Crescendo project** — that would change your machine-global account.

---

## Acknowledgments

Crescendo was built on the shoulders of an open-source community. The following
people, articles, and repositories were direct inspirations:

| Contributor | Contribution | Link |
|-------------|--------------|------|
| Riccardo Carlesso (@palladius) | Original "Crescendo of Agents" blog series, `conductor-worktree-hitl` skill, Conductor++ architecture, and the coordinator concept | [Blog (Part 2)](https://ricc.rocks/en/posts/technology/2026-06-16-crescendo-of-agents-part-2/) |
| Keith | Conductor extension — the Rails-like orchestration framework Crescendo's track system is built on | [gemini-cli-extensions/conductor](https://github.com/gemini-cli-extensions/conductor) |
| Barrett Storck | `gemini-superpowers` plugin, including the `using-git-worktrees` skill | [barretstorck/gemini-superpowers](https://github.com/barretstorck/gemini-superpowers) |
| Richard Seroter | "One prompt, four subagents" — the parallel subagent dispatch pattern | [seroter.com](https://seroter.com/2026/06/01/one-prompt-four-subagents-and-ninety-seconds-to-get-a-working-app/) |
| Paul (AI Positive) | "State on Disk" persistence pattern — how Crescendo survives quota interruptions | [AI Positive Substack](https://aipositive.substack.com/p/how-i-turned-gemini-cli-into-a-multi) |

The name "Crescendo" and the musical metaphor (Maestro, Score) come from
Riccardo's original vision of a "crescendo of agents" — a single coordinator that
grows the ensemble from a soloist to a full orchestra. See [NOTICE](./NOTICE) for
the required attribution notices.

---

## License

Copyright 2026 Hackubator LLC

Licensed under the Apache License, Version 2.0 (the "License"); you may not use
this file except in compliance with the License. You may obtain a copy of the
License at http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the [LICENSE](./LICENSE)
file for the full text and the [NOTICE](./NOTICE) file for required attribution
notices.
