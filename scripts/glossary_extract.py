#!/usr/bin/env python3
"""Mine FR→EN terminology candidates from the well-translated SGA volumes.

Writes three files under glossary/candidates/ (committed as curation
provenance for glossary/glossary.json — they are candidates, not the
glossary):

  sga2-index.json    rows of SGA2's own Index terminologique (fr+en columns)
  thm-headings.json  aligned <span class="thm-name"> pairs, corpus-wide,
                     count-ranked, merged with the TITLE_MAP union from the
                     per-book translation scripts
  mined-terms.jsonl  per-block mining of «quoted» terms, emphasis inside
                     definitions, and "On appelle …" captures, deduped and
                     count-ranked — the main curation working file

Corpus: GOOD_BOOKS only (sga4/sga4.5 are raw MT); blocks whose EN side is
empty (sga3's untranslated chapters) are skipped by content, not by name.
"""
import re
from collections import OrderedDict

from glossary_lib import (
    CANDIDATES_DIR, GOOD_BOOKS, THM_NAME_RE, dump_json, iter_aligned_blocks,
    load_chapter, norm_heading, normalize, cite,
)
EM_RE = re.compile(r"<(?:em|i)>(.*?)</(?:em|i)>", re.S)
GUILLEMET_RE = re.compile(r"«\s*([^«»]{2,80}?)\s*»")
EN_QUOTE_RE = re.compile(r'["“]([^"“”]{2,80}?)["”]')
ON_APPELLE_RE = re.compile(
    r"\b(?:on appelle|on dit qu[e'][^,;.:]{0,40}? est|est dite?|est appelée?)\s+"
    r"(?:aussi\s+|encore\s+|parfois\s+)?([^,;.:¶]{3,60})", re.I)
TRIGGER_RE = re.compile(r"\bon appelle\b|\best dite?\b|\bappelée?\b", re.I)

# Union of the TITLE_MAP dicts in sga5/6/7/scripts/llm_translate.py and
# sga4.5/scripts/translate_json_en.py (sga5/6/7 are identical; sga4.5 is a
# subset), folded in so the glossary supersedes them as data.
TITLE_MAP_UNION = {
    "proposition": "Proposition", "théorème": "Theorem",
    "définition": "Definition", "lemme": "Lemma", "corollaire": "Corollary",
    "démonstration": "Proof", "preuve": "Proof", "remarque": "Remark",
    "remarques": "Remarks", "exemple": "Example", "exemples": "Examples",
    "conjecture": "Conjecture", "bibliographie": "Bibliography",
    "introduction": "Introduction", "variante": "Variant",
    "scholie": "Scholium",
}

ARTICLE_RE = re.compile(r"^(?:le |la |les |l'|un |une |des |du |de la |de l')",
                        re.I)


def extract_sga2_index():
    fr = load_chapter("sga2", "fr", "index-terminologie")
    rows = []
    html = "".join(b.get("html", "")
                   for p in fr["pages"] for b in p.get("blocks", []))
    for row in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        tds = re.findall(r"<td>(.*?)</td>", row, re.S)
        if len(tds) < 2:
            continue
        fr_term = normalize(tds[0], lower=False)
        en_term = normalize(tds[1], lower=False)
        refs = re.findall(r'href="#([^"]+)"', tds[2]) if len(tds) > 2 else []
        if fr_term and en_term:
            rows.append({"fr": fr_term, "en": en_term,
                         "refs": [f"sga2:{r}" for r in refs[:8]]})
    return rows


def extract_headings():
    pairs = OrderedDict()
    for book in GOOD_BOOKS:
        for cid, page_id, b_idx, fr_b, en_b in iter_aligned_blocks(book):
            fr_names = THM_NAME_RE.findall(fr_b.get("html", ""))
            if not fr_names or en_b is None:
                continue
            en_names = THM_NAME_RE.findall(en_b.get("html", ""))
            for i, fr_name in enumerate(fr_names):
                if i >= len(en_names):
                    break
                key = (norm_heading(fr_name), norm_heading(en_names[i]))
                if not key[0] or not key[1]:
                    continue
                rec = pairs.setdefault(
                    key, {"fr": key[0], "en": key[1], "count": 0, "seen": [],
                          "source": "thm-name"})
                rec["count"] += 1
                if len(rec["seen"]) < 8:
                    rec["seen"].append(cite(book, page_id, fr_b, b_idx))
    for fr_l, en in TITLE_MAP_UNION.items():
        key = (fr_l.capitalize(), en)
        if key not in pairs:
            pairs[key] = {"fr": key[0], "en": en, "count": None, "seen": [],
                          "source": "TITLE_MAP"}
    return sorted(pairs.values(),
                  key=lambda r: -(r["count"] or 0))


def candidate_key(fr_candidate):
    key = ARTICLE_RE.sub("", fr_candidate.lower()).strip()
    words = [w[:-1] if len(w) > 4 and w.endswith("s") else w
             for w in key.split()]
    return " ".join(words)


def clean_candidate(text):
    text = re.sub(r"\s+", " ", text).strip(" \t'\"“”.,;:-")
    if not (3 <= len(text) <= 60) or "¶" in text:
        return None
    if sum(c.isdigit() for c in text) > 2 or text.count("\\") > 0:
        return None
    return text


def mine_blocks():
    merged = OrderedDict()

    def add(fr_cand, en_cand, fr_ctx, en_ctx, where, source):
        fr_cand = clean_candidate(fr_cand)
        if fr_cand is None:
            return
        en_cand = clean_candidate(en_cand) if en_cand else None
        key = candidate_key(fr_cand)
        rec = merged.setdefault(key, {
            "fr_candidate": fr_cand, "en_candidates": [], "count": 0,
            "fr_context": fr_ctx, "en_context": en_ctx,
            "cites": [], "sources": []})
        rec["count"] += 1
        if en_cand and en_cand.lower() not in [c.lower()
                                               for c in rec["en_candidates"]]:
            rec["en_candidates"].append(en_cand)
            rec["en_candidates"] = rec["en_candidates"][:5]
        if len(rec["cites"]) < 8:
            rec["cites"].append(where)
        if source not in rec["sources"]:
            rec["sources"].append(source)

    def context(text, term, margin=80):
        pos = text.lower().find(term.lower())
        if pos < 0:
            return text[:2 * margin]
        return text[max(0, pos - margin):pos + len(term) + margin]

    for book in GOOD_BOOKS:
        for cid, page_id, b_idx, fr_b, en_b in iter_aligned_blocks(book):
            if en_b is None:
                continue
            fr_html, en_html = fr_b.get("html", ""), en_b.get("html", "")
            fr_text = normalize(fr_html, lower=False)
            en_text = normalize(en_html, lower=False)
            if not fr_text or not en_text:
                continue
            where = cite(book, page_id, fr_b, b_idx)

            # «guillemet» spans, paired with the same-ordinal EN quoted span
            fr_quotes = GUILLEMET_RE.findall(fr_text)
            en_quotes = EN_QUOTE_RE.findall(en_text) if fr_quotes else []
            for i, q in enumerate(fr_quotes):
                en_q = en_quotes[i] if i < len(en_quotes) else None
                add(q, en_q, context(fr_text, q), context(en_text, en_q or q),
                    where, "guillemet")

            # emphasis — only inside definition blocks or near a naming verb
            is_def = fr_b.get("type") == "definition"
            triggers = [m.start() for m in TRIGGER_RE.finditer(fr_text)]
            fr_ems = [normalize(e, lower=False) for e in EM_RE.findall(fr_html)]
            en_ems = [normalize(e, lower=False) for e in EM_RE.findall(en_html)]
            for i, em in enumerate(fr_ems):
                if not em:
                    continue
                pos = fr_text.lower().find(em.lower())
                near = any(0 <= pos - t <= 120 for t in triggers if pos >= 0)
                if not (is_def or near):
                    continue
                en_em = en_ems[i] if i < len(en_ems) else None
                add(em, en_em, context(fr_text, em),
                    context(en_text, en_em or em), where, "em-def")

            # crude "On appelle X" noun-phrase capture (curator cleans)
            for m in ON_APPELLE_RE.finditer(fr_text):
                add(m.group(1), None, context(fr_text, m.group(1)),
                    en_text[:160], where, "on-appelle")

    rows = sorted(merged.values(), key=lambda r: (-r["count"],
                                                  r["fr_candidate"].lower()))
    return rows


def main():
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)

    index_rows = extract_sga2_index()
    (CANDIDATES_DIR / "sga2-index.json").write_text(
        dump_json(index_rows), encoding="utf-8")
    print(f"sga2-index.json: {len(index_rows)} rows")

    headings = extract_headings()
    (CANDIDATES_DIR / "thm-headings.json").write_text(
        dump_json(headings), encoding="utf-8")
    print(f"thm-headings.json: {len(headings)} rows")

    mined = mine_blocks()
    import json
    with open(CANDIDATES_DIR / "mined-terms.jsonl", "w",
              encoding="utf-8") as fh:
        for row in mined:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"mined-terms.jsonl: {len(mined)} rows "
          f"({sum(1 for r in mined if r['count'] >= 2)} with count >= 2)")


if __name__ == "__main__":
    main()
