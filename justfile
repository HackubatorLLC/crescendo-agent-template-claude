# Orchestration targets for Conductor Crescendo Flow (cross-platform).
# No `set shell` override: recipes delegate to Python so they run identically
# on macOS, Linux, and Windows. Requires: just, git, python3 (>=3.9), gh.

# Auto-load the project's .env for every recipe. This is how Crescendo runs as
# its own GitHub identity: put GH_TOKEN=<pat> in .env and every gh/git call in a
# `just` target authenticates as that account — without touching your global
# `gh auth login` or any other GitHub account you use in parallel.
set dotenv-load := true

default:
    @just --list

# Show which GitHub identity Crescendo will act as (reads GH_TOKEN from .env).
# Expect your Crescendo bot/service account here, NOT your personal login.
gh-whoami:
    gh api user --jq .login

# Initialize a new agent worktree with read-only conductor/ + .env copies.
# All OS-specific isolation (ACLs / chmod) lives in init_worktree.py so this
# target is portable across Windows, macOS, and Linux.
init-worktree track_id role:
    python conductor/bin/init_worktree.py {{track_id}} {{role}}

# View the unified status of all active parallel worktrees and agents
git-status-condutree:
    python conductor/bin/git_status_patched.py

# Sanitize all files in input/ — strips prompt injections, invisible chars, HTML comments
sanitize-inputs:
    python conductor/bin/sanitize_inputs.py

# Run pre-flight infrastructure check before a Crescendo run
preflight:
    python conductor/bin/preflight_check.py

# Inspect active tracks, agents, and questions across all worktrees
inspect:
    python conductor/bin/conductor_inspector.py --open

# Inspect ALL tracks (including completed) in compact one-line format
inspect-all:
    python conductor/bin/conductor_inspector.py --all --short

# Poll GitHub Issues for human answers to agent questions
poll-questions:
    python conductor/bin/poll_ghi_questions.py

# Push an integration branch as the Crescendo identity (GH_TOKEN from .env).
# Requires the repo-local credential helper set by conductor-setup:
#   git config --local credential."https://github.com".helper "!gh auth git-credential"
push-integration branch:
    git push origin {{branch}}

# Open the unified PR as the Crescendo identity (GH_TOKEN from .env).
create-pr title head base="main":
    gh pr create --base {{base}} --head {{head}} --title "{{title}}" --fill
