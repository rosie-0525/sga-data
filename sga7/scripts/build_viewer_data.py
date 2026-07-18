#!/usr/bin/env python3
"""Convert hand-transcribed SGA 7 exposé HTML (01-transcribed/) into the JSON
data tree consumed by translation-viewer (02-converted_html/data/).

Adapted from sga5/scripts/build_viewer_data.py. Same overall conventions
(section headings <h2 id="…">, one aligned block per direct child of <body>,
pages split at <h2> boundaries), with the SGA 7 transcription quirks handled:

  * files are named by arabic exposé number (1.html … 22.html; III–V were
    never published, 6.html — Rim's exposé — is originally in English) and all
    internal ids are arabic-dotted ("13.2", "17.2.3"), so chapter/page ids stay
    arabic and the printed roman numeral is carried in "number" for display;
  * there are no footnote-list containers: footnotes are individual top-level
    <p class="footnote"> / <aside class="footnote"> elements dropped into the
    text at their source-page position, with or without an id, their printed
    mark being either a leading <sup> (possibly inside the aside's first <p>),
    a leading "(*)"-style text prefix, or a backref <a> (8.html only);
  * in-text markers, when present, are plain <a href="#<footnote-id>">
    anchors (no fnref class/id convention worth matching on) — recognized by
    their href pointing at a known footnote id;
  * exposé IX's sixteen footnotes are all markerless; ten of them were
    transcribed as a trailing dump at end of file, so they attach to the last
    page rather than the page they were printed on (no marker to place them);
  * a lone <hr> directly before a footnote is the printed separator — dropped.

Emits data/fr/manifest.json as a *full* manifest (chapters + toc +
anchor_index + default_page_id), the format viewer.js reads natively. English
is left empty for now: one empty stub chapter per exposé (same page ids, no
blocks) so the right pane shows the standard placeholder.

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
EN_DIR = OUT_DIR / "en"
EN_CH_DIR = EN_DIR / "chapters"

# Canonical reading order: the nineteen exposés of the published SGA 7 volumes
# (Lecture Notes 288 = I, II, VI–IX; Lecture Notes 340 = X–XXII).
# Exposés III, IV, V were never published.
ORDER = ["1", "2", "6", "7", "8", "9", "10", "11", "12", "13", "14",
         "15", "16", "17", "18", "19", "20", "21", "22"]

ROMAN = {"1": "I", "2": "II", "6": "VI", "7": "VII", "8": "VIII", "9": "IX",
         "10": "X", "11": "XI", "12": "XII", "13": "XIII", "14": "XIV",
         "15": "XV", "16": "XVI", "17": "XVII", "18": "XVIII", "19": "XIX",
         "20": "XX", "21": "XXI", "22": "XXII"}


def is_transcribed(src: str) -> bool:
    """A finished transcription has semantic <h2 id=…> section headings; a raw
    draft is just <p> dumps. (Unlike SGA 5, theorem envs are not required —
    exposé XIII legitimately has none.)"""
    return "<h2 id=" in src


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
    body.text), which the block walk below would silently drop. Wrap each run
    in its own <p> so it becomes a block."""
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


def is_footnote(el):
    return (isinstance(el.tag, str)
            and el.tag in ("p", "aside")
            and "footnote" in (el.get("class") or "").split())


MARK_TEXT = re.compile(r"^\s*\((\*+|\d+)\)\s*")


def extract_footnote(el, num, stem):
    """Turn one <p|aside class=footnote> into {id, number, html}: drop the
    backref <a> / leading <sup> / leading "(*)" text prefix, keeping its text
    as the printed mark. Returns (orig_id_or_None, footnote_dict_sans_id)."""
    printed = ""
    # backref anchor (8.html: <a href="#8.fnref-1">(*)</a> inside the aside)
    for a in el.xpath('.//a[@href]'):
        printed = (a.text_content() or "").strip() or printed
        a.drop_tree()
    # leading <sup> mark — direct child, or inside the aside's first <p>
    container = el
    if (len(el) and el[0].tag == "p" and not (el.text or "").strip()):
        container = el[0]
    if (len(container) and container[0].tag == "sup"
            and not (container.text or "").strip()):
        sup = container[0]
        printed = printed or (sup.text_content() or "").strip()
        sup.drop_tree()          # its tail is merged into container.text
    else:
        m = MARK_TEXT.match(container.text or "")
        if m:
            printed = printed or f"({m.group(1)})"
            container.text = (container.text or "")[m.end():]
    return {
        "number": printed or str(num),
        "html": inner_html(el),
    }


def convert(stem: str, src: str):
    doc = LH.fromstring(src)
    body = doc.body
    promote_stray_text(body)
    children = [el for el in body if isinstance(el.tag, str)]

    # 1) Rename in-text footnote markers to the viewer's backref convention and
    #    namespace them per exposé: href "#fn1" -> "#17-fn1", marker id ->
    #    "17-fn1ref" (set on the <a> itself, overwriting any transcription id).
    #    Markers are recognized by their href pointing at a known footnote id;
    #    the only anchors *inside* footnote elements target markers, not
    #    footnotes, so they never match here (they are dropped later anyway).
    fn_ids = {el.get("id") for el in children if is_footnote(el) and el.get("id")}
    fn_number = {}
    for a in body.xpath('.//a[@href]'):
        href = a.get("href") or ""
        if not href.startswith("#") or href[1:] not in fn_ids:
            continue
        orig = href[1:]
        fn_number[orig] = (a.text_content() or "").strip()
        a.set("href", f"#{stem}-{orig}")
        a.set("id", f"{stem}-{orig}ref")

    # 2) Walk top-level children: lift footnote elements out of the block
    #    stream, and split blocks into viewer pages at <h2> boundaries (one
    #    page per numbered section). The landing page (id = stem) holds
    #    everything before the first <h2>. An <hr> directly before a footnote
    #    is the printed separator — dropped.
    title = chapter_title(body)
    pages = [{"id": stem, "title": title, "blocks": [], "footnotes": []}]
    footnotes = []
    fn_seen = 0
    for i, el in enumerate(children):
        if is_footnote(el):
            fn_seen += 1
            orig_id = el.get("id")
            fn = extract_footnote(el, fn_seen, stem)
            if orig_id:
                fn["number"] = fn_number.get(orig_id) or fn["number"]
            fn["id"] = f"{stem}-{orig_id or f'fn-x{fn_seen}'}"
            fn["_page_idx"] = len(pages) - 1
            footnotes.append(fn)
            continue
        if (el.tag == "hr" and i + 1 < len(children)
                and is_footnote(children[i + 1])):
            continue

        if el.tag == "h2":
            hid = el.get("id") or ""
            pid = (hid.replace(".", "-") if hid
                   else f"{stem}-s{len(pages) + 1}")
            if pid != stem and not pid.startswith(f"{stem}-"):
                pid = f"{stem}-{pid}"
            h_title = re.sub(r"\s+", " ", el.text_content()).strip()
            pages.append({"id": pid, "title": h_title,
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

    # 3) Attach each footnote to the page holding its in-text marker (renamed
    #    to id="<fn.id>ref" above); a markerless footnote goes to the page it
    #    appeared in.
    for fn in footnotes:
        marker = f'id="{fn["id"]}ref"'
        fallback = pages[fn.pop("_page_idx")]
        target = next((p for p in pages
                       if any(marker in b["html"] for b in p["blocks"])),
                      fallback)
        target["footnotes"].append(fn)

    chapter = {
        "chapter_id": stem,
        "title": title,
        "number": ROMAN[stem],
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
    no translated blocks)."""
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

    transcribed, skipped = [], []
    for stem in ORDER:
        f = present.get(stem)
        if not f:
            skipped.append(stem)
            continue
        src = f.read_text(encoding="utf-8")
        if is_transcribed(src):
            transcribed.append((stem, src))
        else:
            skipped.append(stem)

    print(f"transcribed exposes: {len(transcribed)} | skipped: {skipped}\n")

    chapters_meta = []
    toc = []
    anchor_index = {}
    dup_ids = {}
    all_defined = set()
    all_refs = {}  # target -> count
    en_created = []

    toc_order = 0
    for stem, src in transcribed:
        ch = convert(stem, src)
        ids = collect_ids(ch)
        for k, v in ids.items():
            if k in anchor_index:
                dup_ids[k] = dup_ids.get(k, 1) + 1
            anchor_index.setdefault(k, v)
        all_defined |= set(ids)

        for page in ch["pages"]:
            for b in page["blocks"]:
                for tgt in re.findall(r'<a[^>]+href="#([^"]+)"', b["html"]):
                    all_refs[tgt] = all_refs.get(tgt, 0) + 1

        chapters_meta.append({
            "id": stem, "title": ch["title"], "number": ch["number"],
            "page_ids": [p["id"] for p in ch["pages"]],
        })
        for pi, page in enumerate(ch["pages"]):
            toc.append({
                "page_id": page["id"], "title": page["title"],
                "level": 0 if pi == 0 else 1,
                "order": toc_order,
                "is_numbered_chapter": pi == 0,
                "chapter_number": ch["number"] if pi == 0 else None,
            })
            toc_order += 1
        nblocks = sum(len(p["blocks"]) for p in ch["pages"])
        nfns = sum(len(p["footnotes"]) for p in ch["pages"])
        print(f"  {stem:3s} ({ch['number']:5s}) pages={len(ch['pages']):3d} "
              f"blocks={nblocks:4d} footnotes={nfns:3d}  "
              f"\"{ch['title'][:52]}\"")

        if write:
            CH_DIR.mkdir(parents=True, exist_ok=True)
            (CH_DIR / f"{stem}.json").write_text(
                json.dumps(ch, ensure_ascii=False, indent=1), encoding="utf-8")
            # Emit an empty English stub, but never overwrite one that already
            # holds a real translation (any page with blocks).
            EN_CH_DIR.mkdir(parents=True, exist_ok=True)
            en_path = EN_CH_DIR / f"{stem}.json"
            write_en = True
            if en_path.exists():
                existing = json.loads(en_path.read_text(encoding="utf-8"))
                write_en = not any(p.get("blocks")
                                   for p in existing.get("pages", []))
            if write_en:
                en_path.write_text(
                    json.dumps(en_placeholder(ch), ensure_ascii=False, indent=1),
                    encoding="utf-8")
                en_created.append(stem)

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

    # Diagnostics: duplicate ids across exposés, dangling hrefs.
    dangling = {t: n for t, n in all_refs.items() if t not in all_defined}
    print(f"\nanchor_index entries: {len(anchor_index)} | "
          f"duplicate ids across exposés: {len(dup_ids)}")
    if dup_ids:
        print("  dups:", ", ".join(sorted(dup_ids)[:20]))
    print(f"distinct internal href targets: {len(all_refs)} | "
          f"dangling (unresolved): {len(dangling)}")
    if dangling:
        print("  dangling:", ", ".join(sorted(dangling)[:20]))
    if en_created:
        print(f"en placeholders created: {len(en_created)} "
              f"({', '.join(en_created)})")

    print(f"\n{'WROTE' if write else 'DRY RUN — no files written'}")


if __name__ == "__main__":
    main()
