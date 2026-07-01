#!/usr/bin/env python3
"""Inline / strip editorial macros and presentation commands.

Operates on the post-\\sisi-resolution staged file. Only touches the
SGA2-specific editorial layer; math/content macros (\\Hom, \\Pic, \\SGA,
\\og, ...) are left intact and defined in sga2-macros.sty by the
sga2-build-main skill.
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
        # optional [...] argument
        if j < n and text[j] == "[":
            j = find_matching(text, j, "[", "]") + 1
        # optional {...} argument
        if j < n and text[j] == "{":
            j = find_matching(text, j, "{", "}") + 1
        i = j
    return "".join(out)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def rule_ref(text: str) -> str:
    return replace_command_with_arg(text, "Ref", lambda a: r"\ref{" + a + "}")


def rule_ptbl(text: str) -> str:
    # \ptbl renders as "." + thin space
    return re.sub(r"\\ptbl(?![a-zA-Z])", r".\,", text)


def rule_sheaf(text: str) -> str:
    # Original sga2-smf.sty: \def\sheaf#1{\protect\underline{#1}} — sheafified
    # functors are underlined, NOT script. (\mathcal is \let to \mathscr in the
    # macros, so \mathcal{X} would render as rsfs script and silently drop the
    # underline — and produce nothing for Greek args like \sheaf{\Gamma}.)
    return replace_command_with_arg(text, "sheaf", lambda a: r"\underline{" + a + "}")


def rule_rest(text: str) -> str:
    return replace_command_with_arg(text, "rest", lambda a: r"|_{" + a + "}")


def rule_makeschapterhead(text: str) -> str:
    return replace_command_with_arg(text, "makeschapterhead",
                                    lambda a: r"\chapter*{" + a + "}")


def rule_pageoriginale(text: str) -> str:
    # zero-arg macro \pageoriginale (and the aliased \pageoriginaled)
    text = drop_command_no_arg(text, "pageoriginaled")
    text = drop_command_no_arg(text, "pageoriginale")
    return text


def rule_nde(text: str) -> str:
    text = drop_command_with_arg(text, "ndetext")
    text = drop_command_with_arg(text, "nde")
    return text


def rule_sfootnote(text: str) -> str:
    text = replace_command_with_arg(text, "sfootnote",
                                    lambda a: r"\footnote{" + a + "}")
    # sfootnotemark / sfootnotetext are rare; drop if present
    text = drop_optional_then_brace(text, "sfootnotetext")
    text = drop_command_no_arg(text, "sfootnotemark")
    return text


def rule_manyfoot(text: str) -> str:
    text = drop_optional_then_brace(text, "Footnotetext")
    text = drop_optional_then_brace(text, "Footnotemark")
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
    """\\smaller and \\larger are SMF class commands; map to plain LaTeX."""
    text = re.sub(r"\\smaller(?![a-zA-Z])", r"\\small", text)
    text = re.sub(r"\\larger(?![a-zA-Z])", r"\\large", text)
    return text


def rule_arrow_macros(text: str) -> str:
    """Inline \\hto, \\mlto{#1}, \\mfrom to MathJax-portable equivalents.

    Originals expand to \\joinrel / \\mapstochar, which MathJax 3 doesn't
    recognize. pdflatex renders these replacements identically (or near-so
    for \\mfrom, where ↢ stands in for the composed ↤).
    """
    text = re.sub(r"\\hto(?![a-zA-Z])", r"\\hookrightarrow", text)
    text = re.sub(r"\\mfrom(?![a-zA-Z])", r"\\leftarrowtail", text)
    text = replace_command_with_arg(
        text, "mlto", lambda a: r"\overset{" + a + r"}{\mapsto}"
    )
    return text


def rule_sheaf_operators(text: str) -> str:
    """Inline \\h, \\SheafH, \\SheafHom, \\SheafExt past \\operatorname.

    The originals expand (via \\DeclareMathOperator in sga2-macros.sty) to
    \\operatorname{\\underline{...}}, which XyJax-v3 cannot reparse inside
    \\xymatrix cells. \\mathop{...}\\nolimits is what \\operatorname expands
    to internally, so pdflatex output stays identical.
    """
    text = re.sub(r"\\SheafExt(?![a-zA-Z])", r"\\mathop{\\underline{\\mathrm{Ext}}}\\nolimits", text)
    text = re.sub(r"\\SheafHom(?![a-zA-Z])", r"\\mathop{\\underline{\\mathrm{Hom}}}\\nolimits", text)
    text = re.sub(r"\\SheafH(?![a-zA-Z])",   r"\\mathop{\\underline{\\mathrm{H}}}\\nolimits",   text)
    text = re.sub(r"\\h(?![a-zA-Z])",        r"\\mathop{\\underline{\\mathrm{H}}}\\nolimits",   text)
    return text


def rule_xymatrix_safe(text: str) -> str:
    """Inside \\xymatrix{...} bodies, rewrite operator-class macros to
    XyJax-parseable equivalents.

    XyJax-v3 inside diagram cells parses only plain math primitives — it
    cannot handle \\mathop{...}\\nolimits or \\operatorname{...}. Outside
    xymatrix those forms render correctly under regular MathJax and
    pdfLaTeX, so we leave them alone there to preserve operator-class
    spacing across the rest of the document.

    Must run AFTER rule_sheaf_operators (which produces the
    \\mathop{\\underline{\\mathrm{X}}}\\nolimits forms this rule rewrites).
    Operates on raw \\R; the .sty's \\DeclareMathOperator{\\R}{R} would
    otherwise emit \\operatorname{R} when the macro is expanded.
    """
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
        body = re.sub(
            r"\\mathop\{(\\underline\{\\mathrm\{(?:H|Hom|Ext)\}\})\}\\nolimits",
            r"\1",
            body,
        )
        body = re.sub(r"\\R(?![a-zA-Z])", r"\\mathrm{R}", body)
        out.append(body)
        i = brace_end + 1
    return "".join(out)


def rule_text_abbreviations(text: str) -> str:
    """Inline \\cf / \\Cf / \\ie / \\resp without trailing \\space.

    The .sty definitions append \\space, which MathJax 3 rejects inside
    \\text{...}. Source-level whitespace after the macro call is preserved
    by this substitution, so pdflatex output is unchanged.
    """
    text = re.sub(r"\\cf(?![a-zA-Z])",   r"cf.",   text)
    text = re.sub(r"\\Cf(?![a-zA-Z])",   r"Cf.",   text)
    text = re.sub(r"\\ie(?![a-zA-Z])",   r"i.e.",  text)
    text = re.sub(r"\\resp(?![a-zA-Z])", r"resp.", text)
    return text


def rule_underline_operator(text: str) -> str:
    """Brace \\underline\\H so \\H's expansion to \\operatorname{H} isn't
    swallowed as \\underline's lone-token argument."""
    return re.sub(r"\\underline\s*\\H(?![a-zA-Z])", r"\\underline{\\H}", text)


def rule_stepcounter(text: str) -> str:
    """Drop \\stepcounter{...}. The HTML converter passes it through into
    displaymath bodies where MathJax renders it as literal text. HTML equation
    numbering is converter-driven and unaffected; pdflatex loses a cosmetic
    counter bump but \\ref{...} cross-references resolve via labels and stay
    consistent.
    """
    return drop_command_with_arg(text, "stepcounter")


def rule_numberwithin(text: str) -> str:
    """Rewrite \\numberwithin{X}{Y} to an explicit reset + format pair.

    amsmath's ``\\numberwithin`` is avoided here because this tree
    ``\\renewcommand``s ``\\thesection`` / ``\\thesubsection`` in sga2-macros.sty
    (storing them as plain macros, not formatted counters), which breaks
    ``\\numberwithin``'s counter-format lookup in some processors. So we split
    ``\\numberwithin`` into its two underlying LaTeX effects:

      * ``\\@addtoreset{X}{Y}`` — reset counter X whenever Y steps;
      * ``\\renewcommand{\\theX}{\\theY.\\arabic{X}}`` — the within-Y format.

    Both are honoured by pdflatex, where ``\\@addtoreset`` is a LaTeX kernel
    primitive. A downstream HTML converter that does not model the kernel's
    cumulative reset list should treat ``\\@addtoreset`` as a two-argument no-op
    so its arguments are consumed rather than leaked as the visible word
    ``equationsection`` / ``equationsubsection``; this also avoids clashing with
    the manual ``\\setcounter{equation}{N}`` numbering in chapters like IX. The
    ``\\renewcommand`` half supplies the within-section display format.
    """
    def replace(m: re.Match[str]) -> str:
        inner, outer = m.group(1), m.group(2)
        return (
            f"\\makeatletter\\@addtoreset{{{inner}}}{{{outer}}}\\makeatother"
            f"\\renewcommand{{\\the{inner}}}{{\\the{outer}.\\arabic{{{inner}}}}}"
        )
    return re.sub(
        r"\\numberwithin\s*\{(\w+)\}\s*\{(\w+)\}",
        replace,
        text,
    )


def rule_english_preface(text: str) -> str:
    """Drop the English preface block.

    The French preface ends with `\\begin{flushright}L'\\'editeur, Yves
    Laszlo.\\end{flushright}` and the English preface ends with
    `\\begin{flushright}The editor, Yves Laszlo.\\end{flushright}`.
    Everything between (exclusive of the French closer, inclusive of the
    English closer) is dropped.
    """
    fr_pat = re.compile(
        r"\\begin\{flushright\}\s*L'\\'editeur,\s*Yves\s+Laszlo\.\s*\\end\{flushright\}",
        re.MULTILINE,
    )
    en_pat = re.compile(
        r"\\begin\{flushright\}\s*The\s+editor,\s*Yves\s+Laszlo\.\s*\\end\{flushright\}",
        re.MULTILINE,
    )
    fr = fr_pat.search(text)
    en = en_pat.search(text)
    if fr is None or en is None:
        return text
    return text[: fr.end()] + text[en.end():]


def rule_protect(text: str) -> str:
    """Strip \\protect fragile-command guards.

    They survive into the math of chapter/section titles (e.g. chapter 6's
    `$\\protect\\Ext^{\\protect\\boule}_Z...$`), which the HTML converter
    replicates into every file's table of contents, where MathJax then renders `\\protect` as
    literal text. The guarded tokens (\\Ext, \\boule, \\mathop, \\ndemark) are
    robust in the modern preamble, so dropping the guard is safe for pdflatex
    too. `(?![a-zA-Z])` keeps \\protected@file@percent untouched.
    """
    return drop_command_no_arg(text, "protect")


def rule_nobreak(text: str) -> str:
    """Strip \\nobreak line-break penalties left inside math.

    Meaningless for HTML math output and leaked as literal text by MathJax
    (e.g. `\\in\\nobreak X`, `=\\nobreak0`). Every occurrence is followed by a
    space or a token, so no tokens fuse.
    """
    return drop_command_no_arg(text, "nobreak")


def rule_boule(text: str) -> str:
    """Replace \\boule with a plain \\bullet superscript.

    \\boule is `{\\raisebox{0.2ex}{$\\scriptscriptstyle\\bullet$}}`; MathJax
    has no \\raisebox, so the token leaks, and in an inline superscript the HTML
    converter emits an empty `<sup>` that fractures the formula and strands the rest
    (e.g. `\\operatorname{Ext}`) as visible text. Every use is a cochain-degree
    superscript (`X^\\boule`, `^{\\boule}`, `^{\\boule\\boule}`), so the plain
    `\\bullet` superscript is the standard, MathJax-safe rendering.
    """
    return re.sub(r"\\boule(?![a-zA-Z])", r"\\bullet", text)


def rule_uH(text: str) -> str:
    """Replace \\uH with a \\raisebox-free underset-tilde H.

    \\uH is `\\underset{\\raisebox{1pt}{$\\sim$}}{\\mathrm{H}}`; MathJax has no
    \\raisebox, so the token leaks (chapter 5 uses, e.g. `\\uH^{\\bullet}`).
    `\\underset{\\sim}{\\mathrm{H}}` renders the same H-with-tilde-below and is
    MathJax-safe; the \\raisebox was only vertical fine-tuning.
    """
    return re.sub(r"\\uH(?![a-zA-Z])", r"\\underset{\\sim}{\\mathrm{H}}", text)


# LaTeX text-mode symbol-accent command -> Unicode combining mark.
# Only the symbol accents (\' \` \^ \" \~ \= \.) are handled: a backslash
# followed by one of these punctuation chars is *unambiguously* a text-mode
# accent in this corpus (letter-named accents like \c, \v never appear inside
# the math-mode text containers this rule targets).
_TEXT_ACCENT_COMBINING = {
    "'": "́",  # acute      -> é
    "`": "̀",  # grave      -> è à ù
    "^": "̂",  # circumflex -> ô ê
    '"': "̈",  # diaeresis  -> ï ë
    "~": "̃",  # tilde      -> ñ
    "=": "̄",  # macron
    ".": "̇",  # dot above
}
# Accent base \i / \j: the precomposed accented forms (î, ï, ĵ, …) use the
# dotted letter — the accent replaces the dot — so compose from i / j.
_ACCENT_DOTLESS = {r"\i": "i", r"\j": "j"}


def _compose_text_accents(s: str) -> str:
    """Replace LaTeX text-accent macros (\\'e, \\`u, \\^{o}, \\^{\\i}, …) in a
    text-mode string with precomposed Unicode (é, ù, ô, î).

    Output-identical under pdflatex (utf8 inputenc) and the HTML converter; the win is for
    MathJax, whose textmacros extension renders \\` as a detached, mis-placed
    spacing glyph (U+2035) instead of an accented letter.
    """
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            nxt = s[i + 1]
            if nxt == "\\":            # \\ line break: emit verbatim
                out.append("\\\\")
                i += 2
                continue
            if nxt in _TEXT_ACCENT_COMBINING:
                comb = _TEXT_ACCENT_COMBINING[nxt]
                j = i + 2
                base = None
                end_at = None
                if j < n and s[j] == "{":               # \'{e}  \^{\i}
                    e = find_matching(s, j, "{", "}")
                    inner = s[j + 1 : e].strip()
                    inner = _ACCENT_DOTLESS.get(inner, inner)
                    if len(inner) == 1:
                        base, end_at = inner, e + 1
                elif s.startswith(r"\i", j) or s.startswith(r"\j", j):  # \^\i
                    base, end_at = _ACCENT_DOTLESS[s[j : j + 2]], j + 2
                elif j < n and s[j].isalpha():           # \'e
                    base, end_at = s[j], j + 1
                if base is not None:
                    out.append(unicodedata.normalize("NFC", base + comb))
                    i = end_at
                    continue
        out.append(c)
        i += 1
    return "".join(out)


# Text-mode containers whose argument may carry an accent that reaches MathJax
# when the container sits inside math (\text, \textup{\'et} subscript, \hbox in
# eqnarray, \tag* from \leqno). The \textXX style family and \emph are included
# so the conversion is uniform; it is output-preserving in running text too.
_TEXT_ACCENT_COMMANDS = (
    "text", "textup", "textit", "textbf", "textsc", "textrm", "textsf",
    "textsl", "textmd", "textnormal", "textsuperscript", "emph", "hbox",
    "mbox", "tag",
)


def rule_text_mode_accents(text: str) -> str:
    """Convert LaTeX text-accent macros to precomposed Unicode inside text-mode
    command arguments.

    MathJax's textmacros extension mis-renders \\`u / \\'e inside \\text{...}
    (the accent detaches into a floating U+2035/U+00B4 glyph and a literal
    backtick leaks into the accessibility text). Precomposed Unicode renders as
    one correctly-placed glyph. The HTML converter already converts these accents in
    running text, but leaves math verbatim for MathJax — so the breakage is
    confined to accents inside math-mode text containers; converting the
    container arguments here is the durable fix.

    Handles the starred form (\\tag*{...}). Runs after rule_leqno, which is what
    produces the \\tag*{d'o\\`u} labels.
    """
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
            out.append(text[i : m.end()])           # command token (+ optional *)
            bs = m.end()
            be = find_matching(text, bs, "{", "}")
            out.append("{" + _compose_text_accents(text[bs + 1 : be]) + "}")
            i = be + 1
        text = "".join(out)
    return text


def rule_et_macro(text: str) -> str:
    """Inline \\et (étale abbreviation) to its MathJax-safe Unicode form.

    sga2-macros.sty defines \\et as `{\\textup{\\'et}}`; the HTML converter expands it inside
    math (X_{\\et}, \\prof \\et(X)), where MathJax's textmacros renders the \\'e
    as a detached, floating acute glyph. `{\\textup{ét}}` (precomposed Unicode)
    is byte-for-byte the same upright "ét" under pdflatex and renders as one
    clean glyph under MathJax. Per the no-.sty-edits policy, inline here rather
    than redefining the macro. `(?![a-zA-Z])` keeps \\eta / \\etale untouched.
    """
    return re.sub(r"\\et(?![a-zA-Z])", r"{\\textup{ét}}", text)


def rule_logic_connectives(text: str) -> str:
    """Inline \\SSI / \\ALORS without the leaking text primitives.

    Their .sty definitions are `\\unskip~$\\Ssi$~\\ignorespaces` /
    `\\unskip~$\\To$~\\ignorespaces`; when used inside \\text{...} in display
    math (chapter 14), the \\unskip / \\ignorespaces primitives leak into
    MathJax. The `~$\\Ssi$~` / `~$\\To$~` form (same symbol, same thin spaces,
    minus the primitives) is valid both in running text and inside \\text{...},
    and \\Ssi / \\To remain defined in the .sty.
    """
    text = re.sub(r"\\SSI(?![a-zA-Z])",   r"~$\\Ssi$~", text)
    text = re.sub(r"\\ALORS(?![a-zA-Z])", r"~$\\To$~",  text)
    return text


def rule_footnote_out_of_display(text: str) -> str:
    """Relocate a \\footnote{...} that sits inside a $$...$$ display.

    \\footnote cannot live in math mode; MathJax leaks the \\footnote token and
    its text-mode contents (\\emph, \\numero -> \\textsuperscript). The one
    occurrence (chapter 13: `... i\\ge s.{}\\footnote{...}` just before the
    closing $$) is moved to immediately before the opening $$, where it attaches
    to the preceding paragraph text (horizontal mode, valid for \\footnote).

    Narrowly targets only a \\footnote whose brace-balanced argument is followed
    by $$ and which lies inside a balanced $$...$$ pair; a no-op everywhere else.
    Must run after rule_sfootnote (which produces \\footnote).
    """
    pattern = re.compile(r"\\footnote(?![a-zA-Z])\s*(?=\{)")
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        m = pattern.search(text, i)
        if m is None:
            out.append(text[i:])
            break
        brace_end = find_matching(text, m.end(), "{", "}")
        # Is the footnote immediately (modulo whitespace) followed by a $$ close?
        k = brace_end + 1
        while k < n and text[k] in " \t\r\n":
            k += 1
        followed_by_dd = text.startswith("$$", k)
        # Nearest preceding $$ — must be a display opener (even number of $$
        # before it) with no other $$ between it and the footnote.
        open_dd = text.rfind("$$", 0, m.start())
        in_display = (
            followed_by_dd
            and open_dd != -1
            and text.count("$$", 0, open_dd) % 2 == 0
            and text.find("$$", open_dd + 2, m.start()) == -1
        )
        if not in_display:
            out.append(text[i : brace_end + 1])
            i = brace_end + 1
            continue
        footnote = text[m.start() : brace_end + 1]
        out.append(text[i:open_dd])           # text before the $$ opener
        out.append(footnote)                  # footnote now in horizontal mode
        out.append(text[open_dd : m.start()])  # $$ + display body up to footnote
        i = brace_end + 1                      # drop footnote from inside math
    return "".join(out)


def _leqno_label(raw: str) -> str:
    """Normalise a \\leqno argument into a \\tag* text-mode body.

    \\tag* processes its argument in text mode (in both amsmath and MathJax),
    so a nested \\text{...} is wrong — MathJax raises "\\text is only supported
    in math mode". Strip fully-matched outer braces and unwrap one enclosing
    \\text{...}; a paren form like (26) passes through unchanged.
    """
    s = raw.strip()
    while s.startswith("{") and find_matching(s, 0, "{", "}") == len(s) - 1:
        s = s[1:-1].strip()
    if s.startswith("\\text"):
        b = s.find("{")
        if b != -1 and find_matching(s, b, "{", "}") == len(s) - 1:
            s = s[b + 1 : -1]
    return s


def rule_leqno(text: str) -> str:
    """Convert \\leqno equation labels to amsmath \\tag*{...}.

    \\leqno leaks under MathJax. \\tag* is both pdflatex- (amsmath is loaded)
    and MathJax-safe. Placement moves from left to the default right. Handles
    the three argument forms found in the source and promotes the single plain
    $$...$$ display (chapter 5) to equation*, where \\tag* is valid:
      \\leqno{{\\text{d'ou}}} -> \\tag*{d'ou}
      \\leqno\\text{et}       -> \\tag*{et}
      \\leqno(26)             -> \\tag*{(26)}
    The \\text{...} wrapper (needed because \\leqno's arg was math mode) is
    unwrapped by _leqno_label, since \\tag*'s arg is already text mode.
    """
    # Promote a plain $$...\leqno(..)..$$ display to equation* (so \tag* is
    # valid). Only the paren form occurs in a $$ display; the brace/\text forms
    # are already inside equation*. (?!\$\$) keeps the match within one display.
    text = re.sub(
        r"\$\$(?P<body>(?:(?!\$\$).)*?\\leqno\s*\((?:(?!\$\$).)*?)\$\$",
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
            else:  # unexpected; leave untouched
                out.append(r"\leqno")
                i = j
        else:  # unrecognised form; leave untouched
            out.append(r"\leqno")
            i = j
    return "".join(out)


_XYMATRIX_PATCHES = [
    # XyJax-v3 \xymatrix rewrites — see the sga2-normalize-xymatrix catalogue
    # for the per-category rationale. Each is pdflatex-output-preserving.

    # IV-2 (c): drop the space inside the \dir hookrightarrow
    (r"\ar@{^{ (}->}", r"\ar@{^{(}->}"),

    # X-2 / X-3 (b): \UseTips/\newdir are unsupported; default arrow tips suffice
    (r"\UseTips \newdir{ >}{!/-5pt/\dir{>}} ", r""),

    # X-3 (e): primes -> ^{\prime}
    (r"\xymatrix{ X' & X\ar[l] && \Et(X')",
     r"\xymatrix{ X^{\prime} & X\ar[l] && \Et(X^{\prime})"),
    (r"Y'\ar[u] & Y\ar[l] \ar[u] && \Et(Y')",
     r"Y^{\prime}\ar[u] & Y\ar[l] \ar[u] && \Et(Y^{\prime})"),

    # XI-3 (h): operator \Pic(..) -> brace-wrapped \mathrm
    (r"\xymatrix{\Pic(X)\ar[rr]\ar[dr]&&\Pic(X_n)\\&\Pic(U)\ar[ur]&}",
     r"\xymatrix{{\mathrm{Pic}(X)}\ar[rr]\ar[dr]&&{\mathrm{Pic}(X_n)}\\&{\mathrm{Pic}(U)}\ar[ur]&}"),

    # XIV-1 #1 (a)+(g)+(j): {}\ar[r] at row starts; wrap each script-bearing
    # cell-object in {..} so XyJax-v3 takes it as one opaque math object (a bare
    # \underline{...} carrying both _ and ^ otherwise trips its cell parser).
    (r"\xymatrix{ \ar[r]&f^*({\underline{\mathrm{H}}}_Z^i(F))\ar[r]\ar[d]& f^*({\underline{\mathrm{H}}}^i(F))\ar[r]\ar[d]^{\wr} &f^*({\underline{\mathrm{H}}}^i(\mathrm{R} j_*(j^*F)))\ar[r]\ar[d]& ",
     r"\xymatrix{ {}\ar[r]&{f^*(\underline{\mathrm{H}}_Z^i(F))}\ar[r]\ar[d]& {f^*(\underline{\mathrm{H}}^i(F))}\ar[r]\ar[d]^{\wr} &{f^*(\underline{\mathrm{H}}^i(\mathrm{R} j_*(j^*F)))}\ar[r]\ar[d]& "),
    (r"\ar[r] &{\underline{\mathrm{H}}}_T^i(f^*F)\ar[r]& {\underline{\mathrm{H}}}^i(f^*F) \ar[r]&{\underline{\mathrm{H}}}^i(\mathrm{R} k_*(k^*f^*F)) \ar[r]&\text{;}}",
     r"{}\ar[r] &{\underline{\mathrm{H}}_T^i(f^*F)}\ar[r]& {\underline{\mathrm{H}}^i(f^*F)} \ar[r]&{\underline{\mathrm{H}}^i(\mathrm{R} k_*(k^*f^*F))} \ar[r]&\text{;}}"),

    # XIV-1 #2 (e)+(g)+(j): primes; wrap each script-bearing cell-object in {..}
    (r"\xymatrix{f^*E_2^{p, q}=f^*(\mathrm{R}^pj_*({\underline{\mathrm{H}}}^q(j^*F)))\ar@{=>} [r]\ar[d]&f^*({\underline{\mathrm{H}}}^*(\mathrm{R} j_*(j^*F)))\ar[d]",
     r"\xymatrix{{f^*E_2^{p, q}=f^*(\mathrm{R}^pj_*(\underline{\mathrm{H}}^q(j^*F)))}\ar@{=>} [r]\ar[d]&{f^*(\underline{\mathrm{H}}^*(\mathrm{R} j_*(j^*F)))}\ar[d]"),
    (r"E'^{p, q}_2=\mathrm{R}^pk_*({\underline{\mathrm{H}}}^q(k^*f^*F))\ar@{=>}[r]&{\underline{\mathrm{H}}}^*(\mathrm{R} k_*(k^*f^*F)).}",
     r"{E^{\prime p, q}_2=\mathrm{R}^pk_*(\underline{\mathrm{H}}^q(k^*f^*F))}\ar@{=>}[r]&{\underline{\mathrm{H}}^*(\mathrm{R} k_*(k^*f^*F)).}}"),

    # IX-1 (d)+(f)+(e): unwrap array{c}; reorder \ar[l] Y -> Y \ar[l]; primes
    (r"""\begin{equation} \label{eq:IX.1.1}
\begin{array}{c}
\xymatrix{ X \ar[d]_f & \ar[l] Y \ar[d]& &\hat{X}\ar[d]_{\hat f} \ar[r]^j & X\ar[d]^f &\\
X' & \ar[l] Y' &, &\hat{X'} \ar[r]^i & X'.
}
\end{array}
\end{equation}""",
     r"""\begin{equation} \label{eq:IX.1.1}
\xymatrix{ X \ar[d]_f & Y \ar[l] \ar[d]& &\hat{X}\ar[d]_{\hat f} \ar[r]^j & X\ar[d]^f &\\
X^{\prime} & Y^{\prime} \ar[l] &, &\hat{X^{\prime}} \ar[r]^i & X^{\prime}.
}
\end{equation}"""),

    # XII-4 #1 (e)+(f): primes; reorder \ar[l] U' -> U' \ar[l]
    (r"""\xymatrix{
X'\ar[d]_f&\ar[l]_-{i'} U'\ar[d]^g \\
X&\ar[l]_-{i} U
}""",
     r"""\xymatrix{
X^{\prime}\ar[d]_f&U^{\prime}\ar[l]_-{i^{\prime}}\ar[d]^g \\
X&U\ar[l]_-{i}
}"""),

    # XII-4 #2 (e)+(f)
    (r"""\xymatrix{
X'_0\ar[d]_{f_0}&\ar[l]_-{i'_0} U'_0\ar[d]^{g_0} \\
X_0&\ar[l]_-{i_0} U_0
}""",
     r"""\xymatrix{
X^{\prime}_0\ar[d]_{f_0}&U^{\prime}_0\ar[l]_-{i^{\prime}_0}\ar[d]^{g_0} \\
X_0&U_0\ar[l]_-{i_0}
}"""),

    # XIV-3 #1 (h)+(j): \Spec -> \mathrm{Spec}\,, and wrap each cell-object in
    # {..} — a bare \mathrm{Spec}\,L trips XyJax (the \, after the operator),
    # so the whole "operator + thinspace + arg" must be one braced object.
    (r"""\xymatrix{
&{\Spec L}\ar[dl]_v\ar[dr]^u&\\
{\Spec k_i} \ar[rr]^w &{}&{\Spec k}\,,
}""",
     r"""\xymatrix{
&{\mathrm{Spec}\,L}\ar[dl]_v\ar[dr]^u&\\
{\mathrm{Spec}\,k_i} \ar[rr]^w &{}&{\mathrm{Spec}\,k\,,}
}"""),

    # XIV-3 #2 (e)+(i): primes; drop outer braces on cell-objects
    (r"""\xymatrix{
{X'}\ar[r]^h\ar[d]_{f'} &{X}\ar[d]^f\\
{S'}\ar[r]^g &{S}\,,
}""",
     r"""\xymatrix{
X^{\prime}\ar[r]^h\ar[d]_{f^{\prime}} &X\ar[d]^f\\
S^{\prime}\ar[r]^g &S\,,
}"""),

    # IV-1 (e)+(j): prime -> ^{\prime}; wrap the \ccat cell-objects (a bare
    # \underline{...} carrying a script as a cell-object trips XyJax-v3).
    # \ccat/\Ab expand later (in the HTML converter) to \underline{\mathrm{C}}/
    # \underline{\mathrm{Ab}}; the brace wrap survives that expansion.
    (r"""\xymatrix{ \ccat^{\circ}\ar^{T}[rr]\ar_{T_{\circ}}[dr]&&\Ab\\
&\ccat'\ar[ur]&}""",
     r"""\xymatrix{ {\ccat^{\circ}}\ar^{T}[rr]\ar_{T_{\circ}}[dr]&&\Ab\\
&{\ccat^{\prime}}\ar[ur]&}"""),

    # IV-3 (j): wrap cell-objects — \ccat^{\circ}_{Y} (double script) and the
    # \Ab\,. cell (the \, after the object also needs to be inside the braces).
    (r"""\xymatrix@C=6mm@R=6mm{
\ccat^{\circ}_{Y}\ar[dr]\ar^{T}[rr]&&\Ab\,.\\
&\ccat_{Y}\ar[ur]&}""",
     r"""\xymatrix@C=6mm@R=6mm{
{\ccat^{\circ}_{Y}}\ar[dr]\ar^{T}[rr]&&{\Ab\,.}\\
&{\ccat_{Y}}\ar[ur]&}"""),

    # XIV-1 #3 (j): wrap each script-bearing cell-object; \mathrm{R}^1j_*(..)
    # (leading superscript on the cell-object) is what trips XyJax here.
    (r"""\xymatrix@R=5mm{f^*(k_*k^*F)\ar[r]\ar[d]&f^*G\ar[r]\ar[d]^b&1\\
j_*(g^*(k_*k^*F))\ar[r]&j_*(g^*G)\ar[r]&\mathrm{R}^1j_*(g^*F) \ar[r]&\mathrm{R}^1j_*(g^*(k_*k^*F)).}""",
     r"""\xymatrix@R=5mm{{f^*(k_*k^*F)}\ar[r]\ar[d]&{f^*G}\ar[r]\ar[d]^b&1\\
{j_*(g^*(k_*k^*F))}\ar[r]&{j_*(g^*G)}\ar[r]&{\mathrm{R}^1j_*(g^*F)} \ar[r]&{\mathrm{R}^1j_*(g^*(k_*k^*F)).}}"""),

    # XIV-2 #1 (e): primes -> ^{\prime} (appears 3x identically). The \\S' row
    # break is left as \\S^{\prime}; the converter's \\-tokenisation fix keeps
    # the row break intact (it formerly mis-expanded \\S' -> \§').
    (r"\xymatrix{X'\ar[r]^{h}\ar[d]_{f'}&X\ar[d]^f\\S'\ar[r]^g&S}",
     r"\xymatrix{X^{\prime}\ar[r]^{h}\ar[d]_{f^{\prime}}&X\ar[d]^f\\S^{\prime}\ar[r]^g&S}"),

    # XIV-2 #2 (e)+(h): primes; \Spec k(s) -> wrapped \mathrm{Spec}\,k(s)
    (r"\xymatrix{Z'\ar[r]\ar[d]&Z\ar[d]\\S'_s\ar[r]&\Spec k(s)}",
     r"\xymatrix{Z^{\prime}\ar[r]\ar[d]&Z\ar[d]\\S^{\prime}_s\ar[r]&{\mathrm{Spec}\,k(s)}}"),
]


def rule_xymatrix_patches(text: str) -> str:
    """Re-apply the XyJax-v3 \\xymatrix rewrites from the sga2-normalize-xymatrix
    catalogue as durable pipeline patches.

    These were formerly hand-applied to chapter-NN.tex after the split and were
    lost whenever the pipeline regenerated those files. Encoding them here keeps
    them durable. Runs last, so each patch matches the fully-inlined text (e.g.
    after rule_xymatrix_safe has turned \\R into \\mathrm{R}).
    """
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


def rule_inmath_refs(text: str) -> str:
    """Replace ``\\ref``/``\\eqref`` that survive INSIDE a MathJax-processed equation.

    MathJax cannot resolve the converter's document labels, so a ``\\ref`` left inside a
    ``\\tag{}`` or ``\\text{}`` within an equation renders as ``???``. Substitute the
    literal cross-reference text, scoped to the exact surrounding token so prose links
    to the same labels (which the HTML converter resolves fine) are untouched. Must run after
    ``rule_ref`` (which lowercases ``\\Ref`` -> ``\\ref``).
    """
    subs = [
        (r"\tag{\ref{eq:I.23}}", r"\tag{23 bis}"),
        (r"\text{(cf. (\ref{eq:VIII.2.2})).}", r"\text{(cf. (2.2)).}"),
        (r"\text{(cf. \ref{eq:IX.1.10}).}", r"\text{(cf. 1.10).}"),
        (r"cf. \ref{XIV.3.1})}", r"cf. 3.1)}"),
        (r"\eqref{eq:XIV.4.2.***}}", r"(***)}"),
    ]
    for a, b in subs:
        text = text.replace(a, b)
    return text


def rule_inmath_textup(text: str) -> str:
    """Unwrap a \\textup{..} sitting inside a math \\text{..}.

    Inside \\text{} in math, MathJax's textmacros leaves \\textup as a literal
    token in the assistive MathML mirror (the visible glyphs are fine). \\text
    already renders upright, so dropping the wrapper is output-identical under
    pdflatex and the HTML converter. The sole in-math occurrence is chapter 14's
    equivalence display. \\textup elsewhere (running text, or math NOT inside
    \\text, e.g. $0_{\\textup{III}}$) renders cleanly and is left untouched.
    """
    return text.replace(
        r"\text{\textup{(ii)}$_{t}$~$\Ssi$~(***)}",
        r"\text{(ii)$_{t}$~$\Ssi$~(***)}",
    )


RULES = [
    rule_english_preface,   # before makeschapterhead transform
    rule_altabstract,
    rule_abstract,
    rule_alt_metadata,
    rule_title_metadata,
    rule_makeschapterhead,
    rule_nde,
    rule_sfootnote,
    rule_manyfoot,
    rule_pageoriginale,
    rule_ref,
    rule_sheaf,
    rule_rest,
    rule_ptbl,
    rule_size_macros,
    rule_arrow_macros,
    rule_sheaf_operators,
    rule_xymatrix_safe,
    rule_text_abbreviations,
    rule_underline_operator,
    rule_stepcounter,
    rule_numberwithin,
    # --- MathJax leaked-macro fixes ---
    rule_protect,                 # strip \protect (title-math TOC leaks)
    rule_nobreak,                 # strip \nobreak (math line-break penalty)
    rule_boule,                   # \boule -> \bullet (raisebox leak + math fracture)
    rule_uH,                      # \uH -> \underset{\sim}{\mathrm{H}} (raisebox leak)
    rule_et_macro,                # \et -> {\textup{ét}} (textmacros floating-accent leak)
    rule_logic_connectives,       # \SSI/\ALORS without \unskip/\ignorespaces
    rule_footnote_out_of_display,  # after rule_sfootnote: footnote out of $$...$$
    rule_leqno,                   # \leqno -> \tag* (+ $$ -> equation*)
    rule_text_mode_accents,       # after leqno: \`u/\'e in \text/\tag* -> Unicode
    rule_xymatrix_patches,        # last: XyJax-v3 diagram rewrites (durable)
    rule_inmath_refs,             # LAST: in-math \ref/\eqref -> literal (operates on final form)
    rule_inmath_textup,           # LAST: unwrap \textup inside math \text{}
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
