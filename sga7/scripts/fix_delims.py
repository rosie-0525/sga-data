#!/usr/bin/env python3
"""Repair mistyped math delimiters in 01-transcribed sources.

Typo classes (all leave raw TeX or swallow prose into math when rendered):
  * literal parens typed as math delimiters *inside* math:
      \\(\\mathcal O\\(C)\\simeq…\\)  ->  \\(\\mathcal O(C)\\simeq…\\)
      \\(\\dim u_s\\(G_s\\)\\)         ->  \\(\\dim u_s(G_s)\\)
    (a nested \\( is never valid — MathJax would mispair delimiters and eat
    the prose between two expressions);
  * math opened but closed with a plain paren:
      \\(k)  ->  \\(k\\)     (single letters are math, cf. sga5 fix_bare_math)
      \\(\\operatorname{Pic}_{C/k}^o)  ->  …^o\\)     (TeX-ish content)
      \\(2n;2)  ->  (2n;2)   (trivial content: the opener was the typo)
    and likewise \\[ … ]] -> …]\\] for display math.

Valid constructs are preserved: \\(\\alpha)\\) (a paren that belongs inside
the math — detected by a real \\) right after the plain candidate) is left
alone. Only the <body> is processed. Repeats to fixpoint.

Usage: python3 scripts/fix_delims.py [--write] [stems...]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "01-transcribed"

TEXISH = re.compile(r"\\[a-zA-Z]{2,}|[\^_]")
SINGLE = re.compile(r"^[A-Za-hj-z]['′]*$|^[A-Z]['′]*$")   # letters except bare "i"


def escaped(t, i):
    n = 0
    j = i - 1
    while j >= 0 and t[j] == "\\":
        n += 1
        j -= 1
    return n % 2 == 1


def scan_group(t, start, op, cl):
    """From just after \\op, find what terminates the group first at plain
    depth 0: ('ok', pos of \\cl) | ('plain', pos of bare cl) |
    ('nested', pos of an inner \\op) | ('eof', len)."""
    depth = 0
    i = start
    while i < len(t):
        c = t[i]
        if c == "\\" and i + 1 < len(t) and not escaped(t, i):
            if t[i + 1] == cl:
                return "ok", i
            if t[i + 1] == op:
                return "nested", i
            i += 2
            continue
        if c == op:
            depth += 1
        elif c == cl:
            if depth == 0:
                return "plain", i
            depth -= 1
        i += 1
    return "eof", len(t)


def demote(t, pos):
    """Remove the backslash of the delimiter starting at pos."""
    return t[:pos] + t[pos + 1:]


def fix_kind(t, op, cl, log, fname, offset):
    def ln(i):
        return t.count("\n", 0, i) + 1 + offset

    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(t) - 1:
            if not (t[i] == "\\" and t[i + 1] == op and not escaped(t, i)):
                i += 1
                continue
            kind, pos = scan_group(t, i + 2, op, cl)
            if kind == "nested":
                # innermost wins: resolve the deepest nested opener first
                inner = pos
                while True:
                    k2, p2 = scan_group(t, inner + 2, op, cl)
                    if k2 != "nested":
                        break
                    inner = p2
                if k2 == "ok":
                    ctx = t[inner:p2 + 2][:50]
                    t = demote(demote(t, inner), p2 - 1)  # opener + closer
                    log.append(f"{fname}:{ln(inner)} nested pair {ctx!r} -> literal parens")
                else:  # plain / eof: the nested opener itself is the typo
                    ctx = t[inner:inner + 30]
                    t = demote(t, inner)
                    log.append(f"{fname}:{ln(inner)} nested opener {ctx!r} -> literal")
                changed = True
                break
            if kind == "plain":
                nxt = re.match(r"\s*\\" + re.escape(cl), t[pos + 1:])
                if nxt:
                    i = pos + 1 + nxt.end()   # \(\alpha)\) style: valid, skip
                    continue
                content = t[i + 2:pos]
                if TEXISH.search(content) or SINGLE.match(content.strip()):
                    t = t[:pos] + "\\" + t[pos:]
                    log.append(f"{fname}:{ln(i)} closer \\{op}{content[:55]}…{cl} -> \\{cl}")
                else:
                    t = demote(t, i)
                    log.append(f"{fname}:{ln(i)} opener \\{op}{content[:55]}{cl} -> literal")
                changed = True
                break
            if kind == "eof":
                log.append(f"{fname}:{ln(i)} UNCLOSED \\{op} (left alone)")
            i = pos + 2
    return t


def main():
    write = "--write" in sys.argv
    stems = [a for a in sys.argv[1:] if not a.startswith("--")]
    files = ([SRC / f"{s}.html" for s in stems] if stems
             else sorted(SRC.glob("*.html"), key=lambda p: int(p.stem)))
    for f in files:
        src = f.read_text()
        head, body = src.split("<body>", 1)
        log = []
        off = head.count("\n")
        body = fix_kind(body, "(", ")", log, f.name, off)
        body = fix_kind(body, "[", "]", log, f.name, off)
        if log:
            print(f"== {f.name}: {len(log)} fixes")
            for line in log:
                print("  ", line)
            if write:
                f.write_text(head + "<body>" + body)
    print("WROTE" if write else "DRY RUN")


if __name__ == "__main__":
    main()
