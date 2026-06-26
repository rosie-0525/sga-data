// Headless render/error scan for the SGA2 custom-parser viewer.
//
// Findings are categorised into three files written under the output dir:
//   mathjax_errors.json  — typesetError, mjx-merror, leaked \word macros
//   crossref_errors.json — \ref/\eqref in math, ???/?? markers, dead #anchors
//   other_errors.json    — equation-tag dropout, »-glued-to-word spacing,
//                           fatal, page/console errors
//
// The deliverable (02-converted_html/) is a single-page viewer, NOT a tree of
// standalone HTML files:
//   index.html  — loads MathJax 3 + XyJax-v3 (xypic) from the CDN
//   viewer.js   — fetches <lang>.json + <lang>/chapters/<id>.json and renders
//                 one page at a time into #page, calling MathJax.typesetPromise
//   <lang>.json — manifest: chapters[].page_ids, toc, anchor_index
//   <lang>/chapters/<id>.json — { pages: [{ id, title, html, footnotes }] }
//
// Math (incl. the xymatrix commutative diagrams) lives inside the JSON
// page.html strings. So instead of navigating the viewer (which chains every
// typeset onto MathJax.startup.promise — a stale-promise race and a growing
// document.math list), we load index.html ONCE to obtain the real
// MathJax+XyJax environment, then for every page read its html in Node and
// typeset it directly into an offscreen container, scanning the rendered DOM.
//
// Per page we report:
//   - mjx-merror elements             (DOM)
//   - leaked \word macro tokens       (DOM, post-typeset text nodes)
//   - ??? / ?? unresolved-ref markers (DOM)
//   - \ref/\eqref surviving into math (static, over page.html)
//   - internal #anchor links that resolve to nothing via the manifest (static)
//   - console / page-level errors
//
// Notes:
//   - page.evaluate(...) returns are JSON-serialised explicitly because direct
//     object returns can come back undefined when the page state references
//     MathJax globals.
//   - Source TeX for an mjx-merror is recovered from MathJax 3's
//     MathJax.startup.document.math list (MathItem.math / .typesetRoot); there
//     is no <script type="math/tex"> in MathJax 3 output (that was MathJax 2).

const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

const HTML_DIR = process.argv[2];
const BASE_URL = process.argv[3] || 'http://localhost:8765';
const OUT_DIR = process.argv[4]; // optional; if set, write the category files here
const LANGS = (process.argv[5] || 'fr,en').split(',').map((s) => s.trim()).filter(Boolean);

if (!HTML_DIR) {
  console.error('usage: node check.js <html-dir> [base-url] [out-dir] [langs]');
  process.exit(2);
}

const LOAD_TIMEOUT_MS = 60000;

// ---------------------------------------------------------------------------
// Node-side helpers: read the manifest + per-chapter JSON, assemble page HTML,
// run the static (non-DOM) passes.
// ---------------------------------------------------------------------------

function readJSON(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

// Load one language: manifest + the ordered list of its pages (with html).
function loadLanguage(lang) {
  const manifest = readJSON(path.join(HTML_DIR, lang + '.json'));
  const pageIds = new Set();
  (manifest.chapters || []).forEach((ch) => {
    (ch.page_ids || []).forEach((pid) => pageIds.add(pid));
  });
  const anchorKeys = new Set(Object.keys(manifest.anchor_index || {}));

  const pages = [];
  (manifest.chapters || []).forEach((ch) => {
    const cpath = path.join(HTML_DIR, lang, 'chapters', ch.id + '.json');
    let chapter;
    try {
      chapter = readJSON(cpath);
    } catch (e) {
      pages.push({ chapterId: ch.id, page: { id: ch.id, title: ch.title, html: '', __readError: String(e) } });
      return;
    }
    (chapter.pages || []).forEach((pg) => pages.push({ chapterId: ch.id, page: pg }));
  });
  return { manifest, pageIds, anchorKeys, pages };
}

// Mirror viewer.js renderPage() (lines 110-127): empty-page placeholder +
// footnotes section, so we typeset exactly what ships to the browser.
function assemblePageHtml(pg) {
  let html = pg.html || '';
  if (!html.trim()) {
    html = '<h1>' + (pg.title || '') + '</h1>' +
      '<p class="muted"><em>(Traduction non disponible — la version française est la référence.)</em></p>';
  }
  if (pg.footnotes && pg.footnotes.length) {
    html += '<section class="footnotes"><ol>';
    pg.footnotes.forEach((f) => {
      html += '<li id="' + f.id + '">' + f.html +
        ' <a class="backref" href="#' + f.id + 'ref" title="retour">↩</a></li>';
    });
    html += '</ol></section>';
  }
  return html;
}

// Static pass: \ref/\eqref that survived into the source (refs are pre-resolved
// from main.aux, so any literal token here leaked into a math environment that
// MathJax then renders as ???). Grouped by label.
function staticRefsInMath(html) {
  const re = /\\(?:eq)?ref\s*\{([^}]*)\}/g;
  const byLabel = new Map();
  let m;
  while ((m = re.exec(html)) !== null) {
    const lab = m[1];
    if (byLabel.has(lab)) { byLabel.get(lab).count++; continue; }
    const start = Math.max(0, m.index - 40);
    const ctx = html.slice(start, m.index + m[0].length + 20).replace(/\s+/g, ' ').trim();
    byLabel.set(lab, { context: ctx, count: 1 });
  }
  return Array.from(byLabel, ([label, v]) => ({ label, context: v.context, count: v.count }));
}

function collectIds(html) {
  const re = /\bid\s*=\s*"([^"]+)"/g;
  const out = new Set();
  let m;
  while ((m = re.exec(html)) !== null) out.add(m[1]);
  return out;
}

// Static pass: every internal <a href="#frag"> whose fragment resolves to
// nothing. In the SPA a link resolves (viewer.js resolveHash, lines 159-173)
// if the fragment is a page id, an anchor_index key, a same-page element id, or
// a toc-anchor-<X> fallback. Anything else would 404 in the viewer.
function staticDangling(html, localIds, pageIds, anchorKeys) {
  const re = /href\s*=\s*"#([^"]+)"/g;
  const out = [];
  const seen = new Set();
  let m;
  const resolves = (frag) => {
    let f = frag;
    try { f = decodeURIComponent(frag); } catch (e) { /* keep raw */ }
    if (localIds.has(frag) || localIds.has(f)) return true;
    if (pageIds.has(frag) || pageIds.has(f)) return true;
    if (anchorKeys.has(frag) || anchorKeys.has(f)) return true;
    const tm = f.match(/^toc-anchor-(.+)$/);
    if (tm) {
      const key = tm[1].replace(/-/g, '.');
      if (anchorKeys.has(key) || pageIds.has(key)) return true;
    }
    return false;
  };
  while ((m = re.exec(html)) !== null) {
    const frag = m[1];
    if (!frag || resolves(frag)) continue;
    if (seen.has(frag)) continue;
    seen.add(frag);
    const start = Math.max(0, m.index - 30);
    const ctx = html.slice(start, m.index + m[0].length + 10).replace(/\s+/g, ' ').trim();
    out.push({ frag, context: ctx });
  }
  return out;
}

// Static pass: equation-tag dropout. A numbered display-math block can carry one
// \label (hence one displayed number) per row; the converter emits the first as
// the <div class="equation"> id and the rest as preceding label-anchor spans
// (convert.py render_mathblock). Each numbered row should display a number via an
// explicit \tag{} (MathJax runs tags:'none', so only \tag produces a number, and
// multi-row envs are forced to their starred form). If a block carries more eq:
// labels than \tag{}s, a labeled row renders with NO number — e.g. (21)/(21 bis)
// where the (21) row silently loses its tag. We report the shortfall by block;
// \notag/\nonumber in the body is recorded so a legitimately-unnumbered row isn't
// mistaken for the bug. Fix belongs upstream in the converter (per the README).
function staticTagIntegrity(html) {
  // Each <div class="equation" ...> plus any label-anchor spans glued to its front.
  const re = /((?:<span class="label-anchor" id="[^"]*">\s*<\/span>\s*)*)<div class="equation"([^>]*)>([\s\S]*?)<\/div>/g;
  const out = [];
  let m;
  while ((m = re.exec(html)) !== null) {
    const pre = m[1] || '', attrs = m[2] || '', body = m[3] || '';
    const labels = new Set();
    const idm = /id="([^"]+)"/.exec(attrs);
    if (idm && idm[1].startsWith('eq:')) labels.add(idm[1]);
    const are = /<span class="label-anchor" id="([^"]+)">/g;
    let am;
    while ((am = are.exec(pre)) !== null) {
      if (am[1].startsWith('eq:')) labels.add(am[1]);
    }
    const tagCount = (body.match(/\\tag\s*\{/g) || []).length;
    if (labels.size > tagCount) {
      const ctx = body.replace(/\s+/g, ' ').trim().slice(0, 120);
      out.push({
        blockId: (idm && idm[1]) || null,
        labels: Array.from(labels),
        tagCount,
        hasNotag: /\\(?:notag|nonumber)\b/.test(body),
        context: ctx,
      });
    }
  }
  return out;
}

// Static pass: a closing guillemet » with no space before the following word.
// The converter's control-word rule (convert.py) eats the ASCII space after \fg,
// so source "\fg word" renders as "»word". Punctuation, closing brackets, HTML
// tags and entities legitimately abut », so only a letter/digit, an opening
// paren, or inline math \( right after » is the bug (e.g. "point-base »dans",
// "algébrique »(ou", "résoudre »\(A\)"). Fix belongs upstream in convert.py
// (\fg should not swallow the following space).
// Exception: a superscript-only inline math "»\(^…" is a footnote/editorial mark
// hugging the closing quote (e.g. "…affine »\(^{(**)}\)") — that is correct
// typography (no space wanted), so it is excluded from the flag.
function staticQuoteSpacing(html) {
  const re = /»(?=[\p{L}\p{N}(]|\\\((?!\^))/gu;
  const out = [];
  const seen = new Set();
  let m;
  while ((m = re.exec(html)) !== null) {
    const start = Math.max(0, m.index - 30);
    const ctx = html.slice(start, m.index + 30).replace(/\s+/g, ' ').trim();
    if (seen.has(ctx)) continue; // collapse identical windows
    seen.add(ctx);
    out.push({ context: ctx });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Browser-side: typeset one HTML string into the offscreen container and scan
// the rendered DOM. Returns merrors / leaked macros / ??? markers + count.
// ---------------------------------------------------------------------------

async function renderAndScan(page, html) {
  const json = await page.evaluate(async (html) => {
    const S = (o) => JSON.stringify(o);
    const root = document.getElementById('__check_root');

    // Reset MathJax's math list so document.math holds only this page's items
    // (keeps the source-TeX recovery below trivially scoped).
    try {
      if (window.MathJax && MathJax.typesetClear) MathJax.typesetClear();
      else if (window.MathJax && MathJax.startup && MathJax.startup.document) MathJax.startup.document.clear();
    } catch (e) { /* ignore */ }

    root.innerHTML = html;

    let typesetError = null;
    try {
      if (window.MathJax && MathJax.typesetPromise) {
        await MathJax.typesetPromise([root]);
      }
    } catch (e) {
      typesetError = String(e);
    }

    // container -> source TeX (MathJax 3 MathItem list)
    const srcMap = new Map();
    try {
      const mlist = MathJax.startup.document.math;
      for (const item of mlist) {
        const r = item.typesetRoot;
        if (r && r.isConnected && root.contains(r)) srcMap.set(r, item.math);
      }
    } catch (e) { /* leave srcMap empty; fall back to assistive-mml */ }

    const srcFor = (el) => {
      const c = el.closest ? el.closest('mjx-container') : null;
      if (c && srcMap.has(c)) return srcMap.get(c);
      if (c) {
        const a = c.querySelector('mjx-assistive-mml');
        if (a) return a.textContent.trim().slice(0, 200);
      }
      return '';
    };

    // 1. mjx-merror
    const merrors = [];
    root.querySelectorAll('mjx-merror').forEach((el) => {
      merrors.push({ title: el.getAttribute('title') || '', text: el.textContent, tex: srcFor(el) });
    });

    // 2. Leaked \word macros: any \command surviving as a post-typeset text
    //    node. Visible leaks live in plain text nodes; MathJax-internal leaks
    //    (e.g. \protect rendered as text) live in the hidden mjx-assistive-mml
    //    mirror. Dedupe by container so the visible + assistive copies collapse.
    const leakedMacros = [];
    {
      const re = /\\[a-zA-Z]+/g;
      const containers = Array.from(root.querySelectorAll('mjx-container'));
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const seen = new Set();
      let n;
      while ((n = walker.nextNode())) {
        const p = n.parentElement;
        if (!p) continue;
        const tag = p.tagName;
        if (tag === 'SCRIPT' || tag === 'STYLE') continue;
        const text = n.nodeValue || '';
        const matches = text.match(re);
        if (!matches) continue;
        const mjx = p.closest('mjx-container');
        const idx = mjx ? containers.indexOf(mjx) : -1;
        const key = idx + '|' + Array.from(new Set(matches)).sort().join(',');
        if (idx >= 0 && seen.has(key)) continue;
        seen.add(key);
        leakedMacros.push({
          tokens: Array.from(new Set(matches)),
          context: text.length > 120 ? text.slice(0, 120) + '…' : text,
          inMath: !!mjx,
          viaAssistiveMML: !!p.closest('mjx-assistive-mml'),
          sourceTeX: mjx ? (srcMap.get(mjx) || '') : '',
          parentTag: tag.toLowerCase(),
        });
      }
    }

    // 3. ??? (MathJax unresolved-ref placeholder) / standalone ?? markers.
    const refMarkers = [];
    {
      const standalone = /(?:^|[^?\w])\?\?(?![?\w])/;
      const containers = Array.from(root.querySelectorAll('mjx-container'));
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const seen = new Set();
      let n;
      while ((n = walker.nextNode())) {
        const p = n.parentElement;
        if (!p) continue;
        const tag = p.tagName;
        if (tag === 'SCRIPT' || tag === 'STYLE') continue;
        const text = n.nodeValue || '';
        const triple = /\?\?\?/.test(text);
        if (!triple && !standalone.test(text)) continue;
        const mjx = p.closest('mjx-container');
        const idx = mjx ? containers.indexOf(mjx) : -1;
        const key = idx >= 0 ? 'c' + idx : 't' + refMarkers.length;
        if (idx >= 0 && seen.has(key)) continue;
        seen.add(key);
        const tex = mjx ? (srcMap.get(mjx) || '') : '';
        refMarkers.push({
          marker: triple ? '???' : '??',
          context: text.length > 120 ? text.slice(0, 120).trim() + '…' : text.trim(),
          inMath: !!mjx,
          sourceTeX: tex.length > 200 ? tex.slice(0, 200) + '…' : tex,
          parentTag: tag.toLowerCase(),
        });
      }
    }

    const containers = root.querySelectorAll('mjx-container').length;
    return S({ typesetError, containers, merrors, leakedMacros, refMarkers });
  }, html);

  return JSON.parse(json);
}

function filterConsole(msgs) {
  return msgs.filter((c) => {
    const t = c.text;
    if (/favicon/i.test(t)) return false;
    if (/Failed to load resource.*404/.test(t)) return false;
    if (/symbol-defs\.svg/.test(t)) return false;
    if (/No version information available for component/.test(t)) return false;
    return true;
  });
}

function makeResult(lang, pageId, title, html, scan, L, cmsgs, perrs) {
  return {
    lang,
    file: lang + '/' + pageId,
    pageId,
    title: title || '',
    containers: scan.containers || 0,
    typesetError: scan.typesetError || null,
    fatal: scan.fatal || null,
    merrors: scan.merrors || [],
    leakedMacros: scan.leakedMacros || [],
    refsInMath: staticRefsInMath(html),
    refMarkers: scan.refMarkers || [],
    danglingAnchors: staticDangling(html, collectIds(html), L.pageIds, L.anchorKeys),
    tagIssues: staticTagIntegrity(html),
    quoteSpacing: staticQuoteSpacing(html),
    pageErrors: perrs,
    consoleMsgs: filterConsole(cmsgs),
  };
}

function isBad(r) {
  return (r.merrors && r.merrors.length)
    || (r.leakedMacros && r.leakedMacros.length)
    || (r.refsInMath && r.refsInMath.length)
    || (r.refMarkers && r.refMarkers.length)
    || (r.danglingAnchors && r.danglingAnchors.length)
    || (r.tagIssues && r.tagIssues.length)
    || (r.quoteSpacing && r.quoteSpacing.length)
    || (r.consoleMsgs && r.consoleMsgs.length)
    || (r.pageErrors && r.pageErrors.length)
    || r.typesetError || r.fatal;
}

// ---------------------------------------------------------------------------
// Category split. Each per-page result carries up to ten error channels; we
// route them into three files so a genuine MathJax/XyJax typesetting failure is
// not buried among cross-reference or structural/page-level problems:
//   mathjax  — the typeset engine could not render the math/macros
//   crossref — unresolved references and dead internal links
//   other    — equation-number dropout + page/console-level errors
// The identity fields are repeated in every file so each error stays
// attributable to a page.
// ---------------------------------------------------------------------------

const IDENT = ['lang', 'file', 'pageId', 'title', 'containers'];

const CATEGORIES = {
  mathjax: { scalars: ['typesetError'], arrays: ['merrors', 'leakedMacros'] },
  crossref: { scalars: [], arrays: ['refsInMath', 'refMarkers', 'danglingAnchors'] },
  other: { scalars: ['fatal'], arrays: ['tagIssues', 'quoteSpacing', 'pageErrors', 'consoleMsgs'] },
};

function categoryBad(r, cat) {
  const c = CATEGORIES[cat];
  return c.scalars.some((k) => r[k]) || c.arrays.some((k) => r[k] && r[k].length);
}

function projectCategory(r, cat) {
  const c = CATEGORIES[cat];
  const out = {};
  for (const k of IDENT) out[k] = r[k];
  for (const k of c.scalars) out[k] = r[k] || null;
  for (const k of c.arrays) out[k] = r[k] || [];
  return out;
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

function summarise(results) {
  const lines = [];
  const bad = results.filter(isBad);
  const sumLen = (key) => results.reduce((s, r) => s + (r[key] ? r[key].length : 0), 0);
  const countPages = (cat) => results.filter((r) => categoryBad(r, cat)).length;
  const totalContainers = results.reduce((s, r) => s + (r.containers || 0), 0);

  const totalMerror = sumLen('merrors');
  const totalLeakNodes = sumLen('leakedMacros');
  const totalRefInMath = sumLen('refsInMath');
  const totalRefMarkers = sumLen('refMarkers');
  const totalDangling = sumLen('danglingAnchors');
  const totalTagIssues = sumLen('tagIssues');
  const totalQuoteSpacing = sumLen('quoteSpacing');

  // Rollup indexes used by the MathJax (leaked tokens) and Cross-references
  // (unresolved ref labels) sections below.
  const tokenIndex = new Map();
  for (const r of results) {
    for (const leak of (r.leakedMacros || [])) {
      for (const t of leak.tokens) {
        if (!tokenIndex.has(t)) tokenIndex.set(t, new Set());
        tokenIndex.get(t).add(r.file);
      }
    }
  }
  const refLabelIndex = new Map();
  for (const r of results) {
    for (const rr of (r.refsInMath || [])) {
      if (!refLabelIndex.has(rr.label)) refLabelIndex.set(rr.label, new Set());
      refLabelIndex.get(rr.label).add(r.file);
    }
  }

  lines.push('');
  lines.push(`Checked ${results.length} pages — ${totalContainers} mjx-container elements typeset.`);
  lines.push(`Pages with issues: ${bad.length}.`);
  lines.push(`  MathJax    — ${countPages('mathjax')} page(s): ${totalMerror} mjx-merror, ${totalLeakNodes} leaked text node(s).`);
  lines.push(`  Cross-refs — ${countPages('crossref')} page(s): ${totalRefInMath} ref-in-math, ${totalRefMarkers} ???/?? marker(s), ${totalDangling} dangling anchor(s).`);
  lines.push(`  Other      — ${countPages('other')} page(s): ${totalTagIssues} equation-tag dropout(s), ${totalQuoteSpacing} guillemet-spacing issue(s).`);
  if (bad.length === 0) {
    lines.push('CHECK PASSED');
    return lines.join('\n') + '\n';
  }

  // --- MathJax / typesetting (→ issues/mathjax_errors.json) ---
  const mjBad = results.filter((r) => categoryBad(r, 'mathjax'));
  if (mjBad.length) {
    lines.push('');
    lines.push('## MathJax / typesetting errors  (issues/mathjax_errors.json)');
    for (const x of mjBad) {
      lines.push(`=== ${x.file}  (containers: ${x.containers})`);
      if (x.typesetError) lines.push(`  typesetError: ${x.typesetError}`);
      for (const m of (x.merrors || [])) {
        lines.push(`  [merror] ${m.title}`);
        const src = m.tex || m.text || '';
        if (src) lines.push(`     source: ${JSON.stringify(src.slice(0, 300))}`);
      }
      for (const l of (x.leakedMacros || [])) {
        let where;
        if (l.viaAssistiveMML) where = 'mjx-container (rendered as text by MathJax)';
        else if (l.inMath) where = `<${l.parentTag}> in mjx-container`;
        else where = `<${l.parentTag}>`;
        lines.push(`  [leak] ${l.tokens.join(' ')}  — ${where}`);
        lines.push(`     context: ${JSON.stringify(l.context)}`);
        if (l.sourceTeX) lines.push(`     sourceTeX: ${JSON.stringify(l.sourceTeX.slice(0, 200))}`);
      }
    }
    if (tokenIndex.size > 0) {
      lines.push('');
      lines.push('Leaked macros by token (most files first):');
      const rows = Array.from(tokenIndex.entries())
        .map(([tok, files]) => ({ tok, files: Array.from(files).sort() }))
        .sort((a, b) => b.files.length - a.files.length || a.tok.localeCompare(b.tok));
      for (const { tok, files } of rows) {
        const shown = files.slice(0, 5).join(', ');
        const more = files.length > 5 ? `, … (+${files.length - 5})` : '';
        lines.push(`  ${tok}  — ${files.length} file${files.length === 1 ? '' : 's'}: ${shown}${more}`);
      }
    }
  }

  // --- Cross-references (→ issues/crossref_errors.json) ---
  const xrefBad = results.filter((r) => categoryBad(r, 'crossref'));
  if (xrefBad.length) {
    lines.push('');
    lines.push('## Cross-reference errors  (issues/crossref_errors.json)');
    for (const x of xrefBad) {
      lines.push(`=== ${x.file}  (containers: ${x.containers})`);
      for (const rr of (x.refsInMath || [])) {
        const times = rr.count > 1 ? ` (×${rr.count})` : '';
        lines.push(`  [ref-in-math] \\ref{${rr.label}}${times}  — survives into math; MathJax cannot resolve the label → renders ???`);
        if (rr.context) lines.push(`     context: ${JSON.stringify(rr.context)}`);
      }
      for (const m of (x.refMarkers || [])) {
        const where = m.inMath ? 'mjx-container' : `<${m.parentTag}>`;
        lines.push(`  [unresolved-ref] "${m.marker}" in ${where}`);
        lines.push(`     context: ${JSON.stringify(m.context)}`);
        if (m.sourceTeX) lines.push(`     sourceTeX: ${JSON.stringify(m.sourceTeX.slice(0, 200))}`);
      }
      for (const d of (x.danglingAnchors || [])) {
        lines.push(`  [dangling] href="#${d.frag}" — resolves to no page id, anchor_index key, or same-page id`);
        if (d.context) lines.push(`     context: ${JSON.stringify(d.context)}`);
      }
    }
    if (refLabelIndex.size > 0) {
      lines.push('');
      lines.push('Unresolved refs in math by label (fix upstream in sga2-inline-macros):');
      const rows = Array.from(refLabelIndex.entries())
        .map(([lab, files]) => ({ lab, files: Array.from(files).sort() }))
        .sort((a, b) => b.files.length - a.files.length || a.lab.localeCompare(b.lab));
      for (const { lab, files } of rows) {
        lines.push(`  \\ref{${lab}}  — ${files.join(', ')}`);
      }
    }
  }

  // --- Other (→ issues/other_errors.json) ---
  const otherBad = results.filter((r) => categoryBad(r, 'other'));
  if (otherBad.length) {
    lines.push('');
    lines.push('## Other errors  (issues/other_errors.json)');
    for (const x of otherBad) {
      lines.push(`=== ${x.file}  (containers: ${x.containers})`);
      if (x.fatal) lines.push(`  fatal: ${x.fatal}`);
      for (const t of (x.tagIssues || [])) {
        const note = t.hasNotag ? ' (block also has \\notag/\\nonumber — verify intent)' : '';
        lines.push(`  [tag-missing] ${t.labels.length} eq labels but only ${t.tagCount} \\tag${t.tagCount === 1 ? '' : 's'} — ${t.labels.length - t.tagCount} labeled row(s) render with no number${note}`);
        lines.push(`     labels: ${t.labels.join(', ')}`);
        if (t.context) lines.push(`     context: ${JSON.stringify(t.context)}`);
      }
      for (const q of (x.quoteSpacing || [])) {
        lines.push('  [quote-space] » glued to following text (missing space after closing guillemet)');
        if (q.context) lines.push(`     context: ${JSON.stringify(q.context)}`);
      }
      for (const c of (x.consoleMsgs || [])) {
        lines.push(`  [console.${c.type}] ${c.text}`);
      }
      for (const e of (x.pageErrors || [])) {
        lines.push(`  [pageerror] ${e}`);
      }
    }
  }

  lines.push('');
  lines.push('CHECK FAILED');
  return lines.join('\n') + '\n';
}

// ---------------------------------------------------------------------------
// Driver
// ---------------------------------------------------------------------------

(async () => {
  const browser = await puppeteer.launch({
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  const page = await browser.newPage();

  const consoleMsgs = [];
  const pageErrors = [];
  page.on('console', (msg) => {
    const type = msg.type();
    if (type === 'error' || type === 'warning') consoleMsgs.push({ type, text: msg.text() });
  });
  page.on('pageerror', (err) => pageErrors.push(String(err)));

  // Load the real deliverable once — gives us its exact MathJax + XyJax config.
  console.error(`Loading ${BASE_URL}/index.html`);
  await page.goto(`${BASE_URL}/index.html`, { waitUntil: 'load', timeout: LOAD_TIMEOUT_MS });

  // Wait until MathJax (and the async XyJax loader) is ready and the viewer's
  // own boot render has settled, then add an offscreen scratch container.
  await page.evaluate(async () => {
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    for (let i = 0; i < 600; i++) {
      if (window.MathJax && window.MathJax.startup && window.MathJax.startup.promise) break;
      await wait(100);
    }
    if (window.MathJax && window.MathJax.startup && window.MathJax.startup.promise) {
      try { await window.MathJax.startup.promise; } catch (e) { /* ignore */ }
      await wait(200);
      try { await window.MathJax.startup.promise; } catch (e) { /* ignore */ }
    }
    const d = document.createElement('div');
    d.id = '__check_root';
    d.style.position = 'absolute';
    d.style.left = '-99999px';
    d.style.top = '0';
    document.body.appendChild(d);
  });

  const haveMathJax = await page.evaluate(() => !!(window.MathJax && window.MathJax.typesetPromise));
  if (!haveMathJax) {
    console.error('error: MathJax did not load on index.html (network / CDN?)');
    await browser.close();
    process.exit(2);
  }

  const results = [];

  for (const lang of LANGS) {
    let L;
    try {
      L = loadLanguage(lang);
    } catch (e) {
      console.error(`[${lang}] manifest load failed: ${e}`);
      continue;
    }
    console.error(`[${lang}] ${L.pages.length} pages, ${L.anchorKeys.size} anchors`);

    // Titles pass: chapter + toc titles can carry math (the same titles appear
    // as page headings, but check them here too so a sidebar-only title can't
    // slip through). Deduped by string.
    {
      const titles = new Set();
      (L.manifest.chapters || []).forEach((c) => { if (c.title) titles.add((c.number ? c.number + ' ' : '') + c.title); });
      (L.manifest.toc || []).forEach((t) => { if (t.title) titles.add(t.title); });
      const html = Array.from(titles).map((t) => '<div>' + t + '</div>').join('\n');
      const before = consoleMsgs.length;
      const beforeE = pageErrors.length;
      process.stderr.write(`  ${(lang + '/__titles__').padEnd(28)} ... `);
      let scan;
      try { scan = await renderAndScan(page, html); }
      catch (e) { scan = { fatal: String(e), containers: 0, merrors: [], leakedMacros: [], refMarkers: [] }; }
      const r = makeResult(lang, '__titles__', '(titles)', html, scan, L, consoleMsgs.slice(before), pageErrors.slice(beforeE));
      process.stderr.write(isBad(r) ? `ISSUES (math=${r.containers})\n` : `ok (${r.containers} math)\n`);
      results.push(r);
    }

    for (const { page: pg } of L.pages) {
      const html = assemblePageHtml(pg);
      const before = consoleMsgs.length;
      const beforeE = pageErrors.length;
      process.stderr.write(`  ${(lang + '/' + pg.id).padEnd(28)} ... `);
      let scan;
      try {
        scan = await renderAndScan(page, html);
      } catch (e) {
        scan = { fatal: String(e), containers: 0, merrors: [], leakedMacros: [], refMarkers: [] };
      }
      const r = makeResult(lang, pg.id, pg.title, html, scan, L, consoleMsgs.slice(before), pageErrors.slice(beforeE));
      if (pg.__readError) r.fatal = pg.__readError;
      process.stderr.write(isBad(r)
        ? `ISSUES (math=${r.containers}, merror=${r.merrors.length}, leak=${r.leakedMacros.length}, refMath=${r.refsInMath.length}, mark=${r.refMarkers.length}, dangling=${r.danglingAnchors.length}, tag=${r.tagIssues.length}, quote=${r.quoteSpacing.length}, pageErr=${r.pageErrors.length}, console=${r.consoleMsgs.length}${r.typesetError ? ', typesetError' : ''})\n`
        : `ok (${r.containers} math)\n`);
      results.push(r);
    }
  }

  await browser.close();

  if (OUT_DIR) {
    for (const cat of Object.keys(CATEGORIES)) {
      const subset = results.filter((r) => categoryBad(r, cat)).map((r) => projectCategory(r, cat));
      const out = path.join(OUT_DIR, cat + '_errors.json');
      fs.writeFileSync(out, JSON.stringify(subset, null, 2));
      console.error(`wrote ${out} (${subset.length} page${subset.length === 1 ? '' : 's'})`);
    }
  }

  process.stdout.write(summarise(results));

  process.exit(results.some(isBad) ? 1 : 0);
})();
