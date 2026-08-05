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

GLOSSARY_DIR = ROOT / "glossary"
GLOSSARY_JSON = GLOSSARY_DIR / "glossary.json"
CANDIDATES_DIR = GLOSSARY_DIR / "candidates"
ISSUES_DIR = ROOT / "issues"

MATH_RE = re.compile(r"\\\(.*?\\\)|\\\[.*?\\\]", re.S)
ENV_RE = re.compile(r"\\begin\{([A-Za-z*]+)\}.*?\\end\{\1\}", re.S)
TAG_RE = re.compile(r"<[^>]+>")
THM_NAME_RE = re.compile(r'<span class="thm-name">([^<]+)</span>')


def norm_heading(name):
    """Normalize a thm-name span: strip math (a math-only name like the
    assertion «\\(A\\)» normalizes to empty and is skipped), leading and
    trailing numbering and punctuation (theorem kinds never start with a
    digit, so a leading «6.3.» is run-in section numbering), fold ALL-CAPS
    to title case."""
    name = MATH_RE.sub(" ", name)
    name = re.sub(r"[\s\d.:—–-]+$", "", name.strip())
    name = re.sub(r"^[\d.]+\s+", "", name)
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


def _word_plurals(word):
    """Regular English plural variants of one word (word included)."""
    variants = {word}
    if re.search(r"[a-z]y$", word) and word[-2] not in "aeiou":
        variants.add(word[:-1] + "ies")
    elif re.search(r"(?:s|x|z|ch|sh)$", word):
        variants.add(word + "es")
    elif word.endswith("f"):
        variants.add(word + "s")
        variants.add(word[:-1] + "ves")  # sheaves
    else:
        variants.add(word + "s")
    return variants


def _en_plurals(form):
    """Regular English plural variants of a (possibly multi-word) form.
    In a phrase the head word may carry the plural instead of the last
    ("equivalences of categories")."""
    words = form.split()
    variants = {" ".join(words[:-1] + [v]) for v in _word_plurals(words[-1])}
    if len(words) > 1:
        variants |= {" ".join([v] + words[1:]) for v in _word_plurals(words[0])}
    return variants


def _word_verb_forms(word):
    """Regular -ed/-ing inflections of one word (-s comes from plurals)."""
    if re.search(r"[a-z]y$", word) and word[-2] not in "aeiou":
        return {word[:-1] + "ied", word + "ing"}
    if word.endswith("e") and not word.endswith("ee"):
        return {word + "d", word[:-1] + "ing"}
    return {word + "ed", word + "ing"}


def _en_verb_forms(form):
    """Verb inflections of a form's first and last words; inflecting both
    ends covers "bound" → bounded and "upper bound" → upper bounded, and
    over-generation ("uppered") is harmless in a match-only pattern."""
    words = form.split()
    variants = {" ".join([v] + words[1:]) for v in _word_verb_forms(words[0])}
    if len(words) > 1:
        variants |= {" ".join(words[:-1] + [v])
                     for v in _word_verb_forms(words[-1])}
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


# Between the words of a multi-word rendering: up to two intervening prose
# tokens (coordination "inductive and projective limits", insertions "formal
# moduli scheme", "projective (resp. inductive) limits", appositions
# "covering, i.e. epimorphic, family", math "formal ¶ -adic scheme") and a
# hyphenated prefix on the following word ("reductive S-group scheme").
# No period may follow the head word, so the gap cannot start across a
# sentence boundary.
EN_GAP = r"[,;]?\s+(?:[\w'¶().,;-]+\s+){0,2}(?:[\w'¶]+-)?"


def en_pattern(entry):
    """Compile one regex matching any accepted English rendering (en +
    en_accept, expanded by regular plurals, hyphenation variants and — for
    pos "v" entries — verb inflections).
    Plain \\b boundaries (not the hyphen-aware FR ones): presence inside an
    EN hyphenated compound ("constant-twisted") counts as a match."""
    verb = entry.get("pos") == "v"
    variants = set()
    for base in [entry["en"]] + entry.get("en_accept", []):
        for sep in _en_separator_variants(base.lower()):
            variants |= _en_plurals(sep)
            if verb:
                variants |= _en_verb_forms(sep)
    alts = sorted((re.escape(v).replace(r"\ ", EN_GAP) for v in variants),
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
