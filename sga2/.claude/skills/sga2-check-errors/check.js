// Headless render/error scan for the SGA2 deliverable.
//
// Findings are categorised into three files written under the output dir:
//   mathjax_errors.json  — typesetError, mjx-merror, leaked \word macros
//   crossref_errors.json — \ref/\eqref in math, ???/?? markers, dead #anchors
//   other_errors.json    — equation-tag dropout, »-glued-to-word spacing,
//                           multi-root content blocks, fatal, page/console errors
//
// The deliverable (02-converted_html/) is a single page (paper.html) driven by
// the translation-viewer submodule, NOT a tree of standalone HTML files:
//   paper.html                — bootstraps translation-viewer/viewer-bootstrap.js,
//                                which fetches data/config.json, configures MathJax 3
//                                (SVG) + XyJax-v3 from it, and injects the submodule's
//                                own vendored assets (offline, no CDN)
//   translation-viewer/viewer.js — fetches data/<baseLang>/manifest.json (ONCE, base
//                                language only — it drives navigation for every
//                                language column) and data/<lang>/chapters/<id>.json,
//                                rendering blocks in aligned rows
//   data/<baseLang>/manifest.json — { chapters[].page_ids, toc, anchor_index }
//   data/<lang>/chapters/<id>.json — { pages: [{ id, title, blocks[], footnotes }] }
//
// Math (incl. the xymatrix commutative diagrams) lives inside the JSON block
// html strings. So instead of navigating the viewer (which chains every
// typeset onto MathJax.startup.promise — a stale-promise race and a growing
// document.math list), we load paper.html ONCE to obtain the real
// MathJax+XyJax environment, then for every page read its html in Node and
// typeset it directly into an offscreen container, scanning the rendered DOM.
//
// Per page we report:
//   - mjx-merror elements             (DOM)
//   - leaked \word macro tokens       (DOM, post-typeset text nodes)
//   - ??? / ?? unresolved-ref markers (DOM)
//   - \ref/\eqref surviving into math (static, over page.html)
//   - internal #anchor links that resolve to nothing via the manifest (static)
//   - blocks whose html isn't a single root element (DOM, per-block — see
//     checkBlockShapes; translation-viewer's blockEl() keeps only
//     firstElementChild, so a stray sibling silently drops content)
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
  console.error('usage: node check.js <html-dir> [base-url] [out-dir] [langs] [html-dir-rel]');
  process.exit(2);
}

// The base (source) language — its data/<baseLang>/manifest.json is the only
// manifest translation-viewer reads; it drives navigation for every column.
const BASE_LANG = 'fr';
// check.sh serves from the super-repo root (translation-viewer/ is shared by
// every book, one level above each book's own directory), and passes
// HTML_DIR's path relative to that server root as argv[6] (e.g.
// "sga2/02-converted_html"). Falls back to the bare basename for direct/manual
// invocations that omit argv[6] (matches the old single-book layout).
const HTML_DIR_REL = process.argv[6] || path.basename(HTML_DIR);

const LOAD_TIMEOUT_MS = 60000;

// ---------------------------------------------------------------------------
// Node-side helpers: read the manifest + per-chapter JSON, assemble page HTML,
// run the static (non-DOM) passes.
// ---------------------------------------------------------------------------

function readJSON(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

// data/config.json — only used here for its per-language UI strings (e.g.
// notrans/backref), so assemblePageHtml matches what the browser actually ships.
function loadConfig() {
  try {
    return readJSON(path.join(HTML_DIR, 'data', 'config.json'));
  } catch (e) {
    return null;
  }
}

// Load the single base-language manifest that drives navigation for every
// language column (translation-viewer never reads a per-target-language
// manifest — ids are shared, so one manifest is the source of truth).
function loadManifest() {
  const manifest = readJSON(path.join(HTML_DIR, 'data', BASE_LANG, 'manifest.json'));
  const pageIds = new Set();
  (manifest.chapters || []).forEach((ch) => {
    (ch.page_ids || []).forEach((pid) => pageIds.add(pid));
  });
  const anchorKeys = new Set(Object.keys(manifest.anchor_index || {}));
  return { manifest, pageIds, anchorKeys };
}

// Load one language's content — the ordered list of its pages (with html) —
// using the shared manifest's chapter/page_id list to find each chapter file.
function loadLanguageContent(lang, manifest) {
  const pages = [];
  (manifest.chapters || []).forEach((ch) => {
    const cpath = path.join(HTML_DIR, 'data', lang, 'chapters', ch.id + '.json');
    let chapter;
    try {
      chapter = readJSON(cpath);
    } catch (e) {
      pages.push({ chapterId: ch.id, page: { id: ch.id, title: ch.title, html: '', __readError: String(e) } });
      return;
    }
    (chapter.pages || []).forEach((pg) => pages.push({ chapterId: ch.id, page: pg }));
  });
  return pages;
}

// Mirror translation-viewer/viewer.js's per-language placeholder + footnotesEl()
// (lines ~215-233), so we typeset exactly what ships to the browser.
function assemblePageHtml(pg, lang, config) {
  const strings = (config && config.languages && config.languages[lang]) || {};
  let html = pg.html || '';
  if (!html.trim()) {
    html = '<h1>' + (pg.title || '') + '</h1>' +
      '<p class="muted"><em>' + (strings.notrans || '(no translation)') + '</em></p>';
  }
  if (pg.footnotes && pg.footnotes.length) {
    html += '<section id="footnotes"><ol>';
    pg.footnotes.forEach((f) => {
      html += '<li id="' + f.id + '">' + f.html +
        ' <a class="backref" href="#' + f.id + 'ref" title="' + (strings.backref || 'back') + '">↩</a></li>';
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
// the <div class="equation"> id and the rest as label-anchor spans nested inside
// the div (convert.py render_mathblock — nested, not preceding siblings, so the
// block stays a single root element for viewers that align content block-by-
// block). Each numbered row should display a number via an explicit \tag{}
// (MathJax runs tags:'none', so only \tag produces a number, and multi-row envs
// are forced to their starred form). If a block carries more eq: labels than
// \tag{}s, a labeled row renders with NO number — e.g. (21)/(21 bis) where the
// (21) row silently loses its tag. We report the shortfall by block; \notag/
// \nonumber in the body is recorded so a legitimately-unnumbered row isn't
// mistaken for the bug. Fix belongs upstream in the converter (per the README).
function staticTagIntegrity(html) {
  const re = /<div class="equation"([^>]*)>([\s\S]*?)<\/div>/g;
  const out = [];
  let m;
  while ((m = re.exec(html)) !== null) {
    const attrs = m[1] || '', body = m[2] || '';
    const labels = new Set();
    const idm = /id="([^"]+)"/.exec(attrs);
    if (idm && idm[1].startsWith('eq:')) labels.add(idm[1]);
    const are = /<span class="label-anchor" id="([^"]+)">/g;
    let am;
    while ((am = are.exec(body)) !== null) {
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

// Browser-side pass (needs real DOM parsing, not regex): translation-viewer's
// blockEl() (viewer.js) does `tpl.innerHTML = block.html; return
// tpl.content.firstElementChild` — i.e. it keeps only the FIRST top-level
// element of a block's html. A block whose html is more than one top-level
// element (e.g. a stray sibling <span> before the real content <div>) has its
// real content silently dropped, with no mjx-merror, leak, or ??? to show for
// it. Mirrors that exact parse so a violation here is a true prediction of
// content loss in the shipped viewer.
async function checkBlockShapes(page, blocks) {
  if (!blocks || !blocks.length) return [];
  const json = await page.evaluate((blocks) => {
    const S = (o) => JSON.stringify(o);
    const out = [];
    for (const b of blocks) {
      const tpl = document.createElement('template');
      tpl.innerHTML = b.html || '';
      const rootCount = tpl.content.children.length;
      const hasStrayText = Array.from(tpl.content.childNodes).some(
        (n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
      if (rootCount !== 1 || hasStrayText) {
        out.push({
          blockId: b.id || null,
          type: b.type || null,
          rootCount,
          hasStrayText,
          context: (b.html || '').replace(/\s+/g, ' ').trim().slice(0, 160),
        });
      }
    }
    return S(out);
  }, blocks.map((b) => ({ id: b.id, type: b.type, html: b.html })));
  return JSON.parse(json);
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

function makeResult(lang, pageId, title, html, scan, L, cmsgs, perrs, blockShapeIssues) {
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
    blockShapeIssues: blockShapeIssues || [],
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
    || (r.blockShapeIssues && r.blockShapeIssues.length)
    || (r.consoleMsgs && r.consoleMsgs.length)
    || (r.pageErrors && r.pageErrors.length)
    || r.typesetError || r.fatal;
}

// ---------------------------------------------------------------------------
// Category split. Each per-page result carries up to eleven error channels; we
// route them into three files so a genuine MathJax/XyJax typesetting failure is
// not buried among cross-reference or structural/page-level problems:
//   mathjax  — the typeset engine could not render the math/macros
//   crossref — unresolved references and dead internal links
//   other    — equation-number dropout, multi-root blocks, page/console-level errors
// The identity fields are repeated in every file so each error stays
// attributable to a page.
// ---------------------------------------------------------------------------

const IDENT = ['lang', 'file', 'pageId', 'title', 'containers'];

const CATEGORIES = {
  mathjax: { scalars: ['typesetError'], arrays: ['merrors', 'leakedMacros'] },
  crossref: { scalars: [], arrays: ['refsInMath', 'refMarkers', 'danglingAnchors'] },
  other: { scalars: ['fatal'], arrays: ['tagIssues', 'quoteSpacing', 'blockShapeIssues', 'pageErrors', 'consoleMsgs'] },
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
  const totalBlockShapeIssues = sumLen('blockShapeIssues');

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
  lines.push(`  Other      — ${countPages('other')} page(s): ${totalTagIssues} equation-tag dropout(s), ${totalQuoteSpacing} guillemet-spacing issue(s), ${totalBlockShapeIssues} multi-root block(s).`);
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
      for (const b of (x.blockShapeIssues || [])) {
        const strayNote = b.hasStrayText ? ' + stray top-level text' : '';
        lines.push(`  [multi-root-block] block ${b.blockId || '(no id)'} (${b.type || '?'}) has ${b.rootCount} top-level elements${strayNote} — translation-viewer keeps only the first, dropping the rest`);
        if (b.context) lines.push(`     context: ${JSON.stringify(b.context)}`);
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

  // Load the real deliverable once — gives us its exact MathJax + XyJax config
  // (translation-viewer/viewer-bootstrap.js builds it from data/config.json).
  const paperUrl = `${BASE_URL}/${HTML_DIR_REL}/paper.html`;
  console.error(`Loading ${paperUrl}`);
  await page.goto(paperUrl, { waitUntil: 'load', timeout: LOAD_TIMEOUT_MS });

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
    console.error('error: MathJax did not load on paper.html (network / CDN?)');
    await browser.close();
    process.exit(2);
  }

  const results = [];
  const config = loadConfig();

  let base;
  try {
    base = loadManifest();
  } catch (e) {
    console.error(`manifest load failed: ${e}`);
    await browser.close();
    process.exit(2);
  }
  console.error(`manifest: ${base.pageIds.size} pages, ${base.anchorKeys.size} anchors`);

  // Titles pass: chapter + toc titles can carry math (the same titles appear
  // as page headings, but check them here too so a sidebar-only title can't
  // slip through). Deduped by string. The manifest (hence these titles) is
  // base-language only and shared by every column, so this runs once.
  {
    const titles = new Set();
    (base.manifest.chapters || []).forEach((c) => { if (c.title) titles.add((c.number ? c.number + ' ' : '') + c.title); });
    (base.manifest.toc || []).forEach((t) => { if (t.title) titles.add(t.title); });
    const html = Array.from(titles).map((t) => '<div>' + t + '</div>').join('\n');
    const before = consoleMsgs.length;
    const beforeE = pageErrors.length;
    process.stderr.write(`  ${(BASE_LANG + '/__titles__').padEnd(28)} ... `);
    let scan;
    try { scan = await renderAndScan(page, html); }
    catch (e) { scan = { fatal: String(e), containers: 0, merrors: [], leakedMacros: [], refMarkers: [] }; }
    const r = makeResult(BASE_LANG, '__titles__', '(titles)', html, scan, base, consoleMsgs.slice(before), pageErrors.slice(beforeE));
    process.stderr.write(isBad(r) ? `ISSUES (math=${r.containers})\n` : `ok (${r.containers} math)\n`);
    results.push(r);
  }

  for (const lang of LANGS) {
    let pages;
    try {
      pages = loadLanguageContent(lang, base.manifest);
    } catch (e) {
      console.error(`[${lang}] content load failed: ${e}`);
      continue;
    }
    const L = { manifest: base.manifest, pageIds: base.pageIds, anchorKeys: base.anchorKeys, pages };
    console.error(`[${lang}] ${L.pages.length} pages`);

    for (const { page: pg } of L.pages) {
      const html = assemblePageHtml(pg, lang, config);
      const before = consoleMsgs.length;
      const beforeE = pageErrors.length;
      process.stderr.write(`  ${(lang + '/' + pg.id).padEnd(28)} ... `);
      let scan;
      try {
        scan = await renderAndScan(page, html);
      } catch (e) {
        scan = { fatal: String(e), containers: 0, merrors: [], leakedMacros: [], refMarkers: [] };
      }
      let blockShapeIssues = [];
      try {
        blockShapeIssues = await checkBlockShapes(page, pg.blocks);
      } catch (e) { /* non-fatal: leave empty, other checks still report */ }
      const r = makeResult(lang, pg.id, pg.title, html, scan, L, consoleMsgs.slice(before), pageErrors.slice(beforeE), blockShapeIssues);
      if (pg.__readError) r.fatal = pg.__readError;
      process.stderr.write(isBad(r)
        ? `ISSUES (math=${r.containers}, merror=${r.merrors.length}, leak=${r.leakedMacros.length}, refMath=${r.refsInMath.length}, mark=${r.refMarkers.length}, dangling=${r.danglingAnchors.length}, tag=${r.tagIssues.length}, quote=${r.quoteSpacing.length}, blockShape=${r.blockShapeIssues.length}, pageErr=${r.pageErrors.length}, console=${r.consoleMsgs.length}${r.typesetError ? ', typesetError' : ''})\n`
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
