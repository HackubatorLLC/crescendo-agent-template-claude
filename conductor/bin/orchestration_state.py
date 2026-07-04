#!/usr/bin/env python3
"""Orchestration state manager for crash recovery.

Manages ``orchestration_state.json`` at the project root, tracking agent
lifecycle across a multi-agent crescendo run.  Uses only the Python
standard library.

Subcommands:
    init     – Create a fresh orchestration state file
    register – Add an agent entry with status=pending
    update   – Update an agent's status
    status   – Print a coloured summary of the run
    resume   – List agents that need to be (re-)dispatched

Exit codes:
    0 – success
    1 – error (missing state file, unknown agent, bad arguments)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATE_FILENAME = "orchestration_state.json"

# ANSI colour codes (disabled when NO_COLOR is set or output is not a tty)
_COLOUR_ENABLED = (
    sys.stdout.isatty()
    and os.environ.get("NO_COLOR") is None
)

_RESET = "\033[0m" if _COLOUR_ENABLED else ""
_BOLD = "\033[1m" if _COLOUR_ENABLED else ""
_RED = "\033[31m" if _COLOUR_ENABLED else ""
_GREEN = "\033[32m" if _COLOUR_ENABLED else ""
_YELLOW = "\033[33m" if _COLOUR_ENABLED else ""
_CYAN = "\033[36m" if _COLOUR_ENABLED else ""
_DIM = "\033[2m" if _COLOUR_ENABLED else ""

_STATUS_STYLE = {
    "pending":     (_YELLOW, "⏳"),
    "running":     (_CYAN,   "🔄"),
    "completed":   (_GREEN,  "✅"),
    "failed":      (_RED,    "❌"),
    "interrupted": (_YELLOW, "⚡"),
}

_RUN_STATUS_STYLE = {
    "running":   (_CYAN,   "🔄"),
    "completed": (_GREEN,  "✅"),
    "failed":    (_RED,    "❌"),
    "partial":   (_YELLOW, "⚠️"),
}

VALID_AGENT_STATUSES = {"pending", "running", "completed", "failed", "interrupted"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return current time as ISO 8601 string in UTC."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _state_path(project_root: str) -> Path:
    """Resolve the path to orchestration_state.json."""
    return Path(project_root) / STATE_FILENAME


def _load_state(project_root: str) -> Dict[str, Any]:
    """Load the orchestration state file, or exit with an error."""
    path = _state_path(project_root)
    if not path.exists():
        print(
            f"{_RED}ERROR:{_RESET} State file not found: {path}\n"
            f"  Run 'init' first to create a new orchestration state.",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_state(project_root: str, state: Dict[str, Any]) -> None:
    """Write the orchestration state file atomically (write-then-rename)."""
    state["last_updated"] = _now_iso()
    path = _state_path(project_root)
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    # Atomic rename (or replace on Windows)
    try:
        tmp_path.replace(path)
    except OSError:
        # Fallback for edge-case filesystem issues
        import shutil
        shutil.move(str(tmp_path), str(path))


def _find_agent(state: Dict[str, Any], agent_id: str) -> Optional[Dict[str, Any]]:
    """Find an agent entry by agent_id, or return None."""
    for agent in state.get("agents", []):
        if agent["agent_id"] == agent_id:
            return agent
    return None


def _resolve_project_root() -> str:
    """Walk upward from the script location to find the project root.

    The project root is identified by the presence of ``conductor/``
    directory or a ``justfile``.  Falls back to CWD.
    """
    start = Path(__file__).resolve().parent  # conductor/bin/
    candidate = start.parent.parent          # project root
    if (candidate / "conductor").is_dir() or (candidate / "justfile").exists():
        return str(candidate)
    # Fallback: current working directory
    return os.getcwd()


def _get_git_head_sha(project_root: str) -> Optional[str]:
    """Return the current git HEAD SHA, or None if git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass  # git not installed
    return None


def _git_commit_delta(project_root: str, old_sha: str) -> Optional[int]:
    """Count commits between *old_sha* and current HEAD. Returns None on error."""
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{old_sha}..HEAD"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except (FileNotFoundError, ValueError):
        pass
    return None


def interrupt_all_running(
    state: Dict[str, Any],
    reason: str = "quota_exhausted",
) -> List[str]:
    """Set every *running* agent to *interrupted* with the given reason.

    Returns the list of agent IDs that were interrupted.
    """
    interrupted_ids: List[str] = []
    for agent in state.get("agents", []):
        if agent["status"] == "running":
            agent["status"] = "interrupted"
            agent["interrupt_reason"] = reason
            agent["completed_at"] = _now_iso()
            interrupted_ids.append(agent["agent_id"])
    return interrupted_ids


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> int:
    """Create a new orchestration_state.json."""
    project_root = _resolve_project_root()
    path = _state_path(project_root)

    if path.exists() and not args.force:
        print(
            f"{_YELLOW}WARNING:{_RESET} State file already exists: {path}\n"
            f"  Use --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    # Extract profile name from path
    profile_path = Path(args.profile)
    profile_name = profile_path.stem  # e.g. "engineering" from "conductor/profiles/engineering.json"

    # H3: capture git HEAD SHA at init for divergence detection on resume
    head_sha = _get_git_head_sha(project_root)

    state: Dict[str, Any] = {
        "run_id": args.run_id,
        "profile": profile_name,
        "start_time": _now_iso(),
        "created_at": _now_iso(),
        "last_updated": _now_iso(),
        "status": "running",
        "main_branch_sha": head_sha,
        "agents": [],
    }

    _save_state(project_root, state)
    print(f"{_GREEN}✅ Orchestration state initialised{_RESET}")
    print(f"   Run ID  : {_BOLD}{args.run_id}{_RESET}")
    print(f"   Profile : {profile_name}")
    if head_sha:
        print(f"   HEAD SHA: {_DIM}{head_sha[:12]}{_RESET}")
    print(f"   File    : {path}")
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    """Register a new agent in the orchestration state."""
    project_root = _resolve_project_root()
    state = _load_state(project_root)

    if state["run_id"] != args.run_id:
        print(
            f"{_RED}ERROR:{_RESET} Run ID mismatch: "
            f"state has '{state['run_id']}', got '{args.run_id}'",
            file=sys.stderr,
        )
        return 1

    # Check for duplicate agent_id
    if _find_agent(state, args.agent_id):
        print(
            f"{_YELLOW}WARNING:{_RESET} Agent '{args.agent_id}' is already "
            f"registered. Skipping.",
            file=sys.stderr,
        )
        return 0

    agent_entry: Dict[str, Any] = {
        "agent_id": args.agent_id,
        "role": args.role,
        "phase": args.phase,
        "status": "pending",
        "retries": 0,
        "output_path": None,
        "started_at": None,
        "completed_at": None,
        "interrupt_reason": None,
    }

    state["agents"].append(agent_entry)
    _save_state(project_root, state)

    print(
        f"{_GREEN}✅{_RESET} Registered agent "
        f"{_BOLD}{args.agent_id}{_RESET} "
        f"(role={args.role}, phase={args.phase})"
    )
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    """Update an agent's status in the orchestration state."""
    project_root = _resolve_project_root()
    state = _load_state(project_root)

    if state["run_id"] != args.run_id:
        print(
            f"{_RED}ERROR:{_RESET} Run ID mismatch: "
            f"state has '{state['run_id']}', got '{args.run_id}'",
            file=sys.stderr,
        )
        return 1

    agent = _find_agent(state, args.agent_id)
    if agent is None:
        print(
            f"{_RED}ERROR:{_RESET} Agent '{args.agent_id}' not found in state.",
            file=sys.stderr,
        )
        return 1

    new_status = args.status
    if new_status not in VALID_AGENT_STATUSES:
        print(
            f"{_RED}ERROR:{_RESET} Invalid status '{new_status}'. "
            f"Valid: {', '.join(sorted(VALID_AGENT_STATUSES))}",
            file=sys.stderr,
        )
        return 1

    old_status = agent["status"]
    agent["status"] = new_status

    # Timestamp bookkeeping
    if new_status == "running" and old_status != "running":
        agent["started_at"] = _now_iso()
    if new_status in ("completed", "failed", "interrupted"):
        agent["completed_at"] = _now_iso()
    if new_status == "failed":
        agent["retries"] = agent.get("retries", 0) + 1
    if new_status == "interrupted" and args.interrupt_reason:
        agent["interrupt_reason"] = args.interrupt_reason

    if args.output_path:
        agent["output_path"] = args.output_path

    # Recompute overall run status (with optional failure strategy)
    failure_strategy = getattr(args, "failure_strategy", None)
    # OBS-2: If no explicit CLI override, auto-read from the profile
    if failure_strategy is None:
        failure_strategy = _load_profile_failure_strategy(project_root, state)
    _recompute_run_status(state, failure_strategy=failure_strategy)
    _save_state(project_root, state)

    colour, emoji = _STATUS_STYLE.get(new_status, (_RESET, "•"))
    print(
        f"{colour}{emoji}{_RESET} Agent {_BOLD}{args.agent_id}{_RESET}: "
        f"{old_status} → {new_status}"
    )
    return 0


def _recompute_run_status(
    state: Dict[str, Any],
    failure_strategy: Optional[str] = None,
) -> None:
    """Derive the overall run status from individual agent statuses.

    If *failure_strategy* is ``"all_or_nothing"`` and any agent has failed,
    the entire run is immediately marked as failed.
    """
    agents = state.get("agents", [])
    if not agents:
        state["status"] = "running"
        return

    # NEW-3 helper: determine if an agent counts as a terminal failure
    def _is_hard_failure(a: Dict[str, Any]) -> bool:
        if a["status"] == "failed":
            return True
        if (
            a["status"] == "interrupted"
            and a.get("interrupt_reason") != "quota_exhausted"
        ):
            return True
        return False

    # M4: all_or_nothing – any single failure halts the run
    if failure_strategy == "all_or_nothing":
        for a in agents:
            if _is_hard_failure(a):
                label = a["status"]
                if a["status"] == "interrupted":
                    label = f"interrupted ({a.get('interrupt_reason', 'unknown')})"
                print(
                    f"{_RED}all_or_nothing: Agent {a['agent_id']} {label}. "
                    f"Halting entire run.{_RESET}",
                    file=sys.stderr,
                )
                state["status"] = "failed"
                return

    statuses = {a["status"] for a in agents}

    # Determine which agents are in a truly terminal state:
    #   completed, failed, or interrupted with a non-quota reason
    terminal_agents = [
        a for a in agents
        if a["status"] in ("completed", "failed")
        or (
            a["status"] == "interrupted"
            and a.get("interrupt_reason") != "quota_exhausted"
        )
    ]
    all_terminal = len(terminal_agents) == len(agents)

    if statuses == {"completed"}:
        state["status"] = "completed"
    elif all_terminal:
        # Every agent reached a terminal state – compute final result
        has_failure = any(_is_hard_failure(a) for a in agents)
        has_completed = any(a["status"] == "completed" for a in agents)
        if has_failure and has_completed:
            state["status"] = "partial"
        elif has_failure:
            state["status"] = "failed"
        else:
            state["status"] = "completed"
    elif "running" in statuses or "pending" in statuses or "interrupted" in statuses:
        state["status"] = "running"
    elif "failed" in statuses and "completed" in statuses:
        state["status"] = "partial"
    elif statuses == {"failed"}:
        state["status"] = "failed"
    else:
        state["status"] = "running"


def cmd_status(args: argparse.Namespace) -> int:
    """Print a coloured summary of the orchestration state."""
    project_root = _resolve_project_root()
    state = _load_state(project_root)

    if state["run_id"] != args.run_id:
        print(
            f"{_RED}ERROR:{_RESET} Run ID mismatch: "
            f"state has '{state['run_id']}', got '{args.run_id}'",
            file=sys.stderr,
        )
        return 1

    run_colour, run_emoji = _RUN_STATUS_STYLE.get(
        state["status"], (_RESET, "•")
    )

    print(f"\n{_BOLD}╔══════════════════════════════════════════╗{_RESET}")
    print(f"{_BOLD}║  Orchestration Status                    ║{_RESET}")
    print(f"{_BOLD}╚══════════════════════════════════════════╝{_RESET}\n")
    print(f"  Run ID    : {_BOLD}{state['run_id']}{_RESET}")
    print(f"  Profile   : {state['profile']}")
    print(f"  Started   : {state['start_time']}")
    print(f"  Updated   : {state['last_updated']}")
    print(f"  Status    : {run_colour}{run_emoji} {state['status'].upper()}{_RESET}")

    agents = state.get("agents", [])
    if not agents:
        print(f"\n  {_DIM}No agents registered.{_RESET}\n")
        return 0

    # Summary counts
    counts: Dict[str, int] = {
        "pending": 0, "running": 0, "completed": 0, "failed": 0, "interrupted": 0,
    }
    for a in agents:
        counts[a["status"]] = counts.get(a["status"], 0) + 1

    print(f"\n  {_BOLD}Agents ({len(agents)}):{_RESET}")
    interrupted_str = ""
    if counts["interrupted"]:
        interrupted_str = f"  {_YELLOW}⚡ {counts['interrupted']} interrupted{_RESET}"
    print(
        f"    {_GREEN}✅ {counts['completed']} completed{_RESET}  "
        f"{_CYAN}🔄 {counts['running']} running{_RESET}  "
        f"{_YELLOW}⏳ {counts['pending']} pending{_RESET}  "
        f"{_RED}❌ {counts['failed']} failed{_RESET}"
        f"{interrupted_str}"
    )

    # Per-phase grouping
    phases: Dict[str, List[Dict[str, Any]]] = {}
    for a in agents:
        phase = a.get("phase", "unknown")
        phases.setdefault(phase, []).append(a)

    for phase, phase_agents in phases.items():
        print(f"\n  {_BOLD}Phase: {phase}{_RESET}")
        for a in phase_agents:
            colour, emoji = _STATUS_STYLE.get(a["status"], (_RESET, "•"))
            retry_info = ""
            if a["retries"] > 0:
                retry_info = f" {_DIM}(retries: {a['retries']}){_RESET}"
            output_info = ""
            if a.get("output_path"):
                output_info = f" {_DIM}→ {a['output_path']}{_RESET}"
            print(
                f"    {colour}{emoji}{_RESET} {a['agent_id']:<20s} "
                f"{_DIM}[{a['role']}]{_RESET} "
                f"{colour}{a['status']}{_RESET}"
                f"{retry_info}{output_info}"
            )

    print()
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    """Print agents that need to be (re-)dispatched for crash recovery."""
    project_root = _resolve_project_root()
    state = _load_state(project_root)

    if state["run_id"] != args.run_id:
        print(
            f"{_RED}ERROR:{_RESET} Run ID mismatch: "
            f"state has '{state['run_id']}', got '{args.run_id}'",
            file=sys.stderr,
        )
        return 1

    # -----------------------------------------------------------------
    # H3: main-branch divergence check
    # -----------------------------------------------------------------
    stored_sha = state.get("main_branch_sha")
    divergence_delta: Optional[int] = None
    if stored_sha:
        current_sha = _get_git_head_sha(project_root)
        if current_sha and current_sha != stored_sha:
            divergence_delta = _git_commit_delta(project_root, stored_sha)
            n = divergence_delta if divergence_delta is not None else "?"
            print(
                f"{_YELLOW}WARNING:{_RESET} main has diverged by "
                f"{_BOLD}{n}{_RESET} commits since this run started.",
                file=sys.stderr,
            )

    # H3: staleness check (max_stale_hours = 24)
    created_at_str = state.get("created_at")
    stale_hours: Optional[float] = None
    if created_at_str:
        try:
            created_dt = datetime.fromisoformat(created_at_str)
            age = datetime.now(timezone.utc) - created_dt
            stale_hours = age.total_seconds() / 3600
            if stale_hours > 24:
                print(
                    f"{_YELLOW}WARNING:{_RESET} This run state is "
                    f"{_BOLD}{stale_hours:.1f}{_RESET} hours old. "
                    f"Consider re-planning.",
                    file=sys.stderr,
                )
        except (ValueError, TypeError):
            pass

    # Load profile to get max retries if available
    max_retries = 2  # default
    profile_path = _find_profile(project_root, state["profile"])
    if profile_path:
        try:
            with open(profile_path, "r", encoding="utf-8") as fh:
                profile = json.load(fh)
            fs = profile.get("failure_strategy", {})
            max_retries = fs.get("max_retry_attempts",
                                 profile.get("budget", {}).get("max_retries_per_agent", 2))
        except (OSError, json.JSONDecodeError):
            pass  # Use default

    agents = state.get("agents", [])
    resumable: List[Dict[str, Any]] = []

    for a in agents:
        if a["status"] == "pending":
            resumable.append(a)
        elif a["status"] == "failed" and a.get("retries", 0) < max_retries:
            resumable.append(a)
        elif a["status"] == "running":
            # An agent stuck in "running" after a crash should be re-dispatched
            resumable.append(a)
        elif a["status"] == "interrupted":
            # H2: interrupted agents are treated like stale running agents
            interrupt_reason = a.get("interrupt_reason", "unknown")
            print(
                f"{_YELLOW}INFO:{_RESET} Agent '{a['agent_id']}' was "
                f"interrupted (reason: {interrupt_reason}). Scheduling re-dispatch.",
                file=sys.stderr,
            )
            resumable.append(a)

    if not resumable:
        print(f"{_GREEN}✅ No agents need to be re-dispatched.{_RESET}")
        return 0

    print(f"\n{_BOLD}Agents to re-dispatch ({len(resumable)}):{_RESET}\n")
    for a in resumable:
        colour, emoji = _STATUS_STYLE.get(a["status"], (_RESET, "•"))
        reason = ""
        if a["status"] == "failed":
            reason = f" {_DIM}(retry {a.get('retries', 0)}/{max_retries}){_RESET}"
        elif a["status"] == "running":
            reason = f" {_DIM}(stale – was running at crash){_RESET}"
        elif a["status"] == "interrupted":
            ir = a.get("interrupt_reason", "unknown")
            reason = f" {_DIM}(interrupted – {ir}){_RESET}"
        print(
            f"  {colour}{emoji}{_RESET} {a['agent_id']:<20s} "
            f"{_DIM}[{a['role']}]{_RESET}  "
            f"phase={a['phase']}"
            f"{reason}"
        )

    # Output machine-readable list on a separate line for piping
    print(f"\n{_DIM}Machine-readable agent IDs:{_RESET}")
    for a in resumable:
        print(a["agent_id"])

    # Include divergence metadata in output for downstream consumers
    if divergence_delta is not None or stale_hours is not None:
        print(f"\n{_DIM}Resume metadata:{_RESET}")
        if divergence_delta is not None:
            print(f"  main_branch_diverged_commits: {divergence_delta}")
        if stale_hours is not None:
            print(f"  state_age_hours: {stale_hours:.1f}")

    print()
    return 0


def _find_profile(project_root: str, profile_name: str) -> Optional[str]:
    """Locate a profile JSON by name within the conductor/profiles directory."""
    profiles_dir = Path(project_root) / "conductor" / "profiles"
    candidate = profiles_dir / f"{profile_name}.json"
    if candidate.exists():
        return str(candidate)
    return None


def _load_profile_failure_strategy(
    project_root: str, state: Dict[str, Any]
) -> Optional[str]:
    """Read the failure strategy from the profile referenced in *state*.

    Returns the ``failure_strategy.strategy`` string from the profile JSON,
    or ``None`` if the profile cannot be found or parsed.
    """
    profile_name = state.get("profile")
    if not profile_name:
        return None
    # Sanitize: reject path traversal characters before resolving
    if "/" in profile_name or "\\" in profile_name or ".." in profile_name:
        return None
    profile_path = _find_profile(project_root, profile_name)
    if not profile_path:
        return None
    try:
        with open(profile_path, "r", encoding="utf-8") as fh:
            profile = json.load(fh)
        return profile.get("failure_strategy", {}).get("strategy")
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Orchestration state manager for crash recovery.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s init --run-id abc123 --profile conductor/profiles/engineering.json\n"
            "  %(prog)s register --run-id abc123 --agent-id fe1 --role frontend_developer --phase implementation\n"
            "  %(prog)s update --run-id abc123 --agent-id fe1 --status completed --output-path output/fe1/\n"
            "  %(prog)s status --run-id abc123\n"
            "  %(prog)s resume --run-id abc123\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- init ---------------------------------------------------------------
    p_init = subparsers.add_parser("init", help="Create a new orchestration state file")
    p_init.add_argument("--run-id", required=True, help="Unique run identifier")
    p_init.add_argument("--profile", required=True, help="Path to the profile JSON")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing state file")

    # -- register -----------------------------------------------------------
    p_reg = subparsers.add_parser("register", help="Register a new agent")
    p_reg.add_argument("--run-id", required=True, help="Run identifier")
    p_reg.add_argument("--agent-id", required=True, help="Unique agent name")
    p_reg.add_argument("--role", required=True, help="Agent role (e.g. backend_developer)")
    p_reg.add_argument("--phase", required=True, help="Phase this agent belongs to")

    # -- update -------------------------------------------------------------
    p_upd = subparsers.add_parser("update", help="Update an agent's status")
    p_upd.add_argument("--run-id", required=True, help="Run identifier")
    p_upd.add_argument("--agent-id", required=True, help="Agent name to update")
    p_upd.add_argument(
        "--status", required=True,
        choices=sorted(VALID_AGENT_STATUSES),
        help="New status",
    )
    p_upd.add_argument("--output-path", default=None, help="Path to agent output")
    p_upd.add_argument(
        "--interrupt-reason", default=None, dest="interrupt_reason",
        help="Reason for interruption (e.g. quota_exhausted)",
    )
    p_upd.add_argument(
        "--failure-strategy", default=None, dest="failure_strategy",
        choices=["all_or_nothing"],
        help="Override failure strategy for run-status recomputation",
    )

    # -- status -------------------------------------------------------------
    p_stat = subparsers.add_parser("status", help="Show orchestration status summary")
    p_stat.add_argument("--run-id", required=True, help="Run identifier")

    # -- resume -------------------------------------------------------------
    p_res = subparsers.add_parser("resume", help="List agents to re-dispatch")
    p_res.add_argument("--run-id", required=True, help="Run identifier")

    args = parser.parse_args(argv)

    dispatch = {
        "init": cmd_init,
        "register": cmd_register,
        "update": cmd_update,
        "status": cmd_status,
        "resume": cmd_resume,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
