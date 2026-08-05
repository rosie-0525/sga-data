#!/usr/bin/env python3
"""Check FR→EN terminology consistency against glossary/glossary.json.

For every glossary term, every aligned fr/en block (and footnote) pair is
checked: if the French lemma occurs in the fr prose, at least one accepted
English rendering must occur in the aligned en prose. Theorem-kind headings
(<span class="thm-name">) are checked against the heading entries; unmapped
heading names — including stray English ones on the fr side — are reported
as kind "unknown-heading".

Usage:
  glossary_check.py                 # all 8 books, regenerates both reports
  glossary_check.py --book sga4 [--book ...]   # replace only those books'
                                                 records (issues/ convention)

Reports: issues/glossary_deviations.json (flat records, each carries "book")
and issues/glossary_summary.json (per-book totals). A deviation means "term
present in fr, no accepted rendering in en" — genuine paraphrase produces a
low noise floor; the response is glossary tuning (en_accept), not blind text
edits. The render-QA skill's issues/summary.json is a different file and is
never touched.
"""
import argparse
import os
import re
from datetime import datetime, timezone

from glossary_lib import (
    BOOKS, BOUND_L, BOUND_R, ISSUES_DIR, THM_NAME_RE, dump_json, en_pattern,
    fr_pattern, iter_aligned_blocks, iter_aligned_footnotes, load_glossary,
    load_json, norm_heading, normalize,
)

DEVIATIONS_PATH = ISSUES_DIR / "glossary_deviations.json"
SUMMARY_PATH = ISSUES_DIR / "glossary_summary.json"


def common_probe(entry):
    """Cheap substring gate: the common prefix of all surface forms,
    truncated at the first space — inflection appends a suffix to EVERY word
    of a multi-word lemma ("images réciproques"), so only the first word's
    stem is a guaranteed literal."""
    forms = [entry["fr"].lower()] + [f.lower() for f in
                                     entry.get("fr_forms", [])]
    probe = forms[0]
    for f in forms[1:]:
        while not f.startswith(probe):
            probe = probe[:-1]
    probe = probe.split(" ")[0]
    return probe if len(probe) >= 3 else None


class Checker:
    def __init__(self, entries):
        self.terms = sorted((e for e in entries if e["category"] == "term"),
                            key=lambda e: (-len(e["fr"]), e["fr"]))
        self.term_pats = [(e, fr_pattern(e), en_pattern(e), common_probe(e))
                          for e in self.terms]
        self.headings = sorted(
            (e for e in entries if e["category"] == "heading"),
            key=lambda e: -len(e["fr"]))

    def check_pair(self, fr_text, en_text):
        """Term-check one aligned pair of normalized (case-preserved) texts.
        Returns (n_matched_entries, deviations); each deviation is
        (entry, matched_surface, fr_snippet)."""
        fr_l, en_l = fr_text.lower(), en_text.lower()
        claimed = []
        matched = 0
        deviations = []
        for entry, fpat, epat, probe in self.term_pats:
            if probe and probe not in fr_l:
                continue
            span = None
            for m in fpat.finditer(fr_l):
                if any(m.start() < c1 and m.end() > c0 for c0, c1 in claimed):
                    continue
                claimed.append((m.start(), m.end()))
                if span is None:
                    span = (m.start(), m.end())
            if span is None:
                continue
            matched += 1
            if not epat.search(en_l):
                s, t = span
                surface = fr_text[s:t]
                # the French surface appearing verbatim (word-bounded) in
                # the EN side is a quoted title or proper name (Corps
                # locaux, Groupes et algèbres de Lie, SÉMINAIRE DE
                # GÉOMÉTRIE ALGÉBRIQUE, …), not a translation failure
                if re.search(BOUND_L + re.escape(surface.lower()) + BOUND_R,
                             en_l):
                    continue
                snippet = fr_text[max(0, s - 60):t + 60]
                deviations.append((entry, surface, snippet))
        return matched, deviations

    def match_heading(self, name):
        """Longest heading entry equal to the name or a word-prefix of it
        (composite names like «Théorème de pureté»)."""
        for e in self.headings:
            if name == e["fr"] or name.startswith(e["fr"] + " "):
                return e
        return None

    def match_en_heading(self, name):
        """Heading entry whose accepted EN rendering equals the name or is a
        word-prefix of it — for originally-English text (sga7 Exposé VI),
        where the fr side carries English heading names."""
        for e in self.headings:
            for a in [e["en"]] + e.get("en_accept", []):
                if name == a or name.startswith(a + " "):
                    return e
        return None


def check_book(checker, book):
    records = []
    stats = {"checkedBlocks": 0, "checkedFootnotes": 0,
             "untranslatedBlocks": 0, "skippedFootnotePages": 0,
             "matchedOccurrences": 0, "termDeviations": 0,
             "headingDeviations": 0, "unknownHeadings": 0}

    def record(kind, cid, page_id, where, entry, matched, snippet_fr,
               snippet_en):
        records.append({
            "book": book, "chapter": cid, "page": page_id, "block": where,
            "kind": kind, "fr_term": entry["fr"] if entry else matched,
            "matched": matched,
            "expected_en": entry["en"] if entry else None,
            "accepted": ([entry["en"]] + entry.get("en_accept", []))
            if entry else None,
            "fr_snippet": snippet_fr, "en_snippet": snippet_en})

    def check_texts(fr_html, en_html, cid, page_id, where, is_footnote):
        """Normalize, term-check, record. Returns True when the pair was
        actually checked (fr non-empty and en translated)."""
        fr_text = normalize(fr_html, lower=False)
        if not fr_text:
            return False
        en_text = normalize(en_html or "", lower=False)
        if not en_text:
            stats["untranslatedBlocks"] += 1
            return False
        matched, deviations = checker.check_pair(fr_text, en_text)
        stats["checkedFootnotes" if is_footnote else "checkedBlocks"] += 1
        stats["matchedOccurrences"] += matched
        for entry, surface, snippet in deviations:
            stats["termDeviations"] += 1
            record("term", cid, page_id, where, entry, surface, snippet,
                   en_text[:200])
        return True

    for cid, page_id, b_idx, fr_b, en_b in iter_aligned_blocks(book):
        # bibliographies quote French work titles verbatim — not prose
        # (page ids use both spellings: X-bibliographie and X-biblio)
        if (fr_b.get("type") == "bibliography"
                or "biblio" in (page_id or "")):
            continue
        fr_html = fr_b.get("html", "")
        en_html = en_b.get("html", "") if en_b else ""
        where = fr_b.get("id") or f"{page_id}#{b_idx}"
        translated = check_texts(fr_html, en_html, cid, page_id, where, False)

        # theorem-kind headings, aligned span-by-span (skip untranslated)
        fr_names = THM_NAME_RE.findall(fr_html) if translated else []
        if fr_names:
            en_names = THM_NAME_RE.findall(en_html)
            for i, raw in enumerate(fr_names):
                name = norm_heading(raw)
                if not name:
                    continue
                entry = checker.match_heading(name)
                en_name = norm_heading(en_names[i]) if i < len(en_names) \
                    else None
                if entry is None:
                    # identical known-English name on both sides means the
                    # text is originally English, not a stray heading
                    if name == en_name and checker.match_en_heading(name):
                        continue
                    stats["unknownHeadings"] += 1
                    record("unknown-heading", cid, page_id, where, None,
                           name, name, en_names[i] if i < len(en_names)
                           else None)
                    continue
                accepted = [entry["en"]] + entry.get("en_accept", [])
                exact = name == entry["fr"]
                ok = en_name is not None and any(
                    en_name.lower() == a.lower() if exact else
                    a.lower() in en_name.lower() for a in accepted)
                if not ok:
                    stats["headingDeviations"] += 1
                    record("heading", cid, page_id, where, entry, name,
                           name, en_name)

    for item in iter_aligned_footnotes(book):
        if item[0] == "skip":
            stats["skippedFootnotePages"] += 1
            continue
        cid, page_id, f_idx, fr_fn, en_fn = item
        check_texts(fr_fn.get("html", ""), en_fn.get("html", ""),
                    cid, page_id, f"fn:{page_id}#{f_idx}", True)

    return records, stats


def summarize(records, stats):
    n_dev = stats["termDeviations"]
    n_match = stats["matchedOccurrences"]
    offenders = {}
    for r in records:
        if r["kind"] == "term":
            offenders[r["fr_term"]] = offenders.get(r["fr_term"], 0) + 1
    top = sorted(offenders.items(), key=lambda kv: -kv[1])[:10]
    return dict(stats,
                lastRun=datetime.now(timezone.utc).isoformat(
                    timespec="seconds"),
                deviationRate=round(n_dev / n_match, 4) if n_match else 0.0,
                topOffenders=[{"fr_term": t, "count": c} for t, c in top])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", action="append", choices=BOOKS,
                    help="check only this book (repeatable); its records "
                         "replace the previous run's for that book")
    args = ap.parse_args()
    run_books = args.book or BOOKS

    checker = Checker(load_glossary())

    all_records, summary_books = [], {}
    if args.book:
        if DEVIATIONS_PATH.exists():
            all_records = [r for r in load_json(DEVIATIONS_PATH)
                           if r["book"] not in run_books]
        if SUMMARY_PATH.exists():
            summary_books = load_json(SUMMARY_PATH).get("books", {})

    for book in run_books:
        records, stats = check_book(checker, book)
        all_records.extend(records)
        summary_books[book] = summarize(records, stats)
        s = summary_books[book]
        print(f"{book}: {s['checkedBlocks']} blocks + "
              f"{s['checkedFootnotes']} footnotes, "
              f"{s['matchedOccurrences']} term occurrences, "
              f"{s['termDeviations']} term deviations "
              f"({s['deviationRate']:.2%}), "
              f"{s['headingDeviations']} heading deviations, "
              f"{s['unknownHeadings']} unknown headings, "
              f"{s['untranslatedBlocks']} untranslated blocks")

    all_records.sort(key=lambda r: (r["book"], str(r["chapter"]),
                                    str(r["page"]), str(r["block"])))
    ISSUES_DIR.mkdir(exist_ok=True)
    DEVIATIONS_PATH.write_text(dump_json(all_records), encoding="utf-8")
    SUMMARY_PATH.write_text(
        dump_json({"books": {b: summary_books[b]
                             for b in sorted(summary_books)}}),
        encoding="utf-8")
    print(f"wrote {os.path.relpath(DEVIATIONS_PATH)} "
          f"({len(all_records)} records) and {os.path.relpath(SUMMARY_PATH)}")


if __name__ == "__main__":
    main()
