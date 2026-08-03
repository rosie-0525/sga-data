#!/usr/bin/env python3
"""Retype sga5/6/7 statement and proof blocks into the corpus's canonical shape.

The sga5/6/7 transcriptions left most theorem-like statements and every proof
as plain `<p><u>Definition 4.4.</u> ...` / `<p><em>Proof.</em> ...` paragraphs,
and the blocks they did type carry non-conforming class strings (`thm
proposition` without a `thm-plain`/`thm-remark` modifier, sga6's CSS-less
`thm-definition`, sga5's legacy `div.theorem` shells). The viewer styles blocks
from the html alone, so all of these render as ordinary prose.

Three phases, run in order per book:

  normalize   1:1 rewrite of blocks that already have a theorem shell — adds
              the correct modifier class, rebuilds the head as
              thm-name/thm-num spans, moves statement text stranded in a head
              into the body, strips <u> used as an italic stand-in, converts
              sga5 legacy shells, and normalises type/label/title metadata.
  retype      1:1 conversion of paragraph-encoded statements (single block)
              and proofs. A proof reaching over following blocks becomes a
              `proof proof-part ...` chain (block count unchanged).
  merge       the only index-shifting phase: statements whose body continues
              through display-math siblings are spliced into one thm block,
              at identical indices in fr and en.

Detection runs on the ENGLISH text (the French files contain leaked English
heads) and the decision is mirrored to French by block index; the French head
is re-parsed only to build the French head text. Anything ambiguous — soft
proof extents, one-sided matches, unparseable heads, unknown keywords — lands
in issues/retype_worklist.json instead of being guessed; hand decisions go in
issues/retype_overrides.json keyed by a fingerprint of the en html and are
refused when stale.

Every guard is a refusal. Body text must survive byte-identically (after
whitespace collapse); only the parsed head span may change, and only to the
table-derived form. Writes go through proposals_lib.write_chapter and are
followed by check_alignment on both languages.

Usage:
  retype_statement_blocks.py --book sga6 [--chapter III] [--phase all] [--write]
                             [--overrides issues/retype_overrides.json]
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from glossary_lib import ROOT, chapter_ids, load_chapter
from proposals_lib import chapter_path, check_alignment, root_count, write_chapter
from repair_anchor_index import ID_RE

LANGS = ("fr", "en")
WORKLIST_PATH = ROOT / "issues" / "retype_worklist.json"

# ---------------------------------------------------------------------------
# Kind table
#
# css: thm-plain for asserted mathematics (the CSS supplies the italic body),
# thm-remark for commentary — the split every LaTeX-derived book uses.
# type: the canonical French environment name, as in sga1-3.

KINDS = {
    "theoreme":     ("thm-plain",  {"en": "Theorem",     "fr": "Théorème"}),
    "proposition":  ("thm-plain",  {"en": "Proposition", "fr": "Proposition"}),
    "lemme":        ("thm-plain",  {"en": "Lemma",       "fr": "Lemme"}),
    "corollaire":   ("thm-plain",  {"en": "Corollary",   "fr": "Corollaire"}),
    "conjecture":   ("thm-plain",  {"en": "Conjecture",  "fr": "Conjecture"}),
    "assertion":    ("thm-plain",  {"en": "Assertion",   "fr": "Assertion"}),
    "hypothese":    ("thm-plain",  {"en": "Hypothesis",  "fr": "Hypothèse"}),
    "variante":     ("thm-plain",  {"en": "Variant",     "fr": "Variante"}),
    "complement":   ("thm-plain",  {"en": "Complement",  "fr": "Complément"}),
    "definition":   ("thm-remark", {"en": "Definition",  "fr": "Définition"}),
    "remarque":     ("thm-remark", {"en": "Remark",      "fr": "Remarque"}),
    "exemple":      ("thm-remark", {"en": "Example",     "fr": "Exemple"}),
    "exercice":     ("thm-remark", {"en": "Exercise",    "fr": "Exercice"}),
    "scholie":      ("thm-remark", {"en": "Scholium",    "fr": "Scholie"}),
    "notation":     ("thm-remark", {"en": "Notation",    "fr": "Notation"}),
    "convention":   ("thm-remark", {"en": "Convention",  "fr": "Convention"}),
    "construction": ("thm-remark", {"en": "Construction", "fr": "Construction"}),
    "probleme":     ("thm-remark", {"en": "Problem",     "fr": "Problème"}),
    "question":     ("thm-remark", {"en": "Question",    "fr": "Question"}),
    "rappel":       ("thm-remark", {"en": "Recall",      "fr": "Rappel"}),
}

# keyword (lowercased, accents kept) -> (kind, plural?)
KEYWORDS = {
    "en": {
        "theorem": ("theoreme", False), "theorems": ("theoreme", True),
        "proposition": ("proposition", False), "propositions": ("proposition", True),
        "lemma": ("lemme", False), "lemmas": ("lemme", True), "lemmata": ("lemme", True),
        "corollary": ("corollaire", False), "corollaries": ("corollaire", True),
        "conjecture": ("conjecture", False),
        "variant": ("variante", False), "variants": ("variante", True),
        "complement": ("complement", False),
        "definition": ("definition", False), "definitions": ("definition", True),
        "remark": ("remarque", False), "remarks": ("remarque", True),
        "example": ("exemple", False), "examples": ("exemple", True),
        "exercise": ("exercice", False), "exercises": ("exercice", True),
        "scholium": ("scholie", False),
        "notation": ("notation", False), "notations": ("notation", True),
        "convention": ("convention", False), "conventions": ("convention", True),
        "construction": ("construction", False),
        "problem": ("probleme", False), "problems": ("probleme", True),
        "question": ("question", False), "questions": ("question", True),
    },
    "fr": {
        "théorème": ("theoreme", False), "théorèmes": ("theoreme", True),
        "proposition": ("proposition", False), "propositions": ("proposition", True),
        "lemme": ("lemme", False), "lemmes": ("lemme", True),
        "corollaire": ("corollaire", False), "corollaires": ("corollaire", True),
        "conjecture": ("conjecture", False),
        "variante": ("variante", False), "variantes": ("variante", True),
        "complément": ("complement", False),
        "définition": ("definition", False), "définitions": ("definition", True),
        "remarque": ("remarque", False), "remarques": ("remarque", True),
        "exemple": ("exemple", False), "exemples": ("exemple", True),
        "exercice": ("exercice", False), "exercices": ("exercice", True),
        "scholie": ("scholie", False),
        "notation": ("notation", False), "notations": ("notation", True),
        "convention": ("convention", False), "conventions": ("convention", True),
        "construction": ("construction", False),
        "problème": ("probleme", False), "problèmes": ("probleme", True),
        "question": ("question", False), "questions": ("question", True),
        "rappel": ("rappel", False), "rappels": ("rappel", True),
    },
}
PLURALS = {
    "theoreme": {"en": "Theorems", "fr": "Théorèmes"},
    "proposition": {"en": "Propositions", "fr": "Propositions"},
    "lemme": {"en": "Lemmas", "fr": "Lemmes"},
    "corollaire": {"en": "Corollaries", "fr": "Corollaires"},
    "definition": {"en": "Definitions", "fr": "Définitions"},
    "remarque": {"en": "Remarks", "fr": "Remarques"},
    "exemple": {"en": "Examples", "fr": "Exemples"},
    "exercice": {"en": "Exercises", "fr": "Exercices"},
    "notation": {"en": "Notations", "fr": "Notations"},
    "variante": {"en": "Variants", "fr": "Variantes"},
    "convention": {"en": "Conventions", "fr": "Conventions"},
    "probleme": {"en": "Problems", "fr": "Problèmes"},
    "question": {"en": "Questions", "fr": "Questions"},
    "rappel": {"en": "Recalls", "fr": "Rappels"},
}

# The per-kind classes other books put on the root div, mapped to kinds — used
# both to read existing shells and to emit the canonical class string.
KIND_CLASSES = {
    "theoreme": "theoreme", "theorem": "theoreme",
    "proposition": "proposition",
    "lemme": "lemme", "lemma": "lemme",
    "corollaire": "corollaire", "corollary": "corollaire",
    "definition": "definition",
    "remarque": "remarque", "remark": "remarque", "remarques": "remarque",
    "exemple": "exemple", "example": "exemple",
    "exercice": "exercice", "exercise": "exercice",
    "scholie": "scholie", "scholium": "scholie",
    "conjecture": "conjecture", "variante": "variante", "variant": "variante",
    "complement": "complement", "notation": "notation",
    "construction": "construction", "convention": "convention",
    "probleme": "probleme", "problem": "probleme", "question": "question",
    "assertion": "assertion", "hypothese": "hypothese", "hypothesis": "hypothese",
    "thm-definition": "definition", "thm-corollary": "corollaire",
    "thm-example": "exemple", "thm-exercise": "exercice", "thm-note": "remarque",
}

PROOF_RE = {
    "en": re.compile(
        r"\A(?:(?:sketch|outline|principle|plan|end|beginning)\s+of\s+(?:the\s+)?)?"
        r"proof(?P<obj>\s+(?:of|in|for)\s+.{1,70}?)?\s*[.:]?\s*\Z",
        re.I | re.S),
    "fr": re.compile(
        r"\A(?:(?:esquisse|principe|plan|fin|début)\s+de\s+(?:la\s+)?)?"
        r"(?:démonstration|demonstration|preuve)"
        r"(?P<obj>\s+(?:de|du|des|dans)\s+.{1,70}?)?\s*[.:]?\s*\Z",
        re.I | re.S),
}
PROOF_NAME = {"en": "Proof", "fr": None}  # fr filled per book from dominant usage

WRAPPERS = [  # (open, close) — longest first
    ("<strong><u>", "</u></strong>"),
    ("<em><u>", "</u></em>"),
    ("<strong>", "</strong>"),
    ("<em>", "</em>"),
    ("<u>", "</u>"),
    ("<b>", "</b>"),
]

NUM_RE = re.compile(r"\A(\d+(?:\.\d+)*(?:\s*(?:bis|ter))?(?:\\\([^()\\]{1,12}\\\))?)\s*\Z")
ENUM_RE = re.compile(r"\A(?:[ivxlcdm]{1,6}|[a-hj-z]|[A-H]|\d{1,2})(?:\s+bis)?\Z")
P_OPEN_RE = re.compile(r"\A<p(?P<attrs>(?:\s+[a-z-]+=\"[^\"]*\")*)\s*>", re.S)
MATH_P_RE = re.compile(r"\A<p[^>]*>\s*(?P<m>\\\[.*\\\])\s*</p>\s*\Z", re.S)
MATH_DIV_RE = re.compile(
    r"\A<div class=\"display-formula\"[^>]*>\s*(?P<m>\\\[.*\\\])\s*</div>\s*\Z", re.S)
TAG_RE = re.compile(r"<[^>]+>")


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fingerprint(html):
    return hashlib.sha1((html or "").encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Visible text (the conservation guard's currency)

class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def visible_text(html):
    p = _Text()
    p.feed(html or "")
    p.close()
    return re.sub(r"\s+", " ", "".join(p.parts)).strip()


def ends_sentence(text):
    """Does a block's visible text read as complete? A colon means the next
    block (a formula) belongs to this one, so it counts as unfinished."""
    t = text.rstrip()
    if not t:
        return True
    if re.search(r"[:;,]\s*\Z", t):
        return False
    if re.search(r"[.!?)\]»…]\s*\Z", t) or t.endswith("—"):
        return True
    return False


# ---------------------------------------------------------------------------
# Head parsing

class Head:
    def __init__(self, family, kind, plural, phrase, num, punct, attribution,
                 consumed, body_html, prefix, foreign=False):
        self.foreign = foreign
        self.family = family          # "statement" | "proof"
        self.kind = kind              # KINDS key (statement) or None (proof)
        self.plural = plural
        self.phrase = phrase          # verbatim wrapper text (proof-name source)
        self.num = num                # number token or None
        self.punct = punct
        self.attribution = attribution  # "(…)" kept in the head, or None
        self.consumed = consumed      # html span replaced by the new head
        self.body_html = body_html    # paragraph interior after the head
        self.prefix = prefix          # display-name prefix ("Monodromy" etc.)


def _match_wrapper(rest):
    for op, cl in WRAPPERS:
        if rest.startswith(op):
            end = rest.find(cl)
            if end < 0:
                return None
            inner = rest[len(op):end]
            if "<" in re.sub(r"\\\(.*?\\\)", "", inner):
                return None  # tags inside the head marker: not a head
            return op, cl, inner, end + len(cl)
    return None


def _parse_head_text(inner, lang):
    """(kind, plural, prefix, num, punct, foreign) or None, from the
    wrapper's text. `foreign`: keyword came from the other language's table
    (a leaked head — the emitted display name fixes it)."""
    text = re.sub(r"\s+", " ", inner).strip()
    m = re.match(
        r"\A(?P<words>[^\d\\]{2,60}?)\s*"
        r"(?P<num>\d+(?:\.\d+)*(?:\s*(?:bis|ter))?(?:\\\([^()\\]{1,12}\\\))?)?"
        r"\s*(?P<punct>[.:]|[–—-])?\s*\Z", text, re.S)
    if not m or not m["words"]:
        return None
    words = m["words"].strip().rstrip(".:").split()
    kw = words[-1].lower()
    hit, foreign = KEYWORDS[lang].get(kw), False
    if not hit:
        hit = KEYWORDS["en" if lang == "fr" else "fr"].get(kw)
        foreign = hit is not None
    if not hit:
        return None
    kind, plural = hit
    prefix = " ".join(words[:-1])
    if prefix and not re.match(r"\A[\w'’ .-]{1,40}\Z", prefix):
        return None
    return kind, plural, prefix, m["num"], m["punct"], foreign


def _take_attribution(body, family):
    """Split a leading '(…)' off the body when it reads as an attribution.
    Returns (attribution or None, rest, ambiguous?)."""
    if not body.startswith("("):
        return None, body, False
    depth, i, n = 0, 0, len(body)
    while i < n:
        c = body[i]
        if c == "\\" and i + 1 < n and body[i + 1] in "([":
            close = "\\)" if body[i + 1] == "(" else "\\]"
            j = body.find(close, i + 2)
            i = (j + 2) if j >= 0 else (i + 2)
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    if i >= n:
        return None, body, False
    paren, rest = body[:i + 1], body[i + 1:].lstrip(" ")
    content = visible_text(paren)[1:-1].strip()
    if family == "proof":
        return None, body, False           # for proofs the paren is content
    if ENUM_RE.match(content) or not rest.strip():
        return None, body, False           # enumerator, or the paren IS the body
    if re.match(r"\A(?:cf\b|Cf\b|d'après|following|voir|see\b|loc\.|\[|∗|\*)",
                content) or re.search(r"\bcf\.", content):
        rest = re.sub(r"\A[.:]\s*", "", rest)
        return paren, rest, False
    return None, body, True                # unclear: caller sends to worklist


def parse_head(html, lang):
    """Parse a paragraph block's html into a Head, or (None, reason)."""
    m = P_OPEN_RE.match(html or "")
    if not m:
        return None, "root-not-p"
    rest = html[m.end():]
    lead = re.match(r"\A\s*(?:<a[^>]*>\s*</a>\s*)?", rest)
    rest = rest[lead.end():]
    w = _match_wrapper(rest)
    if not w:
        return None, "no-wrapper"
    op, cl, inner, wlen = w
    after = rest[wlen:]
    if not after.rstrip().endswith("</p>"):
        return None, "unterminated"
    body = after.rstrip()[:-4]
    sep = re.match(r"\A\s*(?:[.:]\s*)?(?:[–—-]\s*)?", body)
    sep_str, body = body[:sep.end()], body[sep.end():]

    text = re.sub(r"\s+", " ", inner).strip()
    pm = PROOF_RE[lang].match(text) or (
        PROOF_RE["en" if lang == "fr" else "fr"].match(text))
    if pm:
        phrase = text.rstrip(" .:")
        attribution, body2, amb = _take_attribution(body, "proof")
        return Head("proof", None, False, phrase, None, None, attribution,
                    html[m.end():m.end() + lead.end() + wlen + sep.end()],
                    body2, None), None

    parsed = _parse_head_text(inner, lang)
    if not parsed:
        return None, "unknown-keyword"
    kind, plural, prefix, num, punct, foreign = parsed
    attribution, body, amb = _take_attribution(body, "statement")
    if amb:
        return None, "ambiguous-attribution"
    return Head("statement", kind, plural, text, num, punct, attribution,
                html[m.end():m.end() + lead.end() + wlen + sep.end()],
                body, prefix, foreign), None


# ---------------------------------------------------------------------------
# Canonical builders

def display_name(kind, plural, lang, prefix=""):
    name = (PLURALS.get(kind, {}).get(lang) if plural else None) \
        or KINDS[kind][1][lang]
    return f"{prefix} {name}".strip() if prefix else name


def canonical_num(num):
    if not num:
        return None
    n = re.sub(r"\s+", " ", num).strip()
    return n if n.endswith(".") else n + "."


def build_thm(kind, head_html, body_html, root_id):
    css = KINDS[kind][0]
    idattr = f' id="{root_id}"' if root_id else ""
    return (f'<div class="thm {css} {kind}"{idattr}>\n'
            f'  <div class="thm-head">{head_html}</div>\n'
            f'  <div class="thm-body">{body_html}</div>\n'
            f'</div>')


def thm_head_html(name, num, attribution):
    parts = [f'<span class="thm-name">{name}</span>']
    if num:
        parts.append(f'<span class="thm-num">{num}</span>')
    if attribution:
        parts.append(attribution)
    return " ".join(parts)


def build_proof(name, body_html, root_id, part=None, group=None):
    """part: None (standalone) | 'first' | 'cont' | 'last'."""
    if part in (None, "first"):
        cls = "proof" if part is None else "proof proof-part proof-first"
        idattr = f' id="{root_id}"' if root_id else ""
        grp = f' data-proof-group="{group}"' if part == "first" else ""
        head = (f'<div class="proof-head"><span class="proof-name">{name}</span>'
                f'<span class="proof-toggle">▾</span></div>')
        return (f'<div class="{cls}"{idattr}{grp}>\n'
                f'  {head}\n'
                f'  <div class="proof-body">{body_html}</div>\n'
                f'</div>')
    cls = "proof proof-part proof-cont" + (" proof-last" if part == "last" else "")
    return (f'<div class="{cls}" data-proof-group="{group}">\n'
            f'  <div class="proof-body">{body_html}</div>\n'
            f'</div>')


def metadata(kind, num, name):
    return {"type": kind, "label": canonical_num(num), "title": name}


# ---------------------------------------------------------------------------
# Block classification helpers

def block_root(html):
    m = re.match(r"\A<(?P<tag>[a-z0-9]+)(?P<attrs>[^>]*)>", html or "")
    if not m:
        return None, ""
    cm = re.search(r'class="([^"]*)"', m["attrs"])
    return m["tag"], (cm.group(1) if cm else "")


def math_content(html):
    m = MATH_P_RE.match(html or "") or MATH_DIV_RE.match(html or "")
    return m["m"] if m else None


def is_pure_math(block):
    return math_content(block.get("html")) is not None


def is_hard_boundary(block, lang):
    if block is None:
        return True
    tag, cls = block_root(block.get("html") or "")
    if tag != "p":
        return True  # heading, table, list, typed div, display-formula …
    head, _ = parse_head(block["html"], lang)
    return head is not None


def starts_like_continuation(block):
    text = visible_text(block.get("html") or "")
    return bool(re.match(r"\A(?:[a-zàâçéèêëîïôùûü(«\[]|\\\()", text))


def starts_with_enum(block):
    text = visible_text(block.get("html") or "")
    return bool(re.match(r"\A\(?[a-z0-9]{1,4}\)|\A\([ivx]+ ?(?:bis)?\)", text))


# ---------------------------------------------------------------------------
# Extent detection

MAX_CHAIN = 60


def detect_extent(blocks, i, head, lang):
    """[(index, role)] for the blocks a statement/proof reaches over, plus a
    confidence flag. role: 'head' | 'math' | 'prose'.

    A proof runs to the next hard boundary (the following statement, heading
    or other non-prose block): sampling every case where conservative rules
    stopped earlier showed the following prose always still belonged to the
    proof. A statement, by contrast, extends only over display math it needs
    mid-sentence and over its own enumerated items — statements are short and
    over-absorbing them would swallow the surrounding prose."""
    chain = [(i, "head")]
    tail_text = visible_text(head.body_html)
    j = i
    while len(chain) < MAX_CHAIN:
        nxt = blocks[j + 1] if j + 1 < len(blocks) else None
        if nxt is None or (not is_pure_math(nxt) and is_hard_boundary(nxt, lang)):
            return chain, False
        if head.family == "proof":
            take = True
        elif is_pure_math(nxt):
            take = not ends_sentence(tail_text)
        else:
            take = (not ends_sentence(tail_text)) or (
                starts_with_enum(nxt)
                and (any(r == "prose" for _, r in chain[1:])
                     or re.match(r"\A[a-z]\)", visible_text(head.body_html))))
        if not take:
            return chain, False
        chain.append((j + 1, "math" if is_pure_math(nxt) else "prose"))
        tail_text = visible_text(math_content(nxt["html"])
                                 if is_pure_math(nxt) else nxt["html"])
        j += 1
    return chain, True  # ran past the cap — needs a human extent


# ---------------------------------------------------------------------------
# Phase: retype / merge planning

class Entry:
    """One planned action at one block index, mirrored across languages."""

    def __init__(self, action, index, chain=None, head=None, reason=None):
        self.action = action  # retype-thm | retype-proof | merge | worklist
        self.index = index
        self.chain = chain or [(index, "head")]
        self.head = head      # en Head
        self.reason = reason


def plan_page(book, page_en, page_fr, overrides, proof_counter):
    entries, work = [], []
    blocks_en, blocks_fr = page_en["blocks"], page_fr["blocks"]
    taken = set()
    for i, ben in enumerate(blocks_en):
        if i in taken or (ben.get("type") not in (None, "paragraph")):
            continue
        tag, _cls = block_root(ben.get("html") or "")
        if tag != "p":
            continue
        ov = overrides.get(i)
        head, reason = parse_head(ben["html"], "en")
        if ov and ov.get("action") == "skip":
            continue
        if head is None:
            if reason in ("ambiguous-attribution", "unknown-keyword"):
                text = visible_text(ben["html"])
                if reason == "ambiguous-attribution" or re.match(
                        r"\A[A-ZÀ-Þ][\w'’ -]{2,40}[.:]", text) and _looks_heady(ben):
                    work.append((i, reason, text[:120]))
            continue
        fhead, freason = parse_head(blocks_fr[i]["html"], "fr") \
            if i < len(blocks_fr) else (None, "fr-missing")
        if fhead is None:
            work.append((i, f"fr-unparsed:{freason}",
                         visible_text(blocks_fr[i]["html"])[:120]
                         if i < len(blocks_fr) else ""))
            continue
        if fhead.family != head.family or (
                head.family == "statement" and fhead.kind != head.kind
                and fhead.kind is not None):
            work.append((i, "en-fr-family-mismatch",
                         f"en={head.family}/{head.kind} fr={fhead.family}/{fhead.kind}"))
            continue
        chain, soft = detect_extent(blocks_en, i, head, "en")
        if ov and "extent" in ov:
            chain = [(i, "head")] + [(k, _chain_role(blocks_en[k]))
                                     for k in range(i + 1, i + ov["extent"])]
            soft = False
        if soft:
            follow = []
            for k in range(chain[-1][0] + 1, min(chain[-1][0] + 9, len(blocks_en))):
                if is_hard_boundary(blocks_en[k], "en"):
                    follow.append(f"[{k}]=BOUNDARY")
                    break
                follow.append(f"[{k}] {visible_text(blocks_en[k]['html'])[:70]}")
            work.append((i, "extent-soft",
                         f"chain={len(chain)} "
                         f"tail=…{visible_text(blocks_en[chain[-1][0]]['html'])[-80:]!r} "
                         "| " + " | ".join(follow)))
            continue
        if head.family == "statement" and head.kind is None:
            continue
        action = ("retype-proof" if head.family == "proof"
                  else ("retype-thm" if len(chain) == 1 else "merge"))
        entries.append(Entry(action, i, chain, head))
        taken.update(k for k, _ in chain)
    # heads only the French side carries (EN-driven detection misses them)
    for i, bfr in enumerate(blocks_fr):
        if i in taken or bfr.get("type") not in (None, "paragraph"):
            continue
        if any(w[0] == i for w in work):
            continue
        fhead, _ = parse_head(bfr.get("html") or "", "fr")
        if fhead is not None:
            work.append((i, "fr-only-head",
                         visible_text(bfr["html"])[:120]))
    return entries, work


def _looks_heady(block):
    """Wrapped head-like text we could not classify — worth a worklist row."""
    m = P_OPEN_RE.match(block.get("html") or "")
    if not m:
        return False
    rest = block["html"][m.end():]
    return _match_wrapper(rest.lstrip()) is not None


def _chain_role(block):
    return "math" if is_pure_math(block) else "prose"


# ---------------------------------------------------------------------------
# Building the rewritten records

def strip_full_u(body):
    """Remove <u> wrappers that span an entire paragraph (sga7's italic
    stand-in); keep every other <u> (defined-term emphasis)."""
    out = re.sub(r"<p([^>]*)>\s*<u>((?:(?!</?u>).)*)</u>\s*</p>",
                 r"<p\1>\2</p>", body, flags=re.S)
    if out.startswith("<u>") and out.rstrip().endswith("</u>") \
            and "<u>" not in out[3:] and out.count("</u>") == 1:
        out = out[3:].rstrip()[:-4]
    return out


def rec_ids(html):
    return ID_RE.findall(html or "")


def root_own_id(block):
    """The id to carry on the rewritten root: the block-level id field, or an
    id attribute on the root element itself — never an interior anchor's."""
    if block.get("id"):
        return block["id"]
    m = re.match(r"\A<[a-z0-9]+[^>]*?\bid=\"([^\"]+)\"", block.get("html") or "")
    return m.group(1) if m else None


def retype_records(entry, blocks, lang, page_id, fr_proof_name, minted):
    """New records for one Entry in one language. Returns (records, notes)."""
    i = entry.index
    src = blocks[i]
    head, _ = parse_head(src["html"], lang)
    if head is None:  # mirrored write: en drove, fr must have parsed in plan
        raise ValueError(f"{lang} head unparseable at {page_id}#{i}")
    root_id = root_own_id(src)
    notes = []

    if entry.head.family == "proof":
        name = head.phrase
        base = PROOF_RE[lang].match(re.sub(r"\s+", " ", name))
        if base is None:  # leaked English head in fr: rebuild from table
            name = fr_proof_name if lang == "fr" else PROOF_NAME["en"]
            notes.append(f"{lang} head {head.phrase!r} -> {name!r}")
        if not root_id:
            root_id = minted
        group = root_id
        pieces = []
        chain = entry.chain
        for n, (k, role) in enumerate(chain):
            if n == 0:
                body = strip_full_u(head.body_html)
                body = f"<p>{body}</p>"
                part = None if len(chain) == 1 else "first"
                pieces.append((k, build_proof(name, body, root_id, part, group)))
            else:
                # continuation piece: the original block html goes inside
                # proof-body verbatim, so its anchors and shape survive
                inner = blocks[k]["html"].rstrip()
                part = "last" if n == len(chain) - 1 else "cont"
                pieces.append((k, build_proof(name, inner, None, part, group)))
        recs = []
        for n, (k, html) in enumerate(pieces):
            old = blocks[k]
            rec = {"id": (root_id if n == 0 else old.get("id")),
                   "type": "proof", "label": None,
                   "title": name if n == 0 else None, "html": html}
            recs.append((k, rec))
        return recs, notes

    # statement
    kind = entry.head.kind
    name = display_name(kind, head.plural if head.kind else entry.head.plural,
                        lang, head.prefix or "")
    if head.foreign or head.kind != kind:
        notes.append(f"{lang} head {head.phrase!r} -> {name!r}")
    num = canonical_num(head.num or entry.head.num)
    attribution = head.attribution
    if not root_id and num:
        root_id = minted
    body = strip_full_u(head.body_html)
    parts = [f"<p>{body}</p>"]
    for k, role in entry.chain[1:]:
        blk = blocks[k]
        inner = math_content(blk["html"])
        if inner is not None:
            prev = parts[-1]
            parts[-1] = prev[:-4].rstrip() + " " + inner + "</p>"
        else:
            parts.append(strip_full_u(blk["html"].rstrip()))
    body_html = "\n  ".join(parts)
    html = build_thm(kind, thm_head_html(name, num, attribution), body_html, root_id)
    rec = dict(metadata(kind, num, name), id=root_id or None, html=html)
    return [(entry.index, rec)], notes


# ---------------------------------------------------------------------------
# Phase: normalize

THM_SHELL_RE = re.compile(
    r'\A<div class="(?P<cls>[^"]*)"(?P<attrs>[^>]*)>\s*'
    r'<div class="thm-head">(?P<head>.*?)</div>\s*'
    r'<div class="thm-body">(?P<body>.*)</div>\s*</div>\s*\Z', re.S)
HEADLESS_SHELL_RE = re.compile(
    r'\A<div class="(?P<cls>[^"]*)"(?P<attrs>[^>]*)>\s*'
    r'<div class="thm-body">(?P<body>.*)</div>\s*</div>\s*\Z', re.S)
LEGACY_SHELL_RE = re.compile(
    r'\A<div class="(?P<cls>theorem|lemma|corollary|proposition)"(?P<attrs>[^>]*)>'
    r'\s*(?P<inner>.*)</div>\s*\Z', re.S)
TITLE_SPAN_RE = re.compile(
    r'\A\s*<p[^>]*>\s*<span class="(?:theorem-title|thm-num)">'
    r'(?P<t>[^<]*)</span>\s*(?P<rest>.*)\Z', re.S)


def kind_from_classes(classes):
    plain = [c for c in classes
             if not c.startswith("thm") and c in KIND_CLASSES]
    if plain:
        return KIND_CLASSES[plain[0]]
    for c in classes:
        if c in KIND_CLASSES:  # thm-definition and friends
            return KIND_CLASSES[c]
    return None


NUMTOK_RE = re.compile(r"\A\d+(?:\.\d+)*(?:\\\([^()\\]{1,12}\\\))?[.:]?\Z")


def parse_shell_head(head_html, lang):
    """(kind, plural, prefix, num, attribution, leftover) from an existing
    thm-head's content, or None. Token-based: the first keyword within the
    first few words wins, an immediately following number token is the
    label, a balanced '(…)' is the attribution, and anything else is
    leftover (statement text stranded in the head)."""
    text = visible_text(head_html)
    toks = text.split()
    other = "en" if lang == "fr" else "fr"
    for wi in range(0, min(4, len(toks))):
        cand = toks[wi].lower().strip(".:")
        hit = KEYWORDS[lang].get(cand) or KEYWORDS[other].get(cand)
        if not hit:
            continue
        kind, plural = hit
        prefix = " ".join(toks[:wi])
        rest = toks[wi + 1:]
        num = None
        if rest and NUMTOK_RE.match(rest[0]):
            num = rest[0].rstrip(".:")
            rest = rest[1:]
        tail = " ".join(rest).strip()
        attribution = None
        if tail.startswith("("):
            depth = 0
            for j, ch in enumerate(tail):
                depth += ch == "("
                depth -= ch == ")"
                if depth == 0:
                    break
            attribution, tail = tail[:j + 1], tail[j + 1:].strip(" .:")
        return kind, plural, prefix, num, attribution, tail
    return None


def normalize_block(block, lang, book):
    """Canonical (record, notes) for an existing theorem shell, or (None, reason)."""
    html = block.get("html") or ""
    tag, cls = block_root(html)
    classes = cls.split()
    if tag != "div" or ("thm" not in classes and not LEGACY_SHELL_RE.match(html)):
        return None, "not-a-shell"

    if "thm" not in classes:  # sga5 legacy div.theorem
        m = LEGACY_SHELL_RE.match(html)
        tm = TITLE_SPAN_RE.match(m["inner"])
        if not tm:
            return None, "legacy-no-title"
        parsed = _legacy_title(tm["t"], lang)
        if not parsed:
            return None, "legacy-title-unparsed"
        kind, plural, prefix, num, attribution = parsed
        body_first = tm["rest"]
        if not body_first.rstrip().endswith("</div>"):
            return None, "legacy-shape"
        inner_rest = body_first.rstrip()
        # tm['rest'] runs to the legacy shell's end; first paragraph is open
        body = "<p>" + inner_rest
        body = re.sub(r"</div>\s*\Z", "", body).rstrip()
        if not body.endswith("</p>"):
            body += "</p>"
        root_id = root_own_id(block)
        name = display_name(kind, plural, lang, prefix)
        out = build_thm(kind, thm_head_html(name, canonical_num(num), attribution),
                        body, root_id)
        rec = dict(metadata(kind, canonical_num(num), name),
                   id=root_id or None, html=out)
        return rec, ["legacy-shell"]

    m = THM_SHELL_RE.match(html)
    if not m:
        hm = HEADLESS_SHELL_RE.match(html)
        if hm:
            # a statement continued from the previous printed page: keep it
            # head-less, give it the styled shell so the box carries on
            kind = kind_from_classes(classes)
            if kind is None:
                return None, "headless-no-kind"
            body = strip_full_u(hm["body"]).strip()
            root_id = root_own_id(block)
            css = KINDS[kind][0]
            idattr = f' id="{root_id}"' if root_id else ""
            out = (f'<div class="thm {css} {kind} continuation"{idattr}>\n'
                   f'  <div class="thm-body">{body}</div>\n</div>')
            rec = {"type": kind, "label": None, "title": None,
                   "id": root_id or None, "html": out}
            return rec, ["headless-continuation"]
        return None, "shell-shape"
    cls_kind = kind_from_classes(classes)
    head_html = m["head"]
    parsed = parse_shell_head(head_html, lang)
    leftover = ""
    if parsed:
        # the head's printed word is the truth; the class is a fallback
        kind, plural, prefix, num, attribution, leftover = parsed
    else:
        kind, plural, prefix, num, attribution = cls_kind, False, "", None, None
        if kind is None:
            return None, "head-unparsed"
    body = m["body"]
    notes = []
    spans = bool(re.search(r'<span class="thm-(?:name|num)">', head_html))
    outside = visible_text(re.sub(
        r'<span class="thm-(?:name|num|title)">.*?</span>', "", head_html,
        flags=re.S)).strip(" .:")
    if spans and (len(outside) <= 20 or outside.startswith("(")):
        # well-formed head: keep it verbatim (footnote refs, name phrases,
        # title spans and all), just drop <u> used as an italic stand-in
        new_head = re.sub(r"</?u>", "", head_html).strip()
        if num is None:
            nm = re.search(r'<span class="thm-num">(.*?)</span>', head_html, re.S)
            num = visible_text(nm.group(1)).strip(".: ") if nm else None
    elif spans:
        return None, f"head-stranded-outside-spans:{outside[:40]!r}"
    else:
        # rebuild from text — refuse when the head carries markup a text
        # rebuild would lose
        if re.search(r"<(?!/?(?:u|em|strong|b)\b)", head_html):
            return None, "head-markup-unrebuildable"
        if leftover:
            if len(leftover) <= 15:
                return None, f"head-leftover:{leftover!r}"
            # statement text stranded inside the head — move it to the body
            body = f"<p>{leftover}</p>\n  " + body.lstrip()
            notes.append("stranded-head-moved")
        new_head = thm_head_html(display_name(kind, plural, lang, prefix),
                                 canonical_num(num), attribution)
    body = strip_full_u(body).strip()
    root_id = root_own_id(block)
    name = display_name(kind, plural, lang, prefix)
    out = build_thm(kind, new_head, body, root_id)
    rec = dict(metadata(kind, canonical_num(num), name), id=root_id or None,
               html=out)
    return rec, notes


def _legacy_title(text, lang):
    text = re.sub(r"\s+", " ", text).strip()
    m = re.match(
        r"\A(?P<words>[^\d]{2,60}?)\s*"
        r"(?P<num>\d+(?:\.\d+)*)?\s*"
        r"(?P<attr>\([^)]{2,80}\))?\s*[.:]?\s*\Z", text)
    if not m:
        return None
    words = m["words"].strip().rstrip(".:").split()
    if not words:
        return None
    hit = KEYWORDS[lang].get(words[-1].lower()) or \
        KEYWORDS["en" if lang == "fr" else "fr"].get(words[-1].lower())
    if not hit:
        return None
    kind, plural = hit
    return kind, plural, " ".join(words[:-1]), m["num"], m["attr"]


# ---------------------------------------------------------------------------
# Guards

def guard_rewrite(before, after, minted_ids=(), pieces=1):
    problems = []
    n = root_count(after)
    if n != pieces:
        problems.append(f"{n} root elements for {pieces} piece(s)")
    old, new = rec_ids(before), rec_ids(after)
    allowed = list(old) + [m for m in minted_ids if m]
    for i in new:
        if i not in allowed:
            problems.append(f"unexpected id {i!r}")
    for i in old:
        if i not in new:
            problems.append(f"lost id {i!r}")
    if len(new) != len(set(new)) and len(old) == len(set(old)):
        dupes = sorted({i for i in new if new.count(i) > 1})
        problems.append(f"duplicated id(s) {dupes!r}")
    return problems


def guard_text(before_body_vt, after_html, head_texts):
    """The body's visible text must survive; the head must be exactly the
    table-derived text."""
    problems = []
    vt = visible_text(after_html)
    expected = " ".join(t for t in head_texts if t)
    joined = re.sub(r"\s+", " ", f"{expected} {before_body_vt}").strip()
    got = re.sub(r"[ ]+", " ", vt).strip()
    if _canon(joined) != _canon(got):
        problems.append("text drift:\n      want: "
                        f"{joined[:160]!r}\n      got:  {got[:160]!r}")
    return problems


def _canon(s):
    return re.sub(r"\s+", "", s).replace("▾", "")


# ---------------------------------------------------------------------------
# Drivers

def load_overrides(path):
    data = json.loads(Path(path).read_text()) if Path(path).exists() else {}
    out = {}
    for rec in data.get("overrides", []):
        key = (rec["book"], rec["chapterId"], rec["pageId"])
        out.setdefault(key, {})[rec["blockIndex"]] = rec
    return out


def dominant_fr_proof_name(book):
    counts = {"Démonstration": 0, "Preuve": 0}
    for cid in chapter_ids(book):
        ch = load_chapter(book, "fr", cid)
        for page in ch.get("pages", []):
            for b in page.get("blocks", []):
                t = visible_text((b.get("html") or "")[:400])
                if re.match(r"\A(?:Démonstration|Dém)\b", t):
                    counts["Démonstration"] += 1
                elif t.startswith("Preuve"):
                    counts["Preuve"] += 1
    return max(counts, key=counts.get) if any(counts.values()) else "Démonstration"


def mint_statement_id(chapter_id, num, used):
    if not num:
        return None
    cand = f"{chapter_id}.{re.sub(r'[^0-9.]', '', num).strip('.')}"
    return None if (not cand or cand in used) else cand


def mint_proof_id(page_id, index, used):
    cand = f"proof-{page_id}-b{index}"
    return None if cand in used else cand


def book_id_set(book):
    used = set()
    for lang in LANGS:
        for cid in chapter_ids(book):
            ch = load_chapter(book, lang, cid)
            if not ch:
                continue
            for page in ch.get("pages", []):
                for b in page.get("blocks", []):
                    used.update(rec_ids(b.get("html")))
                for f in page.get("footnotes") or []:
                    if f.get("id"):
                        used.add(f["id"])
    return used


def run_book(book, chapters, phases, write, overrides_path):
    overrides = load_overrides(overrides_path)
    fr_proof = dominant_fr_proof_name(book)
    used_ids = book_id_set(book)
    worklist = []
    stats = {"normalize": 0, "retype-thm": 0, "retype-proof": 0, "merge": 0,
             "worklist": 0, "notes": []}

    for cid in chapters:
        ch = {lang: load_chapter(book, lang, cid) for lang in LANGS}
        if not ch["fr"] or not ch["en"]:
            sys.exit(f"refused — missing chapter {cid}")
        dirty = {lang: False for lang in LANGS}

        for pi, page_fr in enumerate(ch["fr"]["pages"]):
            page_en = ch["en"]["pages"][pi]
            page_id = page_fr["id"]
            if page_en.get("id") != page_id:
                sys.exit(f"refused — page order differs at {cid}[{pi}]")

            # ---- normalize -------------------------------------------------
            if "normalize" in phases:
                for idx in range(len(page_fr["blocks"])):
                    pair, notes_all, ok = {}, [], True
                    for lang in LANGS:
                        blk = (page_fr if lang == "fr" else page_en)["blocks"][idx]
                        tag, cls = block_root(blk.get("html") or "")
                        if tag != "div" or not (
                                "thm" in cls.split()
                                or LEGACY_SHELL_RE.match(blk.get("html") or "")):
                            ok = False
                            break
                        rec, notes = normalize_block(blk, lang, book)
                        if rec is None:
                            worklist.append(dict(
                                book=book, chapterId=cid, pageId=page_id,
                                blockIndex=idx, lang=lang, reason=f"normalize:{notes}",
                                excerpt=visible_text(blk["html"])[:120],
                                fingerprint=fingerprint(page_en["blocks"][idx]["html"])))
                            ok = False
                            break
                        pair[lang] = rec
                        notes_all += notes
                    if not ok or not pair:
                        continue
                    changed = False
                    for lang in LANGS:
                        blk = (page_fr if lang == "fr" else page_en)["blocks"][idx]
                        rec = pair[lang]
                        moved = any(n in ("stranded-head-moved", "legacy-shell")
                                    for n in notes_all)
                        problems = guard_rewrite(blk["html"], rec["html"])
                        problems += _normalize_text_guard(blk["html"], rec["html"],
                                                          moved)
                        if problems:
                            worklist.append(dict(
                                book=book, chapterId=cid, pageId=page_id,
                                blockIndex=idx, lang=lang,
                                reason="normalize-guard:" + "; ".join(problems)[:200],
                                excerpt=visible_text(blk["html"])[:120],
                                fingerprint=fingerprint(page_en["blocks"][idx]["html"])))
                            pair = None
                            break
                        if rec["html"] != blk["html"] or any(
                                rec[k] != blk.get(k) for k in ("type", "label", "title", "id")):
                            changed = True
                    if pair and changed:
                        stats["normalize"] += 1
                        if write:
                            for lang in LANGS:
                                (page_fr if lang == "fr" else page_en)["blocks"][idx] = pair[lang]
                                dirty[lang] = True

            # ---- retype + merge -------------------------------------------
            if "retype" in phases or "merge" in phases:
                ov = overrides.get((book, cid, page_id), {})
                for key, rec_ov in ov.items():
                    if rec_ov.get("fingerprint") and key < len(page_en["blocks"]) \
                            and rec_ov["fingerprint"] != fingerprint(
                                page_en["blocks"][key]["html"]):
                        sys.exit(f"refused — stale override at {cid}/{page_id}#{key}")
                entries, work = plan_page(book, page_en, page_fr, ov, None)
                for i, reason, excerpt in work:
                    worklist.append(dict(book=book, chapterId=cid, pageId=page_id,
                                         blockIndex=i, lang="en", reason=reason,
                                         excerpt=excerpt,
                                         fingerprint=fingerprint(
                                             page_en["blocks"][i]["html"])))
                merges = []
                for e in entries:
                    phase_of = "merge" if e.action == "merge" else "retype"
                    if phase_of not in phases:
                        continue
                    minted = None
                    if e.head.family == "proof":
                        src = page_en["blocks"][e.index]
                        if not root_own_id(src):
                            minted = mint_proof_id(page_id, e.index, used_ids)
                    else:
                        src = page_en["blocks"][e.index]
                        if not root_own_id(src):
                            minted = mint_statement_id(cid, e.head.num, used_ids)
                    pair = {}
                    problems = []
                    for lang in LANGS:
                        blocks = (page_fr if lang == "fr" else page_en)["blocks"]
                        try:
                            recs, notes = retype_records(
                                e, blocks, lang, page_id, fr_proof, minted)
                        except ValueError as exc:
                            problems.append(str(exc))
                            break
                        stats["notes"] += [f"{cid}/{page_id}#{e.index} {n}"
                                           for n in notes]
                        srcs = [blocks[k] for k, _ in e.chain]
                        before_all = "".join(s["html"] for s in srcs)
                        after_all = "".join(r["html"] for _, r in recs)
                        problems += guard_rewrite(before_all, after_all, [minted],
                                                  pieces=len(recs))
                        body_vt = " ".join(filter(None, (
                            _entry_body_vt(blocks, e, lang))))
                        heads = _entry_head_texts(recs, e)
                        problems += guard_text(body_vt, after_all, heads)
                        for _, r in recs:
                            if root_count(r["html"]) != 1:
                                problems.append("multi-root piece")
                        pair[lang] = recs
                    if problems:
                        worklist.append(dict(
                            book=book, chapterId=cid, pageId=page_id,
                            blockIndex=e.index, lang="both",
                            reason=f"{e.action}-guard:" + "; ".join(problems)[:300],
                            excerpt=visible_text(
                                page_en["blocks"][e.index]["html"])[:120],
                            fingerprint=fingerprint(page_en["blocks"][e.index]["html"])))
                        continue
                    stats[e.action] += 1
                    if minted:
                        used_ids.add(minted)
                    if not write:
                        continue
                    if e.action == "merge":
                        merges.append((e, pair))
                    else:
                        for lang in LANGS:
                            blocks = (page_fr if lang == "fr" else page_en)["blocks"]
                            for k, rec in pair[lang]:
                                blocks[k] = rec
                            dirty[lang] = True
                # merges last, descending, so earlier indices stay valid
                for e, pair in sorted(merges, key=lambda t: -t[0].index):
                    lo, hi = e.chain[0][0], e.chain[-1][0]
                    for lang in LANGS:
                        blocks = (page_fr if lang == "fr" else page_en)["blocks"]
                        blocks[lo:hi + 1] = [pair[lang][0][1]]
                        dirty[lang] = True

        if write:
            for lang in LANGS:
                if dirty[lang]:
                    write_chapter(chapter_path(book, lang, cid), ch[lang])
            for lang in LANGS:
                err = check_alignment(book, lang, cid,
                                      load_chapter(book, lang, cid))
                if err:
                    sys.exit(f"POST-WRITE ALIGNMENT FAILURE: {err}")

    stats["worklist"] = len(worklist)
    return stats, worklist


def _split_shell(html):
    """(head_vt, body_vt) for a theorem shell, (None, None) if unsplittable."""
    m = THM_SHELL_RE.match(html or "")
    if m:
        return visible_text(m["head"]), visible_text(m["body"])
    m = HEADLESS_SHELL_RE.match(html or "")
    if m:
        return "", visible_text(m["body"])
    return None, None


def _normalize_text_guard(before, after, moved=False):
    """Word content must survive everywhere; the body must survive with its
    punctuation too. Head punctuation may change (canonical '1.3.' form)."""
    nopunct = lambda s: re.sub(r"[.:—–]", "", s)
    if _canon(nopunct(visible_text(before))) != _canon(nopunct(visible_text(after))):
        return ["text drift:\n      was: "
                f"{visible_text(before)[:160]!r}\n      now: "
                f"{visible_text(after)[:160]!r}"]
    if not moved:
        _, bb = _split_shell(before)
        _, ba = _split_shell(after)
        if bb is not None and ba is not None and _canon(bb) != _canon(ba):
            return ["body drift:\n      was: "
                    f"{bb[:160]!r}\n      now: {ba[:160]!r}"]
    return []


def _entry_body_vt(blocks, e, lang):
    head, _ = parse_head(blocks[e.index]["html"], lang)
    yield visible_text(head.body_html) if head else ""
    for k, role in e.chain[1:]:
        h = blocks[k]["html"]
        inner = math_content(h)
        yield visible_text(inner if inner is not None else h)


def _entry_head_texts(recs, e):
    first = recs[0][1]["html"]
    m = re.search(r'<div class="(?:thm|proof)-head">(.*?)</div>', first, re.S)
    return [visible_text(m.group(1)) if m else ""]


# ---------------------------------------------------------------------------

def emit_worklist(book, worklist):
    data = {"generatedAt": utcnow(),
            "generator": "scripts/retype_statement_blocks.py",
            "records": []}
    if WORKLIST_PATH.exists():
        old = json.loads(WORKLIST_PATH.read_text())
        data["records"] = [r for r in old.get("records", [])
                           if r.get("book") != book]
    data["records"] += worklist
    data["records"].sort(key=lambda r: (r["book"], r["chapterId"],
                                        r["pageId"], r["blockIndex"]))
    WORKLIST_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapter")
    ap.add_argument("--phase", default="all",
                    choices=["normalize", "retype", "merge", "all"])
    ap.add_argument("--overrides", default=str(ROOT / "issues" / "retype_overrides.json"))
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    phases = (["normalize", "retype", "merge"] if args.phase == "all"
              else [args.phase])
    chapters = [args.chapter] if args.chapter else chapter_ids(args.book)
    stats, worklist = run_book(args.book, chapters, phases, args.write,
                               args.overrides)

    print(f"{args.book}: phases={'+'.join(phases)} "
          f"{'WRITE' if args.write else 'dry-run'}")
    for k in ("normalize", "retype-thm", "retype-proof", "merge"):
        print(f"  {k:14} {stats[k]}")
    print(f"  worklist       {stats['worklist']}")
    for n in stats["notes"][:40]:
        print(f"    note: {n}")
    if len(stats["notes"]) > 40:
        print(f"    … {len(stats['notes']) - 40} more notes")
    if not args.chapter:
        emit_worklist(args.book, worklist)
        print(f"  worklist written to {WORKLIST_PATH}")
    elif worklist:
        for r in worklist:
            print(f"    WL {r['chapterId']}/{r['pageId']}#{r['blockIndex']} "
                  f"{r['reason']}: {r['excerpt'][:90]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
