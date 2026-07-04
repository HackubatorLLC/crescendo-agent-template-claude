# Orchestration targets for Conductor Crescendo Flow (cross-platform).
# No `set shell` override: recipes delegate to Python so they run identically
# on macOS, Linux, and Windows. Requires: just, git, python3 (>=3.8), gh.

default:
    @just --list

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
