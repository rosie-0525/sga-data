#!/usr/bin/env python3
"""Validate that an English chapter JSON structurally mirrors its French source.

Checks (fatal unless noted):
  - both files are valid JSON
  - chapter_id and number identical
  - same page ids, in the same order
  - per page: footnote ids+numbers identical; same block count;
    per block id/type/label identical, and title null-ness identical
  - per block html: identical multiset of id="..." and href="..." (structure +
    cross-refs preserved), identical math-delimiter and \\begin/\\end counts
  - WARN (non-fatal): French stopwords still present in English prose

Usage: compare_translation.py <ROMAN> [<ROMAN> ...]   (or 'all')
Exit code 0 iff every requested chapter passes the fatal checks.
"""
import json, re, sys, glob, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "02-converted_html", "data")

FRENCH = {"le","la","les","un","une","des","du","de","et","est","sont","dans",
    "pour","nous","vous","ils","elle","cette","ces","avec","sur","par","plus",
    "aux","au","ou","où","son","ses","leur","leurs","qui","que","dont","donc",
    "alors","ainsi","soit","soient","tout","tous","toute","toutes","être","fait",
    "deux","même","entre","suivant","suivante","démonstration","théorème","lemme",
    "proposition","corollaire","définition","remarque","exemple","préfaisceau",
    "faisceau","catégorie","morphisme","ensemble","d'un","d'une","l'on","qu'on",
    "n'est","c'est","il","on"}

def visible_text(html):
    t = re.sub(r"\\\(.*?\\\)", " ", html, flags=re.S)
    t = re.sub(r"\\\[.*?\\\]", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&[a-z]+;", " ", t)
    return t

def ids_hrefs(html):
    return (sorted(re.findall(r'id="([^"]*)"', html)),
            sorted(re.findall(r'href="([^"]*)"', html)))

# French theorem-kind names that DIFFER in English (Proposition/Notation/Construction
# are identical in both languages, so they are NOT flagged).
FR_THMNAME = {"Définition","Définitions","Théorème","Théorèmes","Lemme","Lemmes",
    "Corollaire","Corollaires","Remarque","Remarques","Exemple","Exemples","Scholie",
    "Démonstration","Preuve","Variante","Variantes","Exercice","Exercices","Problème",
    "Problèmes","Convention"}

def french_leftovers(html):
    """Return list of clear French mistranslations in translatable spans."""
    hits = []
    for m in re.findall(r'class="thm-name">\s*([^<]*?)\s*</span>', html):
        if m in FR_THMNAME:
            hits.append("thm-name:" + m)
    if re.search(r'class="author">\s*par\b', html):
        hits.append("author:par")
    return hits

def math_sig(html):
    return (html.count(r"\("), html.count(r"\)"),
            html.count(r"\["), html.count(r"\]"),
            html.count(r"\begin{"), html.count(r"\end{"))

def check(roman):
    errs, warns = [], []
    fp = os.path.join(DATA, "fr", "chapters", roman + ".json")
    ep = os.path.join(DATA, "en", "chapters", roman + ".json")
    try:
        fr = json.load(open(fp, encoding="utf-8"))
    except Exception as e:
        return [f"fr unreadable: {e}"], []
    try:
        en = json.load(open(ep, encoding="utf-8"))
    except Exception as e:
        return [f"en INVALID JSON: {e}"], []

    if fr["chapter_id"] != en.get("chapter_id"):
        errs.append(f"chapter_id {fr['chapter_id']!r} != {en.get('chapter_id')!r}")
    if fr["number"] != en.get("number"):
        errs.append(f"number {fr['number']!r} != {en.get('number')!r}")
    if not en.get("title"):
        warns.append("chapter title not translated (null/empty)")

    fpages, epages = fr["pages"], en.get("pages", [])
    if [p["id"] for p in fpages] != [p["id"] for p in epages]:
        errs.append("PAGE IDS differ:\n  fr=%s\n  en=%s" %
                    ([p["id"] for p in fpages], [p["id"] for p in epages]))
        return errs, warns  # can't align further

    fr_words = 0
    for fpg, epg in zip(fpages, epages):
        pid = fpg["id"]
        # footnotes
        if [(x["id"], x["number"]) for x in fpg["footnotes"]] != \
           [(x["id"], x["number"]) for x in epg["footnotes"]]:
            errs.append(f"[{pid}] footnote id/number mismatch")
        # blocks
        fb, eb = fpg["blocks"], epg["blocks"]
        if len(fb) != len(eb):
            errs.append(f"[{pid}] block count {len(fb)} != {len(eb)}")
            continue
        for i, (a, b) in enumerate(zip(fb, eb)):
            tag = f"[{pid}#{i} id={a['id']}]"
            for k in ("id", "type", "label"):
                if a[k] != b.get(k):
                    errs.append(f"{tag} {k} {a[k]!r} != {b.get(k)!r}")
            if (a["title"] is None) != (b.get("title") is None):
                errs.append(f"{tag} title null-ness differs "
                            f"({a['title']!r} vs {b.get('title')!r})")
            if ids_hrefs(a["html"]) != ids_hrefs(b.get("html", "")):
                errs.append(f"{tag} id/href set changed in html")
            if math_sig(a["html"]) != math_sig(b.get("html", "")):
                errs.append(f"{tag} math-delimiter counts changed "
                            f"{math_sig(a['html'])} vs {math_sig(b.get('html',''))}")
            fl = french_leftovers(b.get("html", ""))
            if fl:
                errs.append(f"{tag} untranslated French span(s): {', '.join(fl)}")
            # french leftover heuristic
            words = re.findall(r"[A-Za-zÀ-ÿ']+", visible_text(b.get("html", "")).lower())
            fr_words += sum(1 for w in words if w in FRENCH)
    if fr_words > 8:
        warns.append(f"{fr_words} French-stopword hits in English prose "
                     f"(possible untranslated content)")
    return errs, warns

def main():
    args = sys.argv[1:]
    if not args or args == ["all"]:
        args = sorted(os.path.splitext(os.path.basename(p))[0]
                      for p in glob.glob(os.path.join(DATA, "fr", "chapters", "*.json")))
    ok = True
    for roman in args:
        errs, warns = check(roman)
        status = "PASS" if not errs else "FAIL"
        if errs:
            ok = False
        print(f"=== {roman}: {status} ===")
        for e in errs:
            print("  ERROR:", e)
        for w in warns:
            print("  warn :", w)
    print("\nALL PASS" if ok else "\nSOME FAILED")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
