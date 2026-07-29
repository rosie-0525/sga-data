#!/usr/bin/env python3
"""Apply the glossary's terminology decisions to the English corpus.

glossary.json says what a French term must render as; this script finds every
block where it does not, and emits the fix as a normal proposals run so the
existing guards (conflict, single-root, fr/en block-count) and the review viewer
apply unchanged. It never writes chapter JSON — apply_proposals.py does that.

Two kinds of rule, both in glossary/sweep_rules.json:

  mechanical  fires only when the ALIGNED FRENCH block matches `fr_regex`, and
              swaps a whole rejected phrase for the glossary's rendering.
  spelling    English orthography (fiber -> fibre); no French gate, and
              bibliography blocks are skipped so cited titles keep their form.

A substitution can only touch prose: the block html is segmented on math spans
and html tags first, matching happens strictly between those segments, and the
new html is re-segmented and asserted byte-identical outside prose before any
proposal is emitted. Case, plural and the original inter-word whitespace (prose
carries real newlines from LaTeX wrapping) are preserved.

Everything context-dependent — «majorer», «au-dessus de», stalk/fibre — is never
scripted; it goes to issues/glossary_sweep_worklist.json for per-occurrence review.

Usage:
  glossary_sweep.py --plan                       # counts + worklist, writes nothing
  glossary_sweep.py --emit --book sga3           # append g-* proposals to the run
  glossary_sweep.py --accept-all --book sga3 --out dec.json
  glossary_sweep.py --prune --book sga3 --ids applied.txt
  glossary_sweep.py --audit-reverse              # EN target where the FR term is absent
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from glossary_lib import (BOOKS, GLOSSARY_DIR, ISSUES_DIR, cite, dump_json,
                          iter_aligned_blocks, iter_aligned_footnotes,
                          load_glossary, load_json, normalize)
from proposals_lib import (check_replacement, new_proposal, proposals_path,
                           root_count, write_proposals)

RULES_JSON = GLOSSARY_DIR / "sweep_rules.json"
WORKLIST = ISSUES_DIR / "glossary_sweep_worklist.json"

# Everything that is not prose. Math is alternated BEFORE tags so that an `i<j`
# inside a formula can never be mistaken for a tag (same ordering as
# glossary_lib.normalize, for the same reason).
SEG = re.compile(r"\\\(.*?\\\)"
                 r"|\\\[.*?\\\]"
                 r"|\\begin\{([A-Za-z*]+)\}.*?\\end\{\1\}"
                 r"|<[^>]*>", re.S)


# ---------------------------------------------------------------------------
# prose-only substitution

def segments(html):
    """(protected, prose) — protected is the list of tag/math strings in order,
    prose is the list of (start, end) spans between them."""
    protected, prose, pos = [], [], 0
    for m in SEG.finditer(html):
        if m.start() > pos:
            prose.append((pos, m.start()))
        protected.append(m.group())
        pos = m.end()
    if pos < len(html):
        prose.append((pos, len(html)))
    return protected, prose


def phrase_pattern(phrase):
    """`closed part` -> \\b(closed)(\\s+)(part)(e?s)?\\b, so the match hands back
    its own capitalization, its inter-word whitespace and its plural suffix."""
    words = phrase.split()
    body = r"(\s+)".join("(" + re.escape(w) + ")" for w in words)
    return re.compile(r"(?<![\w-])" + body + r"(e?s)?(?![\w-])", re.I)


def recase(target, matched):
    if matched.isupper() and len(matched) > 1:
        return target.upper()
    if matched[:1].isupper():
        return target[:1].upper() + target[1:]
    return target


def rebuild(m, to):
    """Reassemble the target phrase from a phrase_pattern match."""
    groups = m.groups()
    words = [g for g in groups[:-1:2] if g is not None] or [groups[0]]
    gaps = [g for g in groups[1:-1:2] if g is not None]
    suffix = groups[-1] or ""
    out_words = to.split()
    if len(out_words) == len(words) and len(gaps) == len(out_words) - 1:
        joins = gaps
    else:
        sep = "\n" if any("\n" in g for g in gaps) else " "
        joins = [sep] + [" "] * (len(out_words) - 2)
    out_words = [recase(w, words[i]) if i < len(words) else w
                 for i, w in enumerate(out_words)]
    if suffix:
        out_words[-1] += suffix.lower()
    text = out_words[0]
    for i, w in enumerate(out_words[1:]):
        text += (joins[i] if i < len(joins) else " ") + w
    return text


def substitute(html, matchers):
    """matchers: [(pattern, to, label)]. Returns (new_html, [labels]) — only
    prose is touched, and overlapping matches are resolved longest-first."""
    _protected, prose = segments(html)
    hits = []
    for pat, to, label in matchers:
        # finditer(html, start, end) would truncate the string, hiding the
        # lookarounds' context at a prose/math boundary — scan the whole html
        # and keep only matches that lie wholly inside a prose span.
        for m in pat.finditer(html):
            if any(start <= m.start() and m.end() <= end for start, end in prose):
                hits.append((m.start(), m.end(), rebuild(m, to), label))
    if not hits:
        return html, []
    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    kept, last = [], -1
    for h in hits:
        if h[0] >= last:
            kept.append(h)
            last = h[1]
    out, labels = html, []
    for start, end, text, label in reversed(kept):
        out = out[:start] + text + out[end:]
        labels.append(label)
    return out, sorted(set(labels))


def prose_safe(old, new):
    """Total proof that nothing outside prose moved."""
    return segments(old)[0] == segments(new)[0]


# ---------------------------------------------------------------------------
# rules

class Rules:
    def __init__(self, path=RULES_JSON, glossary=None):
        doc = load_json(path)
        self.warnings = []
        entries = {e["fr"].lower(): e for e in (glossary or load_glossary())}
        self.mechanical = []
        for r in doc["rules"]:
            entry = entries.get(r["fr"].lower())
            if entry is None:
                self.warnings.append(f"{r['fr']}: no glossary entry")
            elif r["to"] not in entry["en"] and entry["en"] not in r["to"] \
                    and r["to"] not in (entry.get("en_accept") or []):
                self.warnings.append(
                    f"{r['fr']}: rule target {r['to']!r} does not match glossary "
                    f"en {entry['en']!r}")
            self.mechanical.append({
                "fr": r["fr"], "to": r["to"],
                "fr_re": re.compile(r["fr_regex"]),
                "fr_veto": re.compile(r["fr_veto"]) if r.get("fr_veto") else None,
                "matchers": [(phrase_pattern(f), r["to"], r["fr"]) for f in r["from"]],
                "from": r["from"],
            })
        # longest rejected phrase first, so `locally closed part` wins over `closed part`
        self.mechanical.sort(key=lambda r: -max(len(f) for f in r["from"]))

        self.spelling = []
        for s in doc.get("spelling", []):
            # Letter-only boundaries, not the hyphen-aware ones the phrase
            # rules use: an orthography fix must reach inside a hyphenated
            # compound ("2-fibered product" -> "2-fibred product"), the same
            # reason glossary_lib.en_pattern uses a plain \b on the English side.
            pat = re.compile(r"(?<![A-Za-z])(" +
                             "|".join(sorted(s["map"], key=len, reverse=True)) +
                             r")(?![A-Za-z])", re.I)
            self.spelling.append({"id": s["id"], "map": s["map"], "re": pat,
                                  "skip_bibliography": s.get("skip_bibliography", True)})

        self.judgment = []
        for j in doc.get("judgment", []):
            self.judgment.append({
                "fr": j["fr"], "suggest": j.get("suggest"), "reason": j.get("reason", ""),
                "fr_re": re.compile(j["fr_regex"]),
                "watch_re": re.compile(r"(?<![\w-])(" +
                                       "|".join(sorted(j["watch"], key=len, reverse=True)) +
                                       r")(?![\w-])", re.I),
                "en_filter": re.compile(j["en_filter"]) if j.get("en_filter") else None,
            })


def spelling_matchers(rule):
    def to_for(word):
        return rule["map"][word.lower()]
    return [(rule["re"], to_for, rule["id"])]


def apply_spelling(html, rule):
    """Word-for-word orthography swap, prose only, case preserved."""
    _protected, prose = segments(html)
    hits = []
    for m in rule["re"].finditer(html):
        if any(start <= m.start() and m.end() <= end for start, end in prose):
            hits.append((m.start(), m.end(),
                         recase(rule["map"][m.group(1).lower()], m.group(1))))
    out = html
    for start, end, text in reversed(hits):
        out = out[:start] + text + out[end:]
    return out, bool(hits)


def is_bibliography(page_id, block):
    return (block.get("type") == "bibliography"
            or "bibliograph" in (page_id or "").lower())


# ---------------------------------------------------------------------------
# the pass over the corpus

def sweep_book(book, rules, skip_addresses=frozenset()):
    """Returns (edits, worklist, deferred, straddles, blocked).

    edits: [{page_id, target, index, after, rules, fr_snippet}]
    """
    edits, worklist, deferred, straddles, blocked = [], [], [], [], []

    def handle(page_id, target, index, fr_block, en_block, chapter_id):
        if en_block is None:
            return
        fr_html = fr_block.get("html", "")
        en_html = en_block.get("html", "")
        fr_text, en_text = normalize(fr_html), normalize(en_html)

        matchers, fired = [], []
        for rule in rules.mechanical:
            if not rule["fr_re"].search(fr_text):
                continue
            if rule["fr_veto"] and rule["fr_veto"].search(fr_text):
                continue
            if not any(re.search(r"(?<![\w-])" + re.escape(f) + r"(e?s)?(?![\w-])",
                                 en_text, re.I) for f in rule["from"]):
                continue
            matchers.extend(rule["matchers"])
            fired.append(rule["fr"])

        after, labels = substitute(en_html, matchers) if matchers else (en_html, [])

        # a rejected phrase that the FR gate wanted but prose matching missed is
        # split by a tag or a math span — never guess, hand it to the worklist
        for name in fired:
            if name not in labels:
                straddles.append({"book": book, "chapter": chapter_id, "page": page_id,
                                  "target": target, "index": index, "rule": name,
                                  "reason": "phrase straddles a tag or math span",
                                  "en_snippet": en_text[:200]})

        for rule in rules.spelling:
            if rule["skip_bibliography"] and is_bibliography(page_id, en_block):
                continue
            after, changed = apply_spelling(after, rule)
            if changed:
                labels = sorted(set(labels) | {rule["id"]})

        if after != en_html:
            if (page_id, target, index) in skip_addresses:
                deferred.append({"book": book, "page": page_id, "target": target,
                                 "index": index, "rules": labels,
                                 "reason": "block already carries an open proposal"})
            elif not prose_safe(en_html, after):
                straddles.append({"book": book, "chapter": chapter_id, "page": page_id,
                                  "target": target, "index": index, "rule": ",".join(labels),
                                  "reason": "substitution would alter a tag or math span"})
            elif check_replacement(after) is not None:
                # Some footnotes are multi-root *already* (bare text + inline
                # elements), so the single-root guard refuses any proposal on
                # them. That is a pre-existing pipeline limit, not a bad edit —
                # the substitution itself is prose-safe (checked just above).
                blocked.append({"book": book, "chapter": chapter_id, "page": page_id,
                                "target": target, "index": index, "rules": labels,
                                "after": after,
                                "reason": check_replacement(after),
                                "rootsBefore": root_count(en_html)})
            else:
                edits.append({"chapter_id": chapter_id, "page_id": page_id,
                              "target": target, "index": index, "after": after,
                              "rules": labels,
                              "cite": cite(book, page_id, fr_block, index)})

        # judgment tier — never edited, only listed
        for j in rules.judgment:
            if not j["fr_re"].search(fr_text):
                continue
            m = j["watch_re"].search(en_text)
            if not m:
                continue
            if j["en_filter"] and not j["en_filter"].search(en_text):
                continue
            at = m.start()
            worklist.append({
                "book": book, "chapter": chapter_id, "page": page_id,
                "target": target, "index": index, "rule": j["fr"],
                "en_present": m.group(1), "suggestion": j["suggest"],
                "reason": j["reason"],
                "fr_snippet": snippet(fr_text, j["fr_re"]),
                "en_snippet": en_text[max(0, at - 60):at + 90],
                "verdict": None,
            })

    for chapter_id, page_id, b_idx, fr_block, en_block in iter_aligned_blocks(book):
        handle(page_id, "block", b_idx, fr_block, en_block, chapter_id)
    for rec in iter_aligned_footnotes(book):
        if rec[0] == "skip":
            continue
        chapter_id, page_id, f_idx, fr_fn, en_fn = rec
        handle(page_id, "footnote", f_idx, fr_fn, en_fn, chapter_id)
    return edits, worklist, deferred, straddles, blocked


def snippet(text, pattern, width=60):
    m = pattern.search(text)
    if not m:
        return text[:2 * width]
    return text[max(0, m.start() - width):m.end() + width]


def open_addresses(book, keep_prefix=("g-",)):
    """Addresses already carrying an open proposal that this sweep did not write."""
    path = proposals_path(book)
    if not path.exists():
        return set(), {}
    run = load_json(path)
    addrs = set()
    for p in run.get("proposals") or []:
        if p.get("id", "").startswith(keep_prefix):
            continue
        target = p.get("target", "block")
        idx = p.get("footnoteIndex") if target == "footnote" else p.get("blockIndex")
        addrs.add((p.get("pageId"), target, idx))
    return addrs, run


# ---------------------------------------------------------------------------
# modes

def rationale_for(labels, rules_by_fr, fr_cite):
    named = []
    for label in labels:
        rule = rules_by_fr.get(label)
        if rule:
            named.append(f"«{label}» renders as \"{rule['to']}\", not "
                         f"\"{rule['from'][0]}\"")
        else:
            named.append("British spelling fibre/fibred is the house form")
    return ("Glossary consistency (glossary/glossary.json): "
            + "; ".join(named)
            + f". The aligned French block is {fr_cite}.")


def do_emit(book, rules, dry=False):
    skip, run = open_addresses(book)
    edits, _wl, deferred, straddles, blocked = sweep_book(book, rules, skip)
    rules_by_fr = {r["fr"]: r for r in rules.mechanical}
    proposals, failed = [], []
    for e in edits:
        pid = (f"g-{book}-en-{e['page_id']}-"
               f"{'fo' if e['target'] == 'footnote' else 'bl'}{e['index']}")
        try:
            proposals.append(new_proposal(
                book, "en", e["chapter_id"], e["page_id"], e["after"],
                rationale_for(e["rules"], rules_by_fr, e["cite"]),
                block_index=e["index"] if e["target"] == "block" else None,
                footnote_index=e["index"] if e["target"] == "footnote" else None,
                target=e["target"], category="translation",
                evidence=[e["cite"]], proposal_id=pid))
        except ValueError as exc:
            failed.append(f"{pid}: {exc}")
    print(f"{book}: {len(proposals)} proposal(s), {len(deferred)} deferred, "
          f"{len(straddles)} straddle(s), {len(blocked)} blocked, {len(failed)} refused")
    for msg in failed:
        print(f"    {msg}")
    if dry or not proposals:
        return proposals, deferred, straddles, blocked
    kept = [p for p in (run.get("proposals") or [])
            if not p.get("id", "").startswith("g-")]
    write_proposals(book, kept + proposals, generator=run.get("generator"),
                    generated_at=run.get("generatedAt"),   # run identity preserved
                    base_commit=run.get("baseCommit"))
    print(f"    wrote {proposals_path(book)} ({len(kept)} kept + {len(proposals)} new)")
    return proposals, deferred, straddles, blocked


def do_accept_all(book, out):
    run = load_json(proposals_path(book))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids = [p["id"] for p in run["proposals"] if p["id"].startswith("g-")]
    doc = {"schemaVersion": 1, "book": book,
           "proposalsGeneratedAt": run["generatedAt"], "decidedAt": now,
           "decisions": [{"id": i, "verdict": "accept", "at": now} for i in ids]}
    Path(out).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")
    print(f"{book}: {len(ids)} accept verdict(s) -> {out}")


def do_prune(book, ids_path):
    ids = {line.strip() for line in Path(ids_path).read_text().splitlines()
           if line.strip()}
    run = load_json(proposals_path(book))
    kept = [p for p in run["proposals"] if p["id"] not in ids]
    dropped = len(run["proposals"]) - len(kept)
    write_proposals(book, kept, generator=run.get("generator"),
                    generated_at=run.get("generatedAt"),
                    base_commit=run.get("baseCommit"))
    print(f"{book}: pruned {dropped}, {len(kept)} left "
          f"(generatedAt {run.get('generatedAt')} preserved)")


def do_audit_reverse(rules):
    """The check glossary_check.py structurally cannot do: the target phrase
    present in English where the French term is absent — i.e. over-application,
    or a pre-existing wrong-direction rendering."""
    out = []
    for book in BOOKS:
        for chapter_id, page_id, b_idx, fr_block, en_block in iter_aligned_blocks(book):
            if en_block is None:
                continue
            fr_text = normalize(fr_block.get("html", ""))
            en_text = normalize(en_block.get("html", ""))
            for rule in rules.mechanical:
                pat = re.compile(r"(?<![\w-])" + re.escape(rule["to"]) +
                                 r"(e?s)?(?![\w-])", re.I)
                if pat.search(en_text) and not rule["fr_re"].search(fr_text):
                    out.append({"book": book, "chapter": chapter_id, "page": page_id,
                                "block": b_idx, "rule": rule["fr"],
                                "en_has": rule["to"], "fr_snippet": fr_text[:160]})
    print(f"audit-reverse: {len(out)} block(s) where the English target appears "
          f"without the French term")
    counts = {}
    for r in out:
        counts[r["rule"]] = counts.get(r["rule"], 0) + 1
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"    {k:<28}{v}")
    return out


def carry_verdicts(worklist):
    """A reviewed item keeps its verdict across re-runs — otherwise every plan
    resurfaces occurrences a human has already decided to leave alone."""
    if not WORKLIST.exists():
        return
    old = {}
    for it in load_json(WORKLIST).get("items") or []:
        if it.get("verdict"):
            old[(it["book"], it["page"], it["target"], it["index"], it["rule"])] = \
                (it["verdict"], it.get("verdictNote"))
    for it in worklist:
        hit = old.get((it["book"], it["page"], it["target"], it["index"], it["rule"]))
        if hit:
            it["verdict"], it["verdictNote"] = hit


def do_plan(rules, books):
    totals, worklist, deferred, straddles, blocked = {}, [], [], [], []
    for book in books:
        skip, _run = open_addresses(book)
        edits, wl, dfr, strd, blk = sweep_book(book, rules, skip)
        worklist += wl
        deferred += dfr
        straddles += strd
        blocked += blk
        per = {}
        for e in edits:
            for label in e["rules"]:
                per[label] = per.get(label, 0) + 1
        totals[book] = {"blocks": len(edits), "byRule": per, "deferred": len(dfr),
                        "straddles": len(strd), "blocked": len(blk),
                        "worklist": len(wl)}
        print(f"{book:<7}{len(edits):>5} block(s)  " +
              "  ".join(f"{k}={v}" for k, v in sorted(per.items())))
    grand = {}
    for book in totals:
        for k, v in totals[book]["byRule"].items():
            grand[k] = grand.get(k, 0) + v
    print("\nby rule, all books:")
    for k, v in sorted(grand.items(), key=lambda kv: -kv[1]):
        print(f"    {k:<28}{v}")
    print(f"\ntotal blocks to edit: {sum(t['blocks'] for t in totals.values())}"
          f" · deferred {len(deferred)} · straddles {len(straddles)}"
          f" · blocked {len(blocked)} · judgment worklist {len(worklist)}")
    carry_verdicts(worklist)
    open_items = [it for it in worklist if not it.get("verdict")]
    print(f"judgment worklist: {len(worklist)} item(s), "
          f"{len(worklist) - len(open_items)} already reviewed, {len(open_items)} open")
    doc = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "scripts/glossary_sweep.py --plan",
        "totals": totals, "deferred": deferred, "straddles": straddles,
        "blocked": [{k: v for k, v in b.items() if k != "after"} for b in blocked],
        "items": worklist,
    }
    WORKLIST.write_text(dump_json(doc), encoding="utf-8")
    print(f"wrote {WORKLIST}")
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", action="append", choices=BOOKS)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--accept-all", action="store_true")
    ap.add_argument("--prune", action="store_true")
    ap.add_argument("--audit-reverse", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--ids")
    args = ap.parse_args()
    books = args.book or list(BOOKS)

    rules = Rules()
    for w in rules.warnings:
        print(f"  warning: {w}")

    if args.plan:
        do_plan(rules, books)
    elif args.emit:
        for book in books:
            do_emit(book, rules, dry=args.dry_run)
    elif args.accept_all:
        for book in books:
            do_accept_all(book, args.out or f"accept-{book}.json")
    elif args.prune:
        if not args.ids:
            raise SystemExit("--prune needs --ids")
        for book in books:
            do_prune(book, args.ids)
    elif args.audit_reverse:
        do_audit_reverse(rules)
    else:
        raise SystemExit("pick a mode: --plan / --emit / --accept-all / --prune / "
                         "--audit-reverse")


if __name__ == "__main__":
    main()
