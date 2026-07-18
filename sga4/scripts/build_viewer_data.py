#!/usr/bin/env python3
"""Convert hand-transcribed SGA 4 exposé HTML (01-transcribed/) into the JSON
data tree consumed by translation-viewer (02-converted_html/data/).

Adapted from sga3/scripts/build_viewer_data.py — same transcription conventions
(footnotes in a trailing <div id="footnotes">, in-text markers
<sup class="footnote-ref"><a id="fnrefN" href="#fnN">, section headings <h2 id="…">),
so the logic is unchanged; only the reading order differs (SGA 4 has no front
matter and includes the half-exposé "Vbis").

For each exposé:
  * each direct child of <body> becomes one aligned block (viewer reads
    block.html via `template.content.firstElementChild`, so one element/block);
  * blocks are split into viewer pages at <h2> boundaries, as in sga1/sga2:
    a landing page (id = roman numeral) for everything before the first <h2>,
    then one page per numbered section (h2 id "I.1" -> page id "I-1");
  * the trailing footnote <ol> (its <li> ids start with "fn") is lifted into the
    page's footnotes[] array;
  * footnote ids are namespaced per exposé (e.g. VIII-fn1) because the viewer's
    anchor_index is a single global map and bare `fn1` collides across exposés;
  * in-text markers are renamed to `<roman>-fn<k>ref` so the back-arrow the
    viewer synthesizes (href="#<footnote.id>ref") lands on the marker.

Emits data/fr/manifest.json as a *full* manifest (chapters + toc +
anchor_index + default_page_id), the format viewer.js reads natively, so every
cross-reference / footnote / back-arrow resolves. English is left empty for now:
one empty stub chapter per exposé (same page ids, no blocks) so the right pane
shows the standard "translation not available" placeholder.

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

# Canonical reading order of the SGA 4 exposés (no front matter; "Vbis" is the
# half-exposé "Techniques de descente cohomologique" between V and VI).
ORDER = ["I", "II", "III", "IV", "V", "Vbis", "VI", "VII", "VIII", "IX", "X",
         "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX"]

THM_KINDS = {"definition", "proposition", "theoreme", "corollaire", "lemme",
             "remarque", "scholie", "scolie", "exemple", "notation",
             "conjecture", "hypothese", "question"}

# SGA 4 has no front matter; kept for parity with the shared is_transcribed().
FRONT_MATTER = set()

def is_transcribed(src: str, roman: str = "") -> bool:
    """A finished transcription has semantic headings + theorem environments;
    a raw draft is just <p> dumps with bare page-number paragraphs.
    Front matter (if any) is accepted with just an <h1>."""
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


def chapter_title(body) -> str:
    """Human title from <h1>: drop author + footnote marker, <br> -> space."""
    h1 = body.find("h1")
    if h1 is None:
        return ""
    h1 = LH.fromstring(tostring(h1, encoding="unicode"))  # work on a clone
    for junk in h1.xpath('.//span[contains(@class,"author")] | .//sup'):
        junk.drop_tree()
    html = inner_html(h1)
    text = re.sub(r"<br\s*/?>", " ", html)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def promote_stray_text(body):
    """The transcriptions leave display math (\\[…\\]) and the occasional
    page-break paragraph continuation as *bare text* at body top level, between
    sibling tags. lxml parses those runs as .tail of the preceding node (or
    body.text), which the block walk below would silently drop — ~82k chars
    across the SGA 4 exposés. Wrap each run in its own <p> so it becomes a
    block. (Ported from sga5/scripts/build_viewer_data.py.)"""
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
    #    namespace them per exposé. Marker href "#fn1" -> "#VIII-fn1",
    #    marker id -> "VIII-fn1ref". Collect display numbers by original id.
    fn_number = {}
    for a in body.xpath('.//sup[contains(@class,"footnote-ref")]/a'):
        href = a.get("href") or ""
        if not href.startswith("#"):
            continue
        orig = href[1:]                       # e.g. "fn1", "fn-s1"
        fn_number[orig] = (a.text_content() or "").strip()
        a.set("href", f"#{roman}-{orig}")
        a.set("id", f"{roman}-{orig}ref")

    # 2) Walk top-level children: split footnote list(s) from content blocks,
    #    and split blocks into viewer pages at <h2> boundaries (one page per
    #    numbered section, as in sga1/sga2). The landing page (id = roman)
    #    holds everything before the first <h2>.
    title = chapter_title(body)
    pages = [{"id": roman, "title": title, "blocks": [], "footnotes": []}]
    footnotes = []
    fn_seen = 0
    for el in body:
        if not isinstance(el.tag, str):       # comments / PIs
            continue
        # Footnotes live in a trailing <div id="footnotes"> (or a bare <ol> of
        # <li id="fn..">). Lift every fn <li> it contains into footnotes[],
        # plus starred notes (<p class="footnote-star" id="fn-s1">) that sit
        # between the <ol> runs.
        classes = (el.get("class") or "").split()
        fn_items = el.xpath('.//li[starts-with(@id,"fn")]'
                            ' | .//p[starts-with(@id,"fn")]')
        is_fn_list = fn_items and (
            el.get("id") == "footnotes"
            or (el.tag in ("ol", "ul") and "enumerate" not in classes)
        )
        if is_fn_list:
            for item in fn_items:
                item_id = item.get("id") or ""
                if not item_id.startswith("fn"):
                    continue
                fn_seen += 1
                for back in item.xpath('.//a[contains(@class,"backref")]'):
                    back.drop_tree()
                html = inner_html(item)
                if item.tag == "p":
                    # the marker ("*") is rendered from "number"; drop it here
                    html = re.sub(r"^\*\s*", "", html)
                footnotes.append({
                    "id": f"{roman}-{item_id}",
                    "number": fn_number.get(item_id, str(fn_seen)),
                    "html": html,
                })
            continue

        if el.tag == "h2":
            h2_id = el.get("id") or ""
            pid = (h2_id.replace(".", "-") if h2_id
                   else f"{roman}-s{len(pages) + 1}")
            h2_title = re.sub(r"\s+", " ", el.text_content()).strip()
            pages.append({"id": pid, "title": h2_title,
                          "blocks": [], "footnotes": []})

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
    #    marker was renamed to id="<fn.id>ref" above); fall back to the last
    #    page if no marker is found.
    for fn in footnotes:
        marker = f'id="{fn["id"]}ref"'
        target = next((p for p in pages
                       if any(marker in b["html"] for b in p["blocks"])),
                      pages[-1])
        target["footnotes"].append(fn)

    chapter = {
        "chapter_id": roman,
        "title": title,
        "number": roman,
        "pages": pages,
    }
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

        chapters_meta.append({
            "id": roman, "title": ch["title"], "number": roman,
            "page_ids": [p["id"] for p in ch["pages"]],
        })
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

    # Diagnostics: dangling cross-references.
    dangling = {t: n for t, n in all_refs.items() if t not in all_defined}
    print(f"\nanchor_index entries: {len(anchor_index)}")
    print(f"distinct class=ref targets: {len(all_refs)} | "
          f"dangling (unresolved): {len(dangling)}")
    by_exp = {}
    for t, n in dangling.items():
        exp = re.match(r'([IVX]+[AB]?)', t)
        by_exp[exp.group(1) if exp else "?"] = by_exp.get(
            exp.group(1) if exp else "?", 0) + n
    if dangling:
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
