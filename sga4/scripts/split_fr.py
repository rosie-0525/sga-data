#!/usr/bin/env python3
"""Split French chapter JSON into per-page files for page-at-a-time translation.

Writes  <PARTS_FR>/<ROMAN>/<page_id>.json  (one French page object each) and
prints, per chapter, the ordered page-id list and each page's block count so the
orchestrator can size the work.  Idempotent.

Usage: split_fr.py <ROMAN> [<ROMAN> ...]
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "02-converted_html", "data")
SCRATCH = "/private/tmp/claude-501/-Users-rosie-dev-sga/e8d7c475-3ea5-495a-b9b4-f1636d48a77f/scratchpad"
PARTS_FR = os.path.join(SCRATCH, "parts_fr")

def split(roman):
    fr = json.load(open(os.path.join(DATA, "fr", "chapters", roman + ".json"), encoding="utf-8"))
    d = os.path.join(PARTS_FR, roman)
    os.makedirs(d, exist_ok=True)
    total = 0
    lines = []
    for p in fr["pages"]:
        with open(os.path.join(d, p["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=1)
        nb = len(p["blocks"])
        total += nb
        lines.append(f"    {p['id']:22} {nb:4} blocks")
    print(f"[{roman}] {len(fr['pages'])} pages, {total} blocks -> {d}")
    for l in lines:
        print(l)
    return [p["id"] for p in fr["pages"]]

if __name__ == "__main__":
    for r in sys.argv[1:]:
        split(r)
