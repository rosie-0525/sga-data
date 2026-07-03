// Headless render/error scan for SGA 3's transcriptions.
//
// Findings are categorised into three files written under the output dir:
//   mathjax_errors.json  — typesetError, mjx-merror, leaked \word macros
//   crossref_errors.json — ???/?? markers, dead #anchor links
//   other_errors.json    — fatal, page/console errors
//
// Unlike sga1/sga2 (whose deliverable is a JSON-driven single-page viewer),
// SGA 3's 01-transcribed/ is a tree of standalone, self-contained HTML files,
// each loading its own MathJax 3 + XyJax-v3 (offline, vendored under
// translation-viewer/). So the checker simply navigates to every file over a
// local HTTP server (needed for the ../../translation-viewer/... relative
// script paths), awaits MathJax startup, runs an explicit typesetPromise()
// (the files ship startup.typeset:false), and scans the rendered DOM.
//
// Per file we report:
//   - mjx-merror elements             (DOM)
//   - leaked \word macro tokens       (DOM, post-typeset text nodes)
//   - ??? / ?? unresolved-ref markers (DOM)
//   - dead <a href="#frag"> links     (static, resolved GLOBALLY: sga3 anchors
//     are chapter-prefixed, e.g. id="VIB.7.2", and an exposé freely links to
//     another exposé's anchors, so a fragment is checked against the ids of
//     ALL transcribed files, not just its own. A fragment whose chapter prefix
//     names a chapter that simply has no file yet — refs run ahead of the
//     transcription effort — is counted separately as "not transcribed yet"
//     and is NOT a failure.)
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

const HTML_DIR = process.argv[2]; // .../sga3/01-transcribed
const BASE_URL = process.argv[3] || 'http://localhost:8765';
const OUT_DIR = process.argv[4]; // optional; if set, write the category files here
// HTML_DIR's path relative to the HTTP server root (the sga/ super-repo root),
// e.g. "sga3/01-transcribed".
const HTML_DIR_REL = process.argv[5] || path.basename(HTML_DIR);
const CHAPTER_MAP = process.argv[6]; // .../sga3/chapter-map.json
// Optional comma-separated chapter ids to check (default: every file).
const ONLY = (process.argv[7] || '').split(',').map((s) => s.trim()).filter(Boolean);

if (!HTML_DIR) {
  console.error('usage: node check.js <html-dir> [base-url] [out-dir] [html-dir-rel] [chapter-map] [ids]');
  process.exit(2);
}

const LOAD_TIMEOUT_MS = 120000;

// ---------------------------------------------------------------------------
// Node-side: enumerate files, collect ids globally, run the static anchor pass.
// ---------------------------------------------------------------------------

// All chapter ids the volume will eventually have (used to tell a link into a
// not-yet-transcribed exposé apart from a genuinely dead fragment).
function loadAllChapterIds() {
  if (!CHAPTER_MAP) return new Set();
  try {
    const map = JSON.parse(fs.readFileSync(CHAPTER_MAP, 'utf8'));
    const ids = new Set();
    (map.entries || []).forEach((e) => {
      const cids = Array.isArray(e.chapter_id) ? e.chapter_id : [e.chapter_id];
      cids.forEach((c) => ids.add(c));
    });
    return ids;
  } catch (e) {
    console.error(`warning: could not read ${CHAPTER_MAP}: ${e}`);
    return new Set();
  }
}

function listFiles() {
  return fs.readdirSync(HTML_DIR)
    .filter((f) => f.endsWith('.html'))
    .sort();
}

function collectIds(html) {
  const re = /\bid\s*=\s*"([^"]+)"/g;
  const out = new Set();
  let m;
  while ((m = re.exec(html)) !== null) out.add(m[1]);
  return out;
}

// Static pass: every internal <a href="#frag">, resolved against the ids of
// every transcribed file. Classified as:
//   dangling        — chapter prefix is transcribed but the anchor is missing
//                     (kind: 'same-file' | 'cross-file'), or the prefix isn't a
//                     chapter id at all → a real error
//   notTranscribed  — chapter prefix is a known chapter with no file yet → info
function anchorPass(chapterId, html, globalIds, transcribedIds, allChapterIds) {
  const re = /href\s*=\s*"#([^"]+)"/g;
  const dangling = [];
  const notTranscribed = [];
  const seen = new Set();
  let m;
  while ((m = re.exec(html)) !== null) {
    const frag = m[1];
    if (!frag || seen.has(frag)) continue;
    seen.add(frag);
    let f = frag;
    try { f = decodeURIComponent(frag); } catch (e) { /* keep raw */ }
    if (globalIds.has(frag) || globalIds.has(f)) continue;
    const start = Math.max(0, m.index - 30);
    const ctx = html.slice(start, m.index + m[0].length + 10).replace(/\s+/g, ' ').trim();
    const prefix = f.split('.')[0];
    if (allChapterIds.has(prefix) && !transcribedIds.has(prefix)) {
      notTranscribed.push({ frag, targetChapter: prefix, context: ctx });
    } else {
      dangling.push({ frag, kind: prefix === chapterId ? 'same-file' : 'cross-file', context: ctx });
    }
  }
  return { dangling, notTranscribed };
}

// ---------------------------------------------------------------------------
// Browser-side: after navigation + typeset, scan the rendered DOM.
// ---------------------------------------------------------------------------

async function typesetAndScan(page) {
  const json = await page.evaluate(async () => {
    const S = (o) => JSON.stringify(o);
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));

    // Wait for MathJax (and the async XyJax loader) to come up.
    for (let i = 0; i < 600; i++) {
      if (window.MathJax && window.MathJax.startup && window.MathJax.startup.promise) break;
      await wait(100);
    }
    if (!(window.MathJax && window.MathJax.startup && window.MathJax.startup.promise)) {
      return S({ fatal: 'MathJax did not load', containers: 0, merrors: [], leakedMacros: [], refMarkers: [] });
    }

    let typesetError = null;
    try {
      await MathJax.startup.promise;
      // The transcriptions ship startup.typeset:false — typeset explicitly.
      await MathJax.typesetPromise();
    } catch (e) {
      typesetError = String(e);
    }

    const root = document.body;

    // container -> source TeX (MathJax 3 MathItem list)
    const srcMap = new Map();
    try {
      const mlist = MathJax.startup.document.math;
      for (const item of mlist) {
        const r = item.typesetRoot;
        if (r && r.isConnected) srcMap.set(r, item.math);
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
    //    live in the hidden mjx-assistive-mml mirror. Dedupe by container.
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
  });

  return JSON.parse(json);
}

function filterConsole(msgs) {
  return msgs.filter((c) => {
    const t = c.text;
    if (/favicon/i.test(t)) return false;
    if (/Failed to load resource.*404/.test(t)) return false;
    if (/No version information available for component/.test(t)) return false;
    return true;
  });
}

function makeResult(chapterId, scan, anchors, cmsgs, perrs) {
  return {
    file: chapterId + '.html',
    chapterId,
    containers: scan.containers || 0,
    typesetError: scan.typesetError || null,
    fatal: scan.fatal || null,
    merrors: scan.merrors || [],
    leakedMacros: scan.leakedMacros || [],
    refMarkers: scan.refMarkers || [],
    danglingAnchors: anchors.dangling,
    notTranscribedRefs: anchors.notTranscribed,
    pageErrors: perrs,
    consoleMsgs: filterConsole(cmsgs),
  };
}

// notTranscribedRefs is informational — it never fails the check.
function isBad(r) {
  return (r.merrors && r.merrors.length)
    || (r.leakedMacros && r.leakedMacros.length)
    || (r.refMarkers && r.refMarkers.length)
    || (r.danglingAnchors && r.danglingAnchors.length)
    || (r.consoleMsgs && r.consoleMsgs.length)
    || (r.pageErrors && r.pageErrors.length)
    || r.typesetError || r.fatal;
}

// ---------------------------------------------------------------------------
// Category split (same three-way split as sga1/sga2's check-errors skills).
// ---------------------------------------------------------------------------

const IDENT = ['file', 'chapterId', 'containers'];

const CATEGORIES = {
  mathjax: { scalars: ['typesetError'], arrays: ['merrors', 'leakedMacros'] },
  crossref: { scalars: [], arrays: ['refMarkers', 'danglingAnchors'] },
  other: { scalars: ['fatal'], arrays: ['pageErrors', 'consoleMsgs'] },
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
  const totalRefMarkers = sumLen('refMarkers');
  const totalDangling = sumLen('danglingAnchors');
  const totalNotTranscribed = sumLen('notTranscribedRefs');

  const tokenIndex = new Map();
  for (const r of results) {
    for (const leak of (r.leakedMacros || [])) {
      for (const t of leak.tokens) {
        if (!tokenIndex.has(t)) tokenIndex.set(t, new Set());
        tokenIndex.get(t).add(r.file);
      }
    }
  }

  lines.push('');
  lines.push(`Checked ${results.length} files — ${totalContainers} mjx-container elements typeset.`);
  lines.push(`Files with issues: ${bad.length}.`);
  lines.push(`  MathJax    — ${countPages('mathjax')} file(s): ${totalMerror} mjx-merror, ${totalLeakNodes} leaked text node(s).`);
  lines.push(`  Cross-refs — ${countPages('crossref')} file(s): ${totalRefMarkers} ???/?? marker(s), ${totalDangling} dangling anchor(s).`);
  lines.push(`  Other      — ${countPages('other')} file(s).`);
  if (totalNotTranscribed) {
    const byChapter = new Map();
    for (const r of results) {
      for (const nt of (r.notTranscribedRefs || [])) {
        byChapter.set(nt.targetChapter, (byChapter.get(nt.targetChapter) || 0) + 1);
      }
    }
    const parts = Array.from(byChapter.entries()).sort().map(([c, n]) => `${c}(${n})`);
    lines.push(`  (info) ${totalNotTranscribed} ref(s) into not-yet-transcribed exposés: ${parts.join(', ')} — not failures.`);
  }
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
      for (const m of (x.refMarkers || [])) {
        const where = m.inMath ? 'mjx-container' : `<${m.parentTag}>`;
        lines.push(`  [unresolved-ref] "${m.marker}" in ${where}`);
        lines.push(`     context: ${JSON.stringify(m.context)}`);
        if (m.sourceTeX) lines.push(`     sourceTeX: ${JSON.stringify(m.sourceTeX.slice(0, 200))}`);
      }
      for (const d of (x.danglingAnchors || [])) {
        lines.push(`  [dangling:${d.kind}] href="#${d.frag}" — no such id in any transcribed file`);
        if (d.context) lines.push(`     context: ${JSON.stringify(d.context)}`);
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
  const allFiles = listFiles();
  if (!allFiles.length) {
    console.error(`error: no .html files in ${HTML_DIR}`);
    process.exit(2);
  }

  // Global id collection reads EVERY transcribed file (even when only some are
  // being checked) so cross-exposé anchors always resolve against the full set.
  const globalIds = new Set();
  const perFileHtml = new Map();
  for (const f of allFiles) {
    const html = fs.readFileSync(path.join(HTML_DIR, f), 'utf8');
    perFileHtml.set(f, html);
    collectIds(html).forEach((id) => globalIds.add(id));
  }
  const transcribedIds = new Set(allFiles.map((f) => f.replace(/\.html$/, '')));
  const allChapterIds = loadAllChapterIds();

  const files = ONLY.length
    ? allFiles.filter((f) => ONLY.includes(f.replace(/\.html$/, '')))
    : allFiles;
  if (ONLY.length && files.length !== ONLY.length) {
    const found = new Set(files.map((f) => f.replace(/\.html$/, '')));
    const missing = ONLY.filter((id) => !found.has(id));
    console.error(`error: no file in ${HTML_DIR} for: ${missing.join(', ')}`);
    process.exit(2);
  }

  console.error(`${files.length} file(s) to check, ${globalIds.size} anchors collected from ${allFiles.length} file(s)`);

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

  const results = [];
  for (const f of files) {
    const chapterId = f.replace(/\.html$/, '');
    const url = `${BASE_URL}/${HTML_DIR_REL}/${f}`;
    const before = consoleMsgs.length;
    const beforeE = pageErrors.length;
    process.stderr.write(`  ${f.padEnd(20)} ... `);
    let scan;
    try {
      await page.goto(url, { waitUntil: 'load', timeout: LOAD_TIMEOUT_MS });
      scan = await typesetAndScan(page);
    } catch (e) {
      scan = { fatal: String(e), containers: 0, merrors: [], leakedMacros: [], refMarkers: [] };
    }
    const anchors = anchorPass(chapterId, perFileHtml.get(f), globalIds, transcribedIds, allChapterIds);
    const r = makeResult(chapterId, scan, anchors, consoleMsgs.slice(before), pageErrors.slice(beforeE));
    process.stderr.write(isBad(r)
      ? `ISSUES (math=${r.containers}, merror=${r.merrors.length}, leak=${r.leakedMacros.length}, mark=${r.refMarkers.length}, dangling=${r.danglingAnchors.length}, pageErr=${r.pageErrors.length}, console=${r.consoleMsgs.length}${r.typesetError ? ', typesetError' : ''})\n`
      : `ok (${r.containers} math${r.notTranscribedRefs.length ? `, ${r.notTranscribedRefs.length} refs into untranscribed exposés` : ''})\n`);
    results.push(r);
  }

  await browser.close();

  if (OUT_DIR) {
    for (const cat of Object.keys(CATEGORIES)) {
      const subset = results.filter((r) => categoryBad(r, cat)).map((r) => projectCategory(r, cat));
      const out = path.join(OUT_DIR, cat + '_errors.json');
      fs.writeFileSync(out, JSON.stringify(subset, null, 2));
      console.error(`wrote ${out} (${subset.length} file${subset.length === 1 ? '' : 's'})`);
    }
  }

  process.stdout.write(summarise(results));

  process.exit(results.some(isBad) ? 1 : 0);
})();
