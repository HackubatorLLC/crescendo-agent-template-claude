#!/usr/bin/env python3
"""
sanitize_inputs.py — Input Sanitization Layer for Crescendo Agent Template

Walks all files in the input/ directory and sanitizes text files by stripping:
  - HTML comments  (<!-- ... -->)
  - Invisible / zero-width Unicode characters
  - Lines matching common prompt-injection patterns

Binary files (.pdf, .docx, .xlsx) are copied as-is with a warning.

Sanitized output is written to  input/.sanitized/  preserving the original
folder structure.  Exit code 1 if any suspicious content was found, 0 if clean.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

# ── Project root = two levels up from conductor/bin/ ────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = INPUT_DIR / ".sanitized"

# ── File-type classification ───────────────────────────────────────────────
TEXT_EXTENSIONS = {".md", ".txt", ".json", ".csv", ".yaml", ".yml"}
BINARY_EXTENSIONS = {".pdf", ".docx", ".xlsx"}

# ── Invisible / zero-width Unicode codepoints ──────────────────────────────
INVISIBLE_CHARS: set[str] = {
    "\u200B",  # ZERO WIDTH SPACE
    "\u200C",  # ZERO WIDTH NON-JOINER
    "\u200D",  # ZERO WIDTH JOINER
    "\uFEFF",  # BYTE ORDER MARK / ZERO WIDTH NO-BREAK SPACE
    "\u2060",  # WORD JOINER
    "\u2061",  # FUNCTION APPLICATION
    "\u2062",  # INVISIBLE TIMES
    "\u2063",  # INVISIBLE SEPARATOR
    "\u2064",  # INVISIBLE PLUS
    "\u180E",  # MONGOLIAN VOWEL SEPARATOR
    "\u00AD",  # SOFT HYPHEN
}
INVISIBLE_RE = re.compile("[" + "".join(INVISIBLE_CHARS) + "]+")

# ── HTML comment regex (single- and multi-line) ───────────────────────────
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# ── Prompt-injection line patterns (case-insensitive, full-line match) ─────
INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*IGNORE\s+ALL\s+PREVIOUS\s+INSTRUCTIONS\b", re.IGNORECASE),
    re.compile(r"^\s*DISREGARD\s+(ALL\s+)?PREVIOUS\b", re.IGNORECASE),
    re.compile(r"^\s*FORGET\s+(ALL\s+)?(PREVIOUS|PRIOR|ABOVE)\b", re.IGNORECASE),
    re.compile(r"^\s*You\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"^\s*SYSTEM\s*:", re.IGNORECASE),
    re.compile(r"^\s*ASSISTANT\s*:", re.IGNORECASE),
    re.compile(r"^\s*NEW\s+INSTRUCTIONS?\s*:", re.IGNORECASE),
    re.compile(r"^\s*BEGIN\s+NEW\s+PROMPT\b", re.IGNORECASE),
    re.compile(r"^\s*<\|im_start\|>", re.IGNORECASE),
    re.compile(r"^\s*<\|system\|>", re.IGNORECASE),
]

# ── ANSI colour helpers ───────────────────────────────────────────────────
_SUPPORTS_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    """Wrap *text* in ANSI colour if the terminal supports it."""
    if _SUPPORTS_COLOR:
        return f"\033[{code}m{text}\033[0m"
    return text


def red(t: str) -> str:
    return _c("91", t)


def yellow(t: str) -> str:
    return _c("93", t)


def green(t: str) -> str:
    return _c("92", t)


def cyan(t: str) -> str:
    return _c("96", t)


def bold(t: str) -> str:
    return _c("1", t)


# ── Sanitisation stats ───────────────────────────────────────────────────
class Stats:
    def __init__(self) -> None:
        self.files_scanned: int = 0
        self.files_clean: int = 0
        self.html_comments_stripped: int = 0
        self.invisible_chars_stripped: int = 0
        self.injection_lines_stripped: int = 0
        self.binary_files_copied: int = 0
        self.files_with_issues: list[str] = []


# ── Core sanitisation ────────────────────────────────────────────────────
def sanitize_text(content: str, rel_path: str, stats: Stats) -> str:
    """Return sanitised text and update *stats* with findings."""
    dirty = False

    # 1. Strip HTML comments
    html_hits = len(HTML_COMMENT_RE.findall(content))
    if html_hits:
        content = HTML_COMMENT_RE.sub("", content)
        stats.html_comments_stripped += html_hits
        dirty = True

    # 2. Strip invisible Unicode characters
    inv_hits = len(INVISIBLE_RE.findall(content))
    if inv_hits:
        content = INVISIBLE_RE.sub("", content)
        stats.invisible_chars_stripped += inv_hits
        dirty = True

    # 3. Strip prompt-injection lines
    clean_lines: list[str] = []
    for line in content.splitlines(keepends=True):
        matched = False
        for pat in INJECTION_PATTERNS:
            if pat.search(line):
                stats.injection_lines_stripped += 1
                dirty = True
                matched = True
                print(
                    f"  {red('⚠ INJECTION')}  {cyan(rel_path)}  →  {line.rstrip()}"
                )
                break
        if not matched:
            clean_lines.append(line)
    content = "".join(clean_lines)

    if dirty:
        stats.files_with_issues.append(rel_path)
    else:
        stats.files_clean += 1

    return content


def process_file(path: Path, stats: Stats) -> None:
    """Sanitise or copy a single file under INPUT_DIR."""
    rel = path.relative_to(INPUT_DIR)
    rel_str = str(rel).replace("\\", "/")
    ext = path.suffix.lower()
    dest = OUTPUT_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)

    stats.files_scanned += 1

    if ext in TEXT_EXTENSIONS:
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = path.read_text(encoding="utf-8", errors="replace")
            print(f"  {yellow('⚠ ENCODING')}  {cyan(rel_str)}  — read with replacement chars")

        cleaned = sanitize_text(raw, rel_str, stats)
        dest.write_text(cleaned, encoding="utf-8")

    elif ext in BINARY_EXTENSIONS:
        shutil.copy2(path, dest)
        stats.binary_files_copied += 1
        print(
            f"  {yellow('⚠ BINARY')}   {cyan(rel_str)}  — copied as-is; manual review recommended"
        )

    else:
        # Unknown extension — treat as text (best-effort)
        try:
            raw = path.read_text(encoding="utf-8")
            cleaned = sanitize_text(raw, rel_str, stats)
            dest.write_text(cleaned, encoding="utf-8")
        except (UnicodeDecodeError, ValueError):
            # Truly binary — copy verbatim
            shutil.copy2(path, dest)
            stats.binary_files_copied += 1
            print(
                f"  {yellow('⚠ BINARY')}   {cyan(rel_str)}  — copied as-is; manual review recommended"
            )


# ── Entry point ──────────────────────────────────────────────────────────
def main() -> int:
    print(bold("\n🛡️  Input Sanitization Layer"))
    print(f"   Source : {INPUT_DIR}")
    print(f"   Output : {OUTPUT_DIR}\n")

    if not INPUT_DIR.is_dir():
        print(red(f"ERROR: input/ directory not found at {INPUT_DIR}"))
        return 1

    # Clean previous sanitised output
    if OUTPUT_DIR.is_dir():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    stats = Stats()

    for root, _dirs, files in os.walk(INPUT_DIR):
        root_path = Path(root)
        # Skip the .sanitized output directory itself
        if root_path == OUTPUT_DIR or OUTPUT_DIR in root_path.parents:
            continue
        for fname in sorted(files):
            process_file(root_path / fname, stats)

    # ── Summary ──────────────────────────────────────────────────────────
    suspicious = bool(stats.files_with_issues)

    print(bold("\n── Summary " + "─" * 50))
    print(f"  Files scanned            : {stats.files_scanned}")
    print(f"  Files clean              : {green(str(stats.files_clean))}")
    print(f"  HTML comments stripped   : {yellow(str(stats.html_comments_stripped)) if stats.html_comments_stripped else '0'}")
    print(f"  Invisible chars stripped : {yellow(str(stats.invisible_chars_stripped)) if stats.invisible_chars_stripped else '0'}")
    print(f"  Injection lines stripped : {red(str(stats.injection_lines_stripped)) if stats.injection_lines_stripped else '0'}")
    print(f"  Binary files (copied)    : {stats.binary_files_copied}")

    if suspicious:
        print(f"\n  {red('✗')} Suspicious content found in {len(stats.files_with_issues)} file(s):")
        for f in stats.files_with_issues:
            print(f"      • {f}")
        print(f"\n  Sanitised files written to {cyan(str(OUTPUT_DIR))}")
        print(f"  {red('Returning exit code 1.')}\n")
        return 1
    else:
        print(f"\n  {green('✓')} All files clean — no suspicious content detected.")
        print(f"  Sanitised copy written to {cyan(str(OUTPUT_DIR))}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
