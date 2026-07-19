#!/usr/bin/env python3
"""Convert hand-transcribed SGA 5 exposé HTML (01-transcribed/) into the JSON
data tree consumed by translation-viewer (02-converted_html/data/).

Adapted from sga4/scripts/build_viewer_data.py. Same overall conventions
(section headings <h2 id="…">, one aligned block per direct child of <body>,
pages split at <h2> boundaries), with the SGA 5 transcription quirks handled:

  * footnote lists are <div class="footnotes"> (SGA 4 used id="footnotes") and
    may appear mid-file (per source PDF page), not only trailing; each holds
    <p id="fn…"> items whose leading <a href="#fnref…"> is the printed backref;
  * in-text markers are <a id="fnref…" href="#fn…">, with or without the
    surrounding <sup class="footnote-ref"> (VIII uses bare <sup>), and one
    marker (VII) is a standalone <p id="fnref-VII-1"> whose <a> carries no id —
    markers are therefore found by their href, not by class;
  * footnote ids are sometimes already namespaced by exposé ("fn-III-6.3");
    they are still prefixed to "<roman>-fn…" uniformly so every id is globally
    unique in the viewer's single anchor_index;
  * the <hr> separating text from a footnote list is dropped (mid-file ones
    would otherwise render as stray rules);
  * a secondary <h1> (the appendix of Exposé I) starts a new page like an <h2>.

Emits data/fr/manifest.json as a *full* manifest (chapters + toc +
anchor_index + default_page_id), the format viewer.js reads natively, so every
cross-reference / footnote / back-arrow resolves. English is left empty for
now: one empty stub chapter per exposé (same page ids, no blocks) so the right
pane shows the standard "translation not available" placeholder.

Usage:
    python3 scripts/build_viewer_data.py [--write]
Without --write it only prints diagnostics (dry run).
"""
import json
import re
import sys
from pathlib import Path

import lxml.html as LH
from lxml.html import tostring

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "01-transcribed"
OUT_DIR = ROOT / "02-converted_html" / "data"
FR_DIR = OUT_DIR / "fr"
CH_DIR = FR_DIR / "chapters"
# English is an empty placeholder for now: we emit one stub chapter per exposé
# (same page ids as French, no blocks) and no en/manifest.json (the viewer only
# reads the base-language manifest). The empty stubs make the right pane show
# the standard "(translation not available)" placeholder until real
# translations replace them.
EN_DIR = OUT_DIR / "en"
EN_CH_DIR = EN_DIR / "chapters"

# Canonical reading order: the ten exposés of the published SGA 5 volume
# (Lecture Notes 589) — II, IV, IX, XI, XIII, XIV were never published.
ORDER = ["I", "III", "IIIB", "V", "VI", "VII", "VIII", "X", "XII", "XV"]

# In-text footnote markers and footnote targets: "fn" followed by a digit
# (fn1) or a hyphen (fn-III-6.3) — never "fnref…", which is a backref target.
FN_ID = re.compile(r"^fn[0-9-]")

FRONT_MATTER = set()

def is_transcribed(src: str, roman: str = "") -> bool:
    """A finished transcription has semantic headings + theorem environments;
    a raw draft is just <p> dumps with bare page-number paragraphs."""
    if roman in FRONT_MATTER:
        return '<h1 id=' in src
    return ('<h2 id=' in src) and ('class="thm' in src)


def inner_html(el) -> str:
    parts = [el.text or ""]
    for ch in el:
        parts.append(tostring(ch, encoding="unicode"))
    return "".join(parts).strip()


def block_meta(el):
    """Best-effort {type,label,title} metadata for a block (viewer ignores it)."""
    tag = el.tag
    meta = {"type": "paragraph", "label": None, "title": None}
    if tag in ("h1", "h2", "h3", "h4", "h5"):
        meta["type"] = "heading"
    elif tag == "table":
        meta["type"] = "table"
    elif tag in ("ol", "ul"):
        meta["type"] = "list"
    elif tag == "div":
        classes = (el.get("class") or "").split()
        if "thm" in classes:
            kind = next((c for c in classes
                         if c not in ("thm", "thm-plain", "thm-remark")), "theoreme")
            meta["type"] = kind
            num = el.find('.//span[@class="thm-num"]')
            name = el.find('.//span[@class="thm-name"]')
            if num is not None:
                meta["label"] = (num.text_content() or "").strip()
            if name is not None:
                meta["title"] = (name.text_content() or "").strip()
        elif "proof" in classes:
            meta["type"] = "proof"
        else:
            meta["type"] = "div"
    return meta


def chapter_title(body):
    """Title metadata from <h1> -> (title, alias, numeral, author).

    Footnote markers are dropped and <br> becomes a space, as before. The
    author span is pulled out as `author`, and a leading "EXPOSÉ <numeral>"
    is split off as alias/numeral so the viewer renders the chapter marker
    once (it used to prepend the number to a title that already began with
    "EXPOSÉ <numeral>"). All of alias/numeral/author may be None.
    """
    h1 = body.find("h1")
    if h1 is None:
        return "", None, None, None
    h1 = LH.fromstring(tostring(h1, encoding="unicode"))  # work on a clone
    author = None
    for span in h1.xpath('.//span[contains(@class,"author")]'):
        author = re.sub(r"\s+", " ", span.text_content()).strip() or None
        break
    for junk in h1.xpath('.//span[contains(@class,"author")] | .//sup'):
        junk.drop_tree()
    html = inner_html(h1)
    text = re.sub(r"<br\s*/?>", " ", html)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    alias = numeral = None
    m = re.match(r"^EXPOSÉ\s+([0-9]+|[IVXLC]+(?:\s*(?:bis|A|B))?)\b[\s.:—–-]*", text)
    if m:
        alias, numeral = "EXPOSÉ", m.group(1)
        text = text[m.end():].strip()
    return text, alias, numeral, author


def promote_stray_text(body):
    """The SGA 5 transcriptions leave display math (\\[…\\]) and the occasional
    page-break paragraph continuation as *bare text* at body top level, between
    sibling tags. lxml parses those runs as .tail of the preceding node (or
    body.text), which the block walk below would silently drop — ~160k chars
    across the ten exposés. Wrap each run in its own <p> so it becomes a block."""
    if body.text and body.text.strip():
        p = body.makeelement("p", {})
        p.text = body.text
        body.text = None
        body.insert(0, p)
    for el in list(body):          # includes comments, whose tails also count
        if el.tail and el.tail.strip():
            p = body.makeelement("p", {})
            p.text = el.tail
            el.tail = None
            body.insert(body.index(el) + 1, p)


def convert(roman: str, src: str):
    doc = LH.fromstring(src)
    body = doc.body
    promote_stray_text(body)

    # 1) Rename in-text footnote markers to the viewer's backref convention and
    #    namespace them per exposé: href "#fn1" -> "#I-fn1", marker id ->
    #    "I-fn1ref" (set on the <a> itself, whether or not the transcription
    #    gave it one). Markers are recognized by their href — SGA 5 marker
    #    markup varies too much for a class selector. Anchors *inside* footnote
    #    lists are backrefs (href "#fnref…"), excluded by FN_ID.
    fn_number = {}
    for a in body.xpath('.//a[@href]'):
        href = a.get("href") or ""
        if not href.startswith("#") or not FN_ID.match(href[1:]):
            continue
        orig = href[1:]                       # e.g. "fn1", "fn-III-6.3"
        fn_number[orig] = (a.text_content() or "").strip()
        a.set("href", f"#{roman}-{orig}")
        a.set("id", f"{roman}-{orig}ref")

    # 2) Walk top-level children: lift footnote lists out of the block stream,
    #    and split blocks into viewer pages at <h2> boundaries (one page per
    #    numbered section, as in sga1/sga2). The landing page (id = roman)
    #    holds everything before the first <h2>. A secondary <h1> (appendix)
    #    also starts a page. An <hr> directly before a footnote list is the
    #    printed separator — dropped.
    title, alias, numeral, author = chapter_title(body)
    if numeral and numeral.replace(" ", "") != roman:
        print(f"  WARN {roman}: h1 numeral {numeral!r} != chapter number")
    pages = [{"id": roman, "title": title, "blocks": [], "footnotes": []}]
    footnotes = []
    fn_seen = 0
    children = [el for el in body if isinstance(el.tag, str)]

    def is_fn_list(el):
        classes = (el.get("class") or "").split()
        return el.tag == "div" and ("footnotes" in classes
                                    or el.get("id") == "footnotes")

    first_h1_seen = False
    for i, el in enumerate(children):
        if is_fn_list(el):
            for item in el.xpath('./p | .//li[@id]'):
                item_id = item.get("id") or ""
                if item_id and not FN_ID.match(item_id):
                    continue
                fn_seen += 1
                # drop the printed backref, e.g. <a href="#fnref1">(1)</a>,
                # keeping its text as the printed footnote mark
                printed_mark = ""
                for back in item.xpath('.//a[starts-with(@href,"#fnref")]'
                                       ' | .//a[contains(@class,"backref")]'):
                    printed_mark = (back.text_content() or "").strip()
                    back.drop_tree()
                html = inner_html(item)
                if not item_id:
                    # markerless footnote (VI has two): synthesize an id; its
                    # printed "(*)"/"(**)" mark is a text prefix, not an <a>
                    item_id = f"fn-x{fn_seen}"
                    m = re.match(r"^\((\*+|\d+)\)\s*", html)
                    if m:
                        printed_mark = f"({m.group(1)})"
                        html = html[m.end():]
                footnotes.append({
                    "id": f"{roman}-{item_id}",
                    # in-text marker text; else the printed mark (some
                    # footnotes — XII-1, VI's starred ones — have no marker)
                    "number": fn_number.get(item_id) or printed_mark
                              or str(fn_seen),
                    "html": html,
                    # fallback attach point: the page the list sits in
                    "_page_idx": len(pages) - 1,
                })
            continue
        if (el.tag == "hr" and i + 1 < len(children)
                and is_fn_list(children[i + 1])):
            continue

        if el.tag == "h2" or (el.tag == "h1" and first_h1_seen):
            hid = el.get("id") or ""
            pid = (hid.replace(".", "-") if hid
                   else f"{roman}-s{len(pages) + 1}")
            h_title = re.sub(r"\s+", " ", el.text_content()).strip()
            pages.append({"id": pid, "title": h_title,
                          "blocks": [], "footnotes": []})
        if el.tag == "h1":
            first_h1_seen = True

        meta = block_meta(el)
        html = tostring(el, encoding="unicode", with_tail=False).strip()
        pages[-1]["blocks"].append({
            "id": el.get("id"),
            "type": meta["type"],
            "label": meta["label"],
            "title": meta["title"],
            "html": html,
        })

    # 3) Attach each footnote to the page holding its in-text marker (the
    #    marker was renamed to id="<fn.id>ref" above); a markerless footnote
    #    goes to the page its footnote list appeared in.
    for fn in footnotes:
        marker = f'id="{fn["id"]}ref"'
        fallback = pages[fn.pop("_page_idx")]
        target = next((p for p in pages
                       if any(marker in b["html"] for b in p["blocks"])),
                      fallback)
        target["footnotes"].append(fn)

    chapter = {
        "chapter_id": roman,
        "title": title,
        "number": roman,
        "pages": pages,
    }
    if alias:
        chapter["alias"] = alias
    if author:
        chapter["author"] = author
    return chapter


def collect_ids(chapter):
    """Every id a #href might target within this chapter -> its page id."""
    ids = {}
    id_re = re.compile(r'\bid="([^"]+)"')
    for page in chapter["pages"]:
        pid = page["id"]
        for b in page["blocks"]:
            for m in id_re.findall(b["html"]):
                ids[m] = pid
        for f in page["footnotes"]:
            ids[f["id"]] = pid
        ids[pid] = pid
    return ids


def en_placeholder(chapter):
    """Empty English stub mirroring a French chapter's page skeleton (same ids,
    no translated blocks). Titles are left null so the viewer's placeholder falls
    back to the French title."""
    return {
        "chapter_id": chapter["chapter_id"],
        "title": None,
        "number": chapter["number"],
        "pages": [{
            "id": p["id"],
            "title": None,
            "blocks": [],
            "footnotes": [],
        } for p in chapter["pages"]],
    }


def main():
    write = "--write" in sys.argv
    present = {f.stem: f for f in SRC_DIR.glob("*.html")}

    transcribed, raw = [], []
    for roman in ORDER:
        f = present.get(roman)
        if not f:
            raw.append((roman, "MISSING FILE"))
            continue
        src = f.read_text(encoding="utf-8")
        (transcribed if is_transcribed(src, roman) else raw).append(
            (roman, src if is_transcribed(src, roman) else "raw draft"))

    print(f"transcribed exposes: {len(transcribed)} | skipped: "
          f"{[r for r, _ in raw]}\n")

    chapters_meta = []
    toc = []
    anchor_index = {}
    all_defined = set()
    all_refs = {}  # target -> count
    en_created = []  # exposés for which a fresh English stub was written

    toc_order = 0
    for roman, src in transcribed:
        ch = convert(roman, src)
        ids = collect_ids(ch)
        for k, v in ids.items():
            anchor_index.setdefault(k, v)
        all_defined |= set(ids)

        for page in ch["pages"]:
            for b in page["blocks"]:
                for tgt in re.findall(r'class="ref" href="#([^"]+)"',
                                      b["html"]):
                    all_refs[tgt] = all_refs.get(tgt, 0) + 1

        ch_meta = {
            "id": roman, "title": ch["title"], "number": roman,
            "page_ids": [p["id"] for p in ch["pages"]],
        }
        if ch.get("alias"):
            ch_meta["alias"] = ch["alias"]
        if ch.get("author"):
            ch_meta["author"] = ch["author"]
        chapters_meta.append(ch_meta)
        for pi, page in enumerate(ch["pages"]):
            toc.append({
                "page_id": page["id"], "title": page["title"],
                "level": 0 if pi == 0 else 1,
                "order": toc_order,
                "is_numbered_chapter": pi == 0,
                "chapter_number": roman if pi == 0 else None,
            })
            toc_order += 1
        nblocks = sum(len(p["blocks"]) for p in ch["pages"])
        nfns = sum(len(p["footnotes"]) for p in ch["pages"])
        print(f"  {roman:6s} pages={len(ch['pages']):3d} "
              f"blocks={nblocks:4d} footnotes={nfns:3d}  "
              f"\"{ch['title'][:52]}\"")

        if write:
            CH_DIR.mkdir(parents=True, exist_ok=True)
            (CH_DIR / f"{roman}.json").write_text(
                json.dumps(ch, ensure_ascii=False, indent=1), encoding="utf-8")
            # Emit an empty English stub, but never overwrite one that already
            # holds a real translation (any page with blocks). Empty stubs are
            # refreshed so their page skeleton tracks the French one.
            EN_CH_DIR.mkdir(parents=True, exist_ok=True)
            en_path = EN_CH_DIR / f"{roman}.json"
            write_en = True
            if en_path.exists():
                existing = json.loads(en_path.read_text(encoding="utf-8"))
                write_en = not any(p.get("blocks")
                                   for p in existing.get("pages", []))
            if write_en:
                en_path.write_text(
                    json.dumps(en_placeholder(ch), ensure_ascii=False, indent=1),
                    encoding="utf-8")
                en_created.append(roman)

    manifest = {
        "chapters": chapters_meta,
        "toc": toc,
        "default_page_id": chapters_meta[0]["id"] if chapters_meta else None,
        "anchor_index": anchor_index,
    }
    if write:
        FR_DIR.mkdir(parents=True, exist_ok=True)
        (FR_DIR / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    # Diagnostics: dangling cross-references and unlifted/orphan footnotes.
    dangling = {t: n for t, n in all_refs.items() if t not in all_defined}
    print(f"\nanchor_index entries: {len(anchor_index)}")
    print(f"distinct class=ref targets: {len(all_refs)} | "
          f"dangling (unresolved): {len(dangling)}")
    if dangling:
        by_exp = {}
        for t, n in dangling.items():
            exp = re.match(r'([IVX]+B?)', t)
            key = exp.group(1) if exp else "?"
            by_exp[key] = by_exp.get(key, 0) + n
        top = sorted(by_exp.items(), key=lambda kv: -kv[1])
        print("  dangling targets by exposé prefix:",
              ", ".join(f"{k}:{v}" for k, v in top))
    if en_created:
        print(f"en placeholders created: {len(en_created)} "
              f"({', '.join(en_created)}) — empty stubs; the right pane shows "
              f"the standard 'translation not available' placeholder until "
              f"real translations replace them")

    print(f"\n{'WROTE' if write else 'DRY RUN — no files written'}")


if __name__ == "__main__":
    main()
