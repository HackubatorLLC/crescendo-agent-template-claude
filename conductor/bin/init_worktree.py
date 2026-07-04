#!/usr/bin/env python3
"""Cross-platform worktree initializer for the Crescendo orchestration flow.

Creates an isolated git worktree for a (track_id, role) pair and copies the
shared ``conductor/`` config and ``.env`` into it as READ-ONLY. Isolation is
enforced at the OS level so an agent process cannot mutate the single source
of truth for all worktrees:

  * Windows : NTFS ACLs via ``icacls`` (deny write to Everyone). Cannot be
              bypassed by flipping the read-only file attribute.
  * POSIX   : recursive ``chmod`` removing the write bit (u/g/o -w).

This replaces the Windows-only PowerShell logic that previously lived in the
``justfile``. Ported from the Antigravity/Gemini Conductor template.

Usage:
    python conductor/bin/init_worktree.py <track_id> <role>
"""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, text=True)


def make_readonly(path: Path) -> None:
    """Recursively make a file or directory tree read-only, cross-platform."""
    if os.name == "nt":
        # NTFS ACL: deny write to Everyone, applied to the whole tree (/T).
        subprocess.run(
            ["icacls", str(path), "/deny", "Everyone:(OI)(CI)(W)", "/T", "/Q"],
            check=False,
        )
        return
    # POSIX: strip write bits from every file and directory.
    ro_mask = ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    if path.is_file():
        path.chmod(path.stat().st_mode & ro_mask)
        return
    for root, dirs, files in os.walk(path):
        for name in files + dirs:
            p = Path(root) / name
            try:
                p.chmod(p.stat().st_mode & ro_mask)
            except OSError:
                pass
    path.chmod(path.stat().st_mode & ro_mask)


def add_git_exclude(track_role: str, entry: str) -> None:
    """Add an entry to the worktree's private git exclude file."""
    exclude = Path(".git") / "worktrees" / track_role / "info" / "exclude"
    if exclude.parent.exists():
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a", encoding="utf-8") as fh:
            fh.write(entry + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize an isolated Crescendo worktree.")
    parser.add_argument("track_id")
    parser.add_argument("role")
    args = parser.parse_args()

    track_role = f"{args.track_id}-{args.role}"
    wt = Path(".worktrees") / track_role
    branch = f"feature/{args.track_id}"

    print(f"Initializing worktree for track {args.track_id} role {args.role}...")

    # Create the worktree. Reuse the branch if it already exists.
    branch_exists = subprocess.run(
        ["git", "rev-parse", "--verify", branch],
        capture_output=True, text=True,
    ).returncode == 0
    if branch_exists:
        run(["git", "worktree", "add", str(wt), branch])
    else:
        run(["git", "worktree", "add", str(wt), "-b", branch])

    # DATA ISOLATION: copy conductor/ as a read-only tree (never a symlink —
    # a symlink would let any agent mutate the shared source of truth).
    print("Copying conductor/ (read-only) into worktree...")
    dest_conductor = wt / "conductor"
    if dest_conductor.exists():
        shutil.rmtree(dest_conductor, ignore_errors=True)
    shutil.copytree("conductor", dest_conductor)
    make_readonly(dest_conductor)

    # Copy .env read-only if present (agents must not mutate shared credentials).
    if Path(".env").exists():
        print("Copying .env (read-only)...")
        shutil.copy2(".env", wt / ".env")
        make_readonly(wt / ".env")

    # Keep the copied conductor/ and .env out of the worktree's git index.
    print("Updating git excludes...")
    add_git_exclude(track_role, "conductor")
    add_git_exclude(track_role, ".env")

    print(f"Worktree ready at {wt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
