import os
import json
import subprocess
from pathlib import Path

def get_git_status(path):
    try:
        result = subprocess.run(['git', 'status', '--porcelain'], cwd=path, capture_output=True, text=True)
        return result.stdout.strip()
    except Exception:
        return "Error fetching git status"

def main():
    print("\n\033[1;36m=== Conductor Multi-Agent Worktree Status ===\033[0m\n")
    worktrees_dir = Path(".worktrees")
    if not worktrees_dir.exists() or not worktrees_dir.is_dir():
        print("No active worktrees found.")
        return

    for wt in worktrees_dir.iterdir():
        if not wt.is_dir():
            continue
        
        print(f"\033[1;33mWorktree: {wt.name}\033[0m")
        
        # Attempt to parse metadata.json based on track ID
        track_id = wt.name.split('-')[0]
        metadata_path = wt / "conductor" / "tracks" / track_id / "metadata.json"
        
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    meta = json.load(f)
                    agent = meta.get("agent", "Unknown")
                    status = meta.get("status", "Unknown")
                    questions = meta.get("active_questions", [])
                    
                    print(f"  Agent: \033[1;32m{agent}\033[0m")
                    print(f"  Track Status: {status}")
                    if questions:
                        print(f"  Active Questions ({len(questions)}):")
                        for q in questions:
                            q_status = q.get("status", "unknown")
                            print(f"    - [{q_status}] {q.get('question', '')[:50]}...")
            except Exception as e:
                print(f"  [Error parsing metadata: {e}]")
        else:
            print("  [No metadata.json found for this track]")
        
        # Print git status
        git_stat = get_git_status(wt)
        if git_stat:
            print("  Git Status (Porcelain):")
            for line in git_stat.split('\n'):
                print(f"    {line}")
        else:
            print("  Git Status: Clean")
        print()

if __name__ == "__main__":
    main()
