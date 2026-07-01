#!/usr/bin/env python3
"""Inline / strip editorial macros and presentation commands (SGA1).

Operates on the post-resolve-orig staged file. Only touches the SGA1-specific
editorial/presentation layer and a handful of MathJax-portability rewrites;
content math macros (\\Hom, \\Pic, \\SheafHom, ...) are left intact and defined
in sga1-macros.sty (by sga1-build-main) for pdflatex, and in convert.py's macro
tables (by sga1-convert-html) for HTML.
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# Brace-balanced helpers
# ---------------------------------------------------------------------------

def find_matching(text: str, start: int, open_c: str, close_c: str) -> int:
    if text[start] != open_c:
        raise ValueError(f"expected {open_c!r} at {start}, got {text[start]!r}")
    depth = 1
    i = start + 1
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"unmatched {open_c!r} at {start}")


def replace_command_with_arg(text: str, name: str, transform) -> str:
    """Find every \\name{...} (brace-balanced) and replace via transform(arg)."""
    pattern = re.compile(r"\\" + name + r"(?![a-zA-Z])\s*(?=\{)")
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        m = pattern.search(text, i)
        if m is None:
            out.append(text[i:])
            break
        out.append(text[i : m.start()])
        brace_start = m.end()
        brace_end = find_matching(text, brace_start, "{", "}")
        arg = text[brace_start + 1 : brace_end]
        out.append(transform(arg))
        i = brace_end + 1
    return "".join(out)


def drop_command_with_arg(text: str, name: str) -> str:
    return replace_command_with_arg(text, name, lambda _: "")


def drop_command_no_arg(text: str, name: str) -> str:
    """Drop \\name (no argument). Honors LaTeX command-name boundary."""
    return re.sub(r"\\" + name + r"(?![a-zA-Z])", "", text)


def drop_optional_then_brace(text: str, name: str) -> str:
    """Drop \\name[...]{...} and \\name[...] forms."""
    pattern = re.compile(r"\\" + name + r"(?![a-zA-Z])\s*")
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        m = pattern.search(text, i)
        if m is None:
            out.append(text[i:])
            break
        out.append(text[i : m.start()])
        j = m.end()
        if j < n and text[j] == "[":
            j = find_matching(text, j, "[", "]") + 1
        if j < n and text[j] == "{":
            j = find_matching(text, j, "{", "}") + 1
        i = j
    return "".join(out)


# ---------------------------------------------------------------------------
# Rules — SGA1 editorial / presentation
# ---------------------------------------------------------------------------

def rule_marginpar(text: str) -> str:
    r"""Drop \marginpar{NNN} page-number margin notes (439 of them).

    These mark the original LNM page numbers; they have no place in reflowed
    HTML and clutter the margin in pdflatex. A \marginpar alone on its line must
    take the whole line with it — otherwise the emptied line becomes a blank
    line (a \par) that breaks any enclosing group (\emph{...}, theorem head, …).
    The argument is always {<digits>}, so a non-nested match is safe.
    """
    text = re.sub(r"(?m)^[ \t]*\\marginpar\{[^}]*\}[ \t]*\n", "", text)
    return drop_command_with_arg(text, "marginpar")


def rule_oldindexnot(text: str) -> str:
    """Drop \\oldindexnot{...}. sga1-smf.sty defines it as a no-op
    (\\def\\oldindexnot#1{}) — a disabled notation-index marker — so its
    brace-balanced argument must be consumed, not leaked."""
    return drop_command_with_arg(text, "oldindexnot")


def rule_kern(text: str) -> str:
    r"""Strip \kern/\mkern with an explicit dimension in text mode.

    Source has cosmetic \kern1pt\footnote / \kern2pt spacers; the HTML converter
    would otherwise leak the dimension ("1pt") as visible text. pdflatex only
    loses a 1–2pt cosmetic gap. (Math-mode \mkern4mu in xymatrix is left for the
    diagram engine and rarely matches this text-spacing pattern.)"""
    text = re.sub(r"\\m?kern\s*[\d.]+\s*(?:pt|em|ex|mm|cm|in|bp|mu|sp)", "", text)
    # \hspace*{1cm} / \hskip 1cm spacers inside math arrow labels leak in MathJax
    text = re.sub(r"\\hspace\*?\s*\{[^}]*\}", "", text)
    text = re.sub(r"\\hskip\s*[\d.]+\s*(?:pt|em|ex|mm|cm|in|bp|mu|sp)", "", text)
    # \raise10mm / \lower2pt box-shift primitives (xymatrix arrow labels) — XyJax
    # has no \raise; drop the shift, keep the following \hbox content.
    text = re.sub(r"\\(?:raise|lower)\s*[\d.]+\s*(?:pt|em|ex|mm|cm|in|bp|sp)", "", text)
    return text


def rule_ref(text: str) -> str:
    r"""\Ref{x} -> \ref{x}. SGA1 cross-refs all use \Ref
    (\newcommand{\Ref}[1]{\textup{\ref{#1}}}); drop the \textup wrapper."""
    return replace_command_with_arg(text, "Ref", lambda a: r"\ref{" + a + "}")


def rule_ptbl(text: str) -> str:
    # \ptbl is `.\kern.2em`; render as "." + thin space
    return re.sub(r"\\ptbl(?![a-zA-Z])", r".\,", text)


def rule_makeschapterhead(text: str) -> str:
    return replace_command_with_arg(text, "makeschapterhead",
                                    lambda a: r"\chapter*{" + a + "}")


def rule_smf_sectioning(text: str) -> str:
    r"""SMF-class \Subsection / \Subsubsection -> plain \subsection / \subsubsection.

    smfbook.cls defines them via \@startsection; the source uses the starred
    forms (\Subsection*{...}). Lowercasing lets both pdflatex (standard
    sectioning) and the HTML converter (which keys on lowercase section names)
    handle them."""
    text = re.sub(r"\\Subsubsection(?![a-zA-Z])", r"\\subsubsection", text)
    text = re.sub(r"\\Subsection(?![a-zA-Z])", r"\\subsection", text)
    return text


def rule_sfootnote(text: str) -> str:
    text = replace_command_with_arg(text, "sfootnote",
                                    lambda a: r"\footnote{" + a + "}")
    text = drop_optional_then_brace(text, "sfootnotetext")
    text = drop_command_no_arg(text, "sfootnotemark")
    return text


def rule_alt_metadata(text: str) -> str:
    for name in ("alttitle", "altkeywords", "subjclass", "keywords"):
        text = drop_command_with_arg(text, name)
    return text


def rule_title_metadata(text: str) -> str:
    """Drop \\title/\\author/\\date — main.tex provides its own."""
    for name in ("title", "author", "date"):
        text = drop_optional_then_brace(text, name)
    return text


def rule_altabstract(text: str) -> str:
    return re.sub(
        r"\\begin\{altabstract\}.*?\\end\{altabstract\}",
        "",
        text,
        flags=re.DOTALL,
    )


def rule_abstract(text: str) -> str:
    """Convert \\begin{abstract}...\\end{abstract} to a quote block."""
    return re.sub(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
        r"\\begin{quote}\\textbf{R\\'esum\\'e.} \1\\end{quote}",
        text,
        flags=re.DOTALL,
    )


def rule_size_macros(text: str) -> str:
    """\\smaller / \\larger (SMF class) -> plain LaTeX size commands."""
    text = re.sub(r"\\smaller(?![a-zA-Z])", r"\\small", text)
    text = re.sub(r"\\larger(?![a-zA-Z])", r"\\large", text)
    return text


def rule_stepcounter(text: str) -> str:
    """Drop \\stepcounter{...} (cosmetic counter bump; refs resolve via labels)."""
    return drop_command_with_arg(text, "stepcounter")


def rule_protect(text: str) -> str:
    """Strip \\protect fragile-command guards that leak into title math."""
    return drop_command_no_arg(text, "protect")


def rule_nobreak(text: str) -> str:
    """Strip \\nobreak line-break penalties (meaningless / leaked in HTML math)."""
    return drop_command_no_arg(text, "nobreak")


def rule_parbox(text: str) -> str:
    r"""\parbox[pos]{width}{content} -> content, and drop \newlength/\setlength/
    \addtolength plumbing. A \parbox of prose appears inside a \left\{ \text{...}
    \right\} set-builder (exposé XIII); MathJax can't host \parbox, so keep just
    the prose. (Length args never nest braces, so a flat regex is safe.)"""
    text = re.sub(r"\\newlength\s*\{[^}]*\}", "", text)
    text = re.sub(r"\\(?:set|addto)length\s*\{[^}]*\}\s*\{[^}]*\}", "", text)
    pattern = re.compile(r"\\parbox(?![a-zA-Z])\s*")
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        m = pattern.search(text, i)
        if m is None:
            out.append(text[i:])
            break
        out.append(text[i : m.start()])
        j = m.end()
        if j < n and text[j] == "[":
            j = find_matching(text, j, "[", "]") + 1
        if j < n and text[j] == "{":
            j = find_matching(text, j, "{", "}") + 1   # width: drop
        if j < n and text[j] == "{":
            end = find_matching(text, j, "{", "}")
            out.append(text[j + 1 : end])               # content: keep
            j = end + 1
        i = j
    return "".join(out)


def rule_allowbreak(text: str) -> str:
    """Strip \\allowbreak — a line-break opportunity with no HTML-math meaning;
    MathJax has no such command, so it leaks into the rendered math as text."""
    return drop_command_no_arg(text, "allowbreak")


def rule_sideset(text: str) -> str:
    r"""\sideset{L}{R}OP -> {}L R OP. amsmath's \sideset needs a big-operator;
    SGA1 uses it for prescripts on a non-operator (\sideset{_n}{}\Pic, the
    n-torsion Picard group), which MathJax rejects. The prescript form
    {}_n\operatorname{Pic} renders identically and is MathJax-safe; pdflatex too."""
    pattern = re.compile(r"\\sideset(?![a-zA-Z])\s*(?=\{)")
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        m = pattern.search(text, i)
        if m is None:
            out.append(text[i:])
            break
        out.append(text[i : m.start()])
        ls = m.end()
        le = find_matching(text, ls, "{", "}")
        rs = le + 1
        re_ = find_matching(text, rs, "{", "}")
        left = text[ls + 1 : le]
        right = text[rs + 1 : re_]
        out.append("{}" + left + right)
        i = re_ + 1
    return "".join(out)


# --- xymatrix safety (XyJax-v3 cannot host \operatorname inside diagram cells) ---

# operator macros that appear inside \xymatrix bodies and would expand (in the
# HTML converter) to \operatorname{...}; rewrite them to plain \mathrm/\mathbf so
# XyJax-v3 can parse the cells. pdflatex renders these near-identically (operator
# spacing is lost only inside the diagram). \R/\H/\id/\pr/\tame/\an are already
# \mathrm in sga1-smf.sty and need no rewrite.
_XYMATRIX_OPS = {
    "SheafHom": r"\mathbf{Hom}",
    "SheafAut": r"\mathbf{Aut}",
    "SheafIsom": r"\mathbf{Isom}",
    "Hom": r"\mathrm{Hom}",
    "Ouv": r"\mathrm{Ouv}",
    "Quot": r"\mathrm{Quot}",
    "Fer": r"\mathrm{Fer}",
    "Ext": r"\mathrm{Ext}",
}


def rule_xymatrix_safe(text: str) -> str:
    """Inside \\xymatrix{...} bodies, rewrite \\operatorname-class macros to
    plain \\mathrm/\\mathbf so XyJax-v3 can parse the diagram cells."""
    pattern = re.compile(r"\\xymatrix(?:@[^{]*)?\s*(?=\{)")
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        m = pattern.search(text, i)
        if m is None:
            out.append(text[i:])
            break
        out.append(text[i:m.end()])
        brace_start = m.end()
        brace_end = find_matching(text, brace_start, "{", "}")
        body = text[brace_start:brace_end + 1]
        for name, repl in _XYMATRIX_OPS.items():
            body = re.sub(r"\\" + name + r"(?![a-zA-Z])", repl.replace("\\", "\\\\"), body)
        # unwrap \hbox{$..$}/\hbox{..} INSIDE the diagram only (an arrow label
        # like \ar[dd]^{\hbox{$f'$}} is math; \hbox there trips XyJax). Outside
        # xymatrix, \hbox{$..$} (e.g. inside \rlap) is text-mode and must keep $.
        for _ in range(4):
            nb = replace_command_with_arg(
                body, "hbox",
                lambda a: a[1:-1] if a.startswith("$") and a.endswith("$") else a)
            if nb == body:
                break
            body = nb
        out.append(body)
        i = brace_end + 1
    return "".join(out)


# --- xymatrix cell normalisation (object-first + braced) for XyJax-v3 ---

def _read_ar_spec(s: str, i: int) -> tuple[str, int]:
    r"""Read one \ar arrow spec at s[i]: \ar + @-modifiers + [target] + _/^ labels."""
    n = len(s)
    j = i + 3  # past \ar
    while j < n and s[j] == "@":
        j += 1
        if j >= n:
            break
        c = s[j]
        if c == "{":
            j = find_matching(s, j, "{", "}") + 1
        elif c == "<":
            k = s.find(">", j)
            j = (k + 1) if k != -1 else n
        elif c == "(":
            j = find_matching(s, j, "(", ")") + 1
        elif c == "/":
            k = s.find("/", j + 1)
            j = (k + 1) if k != -1 else n
        elif c == "[":
            j = find_matching(s, j, "[", "]") + 1
        else:
            j += 1  # single-char modifier (@!, @^, @_, @0, ...)
    while j < n and s[j] == " ":
        j += 1
    if j < n and s[j] == "[":
        j = find_matching(s, j, "[", "]") + 1
    else:
        # no [target] right after \ar (+modifiers): xy turn/curve syntax we
        # don't model — signal the caller to leave the cell untouched.
        raise ValueError("unparseable \\ar spec")
    while True:  # labels _x / ^{..} / _-{..}
        k = j
        while k < n and s[k] == " ":
            k += 1
        if k < n and s[k] in "_^":
            k += 1
            if k < n and s[k] == "-":
                k += 1
            while k < n and s[k] == " ":
                k += 1
            if k < n and s[k] == "{":
                k = find_matching(s, k, "{", "}") + 1
            elif k < n and s[k] == "\\":
                k += 1
                while k < n and s[k].isalpha():
                    k += 1
            elif k < n:
                k += 1
            j = k
        else:
            break
    return s[i:j], j


def _reorder_xymatrix_cell(cell: str) -> str:
    r"""Normalise one xymatrix cell to XyJax-v3's grammar: pull every \ar spec
    out, then emit {object}<arrows>. Wrapping the object in one brace group makes
    XyJax treat it as a single math object (fixes operator/paren cell-objects and
    objects carrying scripts), and putting it before the arrows fixes the
    `\ar[l] OBJ` order pdflatex tolerates but XyJax rejects.

    Cells using xy's backtick turn/curve syntax are left untouched (too complex
    to re-serialise safely); so is any cell whose \ar spec we can't parse."""
    if "`" in cell:
        return cell
    arrows: list[str] = []
    obj: list[str] = []
    i = 0
    n = len(cell)
    while i < n:
        if cell.startswith("\\ar", i) and (i + 3 >= n or not cell[i + 3].isalpha()):
            try:
                spec, i = _read_ar_spec(cell, i)
            except ValueError:
                return cell  # unparseable arrow — leave the whole cell as-is
            arrows.append(spec)
        elif cell[i] == "\\" and i + 1 < n:
            obj.append(cell[i : i + 2]); i += 2
        else:
            obj.append(cell[i]); i += 1
    o = "".join(obj).strip()
    if not o:
        return cell
    if o.startswith("{"):
        try:
            if find_matching(o, 0, "{", "}") == len(o) - 1:
                return o + "".join(arrows)
        except ValueError:
            pass
    return "{" + o + "}" + "".join(arrows)


def _reorder_xymatrix_body(body: str) -> str:
    r"""Apply cell normalisation to every cell of one xymatrix body (split on
    top-level &, \\ and \cr, respecting braces). Bodies using xy's backtick
    turn/curve syntax are left untouched."""
    if "`" in body:
        return body
    out: list[str] = []
    depth = 0
    i = 0
    n = len(body)
    start = 0
    while i < n:
        c = body[i]
        if c == "\\" and i + 1 < n and body[i + 1] == "\\":
            if depth == 0:
                out.append(_reorder_xymatrix_cell(body[start:i]))
                out.append("\\\\")
                i += 2
                start = i
                continue
            i += 2
            continue
        if c == "\\" and body[i + 1 : i + 3] == "cr" and (
            i + 3 >= n or not body[i + 3].isalpha()
        ):
            if depth == 0:
                # XyJax-v3 accepts \\ as the row separator but trips on \cr in
                # many cells; pdflatex's xy-pic accepts either.
                out.append(_reorder_xymatrix_cell(body[start:i]))
                out.append("\\\\")
                i += 3
                start = i
                continue
            i += 3
            continue
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == "&" and depth == 0:
            out.append(_reorder_xymatrix_cell(body[start:i]))
            out.append("&")
            i += 1
            start = i
            continue
        i += 1
    out.append(_reorder_xymatrix_cell(body[start:]))
    return "".join(out)


def rule_xymatrix_reorder(text: str) -> str:
    r"""Rewrite each \xymatrix{...} body so every cell is object-first and the
    object is one braced group — the form XyJax-v3 parses. Runs after
    rule_xymatrix_safe (operators already plain) and before the targeted patches."""
    pattern = re.compile(r"\\xymatrix(?:@[^{]*)?\s*(?=\{)")
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        m = pattern.search(text, i)
        if m is None:
            out.append(text[i:])
            break
        out.append(text[i:m.end()])
        bs = m.end()
        be = find_matching(text, bs, "{", "}")
        out.append("{" + _reorder_xymatrix_body(text[bs + 1:be]) + "}")
        i = be + 1
    return "".join(out)


# --- LaTeX text-accent macros -> precomposed Unicode (for MathJax \text{}) ---

_TEXT_ACCENT_COMBINING = {
    "'": "́", "`": "̀", "^": "̂", '"': "̈",
    "~": "̃", "=": "̄", ".": "̇",
}
_ACCENT_DOTLESS = {r"\i": "i", r"\j": "j"}


def _compose_text_accents(s: str) -> str:
    """Replace LaTeX text-accent macros (\\'e, \\`u, \\^{o}, \\^{\\i}) with
    precomposed Unicode (é, ù, ô, î) — one correctly-placed glyph for MathJax."""
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            nxt = s[i + 1]
            if nxt == "\\":
                out.append("\\\\")
                i += 2
                continue
            if nxt in _TEXT_ACCENT_COMBINING:
                comb = _TEXT_ACCENT_COMBINING[nxt]
                j = i + 2
                base = None
                end_at = None
                if j < n and s[j] == "{":
                    e = find_matching(s, j, "{", "}")
                    inner = s[j + 1 : e].strip()
                    inner = _ACCENT_DOTLESS.get(inner, inner)
                    if len(inner) == 1:
                        base, end_at = inner, e + 1
                elif s.startswith(r"\i", j) or s.startswith(r"\j", j):
                    base, end_at = _ACCENT_DOTLESS[s[j : j + 2]], j + 2
                elif j < n and s[j].isalpha():
                    base, end_at = s[j], j + 1
                if base is not None:
                    out.append(unicodedata.normalize("NFC", base + comb))
                    i = end_at
                    continue
        out.append(c)
        i += 1
    return "".join(out)


_TEXT_ACCENT_COMMANDS = (
    "text", "textup", "textit", "textbf", "textsc", "textrm", "textsf",
    "textsl", "textmd", "textnormal", "textsuperscript", "emph", "hbox",
    "mbox", "tag",
)


def rule_text_mode_accents(text: str) -> str:
    """Convert LaTeX text-accent macros to precomposed Unicode inside text-mode
    command arguments (so accents inside math \\text{}/\\tag*{} render cleanly)."""
    for name in _TEXT_ACCENT_COMMANDS:
        pattern = re.compile(r"\\" + name + r"(?![a-zA-Z])\*?\s*(?=\{)")
        out: list[str] = []
        i = 0
        n = len(text)
        while i < n:
            m = pattern.search(text, i)
            if m is None:
                out.append(text[i:])
                break
            out.append(text[i : m.end()])
            bs = m.end()
            be = find_matching(text, bs, "{", "}")
            out.append("{" + _compose_text_accents(text[bs + 1 : be]) + "}")
            i = be + 1
        text = "".join(out)
    return text


def _leqno_label(raw: str) -> str:
    """Normalise a \\leqno argument into a \\tag* text-mode body."""
    s = raw.strip()
    while s.startswith("{") and find_matching(s, 0, "{", "}") == len(s) - 1:
        s = s[1:-1].strip()
    if s.startswith("\\text"):
        b = s.find("{")
        if b != -1 and find_matching(s, b, "{", "}") == len(s) - 1:
            s = s[b + 1 : -1]
    return s


def rule_leqno(text: str) -> str:
    """Convert \\leqno equation labels to amsmath \\tag*{...} (MathJax-safe)."""
    text = re.sub(
        r"\$\$(?P<body>(?:(?!\$\$).)*?\\leqno(?![a-zA-Z])(?:(?!\$\$).)*?)\$\$",
        lambda m: r"\begin{equation*}" + m.group("body") + r"\end{equation*}",
        text,
        flags=re.DOTALL,
    )
    pattern = re.compile(r"\\leqno(?![a-zA-Z])\s*")
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        m = pattern.search(text, i)
        if m is None:
            out.append(text[i:])
            break
        out.append(text[i : m.start()])
        j = m.end()
        # skip leading spacing macros (\leqno\quad \textup{c)} -> \tag*{c)})
        while True:
            sm = re.match(r"\s*\\(?:qquad|quad|[,;:! ])\s*", text[j:])
            if not sm:
                break
            j += sm.end()
        if j < n and text[j] == "{":
            end = find_matching(text, j, "{", "}")
            out.append(r"\tag*{" + _leqno_label(text[j + 1 : end]) + "}")
            i = end + 1
        elif j < n and text[j] == "(":
            end = find_matching(text, j, "(", ")")
            out.append(r"\tag*{" + text[j : end + 1] + "}")
            i = end + 1
        elif text.startswith(r"\text", j):
            b = text.find("{", j)
            if b != -1:
                end = find_matching(text, b, "{", "}")
                out.append(r"\tag*{" + _leqno_label(text[j : end + 1]) + "}")
                i = end + 1
            else:
                out.append(r"\leqno")
                i = j
        else:
            out.append(r"\leqno")
            i = j
    return "".join(out)


# ---------------------------------------------------------------------------
# Corpus-specific \xymatrix patches — populated iteratively from sga1-check-errors
# (see the sga1-normalize-xymatrix catalogue). Start empty.
# ---------------------------------------------------------------------------
_XYMATRIX_PATCHES: list[tuple[str, str]] = []


def rule_xymatrix_patches(text: str) -> str:
    """Apply the durable XyJax-v3 \\xymatrix rewrites from the
    sga1-normalize-xymatrix catalogue (exact string replacements)."""
    misses = []
    for old, new in _XYMATRIX_PATCHES:
        if old in text:
            text = text.replace(old, new)
        else:
            misses.append(repr(old[:48]))
    if misses:
        print(
            "WARNING rule_xymatrix_patches: %d patch(es) did not match:\n  %s"
            % (len(misses), "\n  ".join(misses)),
            file=sys.stderr,
        )
    return text


RULES = [
    rule_marginpar,
    rule_oldindexnot,
    rule_altabstract,
    rule_abstract,
    rule_alt_metadata,
    rule_title_metadata,
    rule_makeschapterhead,
    rule_smf_sectioning,
    rule_sfootnote,
    rule_ref,
    rule_ptbl,
    rule_size_macros,
    rule_stepcounter,
    rule_kern,
    rule_protect,
    rule_nobreak,
    rule_allowbreak,
    rule_sideset,
    rule_parbox,
    rule_xymatrix_safe,
    rule_xymatrix_reorder,
    rule_leqno,
    rule_text_mode_accents,   # after leqno: \`u/\'e in \text/\tag* -> Unicode
    rule_xymatrix_patches,    # last: corpus-specific XyJax-v3 diagram rewrites
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()

    text = args.input.read_text(encoding="utf-8")
    before = len(text)
    for rule in RULES:
        text = rule(text)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(
        f"inlined macros: {before:,} → {len(text):,} chars "
        f"({before - len(text):,} removed) → {args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
