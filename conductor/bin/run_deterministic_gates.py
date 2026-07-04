#!/usr/bin/env python3
"""Deterministic quality gate runner.

Reads a conductor profile JSON, identifies all quality gates with
``mechanism: deterministic``, and executes them.  Uses only the Python
standard library.

Supported gate types:
    unit_tests          – runs ``npm test`` or ``pytest``
    lint                – runs ``npm run lint`` or ``flake8``
    citation_audit      – checks Article/Section references against source docs
    source_verification – validates URL format in output files
    recency_check       – flags dates older than 6 months

Exit codes:
    0 – all *required* gates passed (or were skipped as not applicable)
    1 – at least one required gate failed
    2 – all gates were skipped; results are inconclusive (auto-merge should NOT proceed)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Exit-code constants
# ---------------------------------------------------------------------------

EXIT_INCONCLUSIVE = 2

# ---------------------------------------------------------------------------
# ANSI colours (respects NO_COLOR and non-tty)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_project_root() -> str:
    """Walk upward from the script location to find the project root."""
    start = Path(__file__).resolve().parent  # conductor/bin/
    candidate = start.parent.parent          # project root
    if (candidate / "conductor").is_dir() or (candidate / "justfile").exists():
        return str(candidate)
    return os.getcwd()


def _find_files(directory: str, extensions: Set[str]) -> List[str]:
    """Recursively find files by extension under *directory*."""
    found: List[str] = []
    root = Path(directory)
    if not root.is_dir():
        return found
    for dirpath, _dirs, filenames in os.walk(root):
        for fname in filenames:
            if Path(fname).suffix.lower() in extensions:
                found.append(os.path.join(dirpath, fname))
    return sorted(found)


def _read_text(path: str) -> str:
    """Read file contents, tolerating encoding errors."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _which(cmd: str) -> bool:
    """Check whether a command is available on PATH (cross-platform)."""
    import shutil
    return shutil.which(cmd) is not None


def _run_external(cmd: List[str], cwd: str) -> Tuple[int, str]:
    """Run an external command, returning (exit_code, combined_output)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode, output.strip()
    except FileNotFoundError:
        return -1, f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, f"Command timed out after 120s: {' '.join(cmd)}"
    except OSError as exc:
        return -1, f"OS error running {cmd[0]}: {exc}"


# ---------------------------------------------------------------------------
# Gate result
# ---------------------------------------------------------------------------

class GateResult:
    """Outcome of a single quality gate."""

    __slots__ = ("gate_type", "required", "passed", "skipped", "details")

    def __init__(
        self,
        gate_type: str,
        required: bool,
        passed: bool,
        skipped: bool = False,
        details: str = "",
    ):
        self.gate_type = gate_type
        self.required = required
        self.passed = passed
        self.skipped = skipped
        self.details = details

    def label(self) -> str:
        if self.skipped:
            return f"{_YELLOW}SKIP{_RESET}"
        return f"{_GREEN}PASS{_RESET}" if self.passed else f"{_RED}FAIL{_RESET}"


# ---------------------------------------------------------------------------
# Gate implementations
# ---------------------------------------------------------------------------

# Patterns that indicate a test runner ran but found no actual tests.
_NO_TEST_PATTERNS = [
    re.compile(r'no\s+tests?\s+specified', re.IGNORECASE),
    re.compile(r'no\s+tests?\s+found', re.IGNORECASE),
    re.compile(r'\b0\s+tests?\b', re.IGNORECASE),
    re.compile(r'error:\s*no\s+test\s+specified', re.IGNORECASE),
]


def _test_output_is_vacuous(output: str) -> bool:
    """Return True if *output* matches common 'no real tests' patterns."""
    for pat in _NO_TEST_PATTERNS:
        if pat.search(output):
            return True
    return False


def gate_unit_tests(project_root: str, gate: Dict[str, Any]) -> GateResult:
    """Run unit tests via npm test or pytest."""
    required = gate.get("required", False)

    # Detect test runner
    has_package_json = (Path(project_root) / "package.json").exists()
    has_pytest = (
        (Path(project_root) / "pytest.ini").exists()
        or (
            (Path(project_root) / "setup.cfg").exists()
            and _which("pytest")
        )
        or (
            (Path(project_root) / "pyproject.toml").exists()
            and _which("pytest")
        )
        or (
            any(_find_files(project_root, {".py"}))
            and _which("pytest")
        )
    )

    if has_package_json:
        # Check if "test" script exists in package.json
        try:
            pkg = json.loads(_read_text(os.path.join(project_root, "package.json")))
            if "test" in pkg.get("scripts", {}):
                exit_code, output = _run_external(["npm", "test"], project_root)
                if exit_code == 0 and _test_output_is_vacuous(output):
                    return GateResult(
                        "unit_tests", required, passed=True, skipped=True,
                        details="Test runner found but no real tests executed: " + output[:200],
                    )
                passed = exit_code == 0
                return GateResult("unit_tests", required, passed, details=output)
        except (json.JSONDecodeError, OSError):
            pass

    if has_pytest and _which("pytest"):
        exit_code, output = _run_external(["pytest", "--tb=short", "-q"], project_root)
        if exit_code == 0 and _test_output_is_vacuous(output):
            return GateResult(
                "unit_tests", required, passed=True, skipped=True,
                details="Test runner found but no real tests executed: " + output[:200],
            )
        passed = exit_code == 0
        return GateResult("unit_tests", required, passed, details=output)

    return GateResult(
        "unit_tests", required, passed=True, skipped=True,
        details="No test runner detected (no npm test script, no pytest)",
    )


def gate_lint(project_root: str, gate: Dict[str, Any]) -> GateResult:
    """Run linter via npm run lint or flake8."""
    required = gate.get("required", False)

    has_package_json = (Path(project_root) / "package.json").exists()

    if has_package_json:
        try:
            pkg = json.loads(_read_text(os.path.join(project_root, "package.json")))
            if "lint" in pkg.get("scripts", {}):
                exit_code, output = _run_external(["npm", "run", "lint"], project_root)
                passed = exit_code == 0
                return GateResult("lint", required, passed, details=output)
        except (json.JSONDecodeError, OSError):
            pass

    if _which("flake8"):
        exit_code, output = _run_external(["flake8", "."], project_root)
        passed = exit_code == 0
        return GateResult("lint", required, passed, details=output)

    return GateResult(
        "lint", required, passed=True, skipped=True,
        details="No linter detected (no npm run lint script, no flake8)",
    )


# Patterns for citation references
_CITATION_ARTICLE = re.compile(
    r'\bArticle\s+(\d+)\s*\((\d+)\)', re.IGNORECASE
)
_CITATION_SECTION = re.compile(
    r'\bSection\s+(\d+(?:\.\d+)+)', re.IGNORECASE
)


def gate_citation_audit(
    project_root: str,
    gate: Dict[str, Any],
    shared_truth: Dict[str, str],
    output_dir: str,
) -> GateResult:
    """Verify that Article X(Y) / Section X.Y references appear in source docs."""
    required = gate.get("required", False)

    # Collect all source document text
    source_texts: Dict[str, str] = {}
    for label, rel_path in shared_truth.items():
        abs_path = os.path.join(project_root, rel_path)
        if os.path.isfile(abs_path):
            source_texts[label] = _read_text(abs_path)

    if not source_texts:
        return GateResult(
            "citation_audit", required, passed=True, skipped=True,
            details="No shared_truth source documents found",
        )

    # Find output markdown files
    output_files = _find_files(output_dir, {".md", ".txt", ".markdown"})
    if not output_files:
        return GateResult(
            "citation_audit", required, passed=True, skipped=True,
            details=f"No markdown files found in {output_dir}",
        )

    # Combine all source text for searching
    combined_source = "\n".join(source_texts.values()).lower()

    failures: List[str] = []
    total_citations = 0

    for fpath in output_files:
        content = _read_text(fpath)
        rel = os.path.relpath(fpath, project_root)

        for m in _CITATION_ARTICLE.finditer(content):
            total_citations += 1
            ref = m.group(0)
            # Check if the reference appears in any source document
            if ref.lower() not in combined_source:
                failures.append(f"  {rel}: {ref} not found in source documents")

        for m in _CITATION_SECTION.finditer(content):
            total_citations += 1
            ref = m.group(0)
            if ref.lower() not in combined_source:
                failures.append(f"  {rel}: {ref} not found in source documents")

    if total_citations == 0:
        return GateResult(
            "citation_audit", required, passed=True, skipped=True,
            details="No citation references found in output files",
        )

    if failures:
        detail = (
            f"Checked {total_citations} citation(s), "
            f"{len(failures)} unverified:\n" + "\n".join(failures)
        )
        return GateResult("citation_audit", required, passed=False, details=detail)

    return GateResult(
        "citation_audit", required, passed=True,
        details=f"All {total_citations} citation(s) verified against source documents",
    )


# URL format validation pattern (RFC 3986 simplified)
_URL_PATTERN = re.compile(
    r'https?://'                    # scheme
    r'[A-Za-z0-9]'                  # first char of host
    r'[A-Za-z0-9._~:/?#\[\]@!$&\'()*+,;=%-]*',  # rest of URL
    re.IGNORECASE,
)

# Stricter host validation: must have at least one dot or be localhost
_VALID_HOST = re.compile(
    r'^https?://'
    r'('
    r'localhost'
    r'|'
    r'[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?'  # label
    r'(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*'  # more labels
    r'\.[A-Za-z]{2,}'              # TLD
    r')',
    re.IGNORECASE,
)


def gate_source_verification(
    project_root: str,
    gate: Dict[str, Any],
    output_dir: str,
) -> GateResult:
    """Validate URL formats in output files (no HTTP requests)."""
    required = gate.get("required", False)

    output_files = _find_files(output_dir, {".md", ".txt", ".markdown"})
    if not output_files:
        return GateResult(
            "source_verification", required, passed=True, skipped=True,
            details=f"No markdown files found in {output_dir}",
        )

    failures: List[str] = []
    total_urls = 0

    for fpath in output_files:
        content = _read_text(fpath)
        rel = os.path.relpath(fpath, project_root)

        for m in _URL_PATTERN.finditer(content):
            url = m.group(0).rstrip(".,;:!?)>\"'")
            total_urls += 1

            # Validate structure
            if not _VALID_HOST.match(url):
                failures.append(f"  {rel}: malformed URL: {url}")
                continue

            # Check for common issues
            if url.count("//") > 1:
                failures.append(f"  {rel}: double-slash in URL: {url}")
            if " " in url:
                failures.append(f"  {rel}: space in URL: {url}")

    if total_urls == 0:
        return GateResult(
            "source_verification", required, passed=True, skipped=True,
            details="No URLs found in output files",
        )

    if failures:
        detail = (
            f"Checked {total_urls} URL(s), "
            f"{len(failures)} invalid:\n" + "\n".join(failures)
        )
        return GateResult("source_verification", required, passed=False, details=detail)

    return GateResult(
        "source_verification", required, passed=True,
        details=f"All {total_urls} URL(s) have valid format",
    )


# Date extraction patterns
_DATE_ISO = re.compile(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b')
_DATE_WRITTEN = re.compile(
    r'\b(January|February|March|April|May|June|July|August|September|'
    r'October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b',
    re.IGNORECASE,
)

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def gate_recency_check(
    project_root: str,
    gate: Dict[str, Any],
    output_dir: str,
) -> GateResult:
    """Flag dates older than 6 months from today."""
    required = gate.get("required", False)
    cutoff = datetime.now(timezone.utc) - timedelta(days=183)  # ~6 months

    output_files = _find_files(output_dir, {".md", ".txt", ".markdown"})
    if not output_files:
        return GateResult(
            "recency_check", required, passed=True, skipped=True,
            details=f"No markdown files found in {output_dir}",
        )

    stale_dates: List[str] = []
    total_dates = 0

    for fpath in output_files:
        content = _read_text(fpath)
        rel = os.path.relpath(fpath, project_root)

        # ISO dates
        for m in _DATE_ISO.finditer(content):
            try:
                year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
                dt = datetime(year, month, day, tzinfo=timezone.utc)
                total_dates += 1
                if dt < cutoff:
                    stale_dates.append(
                        f"  {rel}: {m.group(0)} is older than 6 months"
                    )
            except ValueError:
                continue

        # Written dates
        for m in _DATE_WRITTEN.finditer(content):
            try:
                month = _MONTH_MAP[m.group(1).lower()]
                day = int(m.group(2))
                year = int(m.group(3))
                dt = datetime(year, month, day, tzinfo=timezone.utc)
                total_dates += 1
                if dt < cutoff:
                    stale_dates.append(
                        f"  {rel}: {m.group(0)} is older than 6 months"
                    )
            except (ValueError, KeyError):
                continue

    if total_dates == 0:
        return GateResult(
            "recency_check", required, passed=True, skipped=True,
            details="No dates found in output files",
        )

    if stale_dates:
        detail = (
            f"Checked {total_dates} date(s), "
            f"{len(stale_dates)} stale:\n" + "\n".join(stale_dates)
        )
        return GateResult("recency_check", required, passed=False, details=detail)

    return GateResult(
        "recency_check", required, passed=True,
        details=f"All {total_dates} date(s) are within 6 months",
    )


def gate_scope_validation(
    project_root: str,
    gate: Dict[str, Any],
    output_dir: str,
    commit_scope: Optional[List[str]] = None,
) -> GateResult:
    """Validate that changed files are within allowed directory prefixes.

    If *commit_scope* is ``None`` or empty the gate is skipped.
    Otherwise ``git diff --name-only HEAD`` is executed and every changed file
    is checked against *commit_scope* prefixes.  Any file outside the allowed
    scope causes a FAIL.
    """
    gate_type = "scope_validation"
    required = gate.get("required", True)  # default True: scope violations should block

    if not commit_scope:
        return GateResult(
            gate_type, required, passed=True, skipped=True,
            details="No commit_scope provided; skipping scope validation",
        )

    exit_code, output = _run_external(["git", "diff", "--name-only", "HEAD"], project_root)
    if exit_code != 0:
        return GateResult(
            gate_type, required, passed=False,
            details=f"git diff failed (exit {exit_code}): {output}",
        )

    changed_files = [f for f in output.splitlines() if f.strip()]
    if not changed_files:
        return GateResult(
            gate_type, required, passed=True,
            details="No changed files detected",
        )

    violations: List[str] = []
    for fpath in changed_files:
        normalised = fpath.replace("\\", "/")
        if not any(normalised.startswith(prefix.replace("\\", "/")) for prefix in commit_scope):
            violations.append(f"  {fpath}")

    if violations:
        detail = (
            f"{len(violations)} file(s) outside allowed scope "
            f"{commit_scope}:\n" + "\n".join(violations)
        )
        return GateResult(gate_type, required, passed=False, details=detail)

    return GateResult(
        gate_type, required, passed=True,
        details=f"All {len(changed_files)} changed file(s) within allowed scope",
    )


def gate_string_coverage(
    project_root: str,
    gate: Dict[str, Any],
    output_dir: str,
) -> GateResult:
    """Check that all locale string files have at least as many keys as the base."""
    gate_type = "string_coverage"
    required = gate.get("required", False)

    # Directories that conventionally hold locale files
    locale_dir_names = {"locales", "i18n", "translations", "strings"}
    string_extensions = {".strings", ".xliff", ".po", ".json"}

    # Discover locale directories
    locale_dirs: List[str] = []
    for dirpath, dirnames, _ in os.walk(project_root):
        for d in dirnames:
            if d.lower() in locale_dir_names:
                locale_dirs.append(os.path.join(dirpath, d))

    if not locale_dirs:
        return GateResult(
            gate_type, required, passed=True, skipped=True,
            details="No localization directories found (locales/, i18n/, translations/, strings/)",
        )

    # Collect all string files
    string_files: List[str] = []
    for ld in locale_dirs:
        string_files.extend(_find_files(ld, string_extensions))

    if not string_files:
        return GateResult(
            gate_type, required, passed=True, skipped=True,
            details="Localization directories exist but contain no string files",
        )

    # Only handle JSON files for key counting (simple & practical)
    json_files = [f for f in string_files if f.lower().endswith(".json")]
    if not json_files:
        return GateResult(
            gate_type, required, passed=True, skipped=True,
            details="String files found but none are JSON; key counting not supported for other formats",
        )

    # Identify base language file (en.json)
    base_file: Optional[str] = None
    for jf in json_files:
        basename = Path(jf).stem.lower()
        if basename in ("en", "en-us", "en_us"):
            base_file = jf
            break

    if base_file is None:
        return GateResult(
            gate_type, required, passed=True, skipped=True,
            details="No base language file (en.json / en-us.json) found to compare against",
        )

    # Load base key count
    try:
        base_data = json.loads(_read_text(base_file))
    except (json.JSONDecodeError, OSError) as exc:
        return GateResult(
            gate_type, required, passed=False,
            details=f"Failed to parse base file {base_file}: {exc}",
        )

    if not isinstance(base_data, dict):
        return GateResult(
            gate_type, required, passed=True, skipped=True,
            details=f"Base file {base_file} is not a JSON object; skipping key comparison",
        )

    base_count = len(base_data)
    base_rel = os.path.relpath(base_file, project_root)
    failures: List[str] = []

    for jf in json_files:
        if jf == base_file:
            continue
        try:
            locale_data = json.loads(_read_text(jf))
        except (json.JSONDecodeError, OSError):
            failures.append(f"  {os.path.relpath(jf, project_root)}: failed to parse")
            continue

        if not isinstance(locale_data, dict):
            continue

        locale_count = len(locale_data)
        if locale_count < base_count:
            rel = os.path.relpath(jf, project_root)
            missing = base_count - locale_count
            failures.append(
                f"  {rel}: {locale_count}/{base_count} keys ({missing} missing)"
            )

    if failures:
        detail = (
            f"Base {base_rel} has {base_count} key(s). "
            f"{len(failures)} locale(s) incomplete:\n" + "\n".join(failures)
        )
        return GateResult(gate_type, required, passed=False, details=detail)

    return GateResult(
        gate_type, required, passed=True,
        details=f"All locale JSON files have >= {base_count} key(s) from {base_rel}",
    )


# ---------------------------------------------------------------------------
# Gate dispatcher
# ---------------------------------------------------------------------------

_GATE_HANDLERS = {
    "unit_tests": "unit_tests",
    "lint": "lint",
    "citation_audit": "citation_audit",
    "source_verification": "source_verification",
    "recency_check": "recency_check",
    "scope_validation": "scope_validation",
    "string_coverage": "string_coverage",
}


def run_gate(
    gate_type: str,
    gate: Dict[str, Any],
    project_root: str,
    shared_truth: Dict[str, str],
    output_dir: str,
) -> GateResult:
    """Dispatch to the appropriate gate handler."""
    required = gate.get("required", False)

    if gate_type == "unit_tests":
        return gate_unit_tests(project_root, gate)
    elif gate_type == "lint":
        return gate_lint(project_root, gate)
    elif gate_type == "citation_audit":
        return gate_citation_audit(project_root, gate, shared_truth, output_dir)
    elif gate_type == "source_verification":
        return gate_source_verification(project_root, gate, output_dir)
    elif gate_type == "recency_check":
        return gate_recency_check(project_root, gate, output_dir)
    elif gate_type == "scope_validation":
        commit_scope = gate.get("commit_scope")
        return gate_scope_validation(project_root, gate, output_dir, commit_scope=commit_scope)
    elif gate_type == "string_coverage":
        return gate_string_coverage(project_root, gate, output_dir)
    else:
        return GateResult(
            gate_type, required, passed=True, skipped=True,
            details=f"Unknown deterministic gate type: {gate_type}",
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic quality gates from a conductor profile.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --profile conductor/profiles/engineering.json\n"
            "  %(prog)s --profile conductor/profiles/research.json --output-dir output/\n"
        ),
    )
    parser.add_argument(
        "--profile", required=True,
        help="Path to the conductor profile JSON",
    )
    parser.add_argument(
        "--output-dir", default="output/",
        help="Directory containing agent output files (default: output/)",
    )
    args = parser.parse_args(argv)

    project_root = _resolve_project_root()

    # Load profile
    profile_path = os.path.join(project_root, args.profile)
    if not os.path.isfile(profile_path):
        # Try as absolute path
        if os.path.isfile(args.profile):
            profile_path = args.profile
        else:
            print(
                f"{_RED}ERROR:{_RESET} Profile not found: {args.profile}",
                file=sys.stderr,
            )
            return 1

    try:
        with open(profile_path, "r", encoding="utf-8") as fh:
            profile = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"{_RED}ERROR:{_RESET} Failed to load profile: {exc}",
            file=sys.stderr,
        )
        return 1

    # Extract deterministic gates
    quality_gates = profile.get("quality_gates", [])
    deterministic_gates = [
        g for g in quality_gates
        if g.get("mechanism") == "deterministic"
    ]

    if not deterministic_gates:
        print(f"{_YELLOW}⚠️  No deterministic gates found in profile.{_RESET}")
        return 0

    shared_truth = profile.get("shared_truth", {})
    output_dir = os.path.join(project_root, args.output_dir)

    # Header
    profile_name = Path(profile_path).stem
    print(f"\n{_BOLD}╔══════════════════════════════════════════╗{_RESET}")
    print(f"{_BOLD}║  Deterministic Quality Gates             ║{_RESET}")
    print(f"{_BOLD}╚══════════════════════════════════════════╝{_RESET}")
    print(f"  Profile  : {_BOLD}{profile_name}{_RESET}")
    print(f"  Output   : {output_dir}")
    print(f"  Gates    : {len(deterministic_gates)}\n")

    # Run each gate
    results: List[GateResult] = []
    for gate in deterministic_gates:
        gate_type = gate.get("type", "unknown")
        required = gate.get("required", False)
        req_label = f"{_RED}[required]{_RESET}" if required else f"{_DIM}[optional]{_RESET}"

        print(f"  Running {_BOLD}{gate_type}{_RESET} {req_label} …", end=" ", flush=True)
        result = run_gate(gate_type, gate, project_root, shared_truth, output_dir)
        results.append(result)

        print(result.label())
        if result.details:
            # Indent details
            for line in result.details.split("\n")[:10]:  # Cap detail lines
                print(f"    {_DIM}{line}{_RESET}")
            if result.details.count("\n") > 10:
                remaining = result.details.count("\n") - 10
                print(f"    {_DIM}… and {remaining} more line(s){_RESET}")

    # Summary
    print(f"\n{_BOLD}{'─' * 44}{_RESET}")

    passed = [r for r in results if r.passed and not r.skipped]
    failed = [r for r in results if not r.passed and not r.skipped]
    skipped = [r for r in results if r.skipped]
    required_failed = [r for r in failed if r.required]
    any_actually_ran = bool(passed) or bool(failed)

    print(
        f"  {_GREEN}✅ {len(passed)} passed{_RESET}  "
        f"{_RED}❌ {len(failed)} failed{_RESET}  "
        f"{_YELLOW}⏭️  {len(skipped)} skipped{_RESET}"
    )

    if required_failed:
        print(f"\n  {_RED}{_BOLD}❌ BLOCKED:{_RESET} {len(required_failed)} required gate(s) failed:")
        for r in required_failed:
            print(f"    • {r.gate_type}")
        print()
        return 1

    # C2a — All gates skipped means inconclusive; auto-merge must NOT proceed.
    if not any_actually_ran:
        print(
            f"\n  {_YELLOW}{_BOLD}WARNING: All gates were skipped "
            f"(no test runner or linter found). "
            f"Results are INCONCLUSIVE.{_RESET}\n"
        )
        return EXIT_INCONCLUSIVE

    if failed:
        print(f"\n  {_YELLOW}⚠️  {len(failed)} optional gate(s) failed (not blocking){_RESET}")

    print(f"\n  {_GREEN}{_BOLD}✅ All required gates passed.{_RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
