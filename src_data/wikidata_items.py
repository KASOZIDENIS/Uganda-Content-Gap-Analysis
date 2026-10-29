# -*- coding: utf-8 -*-
"""Every Wikidata item about Uganda, one row each, with the columns the
Wikidata analysis is made from.

The analysis on the Wikidata dashboard counts these items: how many carry a
label in Luganda, English, Swahili, French or German; what they are; where they
are; whether they have coordinates, an image, a Commons category and an article
in English, Luganda or Swahili Wikipedia; and, for people, their gender. This
reads them as rows so the dashboard can hold the data behind its counts.

Wikidata numbers its items in order, so the items are read in ranges of item
numbers small enough for the Query Service, using the counts per range that
projects_history.wikidata() has already stored.

    python src_data/wikidata_items.py
"""

import bisect
import datetime
import time

import category_profiles as cp
import wikiapi
import sister_projects as sp
import ug_utils

SCRIPT = 'wikidata_items'
WD = 'https://www.wikidata.org/w/api.php'
ENTITY = 'http://www.wikidata.org/entity/Q'
PER_RANGE = 6000
BUCKET = 250000
GENDER = {'Q6581072': 'female', 'Q6581097': 'male', 'Q1052281': 'trans woman',
          'Q2449503': 'trans man', 'Q48270': 'non-binary'}


def _schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS wd_items (
            qid text PRIMARY KEY, label_en text, label_lg text, label_sw text,
            label_fr text, label_de text, types text, type_labels text,
            admin text, admin_label text, lat real, lon real, image text,
            commons text, enwiki text, lgwiki text, swwiki text, gender text,
            born integer, died integer, est_year integer, basis text);
        CREATE TABLE IF NOT EXISTS wd_items_done (lo integer PRIMARY KEY);""")


def _ranges(conn):
    """Ranges of item numbers holding about PER_RANGE items each; a number
    bucket with more than that is cut into equal parts."""
    buckets = conn.execute('SELECT bucket, items FROM wd_ug_buckets '
                           'ORDER BY bucket').fetchall()
    out, start, total = [], None, 0
    for b, n in buckets:
        if n > PER_RANGE // 2:
            if start is not None:
                out.append((start * BUCKET, b * BUCKET))
                start, total = None, 0
            parts = max(2, round(n / (PER_RANGE / 3)))
            step = BUCKET // parts
            out.extend((b * BUCKET + k * step,
                        (b + 1) * BUCKET if k == parts - 1
                        else b * BUCKET + (k + 1) * step)
                       for k in range(parts))
            continue
        if start is None:
            start = b
        total += n
        if total >= PER_RANGE:
            out.append((start * BUCKET, (b + 1) * BUCKET))
            start, total = None, 0
    if start is not None:
        out.append((start * BUCKET, (buckets[-1][0] + 1) * BUCKET))
    return out


def _q(value):
    return value.rsplit('/', 1)[-1] if value else ''


def all_items():
    """{item: why it is here}: its country is Uganda, it is a Ugandan citizen,
    or it lies within Uganda. A bare list is a cheap query; the detail comes
    from the API instead, which the Query Service times out on when asked for
    five optional columns at once."""
    sets = (('country', 'SELECT ?i WHERE { ?i wdt:P17 wd:Q1036 }'),
            ('citizen', 'SELECT ?i WHERE { ?i wdt:P27 wd:Q1036 . '
                        '?i wdt:P31 wd:Q5 }'),
            ('located in', 'SELECT ?i WHERE { ?i wdt:P131+ wd:Q1036 }'))
    why = {}
    for name, query in sets:
        got = sp.sparql(query)
        for r in got or []:
            why.setdefault(_q(r['i']['value']), []).append(name)
        print(f'    {name}: {len(got or [])} items', flush=True)
    return {q: '; '.join(v) for q, v in sorted(
        why.items(), key=lambda kv: int(kv[0][1:]))}


def _ranges_simple(step=2_000_000, top=140_000_000):
    return [(a, a + step) for a in range(0, top, step)]


def _first(claims, prop):
    for c in claims.get(prop, []):
        snak = c.get('mainsnak') or {}
        value = (snak.get('datavalue') or {}).get('value')
        if value is not None:
            return value
    return None


def _year(time_value):
    try:
        text = time_value['time']                  # +1980-05-01T00:00:00Z
        sign = -1 if text.startswith('-') else 1
        return sign * int(text[1:].split('-')[0])
    except (KeyError, ValueError, TypeError, IndexError):
        return None


def read_batch(ids):
    payload = wikiapi._api(WD, {
        'action': 'wbgetentities', 'ids': '|'.join(ids),
        'props': 'labels|claims|sitelinks',
        'languages': 'en|lg|sw|fr|de', 'sitefilter': 'enwiki|lgwiki|swwiki'})
    out = {}
    for qid, ent in (payload.get('entities') or {}).items():
        labels = ent.get('labels') or {}
        claims = ent.get('claims') or {}
        links = ent.get('sitelinks') or {}
        d = {'label_' + k: (labels.get(k) or {}).get('value')
             for k in ('en', 'lg', 'sw', 'fr', 'de')}
        types = [(c.get('mainsnak', {}).get('datavalue') or {}).get(
            'value', {}).get('id') for c in claims.get('P31', [])]
        d['types'] = '|'.join(t for t in types if t)
        admin = _first(claims, 'P131')
        d['admin'] = admin.get('id') if isinstance(admin, dict) else None
        coord = _first(claims, 'P625')
        if isinstance(coord, dict):
            d['lat'], d['lon'] = coord.get('latitude'), coord.get('longitude')
        image = _first(claims, 'P18')
        d['image'] = image if isinstance(image, str) else None
        commons = _first(claims, 'P373')
        d['commons'] = commons if isinstance(commons, str) else None
        for key, site in (('enwiki', 'enwiki'), ('lgwiki', 'lgwiki'),
                          ('swwiki', 'swwiki')):
            d[key] = (links.get(site) or {}).get('title')
        if 'Q5' in types:
            g = _first(claims, 'P21')
            d['gender'] = GENDER.get(g.get('id'), 'other')                 if isinstance(g, dict) else 'not recorded'
            d['born'] = _year(_first(claims, 'P569'))
            d['died'] = _year(_first(claims, 'P570'))
        out[qid] = d
    return out


def _labels(qids):
    out = {}
    qids = sorted(q for q in qids if q)
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        payload = wikiapi._api(WD, {'action': 'wbgetentities', 'ids': '|'.join(batch),
                               'props': 'labels', 'languages': 'en'})
        for qid, ent in (payload.get('entities') or {}).items():
            out[qid] = ((ent.get('labels') or {}).get('en') or {}).get(
                'value', '')
    return out


def run(conn, force=False):
    with ug_utils.stage(conn, SCRIPT, 'items', force) as st:
        if st.skip:
            return
        _schema(conn)
        if 'basis' not in [r[1] for r in conn.execute('PRAGMA table_info(wd_items)')]:
            conn.execute('ALTER TABLE wd_items ADD COLUMN basis text')
        cal = conn.execute('SELECT num, created FROM wd_qdates ORDER BY num'
                           ).fetchall()
        nums = [n for n, _ in cal]
        days = [datetime.date.fromisoformat(c).toordinal() for _, c in cal]

        def year_of(num):
            k = bisect.bisect_left(nums, num)
            if not nums:
                return None
            if k <= 0:
                day = days[0]
            elif k >= len(nums):
                day = days[-1]
            else:
                frac = (num - nums[k - 1]) / max(nums[k] - nums[k - 1], 1)
                day = days[k - 1] + frac * (days[k] - days[k - 1])
            return datetime.date.fromordinal(int(day)).year

        have = {q for (q,) in conn.execute('SELECT qid FROM wd_items')}
        everything = all_items()
        todo = [q for q in everything if q not in have]
        conn.executemany('UPDATE wd_items SET basis = ? WHERE qid = ?',
                         [(w, q) for q, w in everything.items()])
        conn.commit()
        print(f'    {len(everything)} items about Uganda, {len(todo)} to read')
        for i in range(0, len(todo), 50):
            batch = todo[i:i + 50]
            rows = read_batch(batch)
            for qid, d in rows.items():
                d['basis'] = everything.get(qid)
                conn.execute(
                    'INSERT OR REPLACE INTO wd_items (qid, label_en, label_lg, '
                    'label_sw, label_fr, label_de, types, admin, lat, lon, '
                    'image, commons, enwiki, lgwiki, swwiki, gender, born, '
                    'died, est_year, basis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'
                    '?,?,?,?)',
                    (qid, d.get('label_en'), d.get('label_lg'),
                     d.get('label_sw'), d.get('label_fr'), d.get('label_de'),
                     d.get('types'), d.get('admin'), d.get('lat'), d.get('lon'),
                     d.get('image'), d.get('commons'), d.get('enwiki'),
                     d.get('lgwiki'), d.get('swwiki'), d.get('gender'),
                     d.get('born'), d.get('died'), year_of(int(qid[1:])),
                     d.get('basis')))
            if (i // 50) % 5 == 0:
                conn.commit()
            cp.tick(min(i + 50, len(todo)), len(todo), batch[0])
            if (i // 50) % 40 == 0:
                print(f'    {min(i + 50, len(todo))}/{len(todo)}', flush=True)
        conn.commit()

        # the words for the type and place codes
        codes = set()
        for types, admin in conn.execute(
                'SELECT types, admin FROM wd_items WHERE type_labels IS NULL'):
            codes.update((types or '').split('|'))
            codes.add(admin or '')
        names = _labels(codes)
        for qid, types, admin in conn.execute(
                'SELECT qid, types, admin FROM wd_items WHERE type_labels IS '
                'NULL').fetchall():
            conn.execute(
                'UPDATE wd_items SET type_labels = ?, admin_label = ? WHERE '
                'qid = ?', ('; '.join(names.get(t, t) for t in
                                      (types or '').split('|') if t),
                            names.get(admin or '', ''), qid))
        conn.commit()


if __name__ == '__main__':
    conn = ug_utils.connect()
    run(conn, '--force' in __import__('sys').argv)
    conn.close()
    print('ITEMS_DONE')
