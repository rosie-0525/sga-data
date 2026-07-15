#!/usr/bin/env python3
"""Translate the SGA 4 1/2 French viewer JSON into English.

The source JSON structure, HTML anchors/links, and TeX math are preserved.
Translated fragments are cached so interrupted runs can be resumed.

Usage:
  python3 sga4.5/scripts/translate_json_en.py all
  python3 sga4.5/scripts/translate_json_en.py introduction I II
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import time
from typing import Iterable

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "02-converted_html" / "data"
FR = DATA / "fr" / "chapters"
EN = DATA / "en" / "chapters"
CACHE_PATH = pathlib.Path(os.environ.get(
    "SGA45_TRANSLATION_CACHE", "/private/tmp/sga45-opus-v2-fr-en-cache.json"
))
MODEL_PATH = pathlib.Path(os.environ.get(
    "SGA45_TRANSLATION_MODEL", "/private/tmp/opus-mt-fr-en"
))

MATH_RE = re.compile(r"(\\\(.+?\\\)|\\\[.+?\\\])", re.S)
SPACE_ONLY_RE = re.compile(r"^\s*$")
ENGLISH_WORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "was",
    "were", "for", "with", "that", "this", "from", "by", "on", "as", "be",
    "it", "its", "may", "most", "any", "used", "using", "should",
}
FRENCH_WORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "ou", "dans",
    "est", "sont", "pour", "avec", "que", "qui", "par", "sur", "comme", "ce",
    "cette", "ces", "on", "il", "elle", "nous", "soit", "être", "tout",
}


def already_english(text: str) -> bool:
    words = re.findall(r"[A-Za-zÀ-ÿ']+", text.lower())
    if len(words) < 5:
        return False
    en = sum(word in ENGLISH_WORDS for word in words)
    fr = sum(word in FRENCH_WORDS for word in words)
    return en >= 3 and en > 2 * fr


def degenerate_translation(source: str, translated: str) -> bool:
    words = re.findall(r"[A-Za-z']+", translated.lower())
    if len(translated) > max(600, 4 * len(source)):
        return True
    if re.search(r"[\u0400-\u04ff\u3400-\u9fff]", translated):
        return True
    if len(words) >= 30:
        counts: dict[tuple[str, ...], int] = {}
        for i in range(len(words) - 3):
            ngram = tuple(words[i : i + 4])
            counts[ngram] = counts.get(ngram, 0) + 1
        if counts and max(counts.values()) >= 5:
            return True
    return False


GLOSSARY = (
    (r"\balgebraically enclosed\b", "algebraically closed"),
    (r"\bfinished type\b", "finite type"),
    (r"\btype finished\b", "finite type"),
    (r"\bfinished presentation\b", "finite presentation"),
    (r"\bfinished dimensional\b", "finite-dimensional"),
    (r"\bfinished extension\b", "finite extension"),
    (r"\bfinished group\b", "finite group"),
    (r"\bfinished rank\b", "finite rank"),
    (r"\bbeams\b", "sheaves"),
    (r"\bbeam\b", "sheaf"),
    (r"\bschemas\b", "schemes"),
    (r"\bschema\b", "scheme"),
    (r"\bbodies\b", "fields"),
    (r"\bbody\b", "field"),
    (r"\bfinitude\b", "finiteness"),
    (r"\bdividers\b", "divisors"),
    (r"\bdivider\b", "divisor"),
    (r"\bspectral suites\b", "spectral sequences"),
    (r"\bspectral suite\b", "spectral sequence"),
    (r"\bexact sequel\b", "exact sequence"),
    (r"\bclean support\b", "compact support"),
    (r"\bown support\b", "compact support"),
    (r"\bconstructable\b", "constructible"),
    (r"\binversible\b", "invertible"),
    (r"\bcompatibilitys\b", "compatibilities"),
    (r"\bsensor product\b", "tensor product"),
    (r"\bmorphism trace\b", "trace morphism"),
    (r"\brow one\b", "rank one"),
    (r"\btorsoes\b", "torsors"),
    (r"\btorsos\b", "torsors"),
    (r"\btorsers\b", "torsors"),
    (r"\btorso\b", "torsor"),
    (r"\btorser\b", "torsor"),
    (r"\bown values\b", "eigenvalues"),
    (r"\bown value\b", "eigenvalue"),
    (r"\bseparate morphism\b", "separated morphism"),
    (r"\bclean morphism\b", "proper morphism"),
    (r"\bclean scheme\b", "proper scheme"),
    (r"\brelated schemes\b", "connected schemes"),
    (r"\brelated scheme\b", "connected scheme"),
    (r"\brelated groups\b", "connected groups"),
    (r"\brelated group\b", "connected group"),
    (r"\brelated curves\b", "connected curves"),
    (r"\brelated curve\b", "connected curve"),
    (r"\bcohomologie\b", "cohomology"),
    (r"\bfaisceaux\b", "sheaves"),
    (r"\bfaisceau\b", "sheaf"),
    (r"\badique\b", "adic"),
)


def normalize_english(text: str) -> str:
    for pattern, replacement in GLOSSARY:
        text = re.sub(pattern, replacement, text, flags=re.I)
    return text


TITLE_MAP = {
    "Proposition": "Proposition",
    "Théorème": "Theorem",
    "Définition": "Definition",
    "Lemme": "Lemma",
    "Corollaire": "Corollary",
    "Démonstration": "Proof",
    "Preuve": "Proof",
    "Bibliographie": "Bibliography",
}


def translate_title(title: str, tr: "Translator") -> str:
    return TITLE_MAP.get(title, tr.translate_text(title))


def load_cache() -> dict[str, str]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict[str, str]) -> None:
    tmp = CACHE_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(CACHE_PATH)


class OpusEngine:
    """Small local wrapper exposing the same translate() shape as web engines."""

    def __init__(self) -> None:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_PATH, local_files_only=True
        )
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL_PATH, local_files_only=True
        )
        self.model.eval()

    def _pieces(self, text: str) -> list[str]:
        # Sentence-sized inputs avoid omissions in long dense paragraphs.
        sentences = re.split(r"(?<=[.!?;:])\s+", text)
        pieces: list[str] = []
        buf = ""
        for sentence in sentences:
            candidate = f"{buf} {sentence}".strip() if buf else sentence
            if len(self.tokenizer(candidate, add_special_tokens=True).input_ids) <= 450:
                buf = candidate
                continue
            if buf:
                pieces.append(buf)
            buf = ""
            words = sentence.split()
            word_buf: list[str] = []
            for word in words:
                trial = " ".join(word_buf + [word])
                if len(self.tokenizer(trial, add_special_tokens=True).input_ids) > 450 and word_buf:
                    pieces.append(" ".join(word_buf))
                    word_buf = [word]
                else:
                    word_buf.append(word)
            buf = " ".join(word_buf)
        if buf:
            pieces.append(buf)
        return pieces

    def translate(self, text: str) -> str:
        normalized = text.replace("“", '"').replace("”", '"').replace("’", "'")
        pieces = self._pieces(normalized)
        translated: list[str] = []
        for start in range(0, len(pieces), 8):
            batch_text = pieces[start : start + 8]
            encoded = self.tokenizer(
                batch_text, return_tensors="pt", padding=True, truncation=False
            )
            with self.torch.inference_mode():
                input_tokens = int(encoded["attention_mask"].sum(dim=1).max())
                generated = self.model.generate(
                    **encoded,
                    max_new_tokens=min(384, max(32, 2 * input_tokens + 16)),
                    repetition_penalty=1.12,
                    no_repeat_ngram_size=4,
                    early_stopping=True,
                )
            translated.extend(
                self.tokenizer.batch_decode(generated, skip_special_tokens=True)
            )
        return " ".join(translated)


class Translator:
    def __init__(self) -> None:

        self.cache = load_cache()
        self.engine = OpusEngine()
        self.calls = 0

    def translate_text(self, text: str) -> str:
        if not text or SPACE_ONLY_RE.match(text):
            return text

        leading = text[: len(text) - len(text.lstrip())]
        trailing = text[len(text.rstrip()) :]
        core = text.strip()
        if not core:
            return text
        if not re.search(r"[A-Za-zÀ-ÿ]", core):
            return text
        if already_english(core):
            return text
        if core in self.cache:
            cached = self.cache[core]
            if not degenerate_translation(core, cached):
                return leading + normalize_english(cached) + trailing

        if len(core) > 4500:
            translated = "".join(self.translate_text(part) for part in split_long_text(core))
            self.cache[core] = translated
            return leading + translated + trailing

        for attempt in range(5):
            try:
                out = self.engine.translate(core) or core
                out = normalize_english(out)
                self.cache[core] = out
                self.calls += 1
                if self.calls % 100 == 0:
                    save_cache(self.cache)
                    print(
                        f"  translated {self.calls} new fragments; cache={len(self.cache)}",
                        flush=True,
                    )
                return leading + out + trailing
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(1.5 * (attempt + 1))
        return text

    def translate_outside_math(self, text: str) -> str:
        math: list[str] = []

        def protect(match: re.Match[str]) -> str:
            math.append(self.translate_math(match.group(0)))
            return f"__SGAMATH{len(math) - 1:05d}__"

        protected = MATH_RE.sub(protect, text)
        translated = self.translate_text(protected)
        restored: dict[int, int] = {}

        def restore(match: re.Match[str]) -> str:
            index = int(match.group(1))
            if index >= len(math):
                return match.group(0)
            restored[index] = restored.get(index, 0) + 1
            return math[index]

        translated = re.sub(r"_+SGAMATH0*(\d+)_+", restore, translated)
        if "SGAMATH" in translated or any(
            restored.get(index) != 1 for index in range(len(math))
        ):
            # Rare model omission: translate around formulas instead. This is
            # less contextual but guarantees no TeX can be lost.
            out: list[str] = []
            for part in MATH_RE.split(text):
                if not part:
                    continue
                if MATH_RE.fullmatch(part):
                    out.append(self.translate_math(part))
                else:
                    # A prose fragment must never introduce a formula from a
                    # cached or hallucinated model continuation.
                    out.append(MATH_RE.sub("", self.translate_text(part)))
            return "".join(out)
        return translated

    def translate_math(self, formula: str) -> str:
        # Translate only brace-free prose in TeX text commands. All TeX syntax
        # and mathematical notation remains outside the model.
        return re.sub(
            r"\\(text|textnormal)\{([^{}]*)\}",
            lambda match: rf"\{match.group(1)}{{{self.translate_text(match.group(2))}}}",
            formula,
        )

    def translate_html(self, html: str) -> str:
        # Translate only HTML text nodes. Tags/attributes and math never enter
        # the model, which makes structural preservation deterministic.
        parts = re.split(r"(<[^>]+>)", html)
        translated_parts: list[str] = []
        for part in parts:
            if not part:
                continue
            if re.fullmatch(r"<[^>]+>", part):
                translated_parts.append(part)
            elif r"\begin{" in part or r"\xymatrix{" in part:
                # Converter display/equation blocks contain raw TeX rather
                # than \(...\) delimiters. Keep those nodes byte-for-byte.
                translated_parts.append(self.translate_math(part))
            else:
                translated_parts.append(self.translate_outside_math(part))
        translated = "".join(translated_parts)
        translated = translated.replace('title="retour"', 'title="back"')
        translated = translated.replace(
            'class="thm-name">Proposal</span>',
            'class="thm-name">Proposition</span>',
        )
        translated = translated.replace(
            'class="proof-name">Demonstration</span>',
            'class="proof-name">Proof</span>',
        ).replace(
            'class="proof-name">Evidence</span>',
            'class="proof-name">Proof</span>',
        )
        translated = translated.replace("theorem_", "Theorem. ")
        translated = translated.replace("lemma_", "Lemma. ")
        translated = translated.replace("prop-def_", "Proposition-Definition. ")
        translated = translated.replace("proposal_", "Proposition. ")
        translated = translated.replace("definition_", "Definition. ")
        return translated


def split_long_text(text: str) -> Iterable[str]:
    pieces = re.split(r"(?<=[.;:!?])(\s+)", text)
    buf = ""
    for piece in pieces:
        if len(buf) + len(piece) > 3500 and buf:
            yield buf
            buf = piece
        else:
            buf += piece
    if buf:
        yield buf


def split_long_html(html: str) -> list[str]:
    if len(html) <= 4500:
        return [html]
    raw_parts = re.split(r"(</p>|</li>|</div>|</h[1-6]>|</dd>|\n)", html)
    parts: list[str] = []
    for i in range(0, len(raw_parts), 2):
        part = raw_parts[i]
        if i + 1 < len(raw_parts):
            part += raw_parts[i + 1]
        parts.append(part)

    chunks: list[str] = []
    buf = ""
    for part in parts:
        if not part:
            continue
        if len(buf) + len(part) > 4200 and buf:
            chunks.append(buf)
            buf = part
        elif len(part) > 4500:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(split_long_text(part))
        else:
            buf += part
    if buf:
        chunks.append(buf)
    return chunks


def translate_chapter(chapter: str, tr: Translator) -> None:
    src = FR / f"{chapter}.json"
    dst = EN / f"{chapter}.json"
    data = json.loads(src.read_text(encoding="utf-8"))

    if data.get("title"):
        data["title"] = translate_title(data["title"], tr)
    for page in data.get("pages", []):
        if page.get("title"):
            page["title"] = translate_title(page["title"], tr)
        is_bibliography = data.get("chapter_id") == "bibliographie"
        for block in page.get("blocks", []):
            if block.get("title"):
                block["title"] = translate_title(block["title"], tr)
            if is_bibliography and block.get("type") == "bibliography":
                block["html"] = block.get("html", "").replace(
                    'title="retour"', 'title="back"'
                )
            else:
                block["html"] = tr.translate_html(block.get("html", ""))
        for footnote in page.get("footnotes", []):
            footnote["html"] = tr.translate_html(footnote.get("html", ""))
        if not is_bibliography:
            for entry in page.get("bibliography", []):
                entry["html"] = tr.translate_html(entry.get("html", ""))
                entry["text"] = tr.translate_outside_math(entry.get("text", ""))

        # The converter defines page HTML as the newline-joined block HTML.
        # Rebuilding it avoids a second, potentially inconsistent translation.
        page["html"] = "\n".join(
            block.get("html", "") for block in page.get("blocks", [])
        )

    EN.mkdir(parents=True, exist_ok=True)
    dst.write_text(
        json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    save_cache(tr.cache)
    print(f"{chapter}: wrote {dst}", flush=True)


def main(argv: list[str]) -> int:
    chapters = sorted(p.stem for p in FR.glob("*.json")) if argv == ["all"] else argv
    if not chapters:
        print(__doc__)
        return 2
    tr = Translator()
    for chapter in chapters:
        translate_chapter(chapter, tr)
    print(f"done; new calls={tr.calls}; cache={len(tr.cache)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
