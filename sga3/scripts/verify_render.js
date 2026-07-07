// Headless smoke test for the generated translation-viewer data tree.
// Serves nothing itself — expects a static server rooted at the sga/ super-repo
// so paper.html's ../../translation-viewer/... paths resolve. Loads paper.html,
// navigates a couple of pages, waits for MathJax, and reports what rendered.
const puppeteer = require('puppeteer');

const BASE = process.argv[2]; // e.g. http://localhost:8765
const PAPER = BASE + '/sga3/02-converted_html/paper.html';

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  const consoleErrors = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', (e) => consoleErrors.push('PAGEERROR: ' + e.message));

  async function inspect(hash, label) {
    await page.goto(PAPER + hash, { waitUntil: 'networkidle0', timeout: 60000 });
    // wait for MathJax to finish the async typeset
    await page.evaluate(() => window.MathJax && MathJax.startup && MathJax.startup.promise);
    await new Promise((r) => setTimeout(r, 800));
    const r = await page.evaluate(() => {
      const panes = document.getElementById('panes');
      const leftCells = panes.querySelectorAll('.cell-left');
      const svg = panes.querySelectorAll('mjx-container svg, svg[data-mml-node], .cell-left svg').length;
      const merr = panes.querySelectorAll('mjx-merror').length;
      const rawTeX = /\\\(|\\\[|\\xymatrix/.test(panes.textContent);
      const foot = panes.querySelector('#footnotes, section#footnotes, [id="footnotes"]');
      const footItems = foot ? foot.querySelectorAll('li').length : 0;
      const backrefs = foot ? foot.querySelectorAll('a.backref').length : 0;
      const sidebarLinks = document.querySelectorAll('#sidebar a').length;
      const title = document.getElementById('book-title').textContent;
      const firstBlock = leftCells[0] ? leftCells[0].textContent.trim().slice(0, 60) : '';
      return { blocks: leftCells.length, svg, merr, rawTeX, footItems, backrefs,
               sidebarLinks, title, firstBlock, curPage: panes.dataset.pageId };
    });
    console.log(`\n[${label}] page=${r.curPage}  bookTitle="${r.title}"`);
    console.log(`  sidebar links: ${r.sidebarLinks}`);
    console.log(`  left blocks:   ${r.blocks}`);
    console.log(`  MathJax SVG:   ${r.svg}   mjx-merror: ${r.merr}   raw \\(/\\[ left in DOM: ${r.rawTeX}`);
    console.log(`  footnotes:     ${r.footItems} items, ${r.backrefs} back-arrows`);
    console.log(`  first block:   "${r.firstBlock}…"`);
    return r;
  }

  async function testAnchorJump() {
    // Click a cross-PAGE reference link (target not in the current DOM) and
    // confirm the viewer navigates to the right section page + flashes it.
    await page.goto(PAPER + '#XV-1', { waitUntil: 'networkidle0', timeout: 60000 });
    await page.evaluate(() => window.MathJax && MathJax.startup && MathJax.startup.promise);
    const res = await page.evaluate(() => {
      for (const a of document.querySelectorAll('#panes .cell-left a.ref[href^="#"]')) {
        const id = decodeURIComponent(a.getAttribute('href').slice(1));
        if (document.getElementById(id)) continue; // same-page ref; want a cross-page one
        a.click();
        return { ok: true, href: a.getAttribute('href') };
      }
      return { ok: false, reason: 'no cross-page ref link found' };
    });
    if (!res.ok) { console.log(`\n[anchor jump] ${res.reason}`); return; }
    await new Promise((r) => setTimeout(r, 1200));
    const after = await page.evaluate((href) => {
      const id = decodeURIComponent(href.slice(1));
      const el = document.getElementById(id);
      return { pageId: document.getElementById('panes').dataset.pageId,
               targetExists: !!el, flashed: el ? el.classList.contains('target-flash') : false };
    }, res.href);
    console.log(`\n[anchor jump] clicked ${res.href} -> landed page=${after.pageId} ` +
                `targetExists=${after.targetExists} flashed=${after.flashed}`);
  }

  await inspect('#I', 'default / Exposé I');
  await inspect('#VIII', 'Exposé VIII (footnotes)');
  await inspect('#IV', 'Exposé IV (xymatrix-heavy)');
  await testAnchorJump();

  console.log('\n=== console/page errors (' + consoleErrors.length + ') ===');
  consoleErrors.slice(0, 15).forEach((e) => console.log('  ! ' + e));

  await browser.close();
})().catch((e) => { console.error('FATAL', e); process.exit(1); });
