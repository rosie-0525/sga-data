#!/usr/bin/env python3
"""Repair structurally-invalid translated blocks by retranslating conservatively."""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import time

from deep_translator import GoogleTranslator


ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "02-converted_html" / "data"
FR = DATA / "fr" / "chapters"
EN = DATA / "en" / "chapters"
CACHE_PATH = pathlib.Path(os.environ.get("SGA4_TRANSLATION_CACHE", "/private/tmp/sga4-fr-en-cache.json"))

MATH_RE = re.compile(r"(\\\(.+?\\\)|\\\[.+?\\\])", re.S)
TAG_RE = re.compile(r"(<[^>]+>)")
SPACE_ONLY_RE = re.compile(r"^\s*$")


def load_cache() -> dict[str, str]:
    return json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}


def save_cache(cache: dict[str, str]) -> None:
    tmp = CACHE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(CACHE_PATH)


def ids_hrefs(html: str):
    return (
        sorted(re.findall(r'id="([^"]*)"', html)),
        sorted(re.findall(r'href="([^"]*)"', html)),
    )


def math_sig(html: str):
    return (
        html.count(r"\("),
        html.count(r"\)"),
        html.count(r"\["),
        html.count(r"\]"),
        html.count(r"\begin{"),
        html.count(r"\end{"),
    )


def split_long_text(text: str):
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


class Translator:
    def __init__(self):
        self.cache = load_cache()
        self.engine = GoogleTranslator(source="fr", target="en")
        self.calls = 0

    def text(self, text: str) -> str:
        if not text or SPACE_ONLY_RE.match(text):
            return text
        leading = text[: len(text) - len(text.lstrip())]
        trailing = text[len(text.rstrip()) :]
        core = text.strip()
        if not core:
            return text
        key = "NODE:" + core
        if key in self.cache:
            return leading + self.cache[key] + trailing
        if len(core) > 4500:
            out = "".join(self.text(part) for part in split_long_text(core))
            self.cache[key] = out
            return leading + out + trailing
        for attempt in range(5):
            try:
                out = self.engine.translate(core) or core
                self.cache[key] = out
                self.calls += 1
                if self.calls % 100 == 0:
                    save_cache(self.cache)
                    print(f"  repair translated {self.calls}; cache={len(self.cache)}", flush=True)
                return leading + out + trailing
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(1.5 * (attempt + 1))
        return text

    def outside_math(self, text: str) -> str:
        out = []
        for part in MATH_RE.split(text):
            if not part:
                continue
            out.append(part if MATH_RE.fullmatch(part) else self.text(part))
        return "".join(out)

    def html(self, html: str) -> str:
        out = []
        for part in TAG_RE.split(html):
            if not part:
                continue
            out.append(part if TAG_RE.fullmatch(part) else self.outside_math(part))
        return "".join(out)


def repair_chapter(roman: str, tr: Translator) -> int:
    fr = json.loads((FR / f"{roman}.json").read_text(encoding="utf-8"))
    en_path = EN / f"{roman}.json"
    en = json.loads(en_path.read_text(encoding="utf-8"))
    changed = 0
    for fpg, epg in zip(fr["pages"], en["pages"]):
        for i, (fb, eb) in enumerate(zip(fpg["blocks"], epg["blocks"])):
            if ids_hrefs(fb["html"]) != ids_hrefs(eb.get("html", "")) or math_sig(fb["html"]) != math_sig(eb.get("html", "")):
                eb["html"] = tr.html(fb["html"])
                changed += 1
        for i, (ffn, efn) in enumerate(zip(fpg["footnotes"], epg["footnotes"])):
            if ids_hrefs(ffn["html"]) != ids_hrefs(efn.get("html", "")) or math_sig(ffn["html"]) != math_sig(efn.get("html", "")):
                efn["html"] = tr.html(ffn["html"])
                changed += 1
    if changed:
        en_path.write_text(json.dumps(en, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        save_cache(tr.cache)
    print(f"{roman}: repaired {changed} block/footnote html fields")
    return changed


def main(argv: list[str]) -> int:
    chapters = sorted(p.stem for p in FR.glob("*.json")) if argv == ["all"] else argv
    tr = Translator()
    total = sum(repair_chapter(ch, tr) for ch in chapters)
    print(f"done; repaired={total}; new calls={tr.calls}; cache={len(tr.cache)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
