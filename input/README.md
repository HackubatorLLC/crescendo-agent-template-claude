# Input Intake

Drop your project's source material here, then let Maestro sanitize and read it.

**What to put here:** PRDs, product specs, UI mockups / design oracles (HTML/CSS/Figma
exports), architecture diagrams, constraints, reference documents.

## IMPORTANT — Sanitization is mandatory

Never let agents read raw files from this folder. Before consuming anything, the
Coordinator runs:

```bash
just sanitize-inputs      # or: python conductor/bin/sanitize_inputs.py
```

This strips prompt injections, invisible characters, and HTML comments, writing
cleaned copies to `input/.sanitized/`. Only `input/.sanitized/` files are consumed.

Binary files (PDF, DOCX, XLSX) cannot be auto-sanitized and are flagged for manual
human review (Directive 7).
