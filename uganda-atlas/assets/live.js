// Live additions to the Atlas (loaded by index.html):
//  1. a banner under the top bar for the Mega Editathon (status, countdown, top three, link to the leaderboard)
//  2. a "Live check" strip on the dashboards whose lists the editathon is fixing
// It only reads small public files; nothing here changes the dashboards' own code.
(function () {
  'use strict';
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var fmt = function (n) { return Number(n || 0).toLocaleString('en-GB'); };
  var J = function (u) { return fetch(u).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); };
  var CFG = null, BOARD = null, METRICS = null;

  var css = document.createElement('style');
  css.textContent =
    '.ehbar{background:color-mix(in srgb,var(--blue) 14%,var(--panel));border-bottom:1px solid var(--line);font-size:13.5px}' +
    '.ehbar .wrap{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;padding-top:8px;padding-bottom:8px}' +
    '.ehbar a.go{margin-left:auto;font-weight:600;color:var(--fg);text-decoration:none;border:1px solid var(--fg);border-radius:999px;padding:3px 12px}' +
    '.ehbar a.go:hover{background:var(--fg);color:var(--bg)}' +
    '.ehbar .d{width:8px;height:8px;border-radius:50%;background:var(--green);display:inline-block;margin-right:6px;animation:ehp 1.8s infinite}' +
    '@keyframes ehp{0%{box-shadow:0 0 0 0 rgba(51,153,102,.6)}70%{box-shadow:0 0 0 8px rgba(51,153,102,0)}100%{box-shadow:0 0 0 0 rgba(51,153,102,0)}}' +
    '.ehbar .soft{color:var(--soft)}' +
    '.livestrip{margin:0 0 18px;padding:12px 16px;border:1px solid var(--green);border-radius:6px;background:color-mix(in srgb,var(--green) 10%,transparent);font-size:14px}' +
    '.livestrip b{font-family:var(--f-display);font-size:20px;font-weight:600}';
  document.head.appendChild(css);

  function dur(ms) {
    var d = Math.floor(ms / 864e5), h = Math.floor(ms % 864e5 / 36e5), m = Math.floor(ms % 36e5 / 6e4);
    return d + 'd ' + h + 'h ' + m + 'm';
  }

  function banner() {
    var top = document.querySelector('.topbar');
    if (!top || document.getElementById('ehbar') || !CFG) return;
    var el = document.createElement('div'); el.className = 'ehbar'; el.id = 'ehbar';
    top.parentNode.insertBefore(el, top.nextSibling);
    var paint = function () {
      var now = new Date(), s = new Date(CFG.start), e = new Date(CFG.end), st;
      if (now < s) st = '<span><b>' + esc(CFG.name) + '</b> starts in ' + dur(s - now) + '</span>';
      else if (now <= e) st = '<span><span class="d"></span><b>' + esc(CFG.name) + '</b> is live · ends in ' + dur(e - now) + '</span>';
      else st = '<span><b>' + esc(CFG.name) + '</b> has ended</span>';
      var top3 = '';
      if (BOARD && BOARD.users && BOARD.users.some(function (u) { return u.points > 0; })) {
        top3 = '<span class="soft">Leading: ' + BOARD.users.filter(function (u) { return u.points > 0; }).slice(0, 3)
          .map(function (u) { return esc(u.user) + ' (' + fmt(u.points) + ')'; }).join(' · ') + '</span>';
      }
      el.innerHTML = '<div class="wrap">' + st + top3 + '<a class="go" href="editathon.html">Live leaderboard</a></div>';
    };
    paint(); setInterval(paint, 30000);
    el._paint = paint;
  }

  // dashboards the editathon is fixing -> task lists to total up
  var MAP = {
    english: { lists: ['en-image-exists', 'en-pick-category', 'en-capture'], what: 'English articles that had no image', now: 'now show one' },
    luganda: { lists: ['lg-image-exists', 'lg-capture'], what: 'Luganda articles that had no image', now: 'now show one' },
    runyankore: { lists: ['nyn-image-exists', 'nyn-capture'], what: 'Runyankore pages that had no image', now: 'now show one' },
    wikidata: { lists: ['wd-image-exists'], what: 'Wikidata items with a Commons image waiting to be connected', now: 'now have it connected' }
  };
  function strip() {
    var id = (location.hash || '').replace(/^#/, '').split('.')[0];
    var old = document.getElementById('livestrip');
    if (old) { if (old.dataset.id === id) return; old.remove(); }
    var m = MAP[id]; if (!m || !METRICS || !METRICS.lists) return;
    var tot = 0, done = 0, open = 0;
    m.lists.forEach(function (l) { var x = METRICS.lists[l]; if (x) { tot += x.total; done += x.done; open += x.open; } });
    if (!tot) return;
    var head = document.querySelector('#app h1'); if (!head) return;
    var anchor = head.closest('.wrap') || head.parentNode;
    var el = document.createElement('div'); el.className = 'livestrip wrap'; el.id = 'livestrip'; el.dataset.id = id;
    var when = new Date(METRICS.generated).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
    el.innerHTML = '<span class="eyebrow">Live check · ' + esc(when) + '</span><div><b>' + fmt(done) + '</b> of ' + fmt(tot) + ' ' + esc(m.what) + ' (September 2026) ' + esc(m.now) +
      ' on the live wiki; <b>' + fmt(open) + '</b> still open. <a href="editathon.html#progress">See the editathon progress</a></div>';
    anchor.parentNode.insertBefore(el, anchor.nextSibling);
  }

  function boot() {
    J('editathon/config.json?t=' + Math.floor(Date.now() / 60000)).then(function (c) {
      CFG = c; banner();
      J(c.snapshotUrl + '?t=' + Math.floor(Date.now() / 120000)).then(function (b) { BOARD = b; var e = document.getElementById('ehbar'); if (e && e._paint) e._paint(); }).catch(function () { });
      J(c.metricsUrl + '?t=' + Math.floor(Date.now() / 300000)).then(function (m) { METRICS = m; strip(); }).catch(function () { });
    }).catch(function () { });
    var app = document.getElementById('app');
    if (app) new MutationObserver(function () { strip(); }).observe(app, { childList: true, subtree: false });
    window.addEventListener('hashchange', function () { setTimeout(strip, 400); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
