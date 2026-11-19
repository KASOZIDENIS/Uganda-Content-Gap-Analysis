// The editathon leaderboard: one implementation, used by the page in the browser
// and by the scheduled job in Node (scripts/leaderboard.mjs).
//
// It reads the edits of the signed-up participants from the Wikimedia APIs
// (list=usercontribs, up to 50 users per call) for the editathon window, gives
// each edit its points, and counts which task-list items were worked on.

const FILE_CATEGORY_RE = /^File:/;
const LABEL_RE = /\|lg\b/;
const LABEL_CTX = /wbsetlabel|wbeditentity|wbsetlabeldescriptionaliases/;
const IMAGE_CTX = /wbcreateclaim|wbsetclaim|wbeditentity|wbsetreference|wbsetclaimvalue/;
const P18_RE = /\bP18\b/;
const QID_RE = /^Q\d+$/;

export function windowState(config, now = new Date()) {
  const s = new Date(config.start), e = new Date(config.end);
  return now < s ? 'upcoming' : now > e ? 'ended' : 'live';
}

export function cleanUser(u) {
  return String(u || '').replace(/_/g, ' ').replace(/\s+/g, ' ').trim();
}

// Give one contribution its kinds and points. `ctx.titleMap[wiki]` maps a page
// title to the task list it belongs to; `ctx.qidList` maps item ids to lists.
export function classify(wiki, c, config, ctx) {
  const P = config.points;
  const out = { kinds: [], points: 0, list: null, item: null };
  const tags = c.tags || [];
  if (tags.includes('mw-reverted')) return null;          // undone edits earn nothing
  const title = c.title || '';
  // only content counts: articles and items everywhere, files and categories on Commons (not talk or user pages)
  const okNs = wiki === 'commonswiki' ? (c.ns === 6 || c.ns === 14) : c.ns === 0;
  if (!okNs) return null;
  if (wiki === 'incubatorwiki' && !title.startsWith('Wp/nyn/')) return null;
  const comment = c.comment || '';

  if (wiki === 'commonswiki') {
    if (c.ns === 6 && c.new) { out.kinds.push('upload'); out.points += P.upload; }
  } else if (wiki === 'wikidatawiki') {
    if (c.ns !== 0 || !QID_RE.test(title)) return null;
    out.item = title;
    if (comment.startsWith('/* wb') && LABEL_RE.test(comment) && LABEL_CTX.test(comment)) {
      out.kinds.push('label'); out.points += P.luganda_label; out.list = 'wd-no-luganda';
    }
    if (comment.startsWith('/* wb') && IMAGE_CTX.test(comment) && P18_RE.test(comment)) {
      out.kinds.push('image'); out.points += P.wikidata_image;
      out.list = (ctx.qidList && ctx.qidList.get(title)) || 'wd-capture';
    }
  } else {
    const map = ctx.titleMap[wiki];
    const list = map && map.get(title);
    if (list) { out.kinds.push('task'); out.points += P.task_page; out.list = list; out.item = title; }
  }
  return out;
}

async function api(url, params, fetchFn, tries = 4) {
  const q = new URLSearchParams(Object.assign({ format: 'json', formatversion: '2', origin: '*' }, params));
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetchFn(url + '?' + q.toString());
      if (r.status === 429 || r.status >= 500) { await new Promise(res => setTimeout(res, 1500 * (i + 1))); continue; }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return await r.json();
    } catch (e) {
      if (i === tries - 1) throw e;
      await new Promise(res => setTimeout(res, 800 * (i + 1)));
    }
  }
}

// every contribution of `users` to one wiki inside the window
export async function fetchContribs(wiki, cfg, users, startISO, endISO, fetchFn) {
  const rows = [];
  for (let i = 0; i < users.length; i += 50) {
    const group = users.slice(i, i + 50);
    let cont = {};
    for (let page = 0; page < 200; page++) {
      const j = await api(cfg.api, Object.assign({
        action: 'query', list: 'usercontribs', ucuser: group.join('|'), ucstart: endISO, ucend: startISO,
        uclimit: '500', ucdir: 'older', ucprop: 'ids|title|timestamp|comment|flags|tags'
      }, cont), fetchFn);
      for (const c of (j.query && j.query.usercontribs) || []) rows.push(Object.assign({ wiki }, c));
      if (!j.continue) break;
      cont = j.continue;
    }
  }
  return rows;
}

export async function computeBoard({ config, users, ctx, fetchFn, now = new Date() }) {
  const state = windowState(config, now);
  const names = users.map(u => cleanUser(u.user)).filter(Boolean);
  const board = {
    generated: now.toISOString(), state, start: config.start, end: config.end,
    users: [], totals: {}, progress: { lists: {} }, feed: [], errors: []
  };
  const byUser = new Map(names.map(n => [n.toLowerCase(), {
    user: n, team: (users.find(u => cleanUser(u.user).toLowerCase() === n.toLowerCase()) || {}).team || '',
    points: 0, edits: 0, byWiki: {}, tasks: 0, uploads: 0, labels: 0, images: 0, last: null
  }]));
  if (state === 'upcoming' || !names.length) return finish(board, byUser, config, ctx, new Map());

  const endISO = (now < new Date(config.end) ? now : new Date(config.end)).toISOString();
  const wikis = Object.entries(config.wikis);
  const results = await Promise.all(wikis.map(async ([wiki, cfg]) => {
    try { return await fetchContribs(wiki, cfg, names, config.start, endISO, fetchFn); }
    catch (e) { board.errors.push(wiki + ': ' + e.message); return []; }
  }));

  const seen = new Set(), dayPage = new Set(), items = new Map(); // list -> Set(items)
  const feed = [];
  for (const c of results.flat()) {
    const key = c.wiki + ':' + c.revid;
    if (seen.has(key)) continue;
    seen.add(key);
    const u = byUser.get(cleanUser(c.user).toLowerCase());
    if (!u) continue;
    const k = classify(c.wiki, c, config, ctx);
    if (!k) continue;
    // one base point per page per day, so tiny repeated edits do not count
    const dk = [u.user, c.wiki, c.title, (c.timestamp || '').slice(0, 10)].join('|');
    let pts = k.points;
    if (!dayPage.has(dk)) { dayPage.add(dk); pts += config.points.edit; }
    u.points += pts; u.edits++;
    u.byWiki[c.wiki] = (u.byWiki[c.wiki] || 0) + 1;
    if (k.kinds.includes('upload')) u.uploads++;
    if (k.kinds.includes('label')) u.labels++;
    if (k.kinds.includes('image')) u.images++;
    if (k.kinds.includes('task')) u.tasks++;
    if (!u.last || c.timestamp > u.last) u.last = c.timestamp;
    if (k.list && k.item) {
      if (!items.has(k.list)) items.set(k.list, new Set());
      items.get(k.list).add(k.item);
    }
    feed.push({ wiki: c.wiki, user: u.user, title: c.title, ts: c.timestamp, kind: k.kinds[0] || 'edit', points: pts,
                comment: (c.comment || '').slice(0, 140), revid: c.revid });
  }
  feed.sort((a, b) => (a.ts < b.ts ? 1 : -1));
  board.feed = feed.slice(0, 80);
  return finish(board, byUser, config, ctx, items);
}

function finish(board, byUser, config, ctx, items) {
  board.users = [...byUser.values()].sort((a, b) => b.points - a.points || b.edits - a.edits || a.user.localeCompare(b.user));
  let rank = 0, prev = null, n = 0;
  for (const u of board.users) {
    n++;
    if (u.points !== prev) { rank = n; prev = u.points; }
    u.rank = u.points ? rank : null;
  }
  const t = { participants: board.users.length, active: 0, edits: 0, points: 0, uploads: 0, labels: 0, images: 0, tasks: 0 };
  for (const u of board.users) {
    if (u.edits) t.active++;
    t.edits += u.edits; t.points += u.points; t.uploads += u.uploads; t.labels += u.labels; t.images += u.images; t.tasks += u.tasks;
  }
  board.totals = t;
  for (const l of (ctx.lists || [])) {
    board.progress.lists[l.id] = { done: items.has(l.id) ? items.get(l.id).size : 0, total: l.count };
  }
  return board;
}

// The sets the classifier needs from the task lists (small lists only)
export function buildContext(index, loaded) {
  const titleMap = { enwiki: new Map(), lgwiki: new Map(), incubatorwiki: new Map() };
  const qidList = new Map();
  for (const l of index.lists) {
    const rows = loaded[l.id] || [];
    if (titleMap[l.wiki]) {
      for (const r of rows) titleMap[l.wiki].set(l.wiki === 'incubatorwiki' ? 'Wp/nyn/' + r[0] : r[0], l.id);
    } else if (l.id === 'wd-image-exists') {
      for (const r of rows) qidList.set(r[0], l.id);
    }
  }
  return { titleMap, qidList, lists: index.lists };
}

export const SMALL_LISTS = ['en-image-exists', 'en-pick-category', 'en-capture', 'lg-image-exists', 'lg-capture',
  'nyn-image-exists', 'nyn-capture', 'wd-image-exists'];
