#!/usr/bin/env python3
"""Crescendo Pre-flight Infrastructure Check.

Verifies that all required skills, scripts, tools, and files are present
before any Crescendo operation begins. Exit code 0 = all clear, 1 = issues found.

Run: python conductor/bin/preflight_check.py [--project-root <path>]
"""
import os
import sys
import shutil
import json
import argparse
from pathlib import Path


def _check(label: str, condition: bool, fix: str = "") -> bool:
    """Print a pass/fail line and return the condition."""
    icon = "✅" if condition else "❌"
    msg = f"  {icon} {label}"
    if not condition and fix:
        msg += f"\n     ↳ Fix: {fix}"
    print(msg)
    return condition


def run_preflight(project_root: str) -> int:
    """Run all preflight checks. Returns 0 if all pass, 1 if any fail."""
    root = Path(project_root)
    all_pass = True

    print("\n╔══════════════════════════════════════════╗")
    print("║   CRESCENDO INFRASTRUCTURE PRE-FLIGHT    ║")
    print("╚══════════════════════════════════════════╝\n")

    # --- Section 1: Required Tools ---
    print("[1/5] External Tools")
    all_pass &= _check("git", shutil.which("git") is not None,
                       "Install git: https://git-scm.com")
    all_pass &= _check("python 3.10+", sys.version_info >= (3, 10),
                       f"Current: {sys.version}. Need 3.10+")
    all_pass &= _check("just (task runner)", shutil.which("just") is not None,
                       "Install: https://just.systems/man/en/installation.html")
    gh_installed = shutil.which("gh") is not None
    _check(f"gh (GitHub CLI) — {'installed' if gh_installed else 'optional, needed for HITL'}",
           True)  # always pass — gh is optional
    print()

    # --- Section 2: Required Files ---
    print("[2/5] Core Files")
    core_files = [
        "GEMINI.md",
        "justfile",
        "conductor/workflow.md",
        "conductor/index.md",
        "conductor/product.md",
        "conductor/tech-stack.md",
        "conductor/tracks.md",
        "conductor/schemas/claims.schema.json",
    ]
    for f in core_files:
        all_pass &= _check(f, (root / f).exists(),
                           f"Missing file: {f}")
    print()

    # --- Section 3: Conductor Scripts ---
    print("[3/5] Conductor Scripts")
    scripts = [
        "conductor/bin/orchestration_state.py",
        "conductor/bin/run_deterministic_gates.py",
        "conductor/bin/cross_validate_outputs.py",
        "conductor/bin/sanitize_inputs.py",
        "conductor/bin/git_status_patched.py",
        "conductor/bin/conductor-inspector",
        "conductor/bin/inject-ghi",
        "conductor/bin/poll_ghi_questions.py",
        "conductor/bin/preflight_check.py",
    ]
    for s in scripts:
        all_pass &= _check(s, (root / s).exists(),
                           f"Missing script: {s}")
    print()

    # --- Section 4: Domain Profiles ---
    print("[4/5] Domain Profiles")
    profiles_dir = root / "conductor" / "profiles"
    if profiles_dir.is_dir():
        profiles = list(profiles_dir.glob("*.json"))
        _check(f"{len(profiles)} profile(s) found", len(profiles) > 0,
               "No profiles in conductor/profiles/")
        for p in profiles:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                version = data.get("version", "unknown")
                domain = data.get("domain", "unknown")
                _check(f"  {p.name} (domain={domain}, v{version})", True)
            except (json.JSONDecodeError, OSError) as e:
                all_pass &= _check(f"  {p.name}", False, str(e))
    else:
        all_pass &= _check("conductor/profiles/ directory", False,
                           "Directory missing")
    print()

    # --- Section 5: Skills ---
    print("[5/5] Packaged Skills")
    required_skills = [
        "using-git-worktrees",
        "conductor-worktree-hitl",
        "crescendo-init",
        "conductor-setup",
        "conductor-implement",
        "conductor-newTrack",
        "conductor-review",
        "conductor-status",
        "conductor-revert",
    ]
    skills_dir = root / ".agents" / "skills"
    for skill_name in required_skills:
        skill_file = skills_dir / skill_name / "SKILL.md"
        all_pass &= _check(
            skill_name, skill_file.exists(),
            f"Missing: .agents/skills/{skill_name}/SKILL.md"
        )
    print()

    # --- Summary ---
    if all_pass:
        print("🟢 ALL CHECKS PASSED — Crescendo is ready to run.\n")
        return 0
    else:
        print("🔴 ISSUES FOUND — Fix the items above before running Crescendo.\n")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crescendo pre-flight check")
    parser.add_argument("--project-root", default=os.getcwd(),
                        help="Root of the Crescendo project (default: cwd)")
    args = parser.parse_args()
    sys.exit(run_preflight(args.project_root))
