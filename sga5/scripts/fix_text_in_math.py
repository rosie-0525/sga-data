#!/usr/bin/env python3
"""Translate French prose inside \\text{...} spans of the SGA 5 English
chapter JSON. Math was kept byte-identical during the main translation pass,
so \\text{} contents (and a few surrounding word-order cases) are fixed here.

Only exact, hand-checked replacements are applied; anything unrecognized is
left alone and reported.
"""
from __future__ import annotations

import json
import pathlib
import re

EN = pathlib.Path(__file__).resolve().parents[1] / "02-converted_html" / "data" / "en" / "chapters"

# Word-order cases: the adjective must move across a math symbol, so the
# replacement spans more than one \text{} group. Applied first, verbatim.
SPECIALS = [
    (r"\text{ et tout }A_X\text{-Module constructible }E",
     r"\text{ and every constructible }A_X\text{-Module }E"),
    (r"\mathbb Z_\ell\text{-algèbre finie}",
     r"\text{finite }\mathbb Z_\ell\text{-algebra}"),
    (r"\text{ une }\mathbb Q_\ell\text{-algèbre finie}",
     r"\text{ a finite }\mathbb Q_\ell\text{-algebra}"),
    (r"\mathcal O_T\text{-Module loc. libre}",
     r"\text{loc. free }\mathcal O_T\text{-Module}"),
    (r"\mathcal O_T\text{-Module localement libre}",
     r"\text{locally free }\mathcal O_T\text{-Module}"),
    (r"\text{ complexe de }A\text{-modules borné à droite}",
     r"\text{ right-bounded complex of }A\text{-modules}"),
]

MAP = {
    "si": "if", "Si": "If", "sinon": "otherwise", "sinon.": "otherwise.",
    "si il existe": "if there exists", "s'il existe": "if there exists",
    "pour": "for", "pour tout": "for all", "pour tous": "for all",
    "pour tout idéal": "for every ideal",
    "pour la projection canonique": "for the canonical projection",
    "et": "and", "et tout": "and all", "et que": "and that", "et par": "and by",
    "et, d’après b),": "and, by b),",
    "où": "where", "où la flèche": "where the arrow",
    "dans": "in", "avec": "with", "de": "of", "ou": "or", "à": "to",
    "donc": "hence", "quand": "when", "soit": "that is", "une": "a",
    "fois": "times", "ème": "th", "épi": "epi", "cqfd.": "q.e.d.",
    "est": "is", "est impair": "is odd", "est pair": "is even",
    "est conjugué à": "is conjugate to",
    "est invariant par": "is invariant under",
    "est l'objet nul de": "is the zero object of",
    "est lisse, purement de dimension relative":
        "is smooth, purely of relative dimension",
    "coïncide avec": "coincides with",
    "complexe de": "complex of",
    "de l'image de": "of the image of",
    "de sorte que": "so that",
    "d’après": "by",
    "en utilisant": "using",
    "graphe de": "graph of",
    "la classe": "the class",
    "la multiplicité du point fixe": "the multiplicity of the fixed point",
    "la somme des multiplicités des points fixes de l'application":
        "the sum of the multiplicities of the fixed points of the map",
    "nombre des points fixes de": "number of fixed points of",
    "nombre des points fixes de la restriction":
        "number of fixed points of the restriction",
    "par EGA IV 6.1.3": "by EGA IV 6.1.3",
    "par dualité (SGA 3.1.10),": "by duality (SGA 3.1.10),",
    "proj. can.": "can. proj.", "ch. base": "base ch.",
    "restriction des scalaires": "restriction of scalars",
    "tel que": "such that", "tel qu'on a": "such that we have",
    "une clôture séparable de": "a separable closure of",
    "valeur en": "value at",
    "équivalent si la classe de": "equivalent if the class of",
    "-conjugaison de": "-conjugacy of",
    "étale au-dessus de": "étale over", "au-dessus de": "over",
    "étant un nombre premier donné, distinct de la caractéristique de":
        "being a given prime number, distinct from the characteristic of",
    "(d'après (4.3)),": "(by (4.3)),",
    "(degré de (x))": "(degree of (x))",
    "(en vertu de la formule d'induction complémentaire (4.2.1))":
        "(by the complementary induction formula (4.2.1))",
    "(formule d'induction complémentaire (4.2.1))":
        "(complementary induction formula (4.2.1))",
    "(formule de projection)": "(projection formula)",
    "(induction ordinaire (1.12. b) (i))": "(ordinary induction (1.12. b) (i))",
    "(multiplicativité de \\(f^*\\))": "(multiplicativity of \\(f^*\\))",
    "(n° 1, proposition 1 c))": "(no. 1, proposition 1 c))",
    "(par (4.3) et la formule d'induction 1.12 b) (i))":
        "(by (4.3) and the induction formula 1.12 b) (i))",
    "(par 4.3),": "(by 4.3),",
    "(par a) (i)).": "(by a) (i)).",
    "(par a) (ii))": "(by a) (ii))",
    "(par hypothèse),": "(by hypothesis),",
    "(suite exacte de 8.4.3)": "(exact sequence of 8.4.3)",
    "16.5.12 et IV 5.1.9)": "16.5.12 and IV 5.1.9)",
    "(automorphisme de \\(\\overline X\\) défini par \\(f\\), par transport\nde structure)":
        "(automorphism of \\(\\overline X\\) defined by \\(f\\), by transport\nof structure)",
}

TEXT_RE = re.compile(r"\\text(normal|rm)?\{([^{}]*)\}")
FR_HINT = re.compile(
    r"[àâçèêëîïôùûœ]|\b(si|et|ou|où|de|des|du|la|le|les|une?|pour|avec|dans|"
    r"que|qui|est|sont|donc|soit|tout|tous|par|sur)\b")


def fix_text(match: re.Match[str], leftovers: list[str]) -> str:
    kind = match.group(1) or ""
    content = match.group(2)
    lead = content[: len(content) - len(content.lstrip())]
    trail = content[len(content.rstrip()):]
    core = content.strip()
    if core in MAP:
        return rf"\text{kind}{{{lead}{MAP[core]}{trail}}}"
    if core and FR_HINT.search(core):
        leftovers.append(core)
    return match.group(0)


def main() -> None:
    leftovers: list[str] = []
    for path in sorted(EN.glob("*.json")):
        data = json.loads(path.read_text())
        changed = 0

        def fix_html(html: str) -> str:
            nonlocal changed
            out = html
            for old, new in SPECIALS:
                out = out.replace(old, new)
            out = TEXT_RE.sub(lambda m: fix_text(m, leftovers), out)
            if out != html:
                changed += 1
            return out

        for page in data["pages"]:
            for block in page["blocks"]:
                if block.get("html"):
                    block["html"] = fix_html(block["html"])
            for fn in page["footnotes"]:
                if fn.get("html"):
                    fn["html"] = fix_html(fn["html"])
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
        print(f"{path.name}: {changed} strings changed")
    if leftovers:
        print("UNRECOGNIZED French-looking \\text contents:")
        for item in sorted(set(leftovers)):
            print(" ", repr(item))


if __name__ == "__main__":
    main()
