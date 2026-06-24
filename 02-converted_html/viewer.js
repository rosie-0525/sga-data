/* SGA 2 viewer: loads the JSON manifest + per-chapter content and renders it
   with client-side MathJax 3 + XyJax-v3. Resolves cross-page anchors via the
   manifest's anchor_index. */
(function () {
  'use strict';

  var state = {
    lang: 'fr',
    manifest: null,
    chapterCache: {},      // chapterId -> chapter JSON
    pageToChapter: {},     // pageId -> chapterId
    anchorIndex: {},       // elementId -> pageId
    currentPage: null
  };

  var elPage = document.getElementById('page');
  var elSidebar = document.getElementById('sidebar');
  var elContent = document.getElementById('content');

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

  function loadManifest(lang) {
    return fetchJSON(lang + '.json').then(function (m) {
      state.manifest = m;
      state.lang = lang;
      state.chapterCache = {};
      state.pageToChapter = {};
      state.anchorIndex = m.anchor_index || {};
      m.chapters.forEach(function (ch) {
        (ch.page_ids || []).forEach(function (pid) { state.pageToChapter[pid] = ch.id; });
      });
      buildSidebar();
    });
  }

  function buildSidebar() {
    var m = state.manifest;
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
  }

  function chapterFor(pageId) {
    return state.pageToChapter[pageId] ||
           (state.manifest.chapters[0] && state.manifest.chapters[0].id);
  }

  function loadChapter(chapterId) {
    if (state.chapterCache[chapterId]) return Promise.resolve(state.chapterCache[chapterId]);
    return fetchJSON(state.lang + '/chapters/' + chapterId + '.json').then(function (c) {
      state.chapterCache[chapterId] = c;
      return c;
    });
  }

  function showPage(pageId, anchor) {
    var chId = chapterFor(pageId);
    if (!chId) return;
    loadChapter(chId).then(function (chapter) {
      var page = (chapter.pages || []).filter(function (p) { return p.id === pageId; })[0];
      if (!page) { page = chapter.pages[0]; pageId = page.id; }
      state.currentPage = pageId;
      renderPage(page);
      markCurrent(pageId);
      if (anchor) scrollToAnchor(anchor);
      else elContent.scrollTop = 0;
    }).catch(function (e) {
      elPage.innerHTML = '<p class="error">Erreur de chargement : ' + e.message + '</p>';
    });
  }

  function renderPage(page) {
    var html = page.html || '';
    if (!html.trim()) {
      html = '<h1>' + (page.title || '') + '</h1>' +
             '<p class="muted"><em>(Traduction non disponible — la version française est la référence.)</em></p>';
    }
    if (page.footnotes && page.footnotes.length) {
      html += '<section id="footnotes"><ol>';
      page.footnotes.forEach(function (f) {
        html += '<li id="' + f.id + '">' + f.html +
                ' <a class="backref" href="#' + f.id + 'ref" title="retour">↩</a></li>';
      });
      html += '</ol></section>';
    }
    elPage.innerHTML = html;
    wireProofs();
    typeset(elPage);
  }

  function wireProofs() {
    var heads = elPage.querySelectorAll('.proof-head');
    heads.forEach(function (h) {
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

  function scrollToAnchor(id) {
    var el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ block: 'center' });
      el.classList.add('target-flash');
      setTimeout(function () { el.classList.remove('target-flash'); }, 1300);
    }
  }

  function cssEscape(s) { return String(s).replace(/"/g, '\\"'); }

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
    return null;
  }

  function navigate(hash) {
    var r = resolveHash(hash);
    if (!r) {
      var def = state.manifest.default_page_id || state.manifest.chapters[0].page_ids[0];
      showPage(def, null);
      return;
    }
    showPage(r.page, r.anchor);
  }

  // intercept internal link clicks (incl. links inside rendered content)
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href^="#"]');
    if (!a) return;
    var hash = a.getAttribute('href');
    e.preventDefault();
    if (history.pushState) history.pushState(null, '', hash);
    navigate(hash);
  });

  window.addEventListener('popstate', function () { navigate(location.hash); });

  // language switch
  document.getElementById('lang-switch').addEventListener('click', function (e) {
    var b = e.target.closest('button[data-lang]');
    if (!b) return;
    var lang = b.getAttribute('data-lang');
    if (lang === state.lang) return;
    document.querySelectorAll('#lang-switch button').forEach(function (x) {
      x.classList.toggle('active', x === b);
    });
    var cur = state.currentPage;
    loadManifest(lang).then(function () { showPage(cur || location.hash.slice(1), null); });
  });

  document.getElementById('menu-toggle').addEventListener('click', function () {
    elSidebar.classList.toggle('open');
  });

  // boot
  loadManifest('fr').then(function () {
    if (state.manifest.chapters[0]) {
      var bt = document.getElementById('book-title');
      // keep the static title
    }
    navigate(location.hash || ('#' + (state.manifest.default_page_id || '')));
  }).catch(function (e) {
    elPage.innerHTML = '<p class="error">Impossible de charger le manifeste (' + e.message +
                       '). Servez ce dossier via un serveur HTTP (ex. <code>python3 -m http.server</code>).</p>';
  });
})();
