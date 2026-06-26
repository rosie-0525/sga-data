/* SGA 2 viewer: loads the FR and EN JSON manifests + per-chapter content and
   renders them with client-side MathJax 3 + XyJax-v3. The two languages share an
   identical page/anchor structure, so a page is shown in both columns at once;
   the view switch (FR / EN / FR·EN) picks which columns are visible. Cross-page
   anchors resolve via the manifest's anchor_index. */
(function () {
  'use strict';

  var LANGS = ['fr', 'en'];

  var state = {
    view: 'both',                  // 'fr' | 'en' | 'both'
    manifests: { fr: null, en: null },
    chapterCache: { fr: {}, en: {} },
    pageToChapter: {},             // shared: page_ids are identical across languages
    anchorIndex: {},               // shared: anchor ids are identical across languages
    currentPage: null,
    lastCite: {},                  // bibId -> id of the most recently visited citation
    scrollSync: false,             // when true, the two columns scroll in lockstep
    orderedPages: [],              // flattened page_ids in reading order (set in loadManifests)
    pageTitles: { fr: {}, en: {} } // page_id -> title, per language (set in loadManifests)
  };

  var elSidebar = document.getElementById('sidebar');
  var panes = {
    fr: document.getElementById('page-fr'),
    en: document.getElementById('page-en')
  };

  var mobileMQ = window.matchMedia('(max-width: 800px)');

  // Typeset an element, chaining through MathJax's startup promise so we never
  // race the async CDN load (and so concurrent typesets serialize cleanly).
  function typeset(el) {
    if (!window.MathJax) return;
    if (MathJax.startup && MathJax.startup.promise) {
      MathJax.startup.promise = MathJax.startup.promise
        .then(function () { return MathJax.typesetPromise([el]); })
        .catch(function (e) { console.warn('MathJax typeset', e); });
    } else if (MathJax.typesetPromise) {
      MathJax.typesetPromise([el]).catch(function (e) { console.warn('MathJax', e); });
    }
  }

  function fetchJSON(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status + ' for ' + url);
      return r.json();
    });
  }

  // Languages whose columns are currently visible (and therefore rendered).
  function activeLangs() {
    return state.view === 'both' ? LANGS.slice() : [state.view];
  }

  // The manifest whose titles drive the table of contents.
  function tocLang() { return state.view === 'en' ? 'en' : 'fr'; }

  function defaultPage() {
    var m = state.manifests.fr;
    return m.default_page_id || m.chapters[0].page_ids[0];
  }

  function loadManifests() {
    return Promise.all(LANGS.map(function (lang) {
      return fetchJSON(lang + '.json').then(function (m) { state.manifests[lang] = m; });
    })).then(function () {
      var fr = state.manifests.fr;
      state.pageToChapter = {};
      state.anchorIndex = fr.anchor_index || {};
      state.orderedPages = [];
      fr.chapters.forEach(function (ch) {
        (ch.page_ids || []).forEach(function (pid) {
          state.pageToChapter[pid] = ch.id;
          state.orderedPages.push(pid);          // chapters[].page_ids = reading order
        });
      });
      state.pageTitles = { fr: {}, en: {} };
      LANGS.forEach(function (lang) {
        var map = {};
        (state.manifests[lang].toc || []).forEach(function (t) { map[t.page_id] = t.title; });
        state.pageTitles[lang] = map;
      });
      buildSidebar();
    });
  }

  function buildSidebar() {
    var m = state.manifests[tocLang()];
    var tocByPage = {};
    m.toc.forEach(function (t) { tocByPage[t.page_id] = t; });
    var html = '';
    m.chapters.forEach(function (ch) {
      var pids = ch.page_ids || [];
      var landing = pids[0];
      var num = ch.number ? '<span class="cnum">' + ch.number + '</span>' : '';
      html += '<div class="chap" data-chapter="' + ch.id + '">';
      html += '<a href="#' + encodeURIComponent(landing) + '" data-page="' + landing + '">' +
              num + ch.title + '</a>';
      if (pids.length > 1) {
        html += '<div class="pages">';
        pids.slice(1).forEach(function (pid) {
          var t = tocByPage[pid] || { title: pid };
          html += '<a href="#' + encodeURIComponent(pid) + '" data-page="' + pid + '">' +
                  t.title + '</a>';
        });
        html += '</div>';
      }
      html += '</div>';
    });
    elSidebar.innerHTML = html;
    typeset(elSidebar);
    if (state.currentPage) markCurrent(state.currentPage);
  }

  function chapterFor(pageId) {
    return state.pageToChapter[pageId] ||
           (state.manifests.fr.chapters[0] && state.manifests.fr.chapters[0].id);
  }

  function loadChapter(chapterId, lang) {
    var cache = state.chapterCache[lang];
    if (cache[chapterId]) return Promise.resolve(cache[chapterId]);
    return fetchJSON(lang + '/chapters/' + chapterId + '.json').then(function (c) {
      cache[chapterId] = c;
      return c;
    });
  }

  function showPage(pageId, anchor) {
    var chId = chapterFor(pageId);
    if (!chId) return;
    var langs = activeLangs();
    // clear the inactive column so its stale content/ids don't linger
    LANGS.forEach(function (lang) {
      if (langs.indexOf(lang) === -1) panes[lang].innerHTML = '';
    });
    Promise.all(langs.map(function (lang) {
      return loadChapter(chId, lang).then(function (chapter) {
        var page = (chapter.pages || []).filter(function (p) { return p.id === pageId; })[0];
        if (!page) page = chapter.pages[0];
        return { lang: lang, page: page };
      });
    })).then(function (results) {
      var resolved = (results[0] && results[0].page) ? results[0].page.id : pageId;
      state.currentPage = resolved;
      results.forEach(function (r) { renderPage(panes[r.lang], r.page, r.lang); });
      markCurrent(resolved);
      if (anchor) {
        scrollToAnchor(anchor);
      } else {
        langs.forEach(function (lang) { panes[lang].parentNode.scrollTop = 0; });
        if (mobileMQ.matches) window.scrollTo(0, 0);
      }
    }).catch(function (e) {
      langs.forEach(function (lang) {
        panes[lang].innerHTML = '<p class="error">Erreur de chargement : ' + e.message + '</p>';
      });
    });
  }

  // Bottom-of-page pager: links to the previous and next page in reading order.
  // Reading order is the flattened chapters[].page_ids list (state.orderedPages);
  // the global click handler routes the "#<id>" links, so no extra wiring is needed.
  function pagerHTML(pageId, lang) {
    var list = state.orderedPages || [];
    var i = list.indexOf(pageId);
    if (i === -1) return '';
    var prev = i > 0 ? list[i - 1] : null;
    var next = i < list.length - 1 ? list[i + 1] : null;
    if (!prev && !next) return '';
    var titles = state.pageTitles[lang] || {};
    var prevWord = (lang === 'en') ? 'Previous' : 'Précédent';
    var nextWord = (lang === 'en') ? 'Next' : 'Suivant';
    var navLabel = (lang === 'en') ? 'Page navigation' : 'Navigation entre les pages';
    function link(pid, cls, dir) {
      return '<a class="' + cls + '" href="#' + encodeURIComponent(pid) + '">' +
             '<span class="page-nav-dir">' + dir + '</span>' +
             '<span class="page-nav-title">' + (titles[pid] || pid) + '</span></a>';
    }
    var html = '<nav class="page-nav" aria-label="' + navLabel + '">';
    html += prev ? link(prev, 'page-nav-prev', '‹ ' + prevWord)
                 : '<span class="page-nav-spacer"></span>';
    if (next) html += link(next, 'page-nav-next', nextWord + ' ›');
    html += '</nav>';
    return html;
  }

  function renderPage(el, page, lang) {
    var html = (page && page.html) || '';
    if (!html.trim()) {
      var msg = (lang === 'en')
        ? '<p class="muted"><em>(Translation not available — the French version is the reference.)</em></p>'
        : '<p class="muted"><em>(Traduction non disponible — la version française est la référence.)</em></p>';
      html = '<h1>' + ((page && page.title) || '') + '</h1>' + msg;
    }
    if (page && page.footnotes && page.footnotes.length) {
      html += '<section class="footnotes"><ol>';
      page.footnotes.forEach(function (f) {
        html += '<li id="' + f.id + '">' + f.html +
                ' <a class="backref" href="#' + f.id + 'ref" title="retour">↩</a></li>';
      });
      html += '</ol></section>';
    }
    html += pagerHTML(page && page.id, lang);
    el.innerHTML = html;
    wireProofs(el);
    typeset(el);
  }

  function wireProofs(scope) {
    scope.querySelectorAll('.proof-head').forEach(function (h) {
      h.addEventListener('click', function () {
        h.parentNode.classList.toggle('collapsed');
      });
    });
  }

  function markCurrent(pageId) {
    elSidebar.querySelectorAll('a.current').forEach(function (a) { a.classList.remove('current'); });
    var a = elSidebar.querySelector('a[data-page="' + cssEscape(pageId) + '"]');
    if (a) {
      a.classList.add('current');
      a.scrollIntoView({ block: 'nearest' });
    }
  }

  // Scroll every visible column to its own copy of the anchor. The two columns
  // share element ids, so lookups are scoped per pane rather than via getElementById.
  function scrollToAnchor(id) {
    var sel = '[id="' + cssEscape(id) + '"]';
    activeLangs().forEach(function (lang) {
      var el = panes[lang].querySelector(sel);
      if (!el) return;
      el.scrollIntoView({ block: 'center' });
      el.classList.add('target-flash');
      (function (node) {
        setTimeout(function () { node.classList.remove('target-flash'); }, 1300);
      })(el);
    });
  }

  function anchorInCurrent(id) {
    var sel = '[id="' + cssEscape(id) + '"]';
    return activeLangs().some(function (lang) { return !!panes[lang].querySelector(sel); });
  }

  function cssEscape(s) { return String(s).replace(/(["\\])/g, '\\$1'); }

  // Resolve a hash like "#I.1.3" or "#I-1" into a {page, anchor}.
  function resolveHash(hash) {
    var raw = decodeURIComponent(hash.replace(/^#/, ''));
    if (!raw) return null;
    if (state.pageToChapter.hasOwnProperty(raw)) return { page: raw, anchor: null };
    var pid = state.anchorIndex[raw];
    if (pid) return { page: pid, anchor: raw };
    // toc-anchor-<CHAP> style fallbacks -> jump to chapter landing page
    var m = raw.match(/^toc-anchor-(.+)$/);
    if (m) {
      var key = m[1].replace(/-/g, '.');
      var pid2 = state.anchorIndex[key] || (state.pageToChapter.hasOwnProperty(key) ? key : null);
      if (pid2) return { page: pid2, anchor: key };
    }
    // in-page anchor (e.g. a footnote target/back-ref) already on screen
    if (anchorInCurrent(raw)) return { page: state.currentPage, anchor: raw };
    return null;
  }

  function navigate(hash) {
    var r = resolveHash(hash);
    if (!r) {
      showPage(defaultPage(), null);
      return;
    }
    if (r.page === state.currentPage && r.anchor) {
      scrollToAnchor(r.anchor);          // already loaded — just scroll
    } else {
      showPage(r.page, r.anchor);
    }
  }

  // intercept internal link clicks (incl. links inside rendered content)
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href^="#"]');
    if (!a) return;
    var hash = a.getAttribute('href');
    // Citation source -> remember it so the bibliography entry's back-button
    // can return to the most recently visited citation (like a footnote ↩).
    if (a.classList.contains('cite-src') && a.id) {
      state.lastCite[hash.replace(/^#/, '')] = a.id;
    } else if (a.classList.contains('bibref-back')) {
      var last = state.lastCite[a.getAttribute('data-bib')];
      if (last) hash = '#' + last;        // else fall back to the static href
    }
    e.preventDefault();
    if (history.pushState) history.pushState(null, '', hash);
    navigate(hash);
    // on a phone, picking an entry from the overlay TOC should close it
    if (mobileMQ.matches && a.closest('#sidebar')) {
      document.documentElement.classList.add('nav-collapsed');
    }
  });

  window.addEventListener('popstate', function () { navigate(location.hash); });

  // view switch: FR-only / EN-only / both side by side
  document.getElementById('view-switch').addEventListener('click', function (e) {
    var b = e.target.closest('button[data-view]');
    if (!b) return;
    setView(b.getAttribute('data-view'));
  });

  function setView(view) {
    if (view === state.view) return;
    state.view = view;
    document.querySelectorAll('#view-switch button').forEach(function (x) {
      x.classList.toggle('active', x.getAttribute('data-view') === view);
    });
    document.body.classList.remove('view-fr', 'view-en', 'view-both');
    document.body.classList.add('view-' + view);
    buildSidebar();                       // TOC language may have changed
    if (state.currentPage) showPage(state.currentPage, null);
  }

  // collapsible table of contents
  document.getElementById('menu-toggle').addEventListener('click', function () {
    document.documentElement.classList.toggle('nav-collapsed');
  });

  // ---- synchronized scrolling of the two columns ----
  // Only meaningful side by side on desktop: single-language view shows one
  // pane, and on mobile the panes stack and the window scrolls instead.
  function syncOn() {
    return state.scrollSync && state.view === 'both' && !mobileMQ.matches;
  }

  // Mirror one pane's scroll position onto the other. The lock (released next
  // frame) stops the mirrored scroll from echoing back into an infinite loop.
  var syncLock = false;
  function mirror(src, dst) {
    if (syncLock) return;
    syncLock = true;
    dst.scrollTop = src.scrollTop;
    requestAnimationFrame(function () { syncLock = false; });
  }

  // The scrollable container is the .pane <section> (parent of #page-fr/#page-en).
  var paneFr = panes.fr.parentNode, paneEn = panes.en.parentNode;
  paneFr.addEventListener('scroll', function () { if (syncOn()) mirror(paneFr, paneEn); });
  paneEn.addEventListener('scroll', function () { if (syncOn()) mirror(paneEn, paneFr); });

  // ---- settings popover ----
  var settingsToggle = document.getElementById('settings-toggle');
  var settingsPanel = document.getElementById('settings-panel');

  function openSettings(open) {
    settingsPanel.hidden = !open;
    settingsToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  settingsToggle.addEventListener('click', function (e) {
    e.stopPropagation();
    openSettings(settingsPanel.hidden);
  });

  document.getElementById('settings-save').addEventListener('click', function () {
    var sel = settingsPanel.querySelector('input[name="scroll-mode"]:checked');
    state.scrollSync = !!sel && sel.value === 'together';
    try { localStorage.setItem('sga2.scrollSync', state.scrollSync ? '1' : '0'); } catch (e) {}
    LANGS.forEach(function (lang) { panes[lang].parentNode.scrollTop = 0; });
    if (mobileMQ.matches) window.scrollTo(0, 0);
    openSettings(false);
  });

  // close the popover on outside click or Escape
  document.addEventListener('click', function (e) {
    if (settingsPanel.hidden) return;
    if (!settingsPanel.contains(e.target) && e.target !== settingsToggle) openSettings(false);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !settingsPanel.hidden) openSettings(false);
  });

  function loadSettings() {
    var saved = null;
    try { saved = localStorage.getItem('sga2.scrollSync'); } catch (e) {}
    state.scrollSync = saved === '1';
    var val = state.scrollSync ? 'together' : 'separate';
    var radio = settingsPanel.querySelector('input[name="scroll-mode"][value="' + val + '"]');
    if (radio) radio.checked = true;
  }

  // boot
  loadSettings();
  loadManifests().then(function () {
    navigate(location.hash || ('#' + defaultPage()));
  }).catch(function (e) {
    LANGS.forEach(function (lang) {
      if (panes[lang]) {
        panes[lang].innerHTML = '<p class="error">Impossible de charger le manifeste (' +
          e.message + '). Servez ce dossier via un serveur HTTP (ex. ' +
          '<code>python3 -m http.server</code>).</p>';
      }
    });
  });
})();
