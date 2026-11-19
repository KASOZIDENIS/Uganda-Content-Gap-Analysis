// Checks, on the live wikis, which items on the editathon task lists have since been fixed.
//   node scripts/metrics.mjs [output.json]
// English, Luganda and Runyankore pages: does the page now show an image? Wikidata image list: does the item now have P18?
// (The two big Wikidata lists are not re-checked here; they are counted from participants' edits.)
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const rd = p => JSON.parse(readFileSync(join(root, p), 'utf-8'));
const config = rd('editathon/config.json');
const index = rd('editathon/tasks/index.json');
const UA = { 'User-Agent': 'UgandaAtlasEditathon/1.0 (https://kasozidenis.github.io/uganda-atlas/; wikimedia community user group uganda)' };
const LG_BOIL = new Set(['File:Arbcom ru editing.svg', 'File:Georgia in United States.svg', 'File:Kentucky counties map.png', 'File:Puzzle-W-glossy.svg', 'File:Texas in United States.svg']);
const NYN_BOIL = new Set(['File:OOjs UI icon edit-ltr.svg']);
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function api(wiki, params) {
  const q = new URLSearchParams(Object.assign({ format: 'json', formatversion: '2' }, params));
  for (let i = 0; i < 5; i++) {
    try {
      const r = await fetch(config.wikis[wiki].api + '?' + q, { headers: UA });
      if (r.status === 429 || r.status >= 500) { await sleep(2000 * (i + 1)); continue; }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return await r.json();
    } catch (e) { if (i === 4) throw e; await sleep(1000 * (i + 1)); }
  }
}

// returns Map(title -> true/false/null) for a batch of up to 50 rows
async function check(list, rows) {
  const res = new Map(), wiki = list.wiki;
  if (wiki === 'wikidatawiki') {
    const j = await api(wiki, { action: 'wbgetentities', ids: rows.map(r => r[0]).join('|'), props: 'claims' });
    for (const r of rows) { const e = j.entities && j.entities[r[0]]; res.set(r[0], e && !e.missing ? !!(e.claims && e.claims.P18 && e.claims.P18.length) : null); }
  } else if (wiki === 'enwiki') {
    const j = await api(wiki, { action: 'query', titles: rows.map(r => r[0]).join('|'), prop: 'pageprops', ppprop: 'page_image|page_image_free', redirects: '1' });
    const map = {}; for (const n of (j.query.normalized || [])) map[n.from] = n.to; for (const n of (j.query.redirects || [])) map[n.from] = n.to;
    const by = {}; for (const p of (j.query.pages || [])) by[p.title] = p;
    for (const r of rows) { let t = r[0]; for (let k = 0; k < 2; k++) t = map[t] || t; const p = by[t]; res.set(r[0], p && !p.missing ? !!(p.pageprops && p.pageprops.page_image) : null); }
  } else {
    const prefix = wiki === 'incubatorwiki' ? 'Wp/nyn/' : '', boil = wiki === 'incubatorwiki' ? NYN_BOIL : LG_BOIL;
    const imgs = {}, pages = {}; let cont = {};
    for (let k = 0; k < 30; k++) {
      const j = await api(wiki, Object.assign({ action: 'query', titles: rows.map(r => prefix + r[0]).join('|'), prop: 'images', imlimit: 'max' }, cont));
      for (const p of (j.query.pages || [])) { pages[p.title] = p; imgs[p.title] = (imgs[p.title] || []).concat((p.images || []).map(x => x.title)); }
      if (!j.continue) break; cont = j.continue;
    }
    for (const r of rows) { const p = pages[prefix + r[0]]; res.set(r[0], p && !p.missing ? (imgs[p.title] || []).some(f => !boil.has(f)) : null); }
  }
  return res;
}

const out = { generated: new Date().toISOString(), lists: {} };
for (const l of index.lists) {
  if (!['enwiki', 'lgwiki', 'incubatorwiki'].includes(l.wiki) && l.id !== 'wd-image-exists') continue;
  const rows = [];
  for (let n = 0; n < l.chunks; n++) rows.push(...rd(`editathon/tasks/${l.id}.${n}.json`));
  const m = { total: rows.length, open: 0, done: 0, unknown: 0 };
  for (let i = 0; i < rows.length; i += 50) {
    try {
      const res = await check(l, rows.slice(i, i + 50));
      for (const v of res.values()) { if (v === true) m.done++; else if (v === false) m.open++; else m.unknown++; }
    } catch (e) { m.unknown += Math.min(50, rows.length - i); console.log(l.id, 'batch failed:', e.message); }
    await sleep(250);
  }
  out.lists[l.id] = m;
  console.log(l.id, JSON.stringify(m));
}
const file = process.argv[2] || join(root, 'metrics.json');
mkdirSync(dirname(file), { recursive: true });
writeFileSync(file, JSON.stringify(out));
