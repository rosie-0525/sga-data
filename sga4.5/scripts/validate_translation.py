#!/usr/bin/env python3
"""Validate English SGA 4 1/2 JSON against the French source structure."""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "02-converted_html" / "data"
FR = DATA / "fr" / "chapters"
EN = DATA / "en" / "chapters"

FRENCH_THEOREM_NAMES = {
    "Définition", "Définitions", "Théorème", "Théorèmes", "Lemme", "Lemmes",
    "Corollaire", "Corollaires", "Remarque", "Remarques", "Exemple", "Exemples",
    "Scholie", "Démonstration", "Preuve", "Variante", "Variantes", "Exercice",
    "Exercices", "Problème", "Problèmes", "Convention",
}


def html_signature(value: str) -> tuple:
    return (
        sorted(re.findall(r'id="([^"]*)"', value)),
        sorted(re.findall(r'href="([^"]*)"', value)),
        sorted(re.findall(r'data-bib="([^"]*)"', value)),
        value.count(r"\("), value.count(r"\)"),
        value.count(r"\["), value.count(r"\]"),
        value.count(r"\begin{"), value.count(r"\end{"),
    )


def metadata(items: list[dict], fields: tuple[str, ...]) -> list[tuple]:
    return [tuple(item.get(field) for field in fields) for item in items]


def check_html(fr_html: str, en_html: str, where: str, errors: list[str]) -> None:
    if html_signature(fr_html) != html_signature(en_html):
        errors.append(f"{where}: anchors, links, bibliography refs, or math changed")
    fr_tags = collections.Counter(re.findall(r"</?([a-zA-Z][\w-]*)\b", fr_html))
    en_tags = collections.Counter(re.findall(r"</?([a-zA-Z][\w-]*)\b", en_html))
    if fr_tags != en_tags:
        errors.append(f"{where}: HTML tag counts changed")
    for name in re.findall(r'class="thm-name">\s*([^<]*?)\s*</span>', en_html):
        if name in FRENCH_THEOREM_NAMES:
            errors.append(f"{where}: untranslated theorem name {name!r}")


def check(chapter: str) -> list[str]:
    errors: list[str] = []
    fr = json.loads((FR / f"{chapter}.json").read_text(encoding="utf-8"))
    en = json.loads((EN / f"{chapter}.json").read_text(encoding="utf-8"))

    for field in ("chapter_id", "number"):
        if fr.get(field) != en.get(field):
            errors.append(f"{field} changed")
    if metadata(fr["pages"], ("id",)) != metadata(en.get("pages", []), ("id",)):
        return errors + ["page ids/order changed"]

    for fpage, epage in zip(fr["pages"], en["pages"]):
        where = f"{chapter}/{fpage['id']}"
        if metadata(fpage["blocks"], ("id", "type", "label")) != metadata(
            epage.get("blocks", []), ("id", "type", "label")
        ):
            errors.append(f"{where}: block metadata/order changed")
            continue
        if metadata(fpage["footnotes"], ("id", "number")) != metadata(
            epage.get("footnotes", []), ("id", "number")
        ):
            errors.append(f"{where}: footnote metadata/order changed")
        if metadata(fpage.get("bibliography", []), ("id", "label")) != metadata(
            epage.get("bibliography", []), ("id", "label")
        ):
            errors.append(f"{where}: bibliography metadata/order changed")

        for i, (fb, eb) in enumerate(zip(fpage["blocks"], epage["blocks"])):
            check_html(fb["html"], eb.get("html", ""), f"{where}/block[{i}]", errors)
        for i, (ff, ef) in enumerate(zip(fpage["footnotes"], epage["footnotes"])):
            check_html(ff["html"], ef.get("html", ""), f"{where}/footnote[{i}]", errors)
        for i, (fb, eb) in enumerate(zip(fpage.get("bibliography", []), epage.get("bibliography", []))):
            check_html(fb["html"], eb.get("html", ""), f"{where}/bibliography[{i}]", errors)

        expected_page_html = "\n".join(block["html"] for block in epage["blocks"])
        if epage.get("html") != expected_page_html:
            errors.append(f"{where}: page html does not match translated blocks")
    return errors


def main(argv: list[str]) -> int:
    chapters = sorted(p.stem for p in FR.glob("*.json")) if not argv or argv == ["all"] else argv
    okay = True
    for chapter in chapters:
        try:
            errors = check(chapter)
        except Exception as exc:
            errors = [f"could not validate: {exc}"]
        print(f"{chapter}: {'PASS' if not errors else 'FAIL'}")
        for error in errors:
            print(f"  {error}")
        okay = okay and not errors
    return 0 if okay else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
