#!/usr/bin/env python3
"""LLM-assisted translation pipeline for SGA 5 viewer JSON (fr -> en).

Subcommands:
  extract  <workdir>   Pull translatable fragments out of data/fr/chapters,
                       protect TeX math with placeholders, write batch files
                       (batch-NNN.jsonl) plus fragments.json sidecar.
  check    <workdir>   Validate translated batches (out-NNN.jsonl): every
                       fragment present, math placeholders intact, HTML tag
                       sequence unchanged. Writes retry-NNN.jsonl for failures.
  assemble <workdir>   Re-insert math, rebuild data/en/chapters/*.json.

Fragment record: {"k": key, "t": protected_text}
Translated record: {"k": key, "t": translated_protected_text}
Math placeholders look like [[M7]] and must be preserved verbatim.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FR = ROOT / "02-converted_html" / "data" / "fr" / "chapters"
EN = ROOT / "02-converted_html" / "data" / "en" / "chapters"

MATH_RE = re.compile(r"(\\\(.*?\\\)|\\\[.*?\\\])", re.S)
TAG_RE = re.compile(r"<[^>]+>")
BATCH_TARGET = 14000

TITLE_MAP = {
    "proposition": "Proposition",
    "théorème": "Theorem",
    "theoreme": "Theorem",
    "définition": "Definition",
    "lemme": "Lemma",
    "corollaire": "Corollary",
    "démonstration": "Proof",
    "preuve": "Proof",
    "remarque": "Remark",
    "remarques": "Remarks",
    "exemple": "Example",
    "exemples": "Examples",
    "conjecture": "Conjecture",
    "bibliographie": "Bibliography",
    "introduction": "Introduction",
    "variante": "Variant",
    "scholie": "Scholium",
}


def map_title(title: str) -> str | None:
    """Translate 'Lemme 2.1.'-style titles deterministically; None if unknown."""
    m = re.fullmatch(r"([A-Za-zÉÀÈéàè]+)((?:\s+[\d.]+)?\.?\s*)", title.strip())
    if not m:
        return None
    word = TITLE_MAP.get(m.group(1).lower())
    if word is None:
        return None
    out = word + m.group(2)
    if title.strip().isupper():
        out = out.upper()
    return out


def protect(text: str):
    math: list[str] = []

    def repl(m: re.Match[str]) -> str:
        math.append(m.group(0))
        return f"[[M{len(math)-1}]]"

    protected = MATH_RE.sub(repl, text)
    # Raw-TeX text nodes (display blocks: \begin{...}, \xymatrix) must stay
    # verbatim: protect any inter-tag text node containing TeX control words.
    parts = re.split(r"(<[^>]+>)", protected)
    out = []
    for part in parts:
        if part and not TAG_RE.fullmatch(part) and (
            "\\begin{" in part or "\\xymatrix" in part or "\\displaylines" in part
        ):
            math.append(part)
            out.append(f"[[M{len(math)-1}]]")
        else:
            out.append(part)
    return "".join(out), math


def needs_translation(protected: str) -> bool:
    stripped = TAG_RE.sub("", protected)
    stripped = re.sub(r"\[\[M\d+\]\]", "", stripped)
    return bool(re.search(r"[A-Za-zÀ-ÿ]", stripped))


def walk(data: dict):
    """Yield (key, text) for every translatable string; keys are stable paths."""
    if data.get("title"):
        yield "title", data["title"]
    for pi, page in enumerate(data.get("pages", [])):
        if page.get("title"):
            yield f"p{pi}.title", page["title"]
        for bi, block in enumerate(page.get("blocks", [])):
            if block.get("title"):
                yield f"p{pi}.b{bi}.title", block["title"]
            if block.get("html"):
                yield f"p{pi}.b{bi}.html", block["html"]
        for fi, fn in enumerate(page.get("footnotes", [])):
            if fn.get("html"):
                yield f"p{pi}.f{fi}.html", fn["html"]


def set_by_key(data: dict, key: str, value: str) -> None:
    if key == "title":
        data["title"] = value
        return
    parts = key.split(".")
    page = data["pages"][int(parts[0][1:])]
    if parts[1] == "title":
        page["title"] = value
    elif parts[1].startswith("b"):
        block = page["blocks"][int(parts[1][1:])]
        block["title" if parts[2] == "title" else "html"] = value
    else:
        page["footnotes"][int(parts[1][1:])]["html"] = value


def cmd_extract(workdir: pathlib.Path) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    fragments: dict[str, dict] = {}
    to_translate: list[tuple[str, str]] = []
    for src in sorted(FR.glob("*.json")):
        data = json.loads(src.read_text())
        for key, text in walk(data):
            full_key = f"{src.stem}::{key}"
            if key.endswith("title"):
                mapped = map_title(text)
                if mapped is not None:
                    fragments[full_key] = {"protected": text, "math": [],
                                           "translated": mapped}
                    continue
            prot, math = protect(text)
            fragments[full_key] = {"protected": prot, "math": math}
            if needs_translation(prot):
                to_translate.append((full_key, prot))
            else:
                fragments[full_key]["translated"] = prot

    batches: list[list[tuple[str, str]]] = [[]]
    size = 0
    for item in to_translate:
        if size > BATCH_TARGET and batches[-1]:
            batches.append([])
            size = 0
        batches[-1].append(item)
        size += len(item[1])
    for i, batch in enumerate(batches):
        path = workdir / f"batch-{i:03d}.jsonl"
        path.write_text("\n".join(
            json.dumps({"k": k, "t": t}, ensure_ascii=False) for k, t in batch
        ) + "\n")
    (workdir / "fragments.json").write_text(
        json.dumps(fragments, ensure_ascii=False))
    print(f"{len(fragments)} fragments, {len(to_translate)} need translation, "
          f"{len(batches)} batches in {workdir}")


def check_pair(src: str, out: str) -> str | None:
    """Return an error message, or None if the translation is acceptable."""
    src_tags = TAG_RE.findall(src)
    out_tags = TAG_RE.findall(out)
    if src_tags != out_tags:
        return f"tag sequence changed: {len(src_tags)} vs {len(out_tags)} tags"
    src_math = sorted(re.findall(r"\[\[M\d+\]\]", src))
    out_math = sorted(re.findall(r"\[\[M\d+\]\]", out))
    if src_math != out_math:
        return "math placeholders changed"
    if re.search(r"\[\[M\d+\]\]", out) and not re.search(r"\[\[M\d+\]\]", src):
        return "spurious placeholder"
    return None


def cmd_check(workdir: pathlib.Path) -> int:
    sources: dict[str, str] = {}
    for path in sorted(workdir.glob("batch-*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                sources[rec["k"]] = rec["t"]
    translated: dict[str, str] = {}
    for path in sorted(workdir.glob("out-*.jsonl")):
        for ln, line in enumerate(path.read_text().splitlines(), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"{path.name}:{ln}: bad json: {exc}")
                continue
            translated[rec["k"]] = rec["t"]

    errors: list[dict] = []
    for key, src in sources.items():
        if key not in translated:
            errors.append({"k": key, "t": src, "err": "missing"})
            continue
        err = check_pair(src, translated[key])
        if err:
            errors.append({"k": key, "t": src, "err": err})
    for path in workdir.glob("retry-*.jsonl"):
        path.unlink()
    if errors:
        for i in range(0, len(errors), 40):
            chunk = errors[i:i+40]
            (workdir / f"retry-{i//40:03d}.jsonl").write_text(
                "\n".join(json.dumps(e, ensure_ascii=False) for e in chunk) + "\n")
        print(f"{len(errors)} fragments FAILED "
              f"({sum(1 for e in errors if e['err']=='missing')} missing); "
              f"retry files written")
        for e in errors[:15]:
            print(f"  {e['k']}: {e['err']}")
        return 1
    print(f"all {len(sources)} fragments OK")
    (workdir / "translated.json").write_text(
        json.dumps(translated, ensure_ascii=False))
    return 0


def cmd_assemble(workdir: pathlib.Path) -> None:
    fragments = json.loads((workdir / "fragments.json").read_text())
    translated = json.loads((workdir / "translated.json").read_text())
    EN.mkdir(parents=True, exist_ok=True)
    for src in sorted(FR.glob("*.json")):
        data = json.loads(src.read_text())
        for key, _text in list(walk(data)):
            full_key = f"{src.stem}::{key}"
            frag = fragments[full_key]
            text = frag.get("translated")
            if text is None:
                text = translated[full_key]
            for i, m in enumerate(frag["math"]):
                text = text.replace(f"[[M{i}]]", m)
            if re.search(r"\[\[M\d+\]\]", text):
                raise SystemExit(f"{full_key}: unresolved placeholder")
            set_by_key(data, key, text)
        dst = EN / src.name
        dst.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
        print(f"wrote {dst}")


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in {"extract", "check", "assemble"}:
        print(__doc__)
        return 2
    workdir = pathlib.Path(sys.argv[2])
    if sys.argv[1] == "extract":
        cmd_extract(workdir)
    elif sys.argv[1] == "check":
        return cmd_check(workdir)
    else:
        cmd_assemble(workdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
