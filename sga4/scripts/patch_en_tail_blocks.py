#!/usr/bin/env python3
"""One-off repair for the tail-drop bug (see KNOWN-ISSUES.md).

build_viewer_data.py used to drop bare top-level text runs (display math
between paragraphs, page-break paragraph continuations); the fixed script
promotes each run to its own <p> block. That inserts blocks into the French
chapters — but the viewer pairs fr/en blocks per page *by index*, and the
English chapters (fully translated for sga4, partially for sga3) were built
against the old, shorter French block lists.

This script re-aligns the English chapters: for every French chapter that
changed vs. git HEAD, it computes the insertion-only diff per page (old blocks
must be a subsequence of new blocks) and inserts the very same blocks (they
are language-neutral display math) into the English chapter at the same
positions.

Usage:
    python3 sga4/scripts/patch_en_tail_blocks.py <corpus-dir> [--write]
e.g.
    python3 sga4/scripts/patch_en_tail_blocks.py sga4 --write
Run from the repository root (needs `git show HEAD:` for the old French).
"""
import json
import subprocess
import sys
from pathlib import Path


def old_json(relpath: str):
    out = subprocess.run(["git", "show", f"HEAD:{relpath}"],
                         capture_output=True, check=True)
    return json.loads(out.stdout.decode("utf-8"))


def diff_page(old_blocks, new_blocks):
    """Two-pointer subsequence diff: return the set of indices in new_blocks
    that are insertions, or raise if old_blocks is not a subsequence of
    new_blocks (i.e. the regeneration changed more than it added)."""
    inserted = set()
    i = 0
    for j, nb in enumerate(new_blocks):
        if i < len(old_blocks) and nb == old_blocks[i]:
            i += 1
        else:
            inserted.add(j)
    if i != len(old_blocks):
        raise ValueError(f"old block {i} has no match in the regenerated page")
    return inserted


def main():
    args = [a for a in sys.argv[1:] if a != "--write"]
    write = "--write" in sys.argv
    if len(args) != 1:
        sys.exit(__doc__)
    corpus = Path(args[0])
    fr_dir = corpus / "02-converted_html" / "data" / "fr" / "chapters"
    en_dir = corpus / "02-converted_html" / "data" / "en" / "chapters"

    total_ins = 0
    total_chars = 0
    patched = []
    for fr_path in sorted(fr_dir.glob("*.json")):
        rel = fr_path.as_posix()
        new_fr = json.loads(fr_path.read_text(encoding="utf-8"))
        try:
            old_fr = old_json(rel)
        except subprocess.CalledProcessError:
            print(f"  {fr_path.stem}: not in HEAD, skipping")
            continue
        old_pids = [p["id"] for p in old_fr["pages"]]
        new_pids = [p["id"] for p in new_fr["pages"]]
        if old_pids != new_pids:
            sys.exit(f"FATAL {fr_path.stem}: page ids changed "
                     f"{old_pids} -> {new_pids}")

        en_path = en_dir / fr_path.name
        en = json.loads(en_path.read_text(encoding="utf-8")) \
            if en_path.exists() else None
        en_has_content = en and any(p.get("blocks") for p in en["pages"])

        ch_ins = 0
        for pi, (op, np_) in enumerate(zip(old_fr["pages"], new_fr["pages"])):
            inserted = diff_page(op["blocks"], np_["blocks"])
            if not inserted:
                continue
            ch_ins += len(inserted)
            total_chars += sum(len(np_["blocks"][j]["html"]) for j in inserted)
            if en_has_content:
                en_page = en["pages"][pi]
                if len(en_page["blocks"]) != len(op["blocks"]):
                    sys.exit(f"FATAL {fr_path.stem} page {op['id']}: en has "
                             f"{len(en_page['blocks'])} blocks, old fr "
                             f"{len(op['blocks'])} — was already misaligned")
                rebuilt, ei = [], 0
                for j, nb in enumerate(np_["blocks"]):
                    if j in inserted:
                        rebuilt.append(dict(nb))
                    else:
                        rebuilt.append(en_page["blocks"][ei])
                        ei += 1
                en_page["blocks"] = rebuilt
        if ch_ins:
            total_ins += ch_ins
            tag = "en patched" if en_has_content else "en stub, nothing to do"
            patched.append(fr_path.stem)
            print(f"  {fr_path.stem:6s} +{ch_ins:3d} blocks ({tag})")
            if write and en_has_content:
                en_path.write_text(
                    json.dumps(en, ensure_ascii=False, indent=1),
                    encoding="utf-8")

    print(f"\n{corpus}: {total_ins} inserted blocks, ~{total_chars} chars, "
          f"chapters affected: {', '.join(patched) or 'none'}")
    print("WROTE" if write else "DRY RUN — no files written")


if __name__ == "__main__":
    main()
