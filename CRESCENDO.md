# Crescendo: The Multi-Agent Orchestration Framework

> **Last Updated:** 2026-06-26 · **Version:** 3.1.0 · **Template SHA:** `94e83e3` · **Adversarial Status:** Clean (5 passes, all findings resolved)

---

## 1. What Is Crescendo?

Crescendo is an **architectural paradigm for scaling AI work horizontally across any domain**. Instead of a single AI agent working sequentially through a task, the **Coordinator Agent ("Maestro")** dispatches a "crescendo" of parallel **Subagents** — each isolated in its own workspace, each focused on a specific role — then merges their work through automated quality gates and contradiction detection into a unified result. A dedicated **Scribe Agent ("Score")** runs continuously alongside, maintaining a forensic log of every action.

Maestro doesn't just dispatch from a fixed roster. It **reads the domain profile** to understand which roles exist, but it can also **create new roles and personas on the fly** based on the project's needs. If a legal project needs a tax specialist that isn't in the default profile, Maestro can define that role, assign it a system prompt, and dispatch it — all without modifying the profile file.

The key insight: **the same orchestration pattern works whether you're building software, analyzing legal contracts, producing marketing campaigns, conducting academic research, or localizing an application into 20 languages.** What changes between domains is the *profile* — the roles, the quality gates, the aggregation strategy — not the orchestration engine.

### Domain Examples

| Domain | What the Agents Do |
|--------|-------------------|
| **Engineering** | Architect designs the system, backend/frontend developers implement in parallel, tester writes tests, code reviewer validates — all in isolated git worktrees |
| **Legal** | Classifier triages the case, legal analyst and compliance officer work in parallel, senior counsel reviews, general counsel assembles the final document |
| **Marketing** | Strategist, copywriter, visual designer, SEO specialist, and social media manager each produce their piece — editorial reviewer merges into a cohesive campaign |
| **Research** | Lead researcher, data analyst, literature reviewer, methodology specialist, and statistician each contribute sections — peer reviewer cross-validates claims |
| **Localization** | 10+ locale translators work simultaneously, cultural reviewers check idioms, QA verifier ensures string coverage across all languages |

Crescendo is not a library. It is not a SaaS product. It is a **template repository** that ships as a portable orchestration layer for Claude (via the Claude for VS Code extension, the Claude desktop app, or the `claude` CLI). You clone the template, drop in your project files, select a domain profile, and the AI does the rest.

### The Shift It Represents

| Traditional AI | With Crescendo |
|---|---|
| One AI agent, one task | Coordinator + parallel specialist agents |
| Sequential execution | Phased parallel dispatch |
| Single context window | Distributed context across isolated workspaces |
| Manual quality review | Automated deterministic gates + contradiction detection |
| Human babysitting | Pre-flight → autonomous execution → post-run review |
| Domain-specific tools | Domain-agnostic engine + swappable profiles |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              MAESTRO (Coordinator Agent)                  │
│   Reads profile.json · Dispatches agents · Runs gates    │
│   Merges outputs · Manages orchestration_state.json      │
└─────────┬────────────┬────────────┬─────────────────────┘
          │            │            │
    ┌─────▼─────┐ ┌────▼────┐ ┌────▼────┐
    │  Agent A   │ │ Agent B │ │ Agent C │    ← Parallel within phase
    │ .worktrees │ │ .worktrees │ │ .worktrees │
    │  /role-a   │ │  /role-b │ │  /role-c │
    └─────┬─────┘ └────┬────┘ └────┬────┘
          │            │            │
          ▼            ▼            ▼
    ┌─────────────────────────────────────┐
    │        QUALITY GATES LAYER          │
    │  Deterministic → Heuristic → Claims │
    └─────────────────┬───────────────────┘
                      ▼
    ┌─────────────────────────────────────┐
    │          AGGREGATION LAYER          │
    │  git_merge │ editorial │ doc_assembly │
    └─────────────────────────────────────┘
```

### The Four Pillars

1. **Git Worktrees** — OS-level filesystem isolation. Each agent gets its own checkout of the repo in `.worktrees/`. No agent can see or corrupt another's files.

2. **Conductor** — The `conductor/` directory is the shared brain. It contains the domain profile, workflow rules, quality gates, and orchestration scripts. Agents receive a **read-only copy** in their worktree (enforced by NTFS ACLs on Windows).

3. **Phased Execution** — Work is broken into sequential phases. Agents within a phase run in parallel. All agents in Phase N must complete before Phase N+1 begins.

4. **Orchestration State** — A persistent `orchestration_state.json` file tracks every agent's status, enabling crash recovery, quota-pause resumption, and post-run reporting.

---

## 3. Repository Structure

```
crescendo-agent-template-claude/       ← FULLY SELF-CONTAINED
├── README.md                          # Quick start guide + prerequisites
├── CLAUDE.md                          # Auto-loaded context: 43 directives + file-resolution protocol
├── justfile                           # Cross-platform automation commands
├── .claude/                           # Project-level Claude config (auto-discovered)
│   ├── settings.json                  # Permissions + plan-mode write-gating hooks
│   ├── agents/                        # 3 subagents
│   │   ├── maestro.md                 # Coordinator (dispatches + gates + merges)
│   │   ├── scribe.md                  # Forensic logger (runs continuously)
│   │   └── adversarial-reviewer.md    # Zero-issue QA convergence loop
│   └── skills/                        # 9 packaged skills (zero external dependencies)
│       ├── using-git-worktrees/       # Worktree isolation protocol
│       ├── conductor-worktree-hitl/   # Parallel execution + HITL via GitHub Issues
│       ├── crescendo-init/            # Crescendo project bootstrapper
│       ├── conductor-setup/           # Conductor scaffolding
│       ├── conductor-implement/       # Track execution engine
│       ├── conductor-new-track/       # Track creation
│       ├── conductor-review/          # Code review protocol
│       ├── conductor-status/          # Progress dashboard
│       └── conductor-revert/          # Git-aware revert assistant
├── input/                             # Drop PRDs, constraints, source docs here
│   └── README.md                      # Intake instructions
├── .worktrees/                        # Agent workspaces (created at runtime)
└── conductor/                         # The orchestration brain
    ├── index.md                       # Project manifest
    ├── product.md                     # Product requirements (shared truth)
    ├── tech-stack.md                  # Technology decisions (shared truth)
    ├── workflow.md                    # Execution protocols
    ├── tracks.md                      # Track/task breakdown
    ├── tracks/                        # Track-specific plans
    ├── code_styleguides/              # Style rules per language (populated at setup)
    ├── templates/                     # Setup templates (style guides, workflow)
    ├── bin/                           # Orchestration scripts (cross-platform Python)
    │   ├── init_worktree.py           # Cross-platform worktree isolation (read-only copy)
    │   ├── preflight_check.py         # Infrastructure validator (5-section check)
    │   ├── orchestration_state.py     # State machine (init/register/update/resume)
    │   ├── run_deterministic_gates.py # Quality gates (unit tests, lint, scope, coverage)
    │   ├── cross_validate_outputs.py  # Contradiction detection (Layer 1+2)
    │   ├── sanitize_inputs.py         # Input sanitization (prompt injection defense)
    │   ├── git_status_patched.py      # Multi-worktree status viewer
    │   ├── conductor_inspector.py     # Profile/config inspector
    │   ├── inject-ghi                 # GitHub Issues integration
    │   └── poll_ghi_questions.py      # HITL question polling
    ├── profiles/                      # Domain-specific configurations
    │   ├── engineering.json           # Software engineering (6 roles, 3 phases)
    │   ├── legal.json                 # Legal analysis (9 roles, 3 phases)
    │   ├── marketing.json             # Marketing/content (8 roles, 3 phases)
    │   ├── research.json              # Academic research (11 roles, 3 phases)
    │   └── localization.json          # Internationalization (16 roles, 3 phases)
    └── schemas/
        └── claims.schema.json         # EAV claims format for contradiction detection
```

---

## 4. How to Use Crescendo

### Step 1: Clone the Template

```bash
# Create a new project from the Crescendo template
gh repo create my-project --template <your-org>/crescendo-agent-template --private --clone
cd my-project
```

### Step 2: Verify Infrastructure

```bash
just preflight
```

This runs `preflight_check.py` which validates all 5 categories: external tools, core files, conductor scripts (9/9), domain profiles, and packaged skills (9/9). Fix any ❌ items before proceeding.

> [!NOTE]
> **Cross-platform note:** The `justfile` currently uses PowerShell commands (Windows). On **macOS or Linux**, you can run the preflight check directly with Python:
> ```bash
> python3 conductor/bin/preflight_check.py
> ```
> The preflight script itself is cross-platform (pure Python). The Windows-specific commands in the `justfile` (`icacls`, `Copy-Item`) are only used by `init-worktree` for NTFS ACL enforcement. On Unix systems, substitute `chmod` for file permission control.

### Step 2: Drop In Your Project Files

Inside your cloned project, there is an `input/` folder at the project root (e.g., `my-project/input/`). This is where you place everything the AI needs to understand your project:

```
my-project/
├── input/                    ← Drop files here
│   ├── my-prd.md             # Product requirements
│   ├── architecture.png      # System diagrams
│   ├── constraints.md        # Regulatory/compliance rules
│   └── existing-code.zip     # Source code to extend
└── ...
```

- **PRDs, specs, design docs** → `my-project/input/`
- **Source code** (if extending an existing codebase) → project root
- **Constraints, regulations, style guides** → `my-project/input/`

### Step 3: Sanitize Inputs

```bash
just sanitize-inputs
```

This strips prompt injections, invisible Unicode, and HTML comments from all input files. Only files in `input/.sanitized/` are consumed by agents.

> [!WARNING]
> Binary files (PDF, DOCX, XLSX) cannot be auto-sanitized. Maestro flags them for human review.

### Step 4: Start Maestro

Open the cloned project in the Claude for VS Code extension (or run `claude` in the project directory), then type:

> *"Start the Crescendo workflow."*

That's it. Maestro reads `CLAUDE.md`, discovers the packaged skills in `.agents/skills/`, and begins the orchestration sequence:

1. **Profile selection** — Maestro scans `conductor/profiles/` and prompts you to choose a domain:
   ```
   Available domain profiles:
     1. engineering    — 6 roles (architect, backend, frontend, tester, etc.)
     2. legal          — 9 roles (legal analyst, compliance officer, senior counsel, etc.)
     3. marketing      — 8 roles (strategist, copywriter, SEO specialist, etc.)
     4. research       — 11 roles (lead researcher, data analyst, statistician, etc.)
     5. localization   — 16 roles (translators, cultural reviewers, QA verifiers)

   Which domain profile should this project use?
   ```
   The selected profile is copied to `conductor/profile.json` and governs the entire run.

2. **Input parsing** — Reads your files from `input/.sanitized/`
3. **Project setup** — Updates `conductor/product.md` and `conductor/tech-stack.md`
4. **Track planning** — Breaks the work into tracks and tasks
5. **Pre-flight briefing** — Presents estimated agent count, quota usage, commit scope, and autonomy level for your approval (see Section 8)
6. **Dispatch** — Once you approve, agents are dispatched in parallel phases

> [!TIP]
> You can also pre-select a profile before starting to skip the prompt:
> ```bash
> cp conductor/profiles/engineering.json conductor/profile.json
> ```
> Then tell Maestro: *"Start the Crescendo workflow. Profile is already selected."*

### Step 5: Monitor Progress

```bash
just git-status-condutree    # View all agent worktrees and their status
```

Or ask Maestro: *"What's the current status?"*

### Step 6: Resume After Quota Exhaustion

If the run pauses due to quota limits:

```
# In a new session:
"Resume Crescendo run"
```

Maestro reads `orchestration_state.json` and picks up exactly where it stopped. See Section 10 for the full quota recovery system.

---

## 5. Domain Profiles

Every Crescendo run is governed by a **domain profile** — a JSON configuration file that defines roles, phases, quality gates, budget limits, autonomy level, and failure handling.

### Profile Schema (19 top-level keys)

| Key | Purpose |
|-----|---------|
| `domain` | Domain identifier |
| `version` | Schema version (currently `3.0.0`) |
| `data_classification` | `public` · `internal` · `confidential` · `restricted` |
| `composition` | Inheritance (`extends`) and mixins |
| `isolation` | Worktree vs. folder isolation, access control |
| `agent_archetypes` | Role definitions with system prompts, context files, output format |
| `shared_truth` | Paths to shared documents all agents must read |
| `quality_gates` | Deterministic and heuristic gates |
| `aggregation` | How agent outputs are merged (`git_merge`, `editorial_merge`, `document_assembly`, `matrix_assembly`) |
| `budget` | `suggested_max_agents`, `mode` (`quota_based` / `api_key`), circuit breakers |
| `phases` | Ordered execution phases with assigned roles |
| `failure_strategy` | `all_or_nothing` · `best_effort` · `partial_merge_with_approval` |
| `temporal_constraints` | Deadline awareness, output TTL |
| `iteration_policy` | Max refinement rounds, feedback loops |
| `resource_locking` | File exclusivity, lock mechanisms |
| `contradiction_detection` | Detection layers and blocking rules |
| `output_contract` | Required output format and claims |
| `model_routing` | Per-role model preferences and fallback chains |
| `autonomy` | Autonomy level, execution policies, commit/merge behavior |

### The Five Shipped Profiles

| Profile | Roles | Classification | Autonomy | Isolation | Aggregation | Gates |
|---------|-------|---------------|----------|-----------|-------------|-------|
| **Engineering** | 6 | internal | full | worktree | git_merge | unit_tests, lint, code_review |
| **Legal** | 9 | confidential | checkpoint | folder | document_assembly | citation_audit, compliance_review |
| **Marketing** | 8 | public | full | worktree | editorial_merge | brand_consistency |
| **Research** | 11 | internal | full | worktree | matrix_assembly | source_verification, recency_check |
| **Localization** | 16 | internal | full | worktree | matrix_assembly | string_coverage |

### Agent Archetypes

Each archetype defines:

```json
{
  "role": "backend_developer",
  "system_prompt_template": "Implement server-side logic...",
  "context_files": ["product.md", "tech-stack.md"],
  "output_format": "code",
  "claims_required": true,
  "phase_binding": "auto"
}
```

- **`phase_binding: "auto"`** — Agent is dispatched automatically during its assigned phase
- **`phase_binding: "manual"`** — Agent is available for manual dispatch or mixin composition but not auto-dispatched

### Profile Composition

Profiles support inheritance and mixins:

```json
"composition": {
  "extends": "profiles/base.json",
  "mixins": ["profiles/mixins/strict_gates.json"]
}
```

- `extends`: Base profile loaded first, current profile overlays on top
- `mixins`: Add capabilities (gates, archetypes) without overriding core settings

---

## 6. The 43 directives (CLAUDE.md)

Maestro follows 43 numbered directives organized into 12 sections. These are the **laws** of the system — they define what Maestro must and must not do.

### Autonomous Mode Override
When `autonomy.level` is `full`, directives 11, 14, 15, and 17 are superseded by the profile's `during_execution` policies. All bypassed decisions are logged to `run_report.md`.

### Directive Summary

| # | Section | Rule |
|---|---------|------|
| 1–5 | **Isolation** | Worktrees, no direct main pushes, read-only conductor, no cross-agent access |
| 6–7 | **Input Sanitization** | Must sanitize before consuming; binaries require human review |
| 8–10 | **Domain Profile** | Profile-driven execution, respect data classification and budget limits |
| 11–13 | **Quality Gates** | Cross-validate before merging, deterministic gates before heuristic, check project prompts |
| 14–15 | **Budget** | Cost estimation before dispatch, circuit breaker on token limit |
| 16–17 | **Phased Execution** | Sequential phases, failed phase blocks progression |
| 18–19 | **Failure Handling** | Follow failure strategy (all_or_nothing / best_effort / partial), retry policy |
| 20–21 | **Orchestration State** | Initialize state at run start, track agent status for crash recovery |
| 22–23 | **Profile Composition** | Inheritance and mixin support |
| 24–27 | **Temporal/Iteration** | Deadline awareness, output TTL, max refinement rounds, resource locking |
| 28–29 | **Output Contracts** | Structured claims (EAV), contradiction detection layers |
| 30–32 | **Model Routing** | Advisory model preferences, fallback logging, session token tracking |
| 33–36 | **Aggregation** | git_merge, editorial_merge, document_assembly, matrix_assembly |
| 37–38 | **Live Conflict Detection** | Approach validation before implementation, terminate conflicting agents |
| 39–40 | **HITL Question Protocol** | GHI for clarification (`[QUESTION][<AgentName>]`), Maestro polls answers |
| 41–42 | **Attribution & Safety** | GHI comment signing, `.env` safety |
| 43 | **Scribe Agent (Score)** | Required observer — forensic log at `scribe_log.md` |

---

## 7. Quality Gates

Quality gates are checks that run **before** any merge or aggregation. They are the system's immune system.

### Deterministic Gates (automated, repeatable)

| Gate | What It Checks | Script |
|------|---------------|--------|
| `unit_tests` | npm test / pytest | `run_deterministic_gates.py` |
| `lint` | npm run lint / flake8 | `run_deterministic_gates.py` |
| `citation_audit` | Article/Section references exist in source docs | `run_deterministic_gates.py` |
| `source_verification` | Claims trace back to shared truth documents | `run_deterministic_gates.py` |
| `recency_check` | Output references aren't stale | `run_deterministic_gates.py` |
| `scope_validation` | Changed files are within allowed commit scope | `run_deterministic_gates.py` |
| `string_coverage` | All locale files have ≥ base language key count | `run_deterministic_gates.py` |

### Exit Codes

| Code | Meaning | Auto-Merge? |
|------|---------|-------------|
| `0` | All gates passed | ✅ Allowed |
| `1` | At least one required gate failed | ❌ Blocked |
| `2` | All gates were skipped (inconclusive) | ❌ Blocked |

### Heuristic Gates (LLM-based, non-deterministic)

Heuristic gates use an LLM agent to perform subjective review (e.g., code quality, brand consistency, legal compliance). They run **after** deterministic gates pass.

In autonomous mode, heuristic gate behavior depends on `data_classification`:
- `public` / `internal` → **non-blocking** (log and continue)
- `confidential` / `restricted` → **blocking** (pause for human review)

### Contradiction Detection

After gates pass, `cross_validate_outputs.py` checks for contradictions between agent outputs:

- **Layer 1 (Structured):** Reads `.claims.json` files (EAV format). Preferred source.
- **Layer 2 (Text Extraction):** Falls back to regex-based claim extraction from raw text. Deduplicates against Layer 1 — structured claims win.

Contradiction severity:
- **HIGH** → Merge blocked
- **MEDIUM** → Flagged for review
- **LOW** → Informational

---

## 8. Autonomy System

### Three Levels

| Level | Behavior | Use When |
|-------|----------|----------|
| **Full** | Runs to completion without human input. All decisions pre-specified by profile policies. | Trusted domain, internal data, well-understood task |
| **Checkpoint** | Pauses between phases for human review. | First run, high-stakes, confidential data |
| **Supervised** | Checks in after each agent completes. | Maximum control, debugging |

### Pre-Flight Briefing (Always Mandatory)

Before any autonomous run, Maestro presents a briefing:

```
╔══════════════════════════════════════════════════════╗
║              CRESCENDO PRE-FLIGHT BRIEFING           ║
╠══════════════════════════════════════════════════════╣
║ Profile:     engineering (v3.0.0)                    ║
║ Domain:      Software Engineering                    ║
║ Data:        internal                                ║
║ Autonomy:    full                                    ║
╠══════════════════════════════════════════════════════╣
║ PHASE PLAN:                                          ║
║   Phase 1 (Foundation):       2 agents               ║
║   Phase 2 (Implementation):   2 agents               ║
║   Phase 3 (Testing/Review):   2 agents               ║
║   Peak concurrent:            2 agents               ║
║   Suggested max concurrent:   8 (profile default)    ║
╠══════════════════════════════════════════════════════╣
║ COMMIT SCOPE:                                        ║
║   Repos: my-project                                  ║
║   Directories: src/, tests/, docs/                   ║
║   Auto-commit: YES                                   ║
║   Auto-merge to main: NO                             ║
╠══════════════════════════════════════════════════════╣
║ QUOTA ESTIMATE:                                      ║
║   ~180K tokens across all phases                     ║
║   Recovery: estimate → wait → stop                   ║
╚══════════════════════════════════════════════════════╝

Proceed? [Y/n]
```

The user **must** approve before execution begins. Pre-flight is the user's chance to:
- Adjust `max_agents`
- Confirm commit scope (which repos/directories)
- Choose autonomy level
- Approve or deny auto-merge to main

### During-Execution Policies

| Scenario | Full Autonomous | Checkpoint | Supervised |
|----------|----------------|------------|------------|
| Gate fails | Retry → skip → flag | Ask at phase end | Ask immediately |
| Ambiguous task | Best judgment + log | Ask at phase end | Ask immediately |
| Merge conflict | Write state and stop | Ask at phase end | Ask immediately |
| Quota exhaustion | Estimate → wait → stop | Tell human | Tell human |
| Agent error | Retry → flag → continue | Retry auto | Ask immediately |

### Autonomous Decision Rate Limiting

Maestro can make at most **10 autonomous decisions per run** (5 for legal). Each decision is logged to `run_report.md` with:
- Ambiguity category (`cosmetic` / `architectural` / `data_destructive`)
- What was ambiguous
- Decision made
- Confidence level

If the limit is exceeded, Maestro pauses for human review.

---

## 9. Failure Strategies

| Strategy | Behavior |
|----------|----------|
| **`all_or_nothing`** | If ANY agent fails (or is interrupted with a non-quota reason), the entire run halts immediately. All changes are rolled back. |
| **`best_effort`** | Merge successful outputs, flag failures in the report. Continue with what works. |
| **`partial_merge_with_approval`** | Merge successful outputs only after human approves the partial result. |

The `retry_failed` modifier adds automatic retries before declaring failure:
- `max_retry_attempts`: How many times to retry a failed agent (default: 2)
- `max_total_retries_per_phase`: Cap on total retries per phase (default: 6) to prevent retry storms

### Interrupted vs. Failed

- **`failed`** — Agent completed but produced an error. Triggers `all_or_nothing` halt.
- **`interrupted`** (quota) — Agent was paused due to quota exhaustion. Does NOT trigger `all_or_nothing`. The agent is queued for re-dispatch when quota resets.
- **`interrupted`** (non-quota) — Agent was stopped for another reason (manual abort, etc.). Treated as a failure by `all_or_nothing`.

---

## 10. Quota Recovery System

When run on a Claude subscription plan, Crescendo operates within your plan's usage quota — the quota system acts as the circuit breaker. When run against the Claude API with an API key, set `budget.mode` to `api_key` and provide numeric token/USD limits.

### Three Recovery Layers

```
Layer A: Pre-emptive Estimation        ← always active
    ↓ (if quota exhausts)
Layer B: Timer-Based Auto-Resume       ← best-effort
    ↓ (if timer fails or >2 pauses)
Layer C: User-Assisted Resume          ← guaranteed fallback
```

**Layer A — Pre-emptive Estimation** (zero downside):
- Estimate quota cost before each phase
- Register ALL agents in `orchestration_state.json` BEFORE dispatching
- If quota exhausts mid-phase, completed work is preserved
- Only the interrupted agent needs re-dispatch

**Layer B — Timer-Based Auto-Resume** (best-effort):
- On quota exhaustion: write state, set 15-minute timer
- Probe with `view_file` on `orchestration_state.json` (zero quota cost)
- If probe succeeds → quota reset → auto-resume
- **Thrashing protection**: >2 quota pauses → skip Layer B → go to Layer C
- May fail due to session timeout or stray message cancellation

**Layer C — User-Assisted Resume** (guaranteed):
- State is already written by Layer A
- User starts a new session: *"Resume Crescendo run"*
- Maestro reads `orchestration_state.json`, identifies interrupted agents, re-dispatches
- ~1 minute of user interaction

The policy string `"estimate_then_wait_then_stop"` in profile configs encodes all 3 layers.

### Budget Configuration

```json
"budget": {
  "mode": "quota_based",
  "suggested_max_agents": 8,
  "budget_limit_usd": null,
  "circuit_breaker_token_limit": null,
  "cost_estimation_before_dispatch": true,
  "max_total_retries_per_phase": 6,
  "_budget_note": "In quota_based mode, budget_limit_usd and circuit_breaker_token_limit are null — the platform quota IS the limit. Set mode to 'api_key' and provide numeric values only when using direct API keys."
}
```

- `mode: "quota_based"` (default) — the Claude plan quota handles rate limiting. `budget_limit_usd` and `circuit_breaker_token_limit` are `null` because there's no per-token billing — the quota IS the circuit breaker.
- `mode: "api_key"` — User provides their own API keys. Set `budget_limit_usd` and `circuit_breaker_token_limit` to numeric values to prevent cost overruns.
- `suggested_max_agents` — Always active regardless of mode. Configurable during pre-flight.

---

## 11. Orchestration State

The state machine (`orchestration_state.py`) is the **source of truth** for run progress. It survives context window overflow, session crashes, and quota pauses.

### CLI Commands

```bash
# Initialize a new run
python conductor/bin/orchestration_state.py init --profile engineering --run-id my-run

# Register an agent
python conductor/bin/orchestration_state.py register --agent-id fe1 --role frontend_developer --phase implementation

# Update agent status
python conductor/bin/orchestration_state.py update --agent-id fe1 --status completed

# Update with failure strategy enforcement
python conductor/bin/orchestration_state.py update --agent-id fe1 --status failed --failure-strategy all_or_nothing

# Interrupt all running agents (quota exhaustion)
python conductor/bin/orchestration_state.py update --agent-id fe1 --status interrupted --interrupt-reason quota_exhausted

# View current status
python conductor/bin/orchestration_state.py status

# Resume after crash/quota pause
python conductor/bin/orchestration_state.py resume --profile engineering
```

### Agent Statuses

| Status | Meaning | Resumable? |
|--------|---------|------------|
| `pending` | Registered but not yet dispatched | — |
| `running` | Currently executing | — |
| `completed` | Finished successfully | No |
| `failed` | Finished with error | Yes (if retries remain) |
| `interrupted` | Paused (quota or manual) | Yes |

### Safety Features

- **Atomic writes**: Write-to-temp-then-rename pattern prevents corruption
- **SHA tracking**: Records `main_branch_sha` at init; warns on resume if main has diverged
- **Staleness check**: If state is >24 hours old, warns on resume
- **Path traversal protection**: Profile name sanitized before file resolution

---

## 12. Model Routing

Model routing is **advisory by default**. Maestro logs which model it would select for each role. Claude's Task tool *does* accept a `model` parameter, so routing can be enforced: set `model_routing.status` to `enforced` to pass the preferred model per subagent.

### Per-Role Preferences (Engineering Example)

| Role | Preferred Model | Fallback | Capabilities |
|------|----------------|----------|-------------|
| Maestro (Coordinator) | claude-opus-4-8 | claude-opus-4-8 | orchestration, planning |
| Worker | claude-opus-4-8 | claude-opus-4-8 | code_generation, reasoning |
| Quality Reviewer | claude-opus-4-8 | claude-opus-4-8 | code_review, reasoning |
| Bookkeeping | claude-haiku-4-5-5 | claude-sonnet-5 | summarization |

### Status Field

```json
"model_routing": {
  "status": "advisory",
  ...
}
```

- `"advisory"` — Log preferences, select what's available. Current state.
- `"enforced"` — Specify model in invocation. Future state (requires platform support).

---

## 13. Aggregation Strategies

| Strategy | Used By | How It Works |
|----------|---------|-------------|
| **`git_merge`** | Engineering | Standard git merge of worktree branches. Conflicts resolved by Coordinator or escalated. |
| **`editorial_merge`** | Marketing | Reviewer agent reads all outputs, creates unified document preserving best elements. |
| **`document_assembly`** | Legal | Structured assembly — each agent's output maps to a specific section. Reviewer ensures cross-references. |
| **`matrix_assembly`** | Research, Localization | Outputs organized into a 2D matrix (e.g., locale × string). Reviewer fills gaps per cell. |

### Auto-Merge Safety Rules

1. Auto-merge to main is **fast-forward or clean merge only**
2. If conflicts exist → create PR but do NOT merge
3. **Never** force-push to any branch
4. Run `run_deterministic_gates.py` on the **post-merge** result
5. If post-merge gates fail → abort and revert

---

## 14. Claims & Contradiction Detection

### Claims Schema (EAV)

Every agent can produce a `<deliverable>.claims.json` alongside its output:

```json
{
  "claims": [
    {
      "entity": "UserAuthentication",
      "attribute": "session_timeout",
      "value": "30 minutes",
      "confidence": 0.95,
      "source": "requirements.md section 4.2"
    }
  ]
}
```

- **Required**: `entity`, `attribute`, `value`
- **Optional**: `confidence` (0–1), `source`

### Detection Flow

```
Agent Outputs
    │
    ├── Layer 1: Structured Claims (.claims.json)     ← preferred
    │       ↓ dedup by (entity, attribute)
    ├── Layer 2: Text-Extracted Claims (regex)         ← fallback
    │
    ▼
Cross-Validation
    │
    ├── HIGH severity → merge BLOCKED
    ├── MEDIUM severity → flagged for review
    └── LOW severity → informational
```

### Contradiction Detection Layers (Per Profile)

| Layer | Type | Engineering | Legal |
|-------|------|-------------|-------|
| `claims` | Deterministic | ✅ (blocking) | ✅ (blocking) |
| `similarity` | LLM-based | — | ✅ (blocking) |
| `adversarial` | LLM-based | — | ✅ (non-blocking) |

---

## 15. Input Sanitization

Before consuming any user-provided files, Maestro runs:

```bash
just sanitize-inputs
```

This executes `conductor/bin/sanitize_inputs.py`, which:
- Strips HTML comments
- Removes invisible Unicode characters
- Detects and neutralizes prompt injection patterns
- Copies sanitized files to `input/.sanitized/`

Agents must **only** read from `input/.sanitized/`. Binary files (PDF, DOCX, XLSX) are copied as-is with a warning — they require human review.

---

## 16. Just Commands

| Command | Purpose |
|---------|---------|
| `just` | List all available commands |
| `just preflight` | Run infrastructure validation (5-section check) |
| `just git-status-condutree` | View status of all active agent worktrees |
| `just init-worktree <track_id> <role>` | Create an isolated agent workspace with read-only conductor config |
| `just sanitize-inputs` | Sanitize input files for agent consumption |
| `just inspect` | Inspect active tracks, agents, and questions across all worktrees |
| `just inspect-all` | Inspect ALL tracks (including completed) in compact one-line format |
| `just poll-questions` | Poll GitHub Issues for human answers to agent questions |

---

## 17. Commit & Version History

### Adversarial Review Passes

| Pass | Date | Findings | Fixed | PR |
|------|------|----------|-------|----|
| 1 | 2026-06-25 | 20 (5 CRITICAL, 7 HIGH) | 20 | Template #1 |
| 2 | 2026-06-25 | 15 (0 CRITICAL, 1 HIGH) | 10 | Template #2 |
| 3 | 2026-06-25 | 5 (0 CRITICAL, 0 HIGH) | 3 | Template #3 |
| Deferred | 2026-06-25 | 7 (all LOW/INFO) | 7 | Template #4 |
| 4 | 2026-06-25 | 0 | — | Clean |
| **5 (packaging)** | **2026-06-26** | **4 (1 HIGH, 2 MEDIUM, 1 LOW)** | **4** | **Template #5–#6** |

### Key Milestones

- **v3.0.0** — 5 domain profiles, 43 directives, 3-layer quota recovery
- **v3.1.0** — Self-contained packaging (9 skills, preflight check, README)

### Key Fixes Shipped

- **Self-contained packaging** — All 9 required skills shipped in `.agents/skills/`, zero external plugin dependencies
- **Preflight infrastructure check** — `preflight_check.py` validates tools, files, scripts (9/9), profiles, and skills (9/9)
- **Budget defaults** — Quota-based mode now uses `null` limits (platform quota IS the limit)
- **Hardcoded references removed** — All hardcoded project-specific content genericized; org name parameterized
- **Autonomous override block** — CLAUDE.md now coexists with autonomous mode
- **Gate runner** — skip≠pass (exit code 2), no-test detection, scope validation, string coverage
- **State manager** — `interrupted` status, SHA divergence detection, `all_or_nothing` enforcement
- **Cross-validator** — Structured claims from `.claims.json` with Layer 1/2 dedup
- **50 agent archetypes** across 5 profiles with `phase_binding` annotations
- **3-layer quota recovery** documented and implemented
- **Auto-merge safety** — FF-only, never force-push, post-merge gate validation

---

## 18. Self-Contained Architecture

Crescendo is designed to be **fully self-contained**. Cloning the template gives you everything needed to run — zero external plugin dependencies.

### Bootstrap Chain (How Maestro Knows Its Identity)

When a user clones the template and opens it in Claude (VS Code extension, desktop app, or `claude` CLI), the following discovery chain fires automatically:

```
1. Claude auto-loads CLAUDE.md                 ← AUTO-LOADED at project root
   ├── Tells the AI: "You are Maestro, the Crescendo Coordinator"
   ├── First Action: Read CRESCENDO.md
   ├── Check for active run (orchestration_state.json)
   ├── Check for selected profile (conductor/profile.json)
   ├── Contains the 43 numbered directives (isolation, gates, budget, failures)
   ├── Contains the Universal File Resolution Protocol
   └── Decision hierarchy: Profile > CLAUDE.md directives > workflow.md > judgment

2. Claude discovers .claude/skills/            ← AUTO-DISCOVERED
   └── 9 skills become available (conductor-*, worktree, init)

3. Claude discovers .claude/agents/            ← AUTO-DISCOVERED
   └── maestro, scribe, adversarial-reviewer subagents (dispatched via the Task tool)

4. AI reads CRESCENDO.md                       ← INSTRUCTED BY CLAUDE.md
   └── Full architecture reference (this document)

5. AI reads conductor/profile.json             ← IF EXISTS
   └── Domain-specific roles, phases, autonomy, budget
```

**`CLAUDE.md` is the critical file.** Claude auto-loads it from the project root at the start of every session (the same role Antigravity's `AGENTS.md` played). It carries the Maestro identity, the 43 directives, and the file-resolution protocol; everything else (CRESCENDO.md, profile.json) is read because CLAUDE.md instructs it.

> **Two ways to run.** This template is self-contained: cloning it gives you the skills (`.claude/skills/`) and subagents (`.claude/agents/`) with zero external install. Alternatively, install the **`conductor-crescendo` plugin** once and the same skills are available across every project and every Claude surface. The plugin and the template ship identical skill sources.

### How Skills Are Discovered

Claude auto-discovers skills from `.claude/skills/` (project-level) and from any installed plugin. When a project cloned from this template is opened, all 9 packaged skills are automatically available.

### Skill Provenance

Each packaged skill records its lineage via `_upstream_source` and `_upstream_version` in its YAML frontmatter, tracking the original Antigravity/Gemini source it was ported from:

| Skill | Original Source | Version |
|-------|----------------|--------|
| `using-git-worktrees` | gemini-superpowers | 1.0.0 |
| `conductor-worktree-hitl` | palladius-common-commands | 0.0.11 |
| `conductor-*` (6 skills) | conductor | 1.0.0 |
| `crescendo-init` | conductor | 1.0.0 |

### Infrastructure Validation

Before any Crescendo operation, run:

```bash
just preflight
```

This checks 5 categories:
1. **External tools** — `git`, `python 3.10+`, `just`, `gh` (optional)
2. **Core files** — CLAUDE.md, justfile, workflow.md, schemas, etc.
3. **Conductor scripts** — All 9 scripts in `conductor/bin/`
4. **Domain profiles** — Profile directory exists + JSON validity
5. **Packaged skills** — All 9 skills have their SKILL.md

Any ❌ item includes a fix suggestion.

---

## 19. For Future AIs: How to Ingest This Document

If you are an AI agent reading this document to understand Crescendo:

1. **Run preflight** — `python conductor/bin/preflight_check.py` to verify all infrastructure is present
2. **Start with CLAUDE.md** — it contains the 43 directives you must follow as a Coordinator
3. **Read the profile** — `conductor/profile.json` defines your domain, roles, phases, and autonomy level
4. **Check orchestration state** — run `orchestration_state.py status` to see if there's a run in progress
5. **Respect the hierarchy**: Profile > CLAUDE.md > workflow.md > your judgment
6. **The pre-flight is mandatory** — present it to the user and get approval before dispatching any agents
7. **Log everything** — all autonomous decisions go to `run_report.md` with category, reasoning, and confidence
8. **Never force-push** — if the merge has conflicts, create the PR but do NOT merge
9. **Quota is not a bug** — if you hit quota limits, write state and stop gracefully. Layer A preserves all completed work.
10. **Budget mode matters** — if `mode` is `quota_based`, ignore `budget_limit_usd` and `circuit_breaker_token_limit` (they're `null`). The platform quota IS the limit.

### Key Invariants

- Agents cannot see each other's worktrees
- Agents cannot modify `conductor/` in their worktree
- Deterministic gates always run before heuristic gates
- A failed phase blocks all subsequent phases
- `orchestration_state.json` is the single source of truth for run progress
- Pre-flight approval is the user's chance to validate and walk away
- Skills are packaged in `.agents/skills/` — no external plugins required

---

## 20. Acknowledgments

Crescendo was built on the work of an open-source community. Credit where credit is due:

- **Riccardo Carlesso** ([@palladius](https://github.com/palladius)) — The original ["Crescendo of Agents" blog series](https://ricc.rocks/en/posts/technology/2026-06-16-crescendo-of-agents-part-2/) that defined the architectural vision: parallel subagents, git worktree isolation, Conductor++ orchestration, HITL via GitHub Issues, an