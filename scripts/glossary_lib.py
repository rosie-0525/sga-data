#!/usr/bin/env python3
"""Shared helpers for the cross-book FR→EN terminology glossary tooling.

Used by glossary_extract.py (candidate mining), glossary_check.py
(cross-book consistency checker) and glossary_md.py (Markdown view).
Keeping the HTML/math normalizer and the inflection expanders here is what
guarantees the extractor and the checker can never disagree on what "the
prose text of a block" is.
"""
import html as html_mod
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ["sga1", "sga2", "sga3", "sga4", "sga4.5", "sga5", "sga6", "sga7"]
# Extraction corpus: books whose EN side is human-quality. sga4/sga4.5 are
# raw machine translation and must never seed the glossary.
GOOD_BOOKS = ["sga1", "sga2", "sga3", "sga5", "sga6", "sga7"]

GLOSSARY_DIR = ROOT / "glossary"
GLOSSARY_JSON = GLOSSARY_DIR / "glossary.json"
CANDIDATES_DIR = GLOSSARY_DIR / "candidates"
ISSUES_DIR = ROOT / "issues"

MATH_RE = re.compile(r"\\\(.*?\\\)|\\\[.*?\\\]", re.S)
ENV_RE = re.compile(r"\\begin\{([A-Za-z*]+)\}.*?\\end\{\1\}", re.S)
TAG_RE = re.compile(r"<[^>]+>")
THM_NAME_RE = re.compile(r'<span class="thm-name">([^<]+)</span>')


def norm_heading(name):
    """Normalize a thm-name span: strip trailing numbering/punctuation,
    fold ALL-CAPS to title case."""
    name = re.sub(r"[\s\d.:—–-]+$", "", name.strip())
    name = re.sub(r"\s+", " ", name)
    if name.isupper():
        name = name.capitalize()
    return name


def data_dir(book, lang):
    return ROOT / book / "data" / lang


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def strip_math(html):
    """Replace every math span with a hard separator so prose words can
    never fuse across a removed span and terms inside math never match."""
    html = MATH_RE.sub(" ¶ ", html)
    return ENV_RE.sub(" ¶ ", html)


def normalize(html, lower=True):
    """Block html → plain prose text for term matching.

    Order matters: math is removed on the raw html (so `i<j` inside math
    cannot eat text as a fake tag), then tags, then entities.
    """
    text = strip_math(html)
    text = TAG_RE.sub(" ", text)
    text = html_mod.unescape(text)
    text = text.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    text = text.replace("\u2019", "'").replace("\u0153", "oe").replace("\u0152", "Oe")
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower() if lower else text


# ---------------------------------------------------------------------------
# Inflection

# Hyphen-aware word boundaries: "simple" must not match inside "semi-simple",
# but "l'étale" must match "étale" (apostrophe is not a word char).
BOUND_L = r"(?<![\w-])"
BOUND_R = r"(?![\w-])"

# Regular French endings: -s, -x plurals, -e, -es feminines. Irregulars
# (nette, idéaux, …) are listed per entry in fr_forms.
FR_SUFFIX = r"(?:e?s|x|e)?"

# EN prefixes that may attach closed-up (semisimple) as well as hyphenated.
EN_CLOSE_PREFIXES = {"semi", "quasi", "non", "pseudo", "pre", "bi", "multi",
                     "sub", "ind", "pro", "co"}


def fr_pattern(entry):
    """Compile one regex matching every surface form of a glossary entry's
    French lemma (lemma + fr_forms, each word taking regular endings)."""
    alts = []
    for form in [entry["fr"]] + entry.get("fr_forms", []):
        words = form.lower().split()
        alts.append(r"\s+".join(re.escape(w) + FR_SUFFIX for w in words))
    alts.sort(key=len, reverse=True)
    return re.compile(BOUND_L + "(?:" + "|".join(alts) + ")" + BOUND_R)


def _en_plurals(form):
    """Regular English plural variants of a (possibly multi-word) form."""
    words = form.split()
    last = words[-1]
    variants = {form}
    if re.search(r"[a-z]y$", last) and last[-2] not in "aeiou":
        variants.add(" ".join(words[:-1] + [last[:-1] + "ies"]))
    elif re.search(r"(?:s|x|z|ch|sh)$", last):
        variants.add(form + "es")
    elif last.endswith("f"):
        variants.add(form + "s")
        variants.add(" ".join(words[:-1] + [last[:-1] + "ves"]))  # sheaves
    else:
        variants.add(form + "s")
    return variants


def _en_separator_variants(form):
    """semi-simple ⇄ semi simple ⇄ semisimple (closed form only for known
    prefixes); spaced forms also accept the hyphenated spelling."""
    variants = {form}
    if "-" in form:
        variants.add(form.replace("-", " "))
        head = form.split("-", 1)[0]
        if head in EN_CLOSE_PREFIXES:
            variants.add(form.replace("-", "", 1))
    elif " " in form:
        variants.add(form.replace(" ", "-"))
    return variants


def en_pattern(entry):
    """Compile one regex matching any accepted English rendering (en +
    en_accept, expanded by regular plurals and hyphenation variants).
    Plain \\b boundaries (not the hyphen-aware FR ones): presence inside an
    EN hyphenated compound ("constant-twisted") counts as a match."""
    variants = set()
    for base in [entry["en"]] + entry.get("en_accept", []):
        for sep in _en_separator_variants(base.lower()):
            variants |= _en_plurals(sep)
    alts = sorted((re.escape(v).replace(r"\ ", r"\s+") for v in variants),
                  key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(alts) + r")\b")


def sort_key_fr(term):
    """Accent-insensitive alphabetical sort key."""
    folded = unicodedata.normalize("NFKD", term.lower())
    return "".join(c for c in folded if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Corpus iteration

def load_manifest(book):
    return load_json(data_dir(book, "fr") / "manifest.json")


def chapter_ids(book):
    return [c["id"] for c in load_manifest(book)["chapters"]]


def load_chapter(book, lang, chapter_id):
    path = data_dir(book, lang) / "chapters" / f"{chapter_id}.json"
    return load_json(path) if path.exists() else None


def iter_aligned_blocks(book):
    """Yield (chapter_id, page_id, block_index, fr_block, en_block) for every
    aligned block pair. en_block is None when the EN chapter/page/block is
    missing (untranslated chapters)."""
    for cid in chapter_ids(book):
        fr = load_chapter(book, "fr", cid)
        en = load_chapter(book, "en", cid)
        if fr is None:
            continue
        en_pages = en.get("pages", []) if en else []
        for p_idx, fr_page in enumerate(fr.get("pages", [])):
            en_page = en_pages[p_idx] if p_idx < len(en_pages) else {}
            en_blocks = en_page.get("blocks", [])
            for b_idx, fr_block in enumerate(fr_page.get("blocks", [])):
                en_block = en_blocks[b_idx] if b_idx < len(en_blocks) else None
                yield cid, fr_page.get("id"), b_idx, fr_block, en_block


def iter_aligned_footnotes(book):
    """Yield (chapter_id, page_id, fn_index, fr_fn, en_fn) where the fr/en
    footnote lists have equal length; yield a ("skip", page_id, n_fr, n_en)
    marker otherwise (alignment there is conventional, not schema-backed)."""
    for cid in chapter_ids(book):
        fr = load_chapter(book, "fr", cid)
        en = load_chapter(book, "en", cid)
        if fr is None:
            continue
        en_pages = en.get("pages", []) if en else []
        for p_idx, fr_page in enumerate(fr.get("pages", [])):
            fr_fns = fr_page.get("footnotes") or []
            if not fr_fns:
                continue
            en_page = en_pages[p_idx] if p_idx < len(en_pages) else {}
            en_fns = en_page.get("footnotes") or []
            if len(fr_fns) != len(en_fns):
                yield "skip", fr_page.get("id"), len(fr_fns), len(en_fns)
                continue
            for f_idx, (fr_fn, en_fn) in enumerate(zip(fr_fns, en_fns)):
                yield cid, fr_page.get("id"), f_idx, fr_fn, en_fn


def cite(book, page_id, block, block_index):
    """Citation string: book:anchorId when the block has an id (only ~12% of
    blocks do), book:pageId#blockIndex otherwise."""
    if block and block.get("id"):
        return f"{book}:{block['id']}"
    return f"{book}:{page_id}#{block_index}"


# ---------------------------------------------------------------------------
# Glossary

def load_glossary(path=GLOSSARY_JSON):
    """Load and validate glossary.json; returns the entry list."""
    data = load_json(path)
    entries = data["entries"]
    seen = set()
    for e in entries:
        for field in ("fr", "en", "category"):
            if not e.get(field):
                raise ValueError(f"glossary entry missing '{field}': {e}")
        if e["category"] not in ("term", "heading"):
            raise ValueError(f"bad category in entry: {e}")
        key = (e["fr"].lower(), e["category"])
        if key in seen:
            raise ValueError(f"duplicate glossary entry: {key}")
        seen.add(key)
    return entries
