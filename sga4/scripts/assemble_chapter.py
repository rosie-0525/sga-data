#!/usr/bin/env python3
"""Assemble a translated English chapter from per-page part files.

A translator agent writes one file per page to
  <PARTS>/<ROMAN>/<page_id>.json
each containing the fully-translated page object
  {"id","title","blocks":[...],"footnotes":[...]}.

This script reads the French chapter for the authoritative page ORDER, ids,
chapter_id and number, pulls each translated page from its part file, and emits
  en/chapters/<ROMAN>.json
It is RESUMABLE: if any page part is missing it lists them and exits non-zero
without clobbering, so the translator can fill only the gaps.

Usage: assemble_chapter.py <ROMAN> [<ROMAN> ...]
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "02-converted_html", "data")
PARTS = os.environ.get("PARTS_DIR",
    "/private/tmp/claude-501/-Users-rosie-dev-sga/e8d7c475-3ea5-495a-b9b4-f1636d48a77f/scratchpad/parts")

def assemble(roman):
    fr = json.load(open(os.path.join(DATA, "fr", "chapters", roman + ".json"), encoding="utf-8"))
    pdir = os.path.join(PARTS, roman)
    pages, missing, bad = [], [], []
    for p in fr["pages"]:
        fpath = os.path.join(pdir, p["id"] + ".json")
        if not os.path.exists(fpath):
            missing.append(p["id"]); continue
        try:
            obj = json.load(open(fpath, encoding="utf-8"))
        except Exception as e:
            bad.append(f"{p['id']} ({e})"); continue
        if obj.get("id") != p["id"]:
            bad.append(f"{p['id']} (part id mismatch: {obj.get('id')!r})"); continue
        if len(obj.get("blocks", [])) != len(p["blocks"]):
            bad.append(f"{p['id']} (block count {len(obj.get('blocks',[]))}!={len(p['blocks'])})"); continue
        pages.append(obj)
    if missing or bad:
        print(f"[{roman}] INCOMPLETE — {len(pages)}/{len(fr['pages'])} pages ready")
        if missing: print("  MISSING pages:", ", ".join(missing))
        if bad:     print("  BAD pages   :", "; ".join(bad))
        return False
    out = {
        "chapter_id": fr["chapter_id"],
        "title": pages[0]["title"] if pages else fr["title"],
        "number": fr["number"],
        "pages": pages,
    }
    outpath = os.path.join(DATA, "en", "chapters", roman + ".json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"[{roman}] assembled {len(pages)} pages -> {outpath}")
    return True

if __name__ == "__main__":
    ok = all(assemble(r) for r in sys.argv[1:])
    sys.exit(0 if ok else 1)
