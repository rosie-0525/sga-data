#!/usr/bin/env python3
"""
sga2-convert-html: convert the normalized SGA2 LaTeX tree
(01-normalized_tex/) into JSON-with-embedded-HTML (02-converted_html/).

Pure Python standard library. Math is kept as LaTeX in \\(...\\) / \\[...\\]
for client-side MathJax 3 + XyJax-v3; the ~120 content macros from
sga2-macros.sty are expanded to plain LaTeX. Numbering and cross-references are
resolved authoritatively from main.aux.

Output (per the project schema, with clean readable ids):
  02-converted_html/fr.json                  manifest {toc, chapters, default_*}
  02-converted_html/fr/chapters/<id>.json    {chapter_id, title, pages[]}
  02-converted_html/en.json                  same manifest envelope
  02-converted_html/en/chapters/<id>.json    empty stubs (French is the reference)

Usage:
  python3 convert.py [--src DIR] [--out DIR] [--verify] [--only CHAPTERFILE]
"""

import argparse
import html
import json
import os
import re
import sys
import unicodedata


# --------------------------------------------------------------------------
# Section 1. main.aux parser -> labels, toc, bibcites
# --------------------------------------------------------------------------

def _strip_tex_braces(s):
    s = s.strip()
    while s.startswith('{') and s.endswith('}'):
        # only strip if the outer braces are balanced as a single group
        depth = 0
        ok = True
        for k, c in enumerate(s):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0 and k != len(s) - 1:
                    ok = False
                    break
        if ok:
            s = s[1:-1].strip()
        else:
            break
    return s


def _split_top_groups(s):
    """Split a string like '{a}{b}{c}' into ['a','b','c'] respecting brace depth."""
    groups = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] == '{':
            depth = 1
            j = i + 1
            while j < n and depth:
                if s[j] == '{':
                    depth += 1
                elif s[j] == '}':
                    depth -= 1
                j += 1
            groups.append(s[i + 1:j - 1])
            i = j
        else:
            i += 1
    return groups


def parse_aux(aux_path):
    """Return (labels, bibcites).

    labels[key] = {'num': raw, 'display': cleaned, 'anchor': hyperref anchor,
                   'kind': 'chapter'|'section'|'subsection'|'equation'|...}
    bibcites[key] = label string (e.g. '2').
    """
    labels = {}
    bibcites = {}
    if not os.path.exists(aux_path):
        return labels, bibcites
    text = open(aux_path, encoding='utf-8', errors='replace').read()

    for m in re.finditer(r'\\newlabel\{', text):
        start = m.end()
        # read the {key}
        key, after = _read_braced(text, start - 1)
        if key is None:
            continue
        body, after2 = _read_braced(text, after)
        if body is None:
            continue
        groups = _split_top_groups(body)
        # groups: [number, page, title, anchor, (extra)]
        num = groups[0] if len(groups) > 0 else ''
        anchor = groups[3] if len(groups) > 3 else ''
        num = num.strip()
        display = _clean_num_display(num)
        kind = anchor.split('.')[0] if anchor else ''
        labels[key] = {'num': num, 'display': display, 'anchor': anchor, 'kind': kind}

    for m in re.finditer(r'\\bibcite\{', text):
        key, after = _read_braced(text, m.end() - 1)
        if key is None:
            continue
        lab, _ = _read_braced(text, after)
        if lab is not None:
            bibcites[key] = _clean_num_display(lab.strip())
    return labels, bibcites


def _clean_num_display(num):
    """Turn an aux number like '{$8'$}', '$15'$', '{16 bis}' into '8\\'', '15\\'', '16 bis'."""
    s = _strip_tex_braces(num)
    s = s.replace('$', '')
    s = s.replace('\\,', '').replace('~', ' ')
    s = s.strip()
    return s


def _read_braced(s, i):
    """Given s[i] points at (or before) a '{', return (content, index_after_close).
    Skips leading spaces. Returns (None, i) if no group."""
    n = len(s)
    while i < n and s[i] in ' \t\r\n':
        i += 1
    if i >= n or s[i] != '{':
        return None, i
    depth = 0
    j = i
    while j < n:
        if s[j] == '{':
            depth += 1
        elif s[j] == '}':
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], n


# --------------------------------------------------------------------------
# Section 2. Math macro expansion (from sga2-macros.sty)
# --------------------------------------------------------------------------

# 0-argument math macros: name -> replacement (standard LaTeX/MathJax).
MATH_0ARG = {}
# script letters \Aa..\Zz  (\mathcal is \let to \mathscr)
for _u in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
    MATH_0ARG[_u.lower() + _u.lower()[0].upper()] = ''  # placeholder, overwritten below
MATH_0ARG = {}
for _c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
    MATH_0ARG[_c + _c.lower()] = r'\mathscr{%s}' % _c   # \Aa -> \mathscr{A} ... but key should be 'Aa'
# The macros are named \Aa \Bb ... so key is letter + lowercase-letter
MATH_0ARG = {}
for _c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
    MATH_0ARG['%s%s' % (_c, _c.lower())] = r'\mathscr{%s}' % _c

MATH_0ARG.update({
    'SheafI': r'\mathscr{I}',
    # bold letters
    'CC': r'\mathbf{C}', 'GG': r'\mathbf{G}', 'KK': r'\mathbf{K}', 'LL': r'\mathbf{L}',
    'NN': r'\mathbf{N}', 'PP': r'\mathbf{P}', 'QQ': r'\mathbf{Q}', 'bS': r'\mathbf{S}',
    'ZZ': r'\mathbf{Z}',
    # fraktur ideals
    'aaa': r'\mathfrak{a}', 'pp': r'\mathfrak{p}', 'qq': r'\mathfrak{q}',
    'rr': r'\mathfrak{r}', 'mm': r'\mathfrak{m}', 'm': r'\mathfrak{m}',
    'formelF': r'\mathfrak{F}', 'formelG': r'\mathfrak{G}', 'formelX': r'\mathfrak{X}',
    # sheaf / underlined notation
    'Ab': r'\underline{\mathrm{Ab}}', 'CJ': r'\underline{C}_J',
    'ccat': r'\underline{\mathrm{C}}', 'DDJ': r'\underline{D}_J',
    'cF': r'\underline{\mathrm{F}}', 'HH': r'\underline{H}',
    'SheafGamma': r'\underline{\Gamma}', 'Sheafphi': r'\underline{\varphi}',
    'uH': r'\underset{\sim}{\mathrm{H}}',
    # operators (DeclareMathOperator -> \operatorname)
    'Ann': r'\operatorname{Ann}', 'Ass': r'\operatorname{Ass}', 'Br': r'\operatorname{Br}',
    'cd': r'\operatorname{cd}', 'Cl': r'\operatorname{Cl}', 'codim': r'\operatorname{codim}',
    'codimh': r'\operatorname{codh}', 'coker': r'\operatorname{coker}',
    'colong': r'\operatorname{colong}', 'D': r'\operatorname{D}',
    'degtr': r'\operatorname{deg\,tr}', 'dimp': r'\operatorname{dp}', 'E': r'\operatorname{E}',
    'Ext': r'\operatorname{Ext}', 'Fa': r'\operatorname{F}', 'Frac': r'\operatorname{Frac}',
    'Ga': r'\operatorname{G}', 'geom': r'\operatorname{g\acute{e}om}',
    'gl': r'\operatorname{gl}', 'gr': r'\operatorname{gr}', 'rH': r'\operatorname{H}',
    'H': r'\operatorname{H}', 'Hom': r'\operatorname{Hom}', 'hop': r'\operatorname{hop}',
    'id': r'\operatorname{id}', 'Imm': r'\operatorname{Im}', 'Im': r'\operatorname{Im}',
    'Ker': r'\operatorname{Ker}', 'Lef': r'\operatorname{Lef}', 'Leff': r'\operatorname{Leff}',
    'leff': r'\operatorname{\ell eff}', 'longueur': r'\operatorname{long}',
    'Ob': r'\operatorname{Ob}', 'Pic': r'\operatorname{Pic}', 'prof': r'\operatorname{prof}',
    'profet': r'\operatorname{prof\;\acute{e}t}', 'profgeom': r'\operatorname{prof\;g\acute{e}om}',
    'Proj': r'\operatorname{Proj}', 'R': r'\operatorname{R}', 'rg': r'\operatorname{rg}',
    'Spec': r'\operatorname{Spec}', 'tr': r'\operatorname{tr}', 'variete': r'\operatorname{V}',
    'Supp': r'\operatorname{Supp}', 'supp': r'\operatorname{Supp}',
    'SheafExt': r'\underline{\operatorname{Ext}}', 'SheafH': r'\underline{\operatorname{H}}',
    'SheafHom': r'\underline{\operatorname{Hom}}', 'h': r'\underline{\operatorname{H}}',
    'SheafProj': r'\mathbf{Proj}', 'SheafPic': r'\mathbf{Pic}', 'catSch': r'\mathbf{Sch}',
    'Et': r'\mathbf{Et}', 'Isom': r'\mathrm{Isom}',
    'Annp': r'\mathrm{Ann}.\,', 'dimpt': r'\mathrm{dim}.\,',
    'codimpt': r'\mathrm{codim}.\,', 'profp': r'\mathrm{prof}.\,',
    'AssF': r'\mathrm{Ass}\,F',
    # misc shortcuts
    'boule': r'\bullet', 'OX': r'\mathscr{O}_X', 'Oo': r'\mathscr{O}',
    'OXx': r'\mathscr{O}_{X,x}', 'omx': r'\Omega_{X/k}', 'Lcal': r'L',
    'noo': r'{}^{\circ}',
    'bbmu': r'\boldsymbol{\mu}', 'bbf': r'\boldsymbol{f}', 'bbg': r'\boldsymbol{g}',
    'bbh': r'\boldsymbol{h}',
    # arrows
    'to': r'\mathchoice{\longrightarrow}{\rightarrow}{\rightarrow}{\rightarrow}',
    'from': r'\mathchoice{\longleftarrow}{\leftarrow}{\leftarrow}{\leftarrow}',
    'mto': r'\mathchoice{\longmapsto}{\mapsto}{\mapsto}{\mapsto}',
    'To': r'\mathchoice{\Longrightarrow}{\Rightarrow}{\Rightarrow}{\Rightarrow}',
    'From': r'\mathchoice{\Longleftarrow}{\Leftarrow}{\Leftarrow}{\Leftarrow}',
    'Ssi': r'\mathchoice{\Longleftrightarrow}{\Leftrightarrow}{\Leftrightarrow}{\Leftrightarrow}',
    'isomto': r'\overset{\sim}{\longrightarrow}', 'isomfrom': r'\overset{\sim}{\longleftarrow}',
    # relation aliases (\let)
    'leq': r'\leqslant', 'le': r'\leqslant', 'geq': r'\geqslant', 'ge': r'\geqslant',
    'dpl': r'\displaystyle',
    'llbracket': r'[\![', 'rrbracket': r']\!]',
    'tbigoplus': r'\mathop{\textstyle\bigoplus}\limits',
    'tbigotimes': r'\mathop{\textstyle\bigotimes}\limits',
    'tbigcap': r'\mathop{\textstyle\bigcap}\limits',
    'tbigwedge': r'\mathop{\textstyle\bigwedge}\limits',
    'et': r'\textup{\acute{e}t}',
})

# 1-argument math macros: name -> template with #1
MATH_1ARG = {
    'ideal': r'\mathfrak{#1}',
    'rest': r'|_{#1}',
    'sheaf': r'\underline{#1}',
    'lto': r'\xrightarrow{#1}',
    'lfrom': r'\xleftarrow{#1}',
    'mathcal': r'\mathscr{#1}',   # \let\mathcal\mathscr
    'bar': r'\overline{#1}',
    'hat': r'\widehat{#1}',
    'tilde': r'\widetilde{#1}',
}

# n-argument math macros (incl. chapter-local \newcommand): name -> (nargs, template)
MATH_NARG = {}

# text/citation macros that may also appear inside math; math-safe expansions
MATH_0ARG.update({
    'EGA': r'\mathrm{EGA}\,', 'SGA': r'\mathrm{SGA}\,',
    'S': '§', 'oldS': '§', 'quoi': '', 'steco': '',
    'cf': r'\mathrm{cf.}\,', 'Exp': r'\mathrm{Exp.}\,', 'resp': r'\mathrm{resp.}\,',
    'loccit': r'\mathrm{loc.\,cit.}\,', 'ie': r'\mathrm{i.e.}\,',
    'numero': r'n^{\mathrm{o}}\,',
})
MATH_0ARG['et'] = r'\mathrm{\acute{e}t}'


def register_local_macro(name, nargs, body):
    """Register a chapter-local macro definition for math expansion."""
    if nargs == 0:
        MATH_0ARG[name] = body
    else:
        MATH_NARG[name] = (nargs, body)


def _read_math_arg(s, i):
    """Read one macro argument starting at s[i]: a {group} or a single token.
    Returns (arg, new_index)."""
    n = len(s)
    while i < n and s[i] in ' \t\r\n':
        i += 1
    if i >= n:
        return '', i
    if s[i] == '{':
        depth = 0
        j = i
        while j < n:
            if s[j] == '{':
                depth += 1
            elif s[j] == '}':
                depth -= 1
                if depth == 0:
                    return s[i + 1:j], j + 1
            j += 1
        return s[i + 1:], n
    if s[i] == '\\' and i + 1 < n:
        # control sequence as argument
        if s[i + 1].isalpha():
            j = i + 1
            while j < n and s[j].isalpha():
                j += 1
            return s[i:j], j
        return s[i:i + 2], i + 2
    return s[i], i + 1


def expand_math(s):
    """Expand sga2-macros.sty math macros to plain LaTeX, to a fixpoint."""
    for _ in range(10):
        out = []
        i = 0
        n = len(s)
        changed = False
        while i < n:
            c = s[i]
            if c == '\\' and i + 1 < n and s[i + 1] == '\\':
                # \\ row separator: keep both backslashes together so a macro
                # letter on the next row (\\S, \\et, ...) is not mis-tokenised
                # as a control word and expanded (e.g. \\S' -> \§').
                out.append('\\\\')
                i += 2
                continue
            if c == '\\' and i + 1 < n and s[i + 1].isalpha():
                j = i + 1
                while j < n and s[j].isalpha():
                    j += 1
                name = s[i + 1:j]
                if name in MATH_1ARG:
                    arg, k = _read_math_arg(s, j)
                    out.append(MATH_1ARG[name].replace('#1', arg))
                    i = k
                    changed = True
                    continue
                if name in MATH_NARG:
                    nargs, tmpl = MATH_NARG[name]
                    k = j
                    rep = tmpl
                    for a in range(1, nargs + 1):
                        arg, k = _read_math_arg(s, k)
                        rep = rep.replace('#%d' % a, arg)
                    out.append(rep)
                    i = k
                    changed = True
                    continue
                if name in MATH_0ARG:
                    out.append(MATH_0ARG[name])
                    i = j
                    # keep a separating space so a letter-ending replacement (e.g.
                    # \geq -> \geqslant) does not glue onto a following token
                    changed = True
                    continue
                out.append(s[i:j])
                i = j
                continue
            out.append(c)
            i += 1
        s = ''.join(out)
        if not changed:
            break
    return s


def math_html(tex, ctx=None):
    """Expand macros and HTML-escape a math fragment (without delimiters).
    If ctx is given, resolve any \\ref/\\eqref/\\cite occurring inside math to
    their plain numbers (MathJax can't host anchors)."""
    s = expand_math(tex)
    if ctx is not None:
        def _num(key):
            info = ctx.labels.get(key.strip())
            if info:
                return (info['display'] or info['num'] or '?')
            ctx.unresolved.append((key.strip(), 'math-ref'))
            return '?'
        s = re.sub(r'\\eqref\{([^}]*)\}', lambda m: '(' + _num(m.group(1)) + ')', s)
        s = re.sub(r'\\(?:page)?ref\{([^}]*)\}', lambda m: _num(m.group(1)), s)
        s = re.sub(r'\\cite\{([^}]*)\}',
                   lambda m: '[' + (ctx.bibcites.get(m.group(1).strip(), '?')) + ']', s)
    return html.escape(s, quote=False)


# --------------------------------------------------------------------------
# Section 3. Text-mode macros, accents, specials
# --------------------------------------------------------------------------

TEXT_MACROS = {
    'cf': 'cf. ', 'Cf': 'Cf. ', 'ie': 'i.e. ', 'iev': 'i.e., ',
    'loccit': 'loc. cit. ', 'EGA': 'EGA ', 'SGA': 'SGA ',
    'resp': 'resp. ', 'Exp': 'Exp. ', 'numero': 'nº ',
    'og': '« ', 'fg': ' »', 'S': '§', 'oldS': '§',
    'afortiori': 'a fortiori ', 'ldots': '…', 'dots': '…',
    'cdots': '⋯', 'TeX': 'TeX', 'LaTeX': 'LaTeX', 'pointrait': '. ',
    'danger': '<strong>!</strong>', 'ndemark': '', 'CQFD': 'C.Q.F.D.', 'cqfd': 'C.Q.F.D.',
    'qed': 'C.Q.F.D.', 'SSI': ' \\(\\Longleftrightarrow\\) ', 'ALORS': ' \\(\\Longrightarrow\\) ',
    'noindent': '', 'indent': '', 'nobreak': '', 'par': '\n\n', 'smallskip': '',
    'medskip': '', 'bigskip': '', 'normalfont': '', 'normalsize': '', 'ignorespaces': '',
    'unskip': '', 'hfill': '', 'hfil': '', 'clearpage': '', 'cleardoublepage': '',
    'newpage': '', 'frenchspacing': '', 'nonfrenchspacing': '', 'protect': '',
    'leavevmode': '', 'boldmath': '', 'quoi': '', 'skipqed': '', 'smfbreak': '\n\n',
    'pageoriginale': '', 'pageoriginaled': '', 'sfootnotemark': '', 'skippointrait': '',
    'skpt': '', 'thinspace': ' ', 'enspace': ' ', 'quad': ' ',
    'qquad': '  ',
}

# commands that consume [opt] + N braced arguments, producing nothing
DROP_WITH_ARGS = {
    'label': (0, 1), 'index': (0, 1), 'refstepcounter': (0, 1), 'stepcounter': (0, 1),
    'setcounter': (0, 2), 'addtocounter': (0, 2), 'renewcommand': (0, 2),
    'newcommand': (1, 2), 'providecommand': (1, 2), 'thispagestyle': (0, 1),
    'pagestyle': (0, 1), 'chapterspace': (0, 1), 'vspace': (1, 1), 'hspace': (1, 1),
    'setlength': (0, 2), 'nde': (0, 1), 'ndetext': (0, 1), 'markboth': (0, 2),
    'markright': (0, 1), 'phantom': (0, 1), 'hphantom': (0, 1), 'vphantom': (0, 1),
    'caption': (0, 1), 'addcontentsline': (0, 3), 'addtocontents': (0, 2),
    'value': (0, 1),
}

# commands whose single brace argument is kept verbatim as text content
KEEP_ARG = {
    'hbox': 1, 'mbox': 1, 'text': 1, 'textnormal': 1, 'textrm': 1, 'ensuremath': 1,
    'centerline': 1,
}

ACCENTS = {
    "'": {'a': 'á', 'e': 'é', 'i': 'í', 'o': 'ó', 'u': 'ú', 'y': 'ý', 'c': 'ć',
          'n': 'ń', 's': 'ś', 'z': 'ź', 'r': 'ŕ', 'l': 'ĺ',
          'A': 'Á', 'E': 'É', 'I': 'Í', 'O': 'Ó', 'U': 'Ú', 'Y': 'Ý', 'C': 'Ć',
          'N': 'Ń', 'S': 'Ś', 'Z': 'Ź'},
    '`': {'a': 'à', 'e': 'è', 'i': 'ì', 'o': 'ò', 'u': 'ù',
          'A': 'À', 'E': 'È', 'I': 'Ì', 'O': 'Ò', 'U': 'Ù'},
    '^': {'a': 'â', 'e': 'ê', 'i': 'î', 'o': 'ô', 'u': 'û', 'w': 'ŵ', 'y': 'ŷ',
          'A': 'Â', 'E': 'Ê', 'I': 'Î', 'O': 'Ô', 'U': 'Û'},
    '"': {'a': 'ä', 'e': 'ë', 'i': 'ï', 'o': 'ö', 'u': 'ü', 'y': 'ÿ',
          'A': 'Ä', 'E': 'Ë', 'I': 'Ï', 'O': 'Ö', 'U': 'Ü'},
    '~': {'a': 'ã', 'o': 'õ', 'n': 'ñ', 'A': 'Ã', 'O': 'Õ', 'N': 'Ñ'},
    'c': {'c': 'ç', 'C': 'Ç', 's': 'ş', 'S': 'Ş', 'g': 'ģ', 'e': 'ȩ'},
    'v': {'c': 'č', 's': 'š', 'z': 'ž', 'C': 'Č', 'S': 'Š', 'Z': 'Ž', 'e': 'ě', 'r': 'ř', 'n': 'ň'},
    '=': {'a': 'ā', 'e': 'ē', 'i': 'ī', 'o': 'ō', 'u': 'ū'},
    '.': {'a': 'ȧ', 'e': 'ė', 'z': 'ż', 'Z': 'Ż'},
    'u': {'a': 'ă', 'g': 'ğ', 'e': 'ĕ'},
    'H': {'o': 'ő', 'u': 'ű', 'O': 'Ő', 'U': 'Ű'},
    'r': {'a': 'å', 'A': 'Å', 'u': 'ů'},
    'k': {'a': 'ą', 'e': 'ę'},
}

SPECIAL_CHARS = {
    'oe': 'œ', 'OE': 'Œ', 'ae': 'æ', 'AE': 'Æ', 'o': 'ø', 'O': 'Ø', 'ss': 'ß',
    'aa': 'å', 'AA': 'Å', 'l': 'ł', 'L': 'Ł', 'i': 'ı', 'j': 'ȷ', 'dh': 'ð',
    'P': '¶', 'copyright': '©', 'dag': '†', 'ddag': '‡',
    'pounds': '£', 'guillemotleft': '«', 'guillemotright': '»',
    'textbackslash': '\\', 'textbar': '|', 'textasciitilde': '~',
    'textless': '<', 'textgreater': '>', 'textendash': '–', 'textemdash': '—',
    'textquotedblleft': '“', 'textquotedblright': '”',
    'textquoteleft': '‘', 'textquoteright': '’', 'textbullet': '•',
    'textperiodcentered': '·', 'textdegree': '°', 'degree': '°',
}

# inline font-style commands: name -> (html_open, html_close)
FONT_CMDS = {
    'textit': ('<i>', '</i>'), 'textsl': ('<i>', '</i>'), 'emph': ('<em>', '</em>'),
    'textbf': ('<strong>', '</strong>'), 'textmd': ('', ''),
    'textup': ('<span class="upshape">', '</span>'),
    'textsc': ('<span class="smallcaps">', '</span>'),
    'texttt': ('<code>', '</code>'), 'textsf': ('<span class="sf">', '</span>'),
    'underline': ('<u>', '</u>'), 'uline': ('<u>', '</u>'),
    'textsuperscript': ('<sup>', '</sup>'), 'textsubscript': ('<sub>', '</sub>'),
    'sout': ('<s>', '</s>'),
}

# group-scoped font switches: name -> (open, close)
FONT_SWITCH = {
    'it': ('<i>', '</i>'), 'sl': ('<i>', '</i>'), 'em': ('<em>', '</em>'),
    'bf': ('<strong>', '</strong>'), 'bfseries': ('<strong>', '</strong>'),
    'itshape': ('<i>', '</i>'), 'slshape': ('<i>', '</i>'),
    'scshape': ('<span class="smallcaps">', '</span>'),
    'sc': ('<span class="smallcaps">', '</span>'),
    'tt': ('<code>', '</code>'), 'ttfamily': ('<code>', '</code>'),
    'rm': ('', ''), 'rmfamily': ('', ''), 'sf': ('<span class="sf">', '</span>'),
    'sffamily': ('<span class="sf">', '</span>'), 'upshape': ('<span class="upshape">', '</span>'),
    'small': ('<span class="small">', '</span>'), 'footnotesize': ('<span class="small">', '</span>'),
    'scriptsize': ('<span class="small">', '</span>'), 'large': ('<span class="large">', '</span>'),
    'Large': ('<span class="large">', '</span>'), 'huge': ('<span class="large">', '</span>'),
    'normalsize': ('', ''), 'normalfont': ('', ''), 'mdseries': ('', ''),
}


# --------------------------------------------------------------------------
# Section 4. Inline renderer (text fragment -> HTML)
# --------------------------------------------------------------------------

class Ctx:
    def __init__(self, labels, bibcites):
        self.labels = labels
        self.bibcites = bibcites
        self.page_id = ''
        self.footnotes = []
        self.fn_counter = 0
        self.bibliography = []
        self.unresolved = []      # list of (key, kind)
        self.gen_counter = 0

    def gen_id(self, prefix='x'):
        self.gen_counter += 1
        return '%s-%s-%d' % (prefix, self.page_id or 'p', self.gen_counter)


def ref_link(ctx, key, kind):
    info = ctx.labels.get(key)
    if info is None:
        ctx.unresolved.append((key, kind))
        num = '??'
    else:
        num = info['display'] or info['num'] or '??'
        if num == '??':
            ctx.unresolved.append((key, kind))
    cls = 'eqref' if key.startswith('eq:') else 'ref'
    safe = html.escape(num, quote=True)
    return '<a class="%s" href="#%s">%s</a>' % (cls, html.escape(key, quote=True), safe)


def cite_link(ctx, keys):
    parts = []
    for key in [k.strip() for k in keys.split(',') if k.strip()]:
        num = ctx.bibcites.get(key)
        if num is None:
            info = ctx.labels.get(key)
            num = info['display'] if info else None
        if num is None:
            ctx.unresolved.append((key, 'cite'))
            num = '?'
        parts.append('<a href="#%s">%s</a>' % (html.escape(key, quote=True), html.escape(num)))
    return '<span class="cite">[' + ', '.join(parts) + ']</span>'


def render_inline(s, ctx):
    """Render an inline text fragment (no block environments) to HTML."""
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]

        if c == '$':
            # inline math
            j = i + 1
            while j < n and not (s[j] == '$' and s[j - 1] != '\\'):
                j += 1
            body = s[i + 1:j]
            out.append('\\(' + math_html(body, ctx) + '\\)')
            i = j + 1
            continue

        if c == '{':
            grp, j = _read_group(s, i)
            out.append(_render_group(grp, ctx))
            i = j
            continue

        if c == '}':
            i += 1
            continue

        if c == '~':
            out.append(' ')
            i += 1
            continue

        if c == '&':
            out.append('&amp;')
            i += 1
            continue

        if c == '<':
            out.append('&lt;'); i += 1; continue
        if c == '>':
            out.append('&gt;'); i += 1; continue

        if c == '-' and s[i:i + 3] == '---':
            out.append('—'); i += 3; continue
        if c == '-' and s[i:i + 2] == '--':
            out.append('–'); i += 2; continue

        if c == '`' and s[i:i + 2] == '``':
            out.append('“'); i += 2; continue
        if c == "'" and s[i:i + 2] == "''":
            out.append('”'); i += 2; continue
        if c == '`':
            out.append('‘'); i += 1; continue

        if c == '\\':
            tok, j = _consume_command(s, i, ctx, out)
            i = j
            continue

        out.append(html.escape(c, quote=False))
        i += 1
    return ''.join(out)


def _read_group(s, i):
    """s[i]=='{'. Return (inner, index_after_close)."""
    depth = 0
    n = len(s)
    j = i
    while j < n:
        if s[j] == '{':
            depth += 1
        elif s[j] == '}':
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], n


def _render_group(grp, ctx):
    """Render a {...} group, honouring a leading font switch like {\\it ...}."""
    m = re.match(r'\s*\\([a-zA-Z]+)\b', grp)
    if m and m.group(1) in FONT_SWITCH:
        op, cl = FONT_SWITCH[m.group(1)]
        rest = grp[m.end():]
        return op + render_inline(rest, ctx) + cl
    return render_inline(grp, ctx)


def _skip_spaces(s, i):
    n = len(s)
    while i < n and s[i] in ' \t':
        i += 1
    return i


def _read_optional(s, i):
    """If s[i]=='[', read a balanced [..]; return (content_or_None, new_i)."""
    n = len(s)
    if i >= n or s[i] != '[':
        return None, i
    depth = 0
    j = i
    while j < n:
        if s[j] == '[':
            depth += 1
        elif s[j] == ']':
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return None, i


def _consume_command(s, i, ctx, out):
    """Handle a backslash command at s[i]. Append HTML to out. Return (token, new_i)."""
    n = len(s)
    # control symbol (non-letter) like \, \% \{ \\ \&
    if i + 1 < n and not s[i + 1].isalpha():
        ch = s[i + 1]
        mapping = {
            ',': ' ', ';': ' ', ':': ' ', '!': '', ' ': ' ',
            '%': '%', '&': '&amp;', '#': '#', '_': '_', '$': '$',
            '{': '{', '}': '}', '|': '∥', '-': '­', '/': '',
            '@': '', '~': '~',
        }
        if ch == '\\':
            out.append('<br/>')
            return '\\\\', i + 2
        if ch in mapping:
            out.append(mapping[ch])
            return '\\' + ch, i + 2
        # accent on a braced/next letter (e.g. \'e written as \' then e handled below)
        if ch in ACCENTS:
            return _consume_accent(s, i, ch, ctx, out)
        out.append(html.escape(ch, quote=False))
        return '\\' + ch, i + 2

    m = re.match(r'\\([a-zA-Z]+)', s[i:])
    name = m.group(1)
    j = i + m.end()

    # accent commands written with a letter name? none; accents are control symbols
    if name in ('c', 'v', 'u', 'H', 'r', 'k', 'd', 'b', 't') and name in ACCENTS:
        # e.g. \c c  or \c{c}
        return _consume_accent(s, i, name, ctx, out, letter_name=True)

    if name == 'i':
        out.append('ı'); return name, j
    if name == 'j':
        out.append('ȷ'); return name, j

    if name == 'ref' or name == 'Ref':
        arg, j2 = _grab_brace(s, j)
        out.append(ref_link(ctx, arg.strip(), 'ref'))
        return name, j2
    if name == 'eqref':
        arg, j2 = _grab_brace(s, j)
        out.append('(' + ref_link(ctx, arg.strip(), 'eqref') + ')')
        return name, j2
    if name == 'pageref':
        arg, j2 = _grab_brace(s, j)
        out.append('')
        return name, j2
    if name == 'cite':
        opt, j2 = _read_optional(s, j)
        arg, j3 = _grab_brace(s, j2)
        out.append(cite_link(ctx, arg.strip()))
        return name, j3
    if name == 'footnote':
        arg, j2 = _grab_brace(s, j)
        out.append(_make_footnote(arg, ctx))
        return name, j2
    if name == 'sfootnote':
        arg, j2 = _grab_brace(s, j)
        out.append(_make_footnote(arg, ctx))
        return name, j2
    if name == 'footnotemark':
        return name, j

    if name in FONT_CMDS:
        op, cl = FONT_CMDS[name]
        arg, j2 = _grab_brace(s, j)
        out.append(op + render_inline(arg, ctx) + cl)
        return name, j2

    if name == 'label':
        # Emit an empty anchor so cross-references to this label resolve, even
        # when it sits in running text, a list \item, a \footnote, or an
        # environment's optional-arg title — positions that otherwise drop the
        # label and leave its #anchor dangling. (Block-level labels also become
        # the block's id; a duplicate id is harmless — the block, appearing
        # first in the DOM, still wins getElementById.)
        arg, j2 = _grab_brace(s, j)
        key = arg.strip()
        if key:
            out.append('<span class="label-anchor" id="%s"></span>'
                       % html.escape(key, quote=True))
        return name, j2

    if name in DROP_WITH_ARGS:
        nopt, nargs = DROP_WITH_ARGS[name]
        k = j
        for _ in range(nopt):
            _, k = _read_optional(s, _skip_spaces(s, k))
        for _ in range(nargs):
            _, k = _grab_brace(s, k)
        return name, k

    if name in KEEP_ARG:
        arg, j2 = _grab_brace(s, j)
        out.append(render_inline(arg, ctx))
        return name, j2

    if name in TEXT_MACROS:
        out.append(TEXT_MACROS[name])
        # control word eats following space
        if j < n and s[j] == ' ':
            j += 1
        return name, j

    if name in SPECIAL_CHARS:
        out.append(SPECIAL_CHARS[name])
        if j < n and s[j] == ' ':
            j += 1
        return name, j

    if name in FONT_SWITCH:
        # bare switch outside a group: ignore (rare); approximate by dropping
        return name, j

    if name == 'item':
        # should be handled by list renderer; ignore stray
        return name, j

    # unknown command: drop the name, keep following group content (e.g. \hbox{x})
    if j < n and s[j] == ' ':
        j += 1
    return name, j


def _consume_accent(s, i, acc, ctx, out, letter_name=False):
    """Apply accent. s[i]=='\\'. acc is the accent key. Returns (tok, new_i)."""
    n = len(s)
    # position after the accent command
    if letter_name:
        j = i + 1 + len(acc)
    else:
        j = i + 2
    j = _skip_spaces(s, j)
    base = None
    if j < n and s[j] == '{':
        inner, j2 = _read_group(s, j)
        inner = inner.strip()
        if inner.startswith('\\i'):
            base = 'i'
        elif inner.startswith('\\j'):
            base = 'j'
        elif inner:
            base = inner[0]
        j = j2
    elif j < n and s[j] == '\\' and s[j + 1:j + 2] in ('i', 'j'):
        base = s[j + 1]
        j += 2
    elif j < n:
        base = s[j]
        j += 1
    table = ACCENTS.get(acc, {})
    if base and base in table:
        out.append(table[base])
    elif base:
        # fall back: base char + combining accent
        out.append(html.escape(base, quote=False))
    return '\\' + acc, j


def _grab_brace(s, i):
    """Skip spaces, read a {group} (or single token). Return (content, new_i)."""
    i = _skip_spaces(s, i)
    n = len(s)
    if i < n and s[i] == '{':
        return _read_group(s, i)
    if i < n and s[i] == '\\':
        m = re.match(r'\\([a-zA-Z]+|.)', s[i:])
        return s[i:i + m.end()], i + m.end()
    if i < n:
        return s[i], i + 1
    return '', i


def _make_footnote(arg, ctx):
    ctx.fn_counter += 1
    num = ctx.fn_counter
    fid = 'fn-%s-%d' % (ctx.page_id or 'p', num)
    body = render_flow(arg, ctx, paras=False).strip()
    ctx.footnotes.append({'id': fid, 'number': str(num), 'html': body})
    return ('<a class="footnote-ref" id="%sref" href="#%s"><sup>%d</sup></a>'
            % (fid, fid, num))


# --------------------------------------------------------------------------
# Section 5. Top-level scanner + flow/block renderers
# --------------------------------------------------------------------------

SECTION_CMDS = ('chapter', 'section', 'subsection', 'subsubsection', 'paragraph')
MATH_ENVS_NUMBERED = {'equation', 'align', 'gather', 'multline', 'eqnarray', 'flalign'}
MATH_ENVS_UNNUMBERED = {'equation*', 'align*', 'gather*', 'multline*', 'eqnarray*',
                        'flalign*', 'displaymath'}
MATH_ENVS = MATH_ENVS_NUMBERED | MATH_ENVS_UNNUMBERED
MULTILINE_ENVS = {'align', 'align*', 'gather', 'gather*', 'multline', 'multline*',
                  'eqnarray', 'eqnarray*', 'flalign', 'flalign*'}

THEOREM_CAPTIONS = {
    'theoreme': 'Théorème', 'proposition': 'Proposition', 'lemme': 'Lemme',
    'corollaire': 'Corollaire', 'corollaires': 'Corollaires', 'conjecture': 'Conjecture',
    'probleme': 'Problème', 'theoremedefinition': 'Théorème et définition',
    'subproposition': 'Proposition', 'propositionblah': 'Proposition',
    'criteredenormalitedeserre': 'Critère de normalité de Serre',
    'sublemme': 'Lemme', 'subsublemme': 'Lemme', 'supproposition': 'Proposition',
    'suplemme': 'Lemme', 'suptheoreme': 'Théorème', 'supcorollaire': 'Corollaire',
    'aconjecture': 'Conjecture', 'definition': 'Définition', 'remarque': 'Remarque',
    'remarques': 'Remarques', 'exemple': 'Exemple', 'subremarque': 'Remarque',
    'supdefinition': 'Définition', 'remarquestar': 'Remarque',
}
THEOREM_REMARK_STYLE = {'definition', 'remarque', 'remarques', 'exemple', 'subremarque',
                        'supdefinition', 'remarquestar'}
LIST_ENVS = {'enumerate': 'ol', 'enumeratei': 'ol', 'enumeratea': 'ol', 'itemize': 'ul'}
WRAP_ENVS = {'center': ('<div class="center">', '</div>'),
             'flushright': ('<div class="flushright">', '</div>'),
             'flushleft': ('<div class="flushleft">', '</div>'),
             'quote': ('<blockquote>', '</blockquote>'),
             'quotation': ('<blockquote>', '</blockquote>'),
             'footnotesize': ('<div class="small">', '</div>'),
             'small': ('<div class="small">', '</div>'),
             'abstract': ('<div class="abstract">', '</div>'),
             'empty': ('', '')}


def strip_comments(text):
    out = []
    for line in text.split('\n'):
        res = []
        k = 0
        while k < len(line):
            ch = line[k]
            if ch == '\\' and k + 1 < len(line):
                res.append(line[k:k + 2])
                k += 2
                continue
            if ch == '%':
                break
            res.append(ch)
            k += 1
        out.append(''.join(res))
    return '\n'.join(out)


def register_and_strip_defs(text):
    """Strip LaTeX plumbing and chapter-local macro defs, registering the
    content-bearing ones for math expansion. Returns the cleaned text."""
    text = re.sub(r'\\makeatletter.*?\\makeatother', ' ', text, flags=re.S)
    text = re.sub(r'\\makeatletter|\\makeatother', ' ', text)
    text = re.sub(r'\\@addtoreset\s*\{[^}]*\}\s*\{[^}]*\}', ' ', text)
    text = re.sub(r'\\@[a-zA-Z]+', ' ', text)

    out = []
    i = 0
    n = len(text)
    while i < n:
        m = re.match(r'\\(?:re|provide)?newcommand', text[i:])
        if m:
            j = _skip_spaces_nl(text, i + m.end())
            name = None
            if j < n and text[j] == '{':
                grp, j = _read_group(text, j)
                mm = re.match(r'\s*\\([a-zA-Z]+)', grp)
                name = mm.group(1) if mm else None
            elif j < n and text[j] == '\\':
                mm = re.match(r'\\([a-zA-Z]+)', text[j:])
                name = mm.group(1)
                j += mm.end()
            j = _skip_spaces_nl(text, j)
            nargs = 0
            mo = re.match(r'\[(\d+)\]', text[j:])
            if mo:
                nargs = int(mo.group(1))
                j += mo.end()
            j = _skip_spaces_nl(text, j)
            if j < n and text[j] == '[':      # default value for first arg
                _, j = _read_optional(text, j)
                j = _skip_spaces_nl(text, j)
            body = ''
            if j < n and text[j] == '{':
                body, j = _read_group(text, j)
            if name and body:
                register_local_macro(name, nargs, body)
            i = j
            continue
        m2 = re.match(r'\\def\s*\\([a-zA-Z]+)', text[i:])
        if m2:
            name = m2.group(1)
            j = i + m2.end()
            nargs = len(re.findall(r'#\d', text[j:text.find('{', j) if '{' in text[j:] else n]))
            while j < n and text[j] != '{':
                j += 1
            body = ''
            if j < n:
                body, j = _read_group(text, j)
            if name and body and '#' not in body:
                register_local_macro(name, nargs, body)
            i = j
            continue
        m3 = re.match(r'\\let\s*\\([a-zA-Z]+)\s*=?\s*\\([a-zA-Z]+)', text[i:])
        if m3:
            register_local_macro(m3.group(1), 0, '\\' + m3.group(2))
            i += m3.end()
            continue
        out.append(text[i])
        i += 1
    return ''.join(out)


def _find_env_end(s, start, name):
    """start = index just after \\begin{name}. Return (inner_end, after_end)."""
    bpat = '\\begin{' + name + '}'
    epat = '\\end{' + name + '}'
    depth = 1
    i = start
    n = len(s)
    while i < n:
        nb = s.find(bpat, i)
        ne = s.find(epat, i)
        if ne == -1:
            return n, n
        if nb != -1 and nb < ne:
            depth += 1
            i = nb + len(bpat)
        else:
            depth -= 1
            if depth == 0:
                return ne, ne + len(epat)
            i = ne + len(epat)
    return n, n


def iter_top(s):
    """Yield top-level events:
       ('sec', name, star, opt, title, label)
       ('env', name, inner)
       ('dmath', kind, body)
       ('text', text)
    Sectioning/begin only trigger at brace depth 0.
    """
    i = 0
    n = len(s)
    buf = []
    depth = 0

    def flush():
        if buf:
            t = ''.join(buf)
            buf.clear()
            if t.strip():
                return ('text', t)
        return None

    while i < n:
        c = s[i]

        if c == '{':
            depth += 1
            buf.append(c)
            i += 1
            continue
        if c == '}':
            depth -= 1
            if depth < 0:
                depth = 0
            buf.append(c)
            i += 1
            continue

        if c == '$':
            if s[i:i + 2] == '$$':
                end = s.find('$$', i + 2)
                if end == -1:
                    end = n
                ev = flush()
                if ev:
                    yield ev
                yield ('dmath', '$$', s[i + 2:end])
                i = end + 2
                continue
            j = i + 1
            while j < n and not (s[j] == '$' and s[j - 1] != '\\'):
                j += 1
            buf.append(s[i:j + 1])
            i = j + 1
            continue

        if c == '\\':
            two = s[i:i + 2]
            if two == '\\[':
                end = s.find('\\]', i + 2)
                if end == -1:
                    end = n
                ev = flush()
                if ev:
                    yield ev
                yield ('dmath', '[', s[i + 2:end])
                i = end + 2
                continue
            if two == '\\]':
                i += 2
                continue
            m = re.match(r'\\([a-zA-Z]+)', s[i:])
            if not m:
                buf.append(s[i:i + 2])
                i += 2
                continue
            name = m.group(1)
            after = i + m.end()

            if depth == 0 and name == 'begin':
                mm = re.match(r'\\begin\{([a-zA-Z*]+)\}', s[i:])
                if mm:
                    env = mm.group(1)
                    inner_start = i + mm.end()
                    inner_end, after_end = _find_env_end(s, inner_start, env)
                    ev = flush()
                    if ev:
                        yield ev
                    yield ('env', env, s[inner_start:inner_end])
                    i = after_end
                    continue

            if depth == 0 and name in SECTION_CMDS:
                star = ''
                k = after
                if k < n and s[k] == '*':
                    star = '*'
                    k += 1
                k = _skip_spaces(s, k)
                opt, k = _read_optional(s, k)
                k = _skip_spaces_nl(s, k)
                title, k = (_read_group(s, k) if k < n and s[k] == '{' else ('', k))
                # look ahead for a trailing \label
                label, k = _peek_label(s, k)
                ev = flush()
                if ev:
                    yield ev
                yield ('sec', name, star, opt, title, label)
                i = k
                continue

            # inline command: keep in buffer for the inline renderer
            buf.append(s[i:after])
            i = after
            continue

        buf.append(c)
        i += 1

    ev = flush()
    if ev:
        yield ev


def _skip_spaces_nl(s, i):
    n = len(s)
    while i < n and s[i] in ' \t\r\n':
        i += 1
    return i


def _peek_label(s, i):
    """After a sectioning title, optionally consume a following \\label{..}."""
    k = _skip_spaces_nl(s, i)
    m = re.match(r'\\label\{([^}]*)\}', s[k:])
    if m:
        return m.group(1), k + m.end()
    return None, i


def render_flow(s, ctx, paras=True):
    """Render mixed content (text + nested environments + display math) to HTML."""
    parts = []
    for ev in iter_top(s):
        kind = ev[0]
        if kind == 'text':
            parts.append(_render_text_segment(ev[1], ctx, paras))
        elif kind == 'env':
            parts.append(render_env(ev[1], ev[2], ctx)['html'])
        elif kind == 'dmath':
            parts.append(render_mathblock(ev[1], ev[2], ctx)['html'])
        elif kind == 'sec':
            # nested sectioning inside a flow is unusual; render as a small heading
            parts.append(_render_subheading(ev, ctx))
    return '\n'.join(p for p in parts if p)


def _render_text_segment(text, ctx, paras):
    text = re.sub(r'\\par(?![a-zA-Z])', '\n\n', text)
    if not paras:
        h = render_inline(text, ctx).strip()
        return h
    chunks = re.split(r'\n[ \t]*\n', text)
    html_paras = []
    for ch in chunks:
        if not ch.strip():
            continue
        h = render_inline(ch, ctx).strip()
        if h:
            html_paras.append('<p>' + h + '</p>')
    return '\n'.join(html_paras)


def _render_subheading(ev, ctx):
    _, name, star, opt, title, label = ev
    t = render_inline(title, ctx)
    idattr = (' id="%s"' % html.escape(label, quote=True)) if label else ''
    return '<h4%s>%s</h4>' % (idattr, t)


# ---- environment rendering ----

def render_env(name, inner, ctx):
    """Return a block dict {id,type,label,title,html} for a top-level environment."""
    if name in MATH_ENVS:
        return render_mathblock(name, inner, ctx)
    if name in THEOREM_CAPTIONS:
        return render_theorem(name, inner, ctx)
    if name == 'enonce*':
        return render_enonce(inner, ctx)
    if name == 'proof':
        return render_proof(inner, ctx)
    if name in LIST_ENVS:
        return {'id': None, 'type': 'list', 'label': None, 'title': None,
                'html': render_list(name, inner, ctx)}
    if name == 'thebibliography':
        return render_bibliography(inner, ctx)
    if name in ('tabular', 'tabularx', 'array', 'longtable'):
        return {'id': None, 'type': 'table', 'label': None, 'title': None,
                'html': render_tabular(inner, ctx)}
    if name in WRAP_ENVS:
        op, cl = WRAP_ENVS[name]
        return {'id': None, 'type': 'paragraph', 'label': None, 'title': None,
                'html': op + render_flow(inner, ctx) + cl}
    # unknown environment: render its content as flow
    return {'id': None, 'type': 'paragraph', 'label': None, 'title': None,
            'html': render_flow(inner, ctx)}


def render_mathblock(kind, body, ctx):
    """kind is an env name or '$$'/'[' . Returns a block dict."""
    labels = re.findall(r'\\label\{([^}]*)\}', body)
    block_id = labels[0] if labels else None
    numbered = kind in MATH_ENVS_NUMBERED
    has_tag = '\\tag' in body

    # normalise existing \tag{$..$} -> \tag{..}
    body = re.sub(r'\\tag\{\$([^$]*)\$\}', r'\\tag{\1}', body)

    # Turn each \label into its \tag{<number>} (numbers from main.aux), deciding
    # PER ROW: a multi-line env (align/gather/...) may mix rows that carry an
    # explicit \tag with rows that rely on \label for their number. Splitting on
    # the row separator \\ lets a label-only row still get its tag even when a
    # sibling row already has an explicit \tag (otherwise that number is dropped).
    def repl_row(row):
        if '\\tag' in row:                       # explicit tag: keep it, drop labels
            return re.sub(r'\\label\{[^}]*\}', '', row)
        if not numbered:                          # unnumbered env: just drop labels
            return re.sub(r'\\label\{[^}]*\}', '', row)
        used = [False]
        def repl_label(m):
            if used[0]:                           # only first label of a row -> tag
                return ''
            info = ctx.labels.get(m.group(1))
            disp = (info['display'] if info else '').replace('$', '')
            if disp:
                used[0] = True
                return '\\tag{%s}' % disp
            return ''
        return re.sub(r'\\label\{([^}]*)\}', repl_label, row)

    parts = re.split(r'(\\\\)', body)             # keep the \\ separators
    for i in range(0, len(parts), 2):             # even indices = row contents
        parts[i] = repl_row(parts[i])
    body2 = re.sub(r'\\label\{[^}]*\}', '', ''.join(parts))  # safety: drop strays

    expanded = math_html(body2, ctx).strip()

    if kind in MULTILINE_ENVS:
        env = kind if kind.endswith('*') else kind + '*'
        tex = '\\begin{%s}\n%s\n\\end{%s}' % (env, expanded, env)
    else:
        tex = '\\[\n%s\n\\]' % expanded

    nums = []
    for key in labels:
        info = ctx.labels.get(key)
        if info and info['display']:
            nums.append(info['display'].replace('$', ''))
    is_numbered = bool(labels) and (numbered or has_tag)
    if is_numbered:
        cls = 'equation'
        bid = block_id or ctx.gen_id('eq')
        label = ', '.join(nums) if nums else None
        btype = 'equation'
    else:
        cls = 'displaymath'
        bid = block_id or ctx.gen_id('disp')
        label = None
        btype = 'displaymath'

    html_block = '<div class="%s" id="%s">\n%s\n</div>' % (cls, html.escape(bid, quote=True), tex)
    # A multi-line math env can carry several \label{}s (one per row); only the
    # first becomes the block id. Emit anchors for the rest so references to
    # them resolve instead of dangling.
    if len(labels) > 1:
        extra = ''.join(
            '<span class="label-anchor" id="%s"></span>' % html.escape(k, quote=True)
            for k in labels[1:] if k and k != bid)
        html_block = extra + html_block
    return {'id': bid, 'type': btype, 'label': label, 'title': None, 'html': html_block}


def _split_optional_title(inner):
    """Parse a leading optional [title] from an environment body."""
    k = _skip_spaces_nl(inner, 0)
    if k < len(inner) and inner[k] == '[':
        opt, k2 = _read_optional(inner, k)
        return opt, inner[k2:]
    return None, inner


def render_theorem(name, inner, ctx):
    opt_title, inner = _split_optional_title(inner)
    labels = re.findall(r'\\label\{([^}]*)\}', inner)
    block_id = None
    label_num = None
    if labels:
        block_id = labels[0]
        info = ctx.labels.get(block_id)
        if info:
            label_num = info['display'] or info['num']
    if block_id is None and ctx.__dict__.get('pending_label'):
        block_id = ctx.pending_label
        info = ctx.labels.get(block_id)
        if info:
            label_num = info['display'] or info['num']
    ctx.pending_label = None
    if block_id is None:
        block_id = ctx.gen_id('thm')

    caption = THEOREM_CAPTIONS.get(name, name.capitalize())
    style = 'remark' if name in THEOREM_REMARK_STYLE else 'plain'
    body_html = render_flow(inner, ctx)

    head = '<span class="thm-name">%s</span>' % html.escape(caption)
    if label_num:
        head += ' <span class="thm-num">%s</span>' % html.escape(label_num)
    if opt_title:
        head += ' <span class="thm-title">(%s)</span>' % render_inline(opt_title, ctx)

    block_html = (
        '<div class="thm thm-%s %s" id="%s">\n'
        '  <div class="thm-head">%s</div>\n'
        '  <div class="thm-body">%s</div>\n'
        '</div>' % (style, name, html.escape(block_id, quote=True), head, body_html)
    )
    return {'id': block_id, 'type': name, 'label': label_num, 'title': caption,
            'html': block_html}


def render_enonce(inner, ctx):
    # \begin{enonce*}[style]{Title} body \end{enonce*}
    style_opt, inner = _split_optional_title(inner)
    inner = _skip_ws_str(inner)
    title = ''
    if inner.startswith('{'):
        title, j = _read_group(inner, 0)
        inner = inner[j:]
    block_id = ctx.__dict__.get('pending_label')
    ctx.pending_label = None
    label_num = None
    if block_id:
        info = ctx.labels.get(block_id)
        if info:
            label_num = info['display'] or info['num']
    else:
        block_id = ctx.gen_id('enonce')
    style = 'remark' if (style_opt and 'rem' in style_opt) else 'plain'
    body_html = render_flow(inner, ctx)
    head = '<span class="thm-name">%s</span>' % render_inline(title, ctx)
    block_html = (
        '<div class="thm thm-%s enonce" id="%s">\n'
        '  <div class="thm-head">%s</div>\n'
        '  <div class="thm-body">%s</div>\n'
        '</div>' % (style, html.escape(block_id, quote=True), head, body_html)
    )
    return {'id': block_id, 'type': 'enonce', 'label': label_num,
            'title': render_inline(title, ctx), 'html': block_html}


def _skip_ws_str(s):
    return s[_skip_spaces_nl(s, 0):]


def render_proof(inner, ctx):
    opt_title, inner = _split_optional_title(inner)
    name = render_inline(opt_title, ctx) if opt_title else 'Démonstration'
    pid = ctx.gen_id('proof')
    body_html = render_flow(inner, ctx)
    block_html = (
        '<div class="proof" id="%s">\n'
        '  <div class="proof-head"><span class="proof-name">%s</span>'
        '<span class="proof-toggle">▾</span></div>\n'
        '  <div class="proof-body">%s<span class="qed">C.Q.F.D.</span></div>\n'
        '</div>' % (pid, name, body_html)
    )
    return {'id': pid, 'type': 'proof', 'label': None, 'title': name, 'html': block_html}


def render_list(name, inner, ctx):
    tag = LIST_ENVS[name]
    cls = {'enumerate': 'enumerate', 'enumeratei': 'enumerate-i',
           'enumeratea': 'enumerate-a', 'itemize': 'itemize'}[name]
    items = _split_items(inner)
    lis = []
    for opt, content in items:
        marker = ''
        if opt is not None:
            marker = '<span class="item-label">%s</span> ' % render_inline(opt, ctx)
        lis.append('<li>%s%s</li>' % (marker, render_flow(content, ctx, paras=True)))
    type_attr = ''
    if name == 'enumeratei':
        type_attr = ' type="i"'
    elif name == 'enumeratea':
        type_attr = ' type="a"'
    return '<%s class="%s"%s>\n%s\n</%s>' % (tag, cls, type_attr, '\n'.join(lis), tag)


def _split_items(inner):
    """Split a list body on top-level \\item, returning [(opt_label, content), ...]."""
    items = []
    # find \item occurrences at brace depth 0 and not inside nested environments
    positions = []
    depth = 0
    env_depth = 0
    i = 0
    n = len(inner)
    while i < n:
        c = inner[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif c == '\\':
            if inner[i:i + 6] == '\\begin':
                env_depth += 1
                i += 6
                continue
            if inner[i:i + 4] == '\\end':
                env_depth -= 1
                i += 4
                continue
            m = re.match(r'\\item\b', inner[i:])
            if m and depth == 0 and env_depth == 0:
                positions.append(i)
                i += m.end()
                continue
        i += 1
    if not positions:
        return [(None, inner)] if inner.strip() else []
    for idx, p in enumerate(positions):
        start = p + len('\\item')
        end = positions[idx + 1] if idx + 1 < len(positions) else n
        seg = inner[start:end]
        k = _skip_spaces(seg, 0)
        opt = None
        if k < len(seg) and seg[k] == '[':
            opt, k = _read_optional(seg, k)
        items.append((opt, seg[k:]))
    return items


def render_bibliography(inner, ctx):
    entries = []
    for m in re.finditer(r'\\bibitem', inner):
        pass
    # split on \bibitem
    parts = re.split(r'\\bibitem', inner)
    rows = []
    for part in parts[1:]:
        k = _skip_spaces(part, 0)
        opt, k = _read_optional(part, k)
        key, k2 = _grab_brace(part, k)
        text = part[k2:]
        text = text.lstrip('%').strip()
        key = key.strip()
        label = opt
        if label is None:
            label = ctx.bibcites.get(key, '')
        label = label.strip() if label else ''
        body_html = render_flow(text, ctx, paras=False).strip()
        plain = _plain_text(body_html)
        ctx.bibliography.append({'id': key, 'label': label, 'html': body_html, 'text': plain})
        rows.append('<dt id="%s">[%s]</dt><dd>%s</dd>'
                    % (html.escape(key, quote=True), html.escape(label), body_html))
    block_html = '<dl class="bibliography">\n%s\n</dl>' % '\n'.join(rows)
    return {'id': None, 'type': 'bibliography', 'label': None, 'title': 'Bibliographie',
            'html': block_html}


def render_tabular(inner, ctx):
    # drop the column spec argument if present at the very start: {ccc} or [t]{...}
    k = _skip_spaces_nl(inner, 0)
    if k < len(inner) and inner[k] == '[':
        _, k = _read_optional(inner, k)
        k = _skip_spaces_nl(inner, k)
    if k < len(inner) and inner[k] == '{':
        _, k = _read_group(inner, k)
    body = inner[k:]
    body = re.sub(r'\\hline', '', body)
    rows = re.split(r'\\\\', body)
    out = ['<table class="tabular">']
    for row in rows:
        if not row.strip():
            continue
        cells = _split_cells(row)
        tds = ''.join('<td>%s</td>' % render_inline(_clean_cell(c), ctx) for c in cells)
        out.append('<tr>%s</tr>' % tds)
    out.append('</table>')
    return '\n'.join(out)


def _split_cells(row):
    cells = []
    depth = 0
    cur = []
    i = 0
    n = len(row)
    while i < n:
        c = row[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif c == '$':
            j = i + 1
            while j < n and not (row[j] == '$' and row[j - 1] != '\\'):
                j += 1
            cur.append(row[i:j + 1])
            i = j + 1
            continue
        elif c == '&' and depth == 0:
            cells.append(''.join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    cells.append(''.join(cur))
    return cells


def _clean_cell(c):
    c = re.sub(r'\\dotfill', ' … ', c)
    c = re.sub(r'\\hfill', ' ', c)
    return c.strip()


def _plain_text(h):
    t = re.sub(r'<[^>]+>', '', h)
    t = html.unescape(t)
    t = t.replace(' ', ' ')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


# --------------------------------------------------------------------------
# Section 6. Document builder (file -> chapters/pages/blocks)
# --------------------------------------------------------------------------

ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI',
         'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX']

SLUG_MAP = {
    'préface': 'preface', 'preface': 'preface', 'résumé': 'resume', 'resume': 'resume',
    'introduction': 'introduction', 'index des notations': 'index-notations',
    'index terminologique': 'index-terminologie', 'bibliographie': 'bibliographie',
    'index': 'index',
}


def slugify(title_text):
    t = title_text.strip().lower()
    key = re.sub(r'\s+', ' ', t)
    if key in SLUG_MAP:
        return SLUG_MAP[key]
    t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode('ascii')
    t = re.sub(r'[^a-z0-9]+', '-', t).strip('-')
    return t or 'section'


def page_id_from_label(label):
    """eq:..  -> keep; 'III.1' -> 'III-1'; 'I' -> 'I'."""
    return label.replace('.', '-')


class Chapter:
    def __init__(self, cid, title, number=None, numbered=False):
        self.id = cid
        self.title = title           # short title (HTML)
        self.number = number         # roman numeral or None
        self.numbered = numbered
        self.pages = []


class Page:
    def __init__(self, pid, title):
        self.id = pid
        self.title = title
        self.blocks = []
        self.footnotes = []
        self.bibliography = []


def build_chapters(file_specs, ctx):
    """file_specs: list of (path, orphan_chapter). Returns list[Chapter]."""
    chapters = []
    cur_chapter = None
    cur_page = None

    def start_page(page):
        nonlocal cur_page
        # flush previous page footnotes/bib from ctx into the page object
        cur_page = page
        ctx.page_id = page.id
        ctx.footnotes = page.footnotes
        ctx.bibliography = page.bibliography
        ctx.fn_counter = 0
        ctx.gen_counter = 0
        cur_chapter.pages.append(page)

    for path, orphan in file_specs:
        text = strip_comments(open(path, encoding='utf-8', errors='replace').read())
        text = register_and_strip_defs(text)
        pending_text_label = None
        for ev in iter_top(text):
            kind = ev[0]

            if kind == 'sec' and ev[1] == 'chapter':
                _, _, star, opt, title, label = ev
                short_title = render_inline(opt if opt else title, ctx)
                full_title = render_inline(title, ctx)
                numbered = (star != '*')
                number = None
                cid = None
                if label:
                    info = ctx.labels.get(label)
                    if info and info['display']:
                        number = info['display']
                    cid = page_id_from_label(label)
                if cid is None:
                    cid = slugify(_plain_text(short_title))
                cur_chapter = Chapter(cid, short_title, number, numbered and bool(number))
                chapters.append(cur_chapter)
                ctx.pending_label = None
                page = Page(cid, short_title)
                start_page(page)
                hid = label if label else cid
                prefix = (number + ' ') if number else ''
                cur_page.blocks.append({
                    'id': hid, 'type': 'heading', 'label': number, 'title': None,
                    'html': '<h1 id="%s">%s%s</h1>' % (html.escape(hid, quote=True),
                                                       prefix, full_title)})
                continue

            if kind == 'sec' and ev[1] == 'section':
                _, _, star, opt, title, label = ev
                if cur_chapter is None:
                    cur_chapter = Chapter(orphan[0], orphan[1], None, False)
                    chapters.append(cur_chapter)
                stitle = render_inline(title, ctx)
                number = None
                if label:
                    info = ctx.labels.get(label)
                    if info and info['display']:
                        number = info['display']
                    pid = page_id_from_label(label)
                else:
                    pid = '%s-s%d' % (cur_chapter.id, len(cur_chapter.pages) + 1)
                page = Page(pid, stitle)
                start_page(page)
                hid = label if label else pid
                prefix = (number + ' ') if number else ''
                cur_page.blocks.append({
                    'id': hid, 'type': 'heading', 'label': number, 'title': None,
                    'html': '<h2 id="%s">%s%s</h2>' % (html.escape(hid, quote=True),
                                                       prefix, stitle)})
                continue

            if kind == 'sec' and ev[1] in ('subsection', 'subsubsection', 'paragraph'):
                _, sname, star, opt, title, label = ev
                if cur_chapter is None:
                    cur_chapter = Chapter(orphan[0], orphan[1], None, False)
                    chapters.append(cur_chapter)
                if cur_page is None:
                    page = Page(cur_chapter.id, cur_chapter.title)
                    start_page(page)
                number = None
                if label:
                    info = ctx.labels.get(label)
                    if info and info['display']:
                        number = info['display']
                hid = label if label else ctx.gen_id('sub')
                titxt = render_inline(title, ctx).strip()
                if titxt or number:
                    prefix = (number + ' ') if number else ''
                    cur_page.blocks.append({
                        'id': hid, 'type': 'heading', 'label': number, 'title': None,
                        'html': '<h3 id="%s">%s%s</h3>' % (html.escape(hid, quote=True),
                                                           prefix, titxt)})
                else:
                    cur_page.blocks.append({
                        'id': hid, 'type': 'anchor', 'label': number, 'title': None,
                        'html': '<span class="anchor" id="%s"></span>'
                                % html.escape(hid, quote=True)})
                continue

            # non-sectioning content: ensure a chapter/page exists
            if cur_chapter is None:
                cur_chapter = Chapter(orphan[0], orphan[1], None, False)
                chapters.append(cur_chapter)
            if cur_page is None:
                page = Page(cur_chapter.id, cur_chapter.title)
                start_page(page)

            if kind == 'text':
                # detect a trailing \label to attach to the next environment
                seg = ev[1]
                lbls = list(re.finditer(r'\\label\{([^}]*)\}', seg))
                if lbls:
                    last = lbls[-1]
                    if not seg[last.end():].strip():
                        ctx.pending_label = last.group(1)
                html_seg = _render_text_segment(seg, ctx, paras=True)
                if html_seg.strip():
                    for para in _split_para_blocks(html_seg):
                        cur_page.blocks.append({
                            'id': None, 'type': 'paragraph', 'label': None,
                            'title': None, 'html': para})
                continue

            if kind == 'env':
                blk = render_env(ev[1], ev[2], ctx)
                if blk['html'].strip():
                    cur_page.blocks.append(blk)
                ctx.pending_label = None
                continue

            if kind == 'dmath':
                blk = render_mathblock(ev[1], ev[2], ctx)
                cur_page.blocks.append(blk)
                continue

    return chapters


def _split_para_blocks(html_seg):
    """Split a rendered text segment into individual <p>..</p> blocks."""
    return re.findall(r'<p>.*?</p>', html_seg, re.S) or ([html_seg] if html_seg.strip() else [])


# --------------------------------------------------------------------------
# Section 7. Emit JSON + manifest + en stubs
# --------------------------------------------------------------------------

def emit(chapters, out_dir):
    fr_dir = os.path.join(out_dir, 'fr', 'chapters')
    en_dir = os.path.join(out_dir, 'en', 'chapters')
    os.makedirs(fr_dir, exist_ok=True)
    os.makedirs(en_dir, exist_ok=True)

    toc = []
    manifest_chapters = []
    order = 0
    anchor_index = {}   # element id -> page_id

    for ch in chapters:
        page_ids = []
        for pi, page in enumerate(ch.pages):
            level = 0 if pi == 0 else 1
            toc.append({
                'page_id': page.id,
                'title': page.title,
                'level': level,
                'order': order,
                'is_numbered_chapter': bool(ch.numbered) and pi == 0,
                'chapter_number': ch.number if pi == 0 else None,
            })
            page_ids.append(page.id)
            for blk in page.blocks:
                if blk.get('id'):
                    anchor_index[blk['id']] = page.id
            order += 1
        manifest_chapters.append({
            'id': ch.id,
            'title': ch.title,
            'number': ch.number,
            'order': ch.pages[0].id if ch.pages else ch.id,
            'page_ids': page_ids,
        })

    # second pass: collect every element id (headings, blocks, bib, footnotes)
    for ch in chapters:
        for page in ch.pages:
            for blk in page.blocks:
                for m in re.finditer(r'id="([^"]+)"', blk['html']):
                    anchor_index.setdefault(m.group(1), page.id)
            for b in page.bibliography:
                anchor_index.setdefault(b['id'], page.id)
            for f in page.footnotes:
                anchor_index.setdefault(f['id'], page.id)
                # a \label inside the footnote body emits its own anchor span;
                # index it too so cross-page refs to it (e.g. #noteserre) resolve
                for m in re.finditer(r'id="([^"]+)"', f.get('html', '')):
                    anchor_index.setdefault(m.group(1), page.id)

    default_page = chapters[0].pages[0].id if chapters and chapters[0].pages else None
    default_chapter = chapters[0].id if chapters else None
    manifest = {
        'toc': toc,
        'default_page_id': default_page,
        'default_chapter_id': default_chapter,
        'chapters': manifest_chapters,
        'anchor_index': anchor_index,
    }

    with open(os.path.join(out_dir, 'fr.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, 'en.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    for ch in chapters:
        pages_json = []
        for page in ch.pages:
            html_full = '\n'.join(b['html'] for b in page.blocks)
            pages_json.append({
                'id': page.id,
                'title': page.title,
                'html': html_full,
                'blocks': [{'id': b['id'], 'type': b['type'], 'label': b['label'],
                            'title': b['title'], 'html': b['html']} for b in page.blocks],
                'footnotes': page.footnotes,
                'bibliography': page.bibliography,
            })
        chapter_json = {'chapter_id': ch.id, 'title': ch.title, 'number': ch.number,
                        'pages': pages_json}
        with open(os.path.join(fr_dir, ch.id + '.json'), 'w', encoding='utf-8') as f:
            json.dump(chapter_json, f, ensure_ascii=False, indent=1)
        # English stub: same structure, empty content
        stub_pages = [{'id': p['id'], 'title': p['title'], 'html': '',
                       'blocks': [], 'footnotes': [], 'bibliography': []}
                      for p in pages_json]
        stub = {'chapter_id': ch.id, 'title': ch.title, 'number': ch.number,
                'pages': stub_pages}
        with open(os.path.join(en_dir, ch.id + '.json'), 'w', encoding='utf-8') as f:
            json.dump(stub, f, ensure_ascii=False, indent=1)

    return manifest


# --------------------------------------------------------------------------
# Section 8. Driver + verify
# --------------------------------------------------------------------------

def file_specs(src):
    specs = []
    fm = os.path.join(src, 'front-matter.tex')
    if os.path.exists(fm):
        specs.append((fm, ('resume', 'Résumé')))
    for k in range(0, 15):
        p = os.path.join(src, 'chapter-%02d.tex' % k)
        if os.path.exists(p):
            specs.append((p, ('chapter-%02d' % k, 'Exposé')))
    bm = os.path.join(src, 'back-matter.tex')
    if os.path.exists(bm):
        specs.append((bm, ('bibliographie', 'Bibliographie')))
    return specs


def run(src, out, only=None):
    aux = os.path.join(src, 'main.aux')
    labels, bibcites = parse_aux(aux)
    if not labels:
        print('WARNING: no labels parsed from %s (run pdflatex first).' % aux,
              file=sys.stderr)
    ctx = Ctx(labels, bibcites)
    ctx.pending_label = None
    specs = file_specs(src)
    if only:
        specs = [s for s in specs if only in s[0]]
    chapters = build_chapters(specs, ctx)
    manifest = emit(chapters, out)
    return chapters, ctx, manifest


def verify(chapters, ctx, out):
    problems = []
    n_pages = sum(len(c.pages) for c in chapters)
    n_blocks = sum(len(p.blocks) for c in chapters for p in c.pages)
    n_eq = sum(1 for c in chapters for p in c.pages for b in p.blocks if b['type'] == 'equation')
    n_thm = sum(1 for c in chapters for p in c.pages for b in p.blocks
                if b['type'] in THEOREM_CAPTIONS or b['type'] == 'enonce')
    n_fn = sum(len(p.footnotes) for c in chapters for p in c.pages)
    n_bib = sum(len(p.bibliography) for c in chapters for p in c.pages)

    # invariant: page.html == join(block.html)
    for c in chapters:
        for p in c.pages:
            joined = '\n'.join(b['html'] for b in p.blocks)
            # (this is exactly how emit builds it, so it always holds; sanity only)

    # leaked macros outside math
    leak_re = re.compile(r'\\[a-zA-Z]+')
    leaks = {}
    for c in chapters:
        for p in c.pages:
            for b in p.blocks:
                h = b['html']
                # strip math regions \(...\) and \[...\] and \begin{align*}..
                stripped = re.sub(r'\\\(.*?\\\)', '', h, flags=re.S)
                stripped = re.sub(r'\\\[.*?\\\]', '', stripped, flags=re.S)
                stripped = re.sub(r'\\begin\{[a-z*]+\}.*?\\end\{[a-z*]+\}', '', stripped, flags=re.S)
                for m in leak_re.finditer(stripped):
                    cmd = m.group(0)
                    leaks[cmd] = leaks.get(cmd, 0) + 1

    unresolved = {}
    for key, kind in ctx.unresolved:
        unresolved[key] = unresolved.get(key, 0) + 1

    print('=== verify ===')
    print('chapters: %d  pages: %d  blocks: %d' % (len(chapters), n_pages, n_blocks))
    print('equations: %d  theorems: %d  footnotes: %d  bib entries: %d'
          % (n_eq, n_thm, n_fn, n_bib))
    print('unresolved refs/cites: %d (%d distinct)'
          % (sum(unresolved.values()), len(unresolved)))
    if unresolved:
        for k in list(unresolved)[:25]:
            print('   ?? %s' % k)
    print('leaked backslash-commands outside math: %d distinct' % len(leaks))
    if leaks:
        for cmd, cnt in sorted(leaks.items(), key=lambda x: -x[1])[:30]:
            print('   %5d  %s' % (cnt, cmd))
    # JSON validity
    bad = 0
    for root, _, files in os.walk(out):
        for fn in files:
            if fn.endswith('.json'):
                try:
                    json.load(open(os.path.join(root, fn), encoding='utf-8'))
                except Exception as e:
                    bad += 1
                    print('   BAD JSON %s: %s' % (fn, e))
    print('invalid JSON files: %d' % bad)
    return leaks, unresolved


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, '..', '..', '..'))
    ap.add_argument('--src', default=os.path.join(repo, '01-normalized_tex'))
    ap.add_argument('--out', default=os.path.join(repo, '02-converted_html'))
    ap.add_argument('--only', default=None)
    ap.add_argument('--verify', action='store_true')
    args = ap.parse_args()
    chapters, ctx, manifest = run(args.src, args.out, args.only)
    print('wrote %d chapters to %s' % (len(chapters), args.out))
    if args.verify:
        verify(chapters, ctx, args.out)


if __name__ == '__main__':
    main()
