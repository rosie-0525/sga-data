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

from deep_translator import GoogleTranslator


ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "02-converted_html" / "data"
FR = DATA / "fr" / "chapters"
EN = DATA / "en" / "chapters"
CACHE_PATH = pathlib.Path(
    os.environ.get("SGA45_TRANSLATION_CACHE", "/private/tmp/sga4-fr-en-cache.json")
)

MATH_RE = re.compile(r"(\\\(.+?\\\)|\\\[.+?\\\])", re.S)
SPACE_ONLY_RE = re.compile(r"^\s*$")


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


class Translator:
    def __init__(self) -> None:
        self.cache = load_cache()
        self.engine = GoogleTranslator(source="fr", target="en")
        self.calls = 0

    def translate_text(self, text: str) -> str:
        if not text or SPACE_ONLY_RE.match(text):
            return text

        leading = text[: len(text) - len(text.lstrip())]
        trailing = text[len(text.rstrip()) :]
        core = text.strip()
        if not core:
            return text
        if core in self.cache:
            return leading + self.cache[core] + trailing

        if len(core) > 4500:
            translated = "".join(self.translate_text(part) for part in split_long_text(core))
            self.cache[core] = translated
            return leading + translated + trailing

        for attempt in range(5):
            try:
                out = self.engine.translate(core) or core
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
        parts = MATH_RE.split(text)
        return "".join(
            part if MATH_RE.fullmatch(part) else self.translate_text(part)
            for part in parts
            if part
        )

    def translate_html(self, html: str) -> str:
        math: list[str] = []

        def protect(match: re.Match[str]) -> str:
            math.append(match.group(0))
            return f"[[SGAMATH{len(math) - 1:05d}]]"

        protected = MATH_RE.sub(protect, html)
        translated = "".join(
            self.translate_text(chunk) for chunk in split_long_html(protected)
        )
        for i, value in enumerate(math):
            translated = translated.replace(f"[[SGAMATH{i:05d}]]", value)
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
        data["title"] = tr.translate_text(data["title"])
    for page in data.get("pages", []):
        if page.get("title"):
            page["title"] = tr.translate_text(page["title"])
        for block in page.get("blocks", []):
            if block.get("title"):
                block["title"] = tr.translate_text(block["title"])
            block["html"] = tr.translate_html(block.get("html", ""))
        for footnote in page.get("footnotes", []):
            footnote["html"] = tr.translate_html(footnote.get("html", ""))
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
