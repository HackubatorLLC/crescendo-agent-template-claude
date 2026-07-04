#!/usr/bin/env python3
"""Cross-validate agent outputs for contradictions.

Walks all markdown and text files in subdirectories of the output directory,
extracts key factual claims, compares them across files, and flags potential
contradictions.  Uses only the Python standard library.

Exit codes:
    0 – no HIGH-severity contradictions found
    1 – at least one HIGH-severity contradiction found
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Claim data model
# ---------------------------------------------------------------------------

@dataclass
class Claim:
    """A single factual claim extracted from a source file."""
    source_file: str
    line_number: int
    raw_line: str
    claim_type: str          # "numeric", "date", "url", "proper_noun"
    entity: str              # normalised entity key
    value: str               # the extracted value
    context: str             # surrounding text for display


@dataclass
class Contradiction:
    """A pair of conflicting claims."""
    claim_a: Claim
    claim_b: Claim
    severity: str            # HIGH, MEDIUM, LOW
    reason: str


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

# Patterns -------------------------------------------------------------------

# Dates in common formats: YYYY-MM-DD, MM/DD/YYYY, Month DD YYYY, etc.
_DATE_ISO = re.compile(
    r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b'
)
_DATE_MDY = re.compile(
    r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b'
)
_DATE_WRITTEN = re.compile(
    r'\b((?:January|February|March|April|May|June|July|August|September|'
    r'October|November|December)\s+\d{1,2}(?:,?\s+\d{4})?)\b',
    re.IGNORECASE,
)

# Numbers with optional units / currency: $1,234.56, 42%, 3.14 km, etc.
_NUMERIC = re.compile(
    r'(?<!\w)'                           # not preceded by word char
    r'([$€£¥]?\s*\d[\d,]*(?:\.\d+)?'    # number with optional currency
    r'(?:\s*%|'                          # percent
    r'\s*[A-Za-z]{1,5})?)'               # short unit suffix
    r'(?!\w)',                            # not followed by word char
)

# URLs
_URL = re.compile(
    r'(https?://[^\s\)\]>\"\']+)',
    re.IGNORECASE,
)

# Proper nouns heuristic: sequences of capitalised words (≥2 words) not at
# sentence start.  Simplified – will over-match sometimes, but that's safe.
_PROPER_NOUN = re.compile(
    r'(?<=[.!?]\s{1,3}|^)'             # sentence boundary (negative lookahead below)
    r'(?!(?:The|A|An|In|On|At|For|To|By|Of|And|But|Or|If|So|It|He|She|We|They)\b)'
    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
    re.MULTILINE,
)

# Simpler proper-noun pattern: Capitalised word near a number/value in same line
_ENTITY_NEAR_VALUE = re.compile(
    r'\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*)\b'
)


def _normalise_date(raw: str) -> Optional[str]:
    """Try to normalise a date string to YYYY-MM-DD."""
    for fmt in (
        "%Y-%m-%d", "%Y/%m/%d",
        "%m/%d/%Y", "%m-%d-%Y",
        "%m/%d/%y", "%m-%d-%y",
        "%B %d, %Y", "%B %d %Y",
        "%B %d",
    ):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _normalise_number(raw: str) -> Optional[float]:
    """Strip currency / unit decorations and return a plain float."""
    cleaned = re.sub(r'[,$€£¥%\s]', '', raw)
    cleaned = re.sub(r'[A-Za-z]+$', '', cleaned)  # trailing unit
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalise_url(raw: str) -> str:
    """Lowercase and strip trailing punctuation from URLs."""
    url = raw.rstrip('.,;:!?)>')
    return url.lower()


def _extract_nearby_entity(line: str, value_span: Tuple[int, int]) -> str:
    """Attempt to find a proper-noun entity near a value in the same line."""
    matches = _ENTITY_NEAR_VALUE.findall(line)
    # Filter out common English words that happen to be capitalised
    stopwords = {
        "The", "This", "That", "These", "Those", "There", "Here",
        "When", "Where", "What", "Which", "Who", "How", "Why",
        "Each", "Every", "All", "Some", "Any", "Most", "Many",
        "Before", "After", "During", "Between", "About", "Into",
        "Through", "With", "From", "Over", "Under", "Above", "Below",
        "Not", "Also", "However", "Therefore", "Moreover", "Furthermore",
        "Additionally", "Similarly", "Meanwhile", "Nevertheless",
    }
    candidates = [m for m in matches if m not in stopwords]
    if candidates:
        return candidates[0]
    return ""


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def extract_claims(filepath: str, lines: List[str]) -> List[Claim]:
    """Extract factual claims from file content."""
    claims: List[Claim] = []
    rel_path = filepath  # caller should pass a display-friendly path

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            # Keep headings for context but don't extract claims from them
            pass

        # --- Dates --------------------------------------------------------
        for pattern in (_DATE_ISO, _DATE_MDY, _DATE_WRITTEN):
            for m in pattern.finditer(stripped):
                norm = _normalise_date(m.group(1))
                if norm:
                    entity = _extract_nearby_entity(stripped, m.span())
                    claims.append(Claim(
                        source_file=rel_path,
                        line_number=i,
                        raw_line=stripped,
                        claim_type="date",
                        entity=entity.lower() if entity else norm,
                        value=norm,
                        context=stripped,
                    ))

        # --- URLs ---------------------------------------------------------
        for m in _URL.finditer(stripped):
            url = _normalise_url(m.group(1))
            # Use the URL as both entity and value; context is the line
            claims.append(Claim(
                source_file=rel_path,
                line_number=i,
                raw_line=stripped,
                claim_type="url",
                entity=url,
                value=url,
                context=stripped,
            ))

        # --- Numeric values -----------------------------------------------
        for m in _NUMERIC.finditer(stripped):
            num = _normalise_number(m.group(1))
            if num is not None:
                entity = _extract_nearby_entity(stripped, m.span())
                if entity:
                    claims.append(Claim(
                        source_file=rel_path,
                        line_number=i,
                        raw_line=stripped,
                        claim_type="numeric",
                        entity=entity.lower(),
                        value=str(num),
                        context=stripped,
                    ))

    return claims


def _extract_structured_claims(output_dir: str) -> List[Claim]:
    """Load claims from *.claims.json files (EAV format).

    Each file must contain a top-level ``claims`` array of objects with at
    least ``entity``, ``attribute``, and ``value`` keys.  Optional fields:
    ``confidence`` (float) and ``source`` (str).

    Returns a list of :class:`Claim` objects using ``attribute`` as the
    ``claim_type`` and ``entity`` as the entity key.
    """
    claims: List[Claim] = []
    pattern = os.path.join(output_dir, "**", "*.claims.json")
    for fpath in sorted(glob.glob(pattern, recursive=True)):
        rel = os.path.relpath(fpath, output_dir)
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[cross-validate] WARNING: could not read {rel}: {exc}")
            continue

        if not isinstance(data.get("claims"), list):
            print(f"[cross-validate] WARNING: {rel} missing 'claims' array, skipping")
            continue

        for entry in data["claims"]:
            entity = entry.get("entity", "")
            attribute = entry.get("attribute", "")
            value = entry.get("value", "")
            confidence = entry.get("confidence", 1.0)
            source = entry.get("source", rel)

            claims.append(Claim(
                source_file=rel,
                line_number=0,
                raw_line=f"[structured] {entity}.{attribute}={value}",
                claim_type=attribute,
                entity=entity.lower(),
                value=str(value),
                context=(
                    f"{entity}.{attribute} = {value} "
                    f"(confidence={confidence}, source={source})"
                ),
            ))

        if claims:
            print(f"  • {rel}: {len([c for c in claims if c.source_file == rel])} structured claim(s) loaded")

    return claims


# ---------------------------------------------------------------------------
# Contradiction detection
# ---------------------------------------------------------------------------

def detect_contradictions(all_claims: List[Claim]) -> List[Contradiction]:
    """Compare claims across files and flag contradictions."""
    contradictions: List[Contradiction] = []

    # Group claims by (claim_type, entity)
    grouped: Dict[Tuple[str, str], List[Claim]] = defaultdict(list)
    for c in all_claims:
        if c.entity:
            grouped[(c.claim_type, c.entity)].append(c)

    for (ctype, entity), group in grouped.items():
        # Only compare claims from *different* files
        by_file: Dict[str, List[Claim]] = defaultdict(list)
        for c in group:
            by_file[c.source_file].append(c)

        files = list(by_file.keys())
        if len(files) < 2:
            continue

        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                claims_a = by_file[files[i]]
                claims_b = by_file[files[j]]

                for ca in claims_a:
                    for cb in claims_b:
                        contradiction = _compare_pair(ca, cb)
                        if contradiction:
                            contradictions.append(contradiction)

    # Deduplicate (same file-pair + same entity + same values)
    seen: Set[Tuple[str, str, str, str, str]] = set()
    unique: List[Contradiction] = []
    for c in contradictions:
        key = (
            c.claim_a.source_file, c.claim_b.source_file,
            c.claim_a.entity, c.claim_a.value, c.claim_b.value,
        )
        rev_key = (
            c.claim_b.source_file, c.claim_a.source_file,
            c.claim_a.entity, c.claim_b.value, c.claim_a.value,
        )
        if key not in seen and rev_key not in seen:
            seen.add(key)
            unique.append(c)

    return unique


def _compare_pair(a: Claim, b: Claim) -> Optional[Contradiction]:
    """Compare two claims with the same entity from different files."""
    if a.source_file == b.source_file:
        return None
    if a.value == b.value:
        return None  # identical – no conflict

    # --- Numeric conflicts ------------------------------------------------
    if a.claim_type == "numeric" and b.claim_type == "numeric":
        try:
            va, vb = float(a.value), float(b.value)
        except ValueError:
            return None
        if va == vb:
            return None
        # Determine severity by relative difference
        denom = max(abs(va), abs(vb), 1e-9)
        rel_diff = abs(va - vb) / denom
        if rel_diff > 0.01:  # >1% difference
            return Contradiction(
                claim_a=a, claim_b=b,
                severity="HIGH",
                reason=(
                    f"Numeric conflict for '{a.entity}': "
                    f"{a.value} vs {b.value} (relative diff {rel_diff:.1%})"
                ),
            )
        else:
            return Contradiction(
                claim_a=a, claim_b=b,
                severity="LOW",
                reason=(
                    f"Minor numeric variance for '{a.entity}': "
                    f"{a.value} vs {b.value}"
                ),
            )

    # --- Date conflicts ---------------------------------------------------
    if a.claim_type == "date" and b.claim_type == "date":
        return Contradiction(
            claim_a=a, claim_b=b,
            severity="HIGH",
            reason=(
                f"Date conflict for '{a.entity}': "
                f"{a.value} vs {b.value}"
            ),
        )

    # --- URL description conflicts ----------------------------------------
    if a.claim_type == "url" and b.claim_type == "url":
        if a.entity == b.entity and a.context != b.context:
            return Contradiction(
                claim_a=a, claim_b=b,
                severity="MEDIUM",
                reason=(
                    f"Same URL referenced with different descriptions: "
                    f"{a.entity}"
                ),
            )

    return None


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(contradictions: List[Contradiction]) -> str:
    """Render the contradiction report as Markdown."""
    lines: List[str] = []
    lines.append("# Contradiction Report")
    lines.append("")
    lines.append(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    lines.append("")

    if not contradictions:
        lines.append("> ✅ **No contradictions detected across agent outputs.**")
        lines.append("")
        return "\n".join(lines)

    # Summary counts
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for c in contradictions:
        counts[c.severity] += 1

    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Severity | Count |")
    lines.append(f"|----------|-------|")
    for sev in ("HIGH", "MEDIUM", "LOW"):
        emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}[sev]
        lines.append(f"| {emoji} {sev} | {counts[sev]} |")
    lines.append("")

    if counts["HIGH"] > 0:
        lines.append(
            "> [!CAUTION]\n"
            "> HIGH-severity contradictions detected.  "
            "Merge is **blocked** until these are resolved."
        )
        lines.append("")

    # Detailed findings
    lines.append("## Findings")
    lines.append("")

    # Sort: HIGH first, then MEDIUM, then LOW
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    contradictions.sort(key=lambda c: severity_order.get(c.severity, 9))

    for idx, c in enumerate(contradictions, start=1):
        emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}[c.severity]
        lines.append(f"### {idx}. {emoji} {c.severity} — {c.reason}")
        lines.append("")
        lines.append(f"**Source A:** `{c.claim_a.source_file}` (line {c.claim_a.line_number})")
        lines.append(f"> {c.claim_a.context}")
        lines.append("")
        lines.append(f"**Source B:** `{c.claim_b.source_file}` (line {c.claim_b.line_number})")
        lines.append(f"> {c.claim_b.context}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

_EXTENSIONS = {".md", ".txt", ".markdown"}


def discover_files(output_dir: str) -> List[str]:
    """Walk subdirectories of *output_dir* and return matching file paths."""
    found: List[str] = []
    root = Path(output_dir)
    if not root.is_dir():
        return found

    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in filenames:
            if Path(fname).suffix.lower() in _EXTENSIONS:
                found.append(os.path.join(dirpath, fname))

    return sorted(found)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cross-validate agent outputs for contradictions.",
    )
    parser.add_argument(
        "--output-dir",
        default="output/",
        help="Root directory containing agent output subdirectories (default: output/)",
    )
    args = parser.parse_args(argv)

    output_dir = args.output_dir
    files = discover_files(output_dir)

    if not files:
        print(f"[cross-validate] No markdown/text files found under '{output_dir}'.")
        return 0

    print(f"[cross-validate] Scanning {len(files)} file(s) in '{output_dir}' …")

    # Layer 1: Structured claims from .claims.json (preferred).
    # Layer 2: Text-extracted claims (fallback).
    all_claims: List[Claim] = []

    # --- Layer 1: structured claims from .claims.json -----------------
    structured_claims = _extract_structured_claims(output_dir)
    all_claims.extend(structured_claims)

    # Track (entity, attribute/claim_type) keys covered by structured claims
    # so we can deduplicate against text-extracted ones later.
    structured_keys: Set[Tuple[str, str]] = {
        (c.entity, c.claim_type) for c in structured_claims
    }
    if structured_claims:
        print(f"[cross-validate] Structured claims loaded: {len(structured_claims)}")

    # --- Layer 2: text-extracted claims (fallback) --------------------
    text_claims_total = 0
    for fpath in files:
        rel = os.path.relpath(fpath, output_dir)
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                file_lines = fh.readlines()
        except OSError as exc:
            print(f"[cross-validate] WARNING: could not read {rel}: {exc}")
            continue
        claims = extract_claims(rel, file_lines)
        # Deduplicate: structured claims win over text-extracted ones
        claims = [
            c for c in claims
            if (c.entity, c.claim_type) not in structured_keys
        ]
        all_claims.extend(claims)
        text_claims_total += len(claims)
        if claims:
            print(f"  • {rel}: {len(claims)} text claim(s) extracted")

    print(
        f"[cross-validate] Total claims: {len(all_claims)} "
        f"({len(structured_claims)} structured + {text_claims_total} text-extracted)"
    )

    # Detect contradictions
    contradictions = detect_contradictions(all_claims)
    print(f"[cross-validate] Contradictions found: {len(contradictions)}")

    # Write report
    report = generate_report(contradictions)
    report_path = os.path.join(output_dir, "contradiction_report.md")
    os.makedirs(output_dir, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"[cross-validate] Report written to {report_path}")

    # Exit code
    has_high = any(c.severity == "HIGH" for c in contradictions)
    if has_high:
        print("[cross-validate] ❌ HIGH-severity contradictions found — exit 1")
        return 1

    print("[cross-validate] ✅ No HIGH-severity contradictions — exit 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
