#!/usr/bin/env python3
"""Render glossary/glossary.json into the human-readable glossary/GLOSSARY.md.

The Markdown file is generated output — edit glossary.json and rerun this
script; never edit GLOSSARY.md by hand. Output is deterministic (stable sort,
no timestamps) so diffs stay clean.
"""
from glossary_lib import GLOSSARY_DIR, load_glossary, sort_key_fr

HEADER = """\
<!-- GENERATED from glossary/glossary.json by scripts/glossary_md.py — do not edit by hand -->

# SGA translation glossary (français → English)

Canonical FR→EN renderings of mathematical terminology across the SGA
corpus (sga1–sga7). The machine source of truth is
[`glossary/glossary.json`](glossary.json); this file is a generated view.

- Any tooling that translates or checks SGA text (including the future
  sga4/sga4.5 retranslation and the completion of sga3's untranslated
  exposés) must source its terminology and theorem-kind headings from
  `glossary.json`, not from per-script tables.
- Cross-book conformance is checked by `scripts/glossary_check.py`, which
  reports deviations to `issues/glossary_deviations.json`.
- *Seen* cites exemplar occurrences as `book:anchor` or `book:page#block`.
"""


def esc(text):
    return text.replace("|", "\\|")


def term_row(e):
    fr = esc(e["fr"])
    if e.get("fr_forms"):
        fr += " *(" + ", ".join(esc(f) for f in e["fr_forms"]) + ")*"
    note = e.get("note", "")
    if e.get("pos"):
        note = f"({e['pos']}) {note}".strip()
    return "| {} | {} | {} | {} | {} |".format(
        fr, esc(e["en"]),
        ", ".join(esc(a) for a in e.get("en_accept", [])),
        esc(note),
        ", ".join(e.get("seen", [])[:3]))


def main():
    entries = load_glossary()
    terms = sorted((e for e in entries if e["category"] == "term"),
                   key=lambda e: sort_key_fr(e["fr"]))
    headings = sorted((e for e in entries if e["category"] == "heading"),
                      key=lambda e: sort_key_fr(e["fr"]))

    lines = [HEADER]
    lines.append(f"## Mathematical terms ({len(terms)})\n")
    lines.append("| Français | English | Also accepted | Note | Seen |")
    lines.append("|---|---|---|---|---|")
    lines.extend(term_row(e) for e in terms)

    lines.append(f"\n## Theorem-kind headings ({len(headings)})\n")
    lines.append("| Français | English |")
    lines.append("|---|---|")
    lines.extend(f"| {esc(e['fr'])} | {esc(e['en'])} |" for e in headings)

    out = GLOSSARY_DIR / "GLOSSARY.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}: {len(terms)} terms, {len(headings)} headings")


if __name__ == "__main__":
    main()
