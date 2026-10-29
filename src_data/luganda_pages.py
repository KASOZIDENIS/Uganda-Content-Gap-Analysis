# -*- coding: utf-8 -*-
"""Every article on Luganda Wikipedia, with its readership and its history.

lgwiki is small enough to take whole. Rather than sampling it or reaching it
through a category, this enumerates every content page, then measures each one:
how much it has been read, how long it is, whether it carries a Wikidata item,
and whether an English article exists on the other side of that item.

Readership is the total for all time (every month the Pageviews API holds,
which starts in July 2015) with the figure for each calendar year beside it.
The page's own edit history, read by revision_history.py, supplies when it was
written and the edits and editors of each year, so the record reaches back
before the Pageviews API does.

That Wikidata column is the useful one. A Luganda article with no English
counterpart is something lgwiki has that enwiki does not, which is the opposite
of the gap this project usually measures and worth seeing on its own terms.

**One request per article.** The pageviews API takes a date range and returns a
point per month, so a single call from July 2015 gives every year and the total.

    python src_data/luganda_pages.py
"""

import csv
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import category_profiles as cp
import config
import ug_utils

SCRIPT = 'luganda_pages'

LG_API = 'https://lg.wikipedia.org/w/api.php'
WD_API = 'https://www.wikidata.org/w/api.php'
PAGEVIEWS = ('https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/'
             'lg.wikipedia/all-access/user/{title}/monthly/20150701/{end}')

BATCH = 50
PAUSE = 0.12
MAIN_PAGE = 'Q5296'          # the wiki's front page is not an article

OUT_FILE = os.path.join(config.DATA_PATH, 'ug_luganda_pages.csv')


def _api(base, params):
    session = ug_utils.get_session()
    query = dict(params, format='json', formatversion=2)
    delay = 2
    for attempt in range(30):
        try:
            r = session.get(base, params=query, timeout=90)
            if r.status_code == 429:
                time.sleep(min(int(r.headers.get('Retry-After') or delay), 120))
                delay = min(delay * 2, 120)
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == 29:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 120)


def _schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS luganda_pages (
        title text PRIMARY KEY, pageid integer, bytes integer,
        qid text, enwiki text, label text, instance_of text,
        views integer DEFAULT 0, views_prior integer DEFAULT 0,
        months integer DEFAULT 0, views_all integer DEFAULT 0,
        views_json text)""")
    cols = [r[1] for r in conn.execute('PRAGMA table_info(luganda_pages)')]
    for name, kind in (('views_all', 'integer DEFAULT 0'),
                       ('views_json', 'text')):
        if name not in cols:
            conn.execute(f'ALTER TABLE luganda_pages ADD COLUMN {name} {kind}')
    conn.commit()


def list_pages(conn, force=False):
    """Every content page on lgwiki, redirects excluded; new ones are added
    and pages that no longer exist are dropped."""
    with ug_utils.stage(conn, SCRIPT, 'list_pages', force) as st:
        if st.skip:
            return
        _schema(conn)
        rows, cont = [], {}
        while True:
            payload = _api(LG_API, dict(
                {'action': 'query', 'list': 'allpages', 'apnamespace': 0,
                 'apfilterredir': 'nonredirects', 'aplimit': 500}, **cont))
            for page in payload.get('query', {}).get('allpages', []):
                rows.append((page['title'], page['pageid']))
            cont = payload.get('continue') or {}
            print(f'    {len(rows)} pages')
            cp.tick(len(rows), max(len(rows), 7000), 'listing Luganda pages')
            if not cont:
                break
            time.sleep(PAUSE)
        conn.executemany(
            'INSERT OR IGNORE INTO luganda_pages (title, pageid, bytes, qid, '
            "enwiki, label, instance_of) VALUES (?, ?, 0, '', '', '', '')",
            rows)
        now = {t for t, _ in rows}
        gone = [(t,) for (t,) in conn.execute('SELECT title FROM luganda_pages')
                if t not in now]
        conn.executemany('DELETE FROM luganda_pages WHERE title = ?', gone)
        conn.commit()
        print(f'    {len(rows)} content pages on lgwiki ({len(gone)} gone)')


def fetch_details(conn, force=False):
    """Article length and the Wikidata item behind each page, refreshed."""
    with ug_utils.stage(conn, SCRIPT, 'fetch_details', force) as st:
        if st.skip:
            return
        titles = [t for (t,) in conn.execute('SELECT title FROM luganda_pages')]
        print(f'    {len(titles)} pages to describe')
        for i in range(0, len(titles), BATCH):
            batch = titles[i:i + BATCH]
            payload = _api(LG_API, {
                'action': 'query', 'titles': '|'.join(batch),
                'prop': 'info|pageprops'})
            updates = []
            for page in payload.get('query', {}).get('pages', []):
                if 'missing' in page:
                    continue
                updates.append((
                    page.get('length', 0),
                    (page.get('pageprops') or {}).get('wikibase_item', ''),
                    page['title']))
            conn.executemany('UPDATE luganda_pages SET bytes=?, qid=? '
                             'WHERE title=?', updates)
            conn.commit()
            cp.tick(min(i + BATCH, len(titles)), len(titles),
                    'describing Luganda pages')
            time.sleep(PAUSE)


def fetch_wikidata(conn, force=False):
    """The English article on the other side of the item, and its class."""
    with ug_utils.stage(conn, SCRIPT, 'fetch_wikidata', force) as st:
        if st.skip:
            return
        qids = [q for (q,) in conn.execute(
            "SELECT DISTINCT qid FROM luganda_pages WHERE qid != ''")]
        print(f'    {len(qids)} Wikidata items')
        for i in range(0, len(qids), BATCH):
            batch = qids[i:i + BATCH]
            payload = _api(WD_API, {
                'action': 'wbgetentities', 'ids': '|'.join(batch),
                'props': 'sitelinks|labels|claims', 'languages': 'en'})
            updates = []
            for qid, entity in (payload.get('entities') or {}).items():
                links = entity.get('sitelinks') or {}
                kinds = []
                for claim in (entity.get('claims') or {}).get('P31', []):
                    try:
                        kinds.append(
                            claim['mainsnak']['datavalue']['value']['id'])
                    except Exception:                  # noqa: BLE001
                        pass
                updates.append((
                    links.get('enwiki', {}).get('title', ''),
                    (entity.get('labels') or {}).get('en', {}).get('value', ''),
                    ','.join(kinds), qid))
            conn.executemany("""UPDATE luganda_pages
                SET enwiki=?, label=?, instance_of=? WHERE qid=?""", updates)
            conn.commit()
            cp.tick(min(i + BATCH, len(qids)), len(qids), 'Wikidata items')
            time.sleep(PAUSE)


def _measure(title, end):
    """({year: views}, last twelve months, the twelve before) for one page."""
    url = PAGEVIEWS.format(title=title.replace(' ', '_').replace('/', '%2F')
                           .replace('?', '%3F'), end=end)
    session = ug_utils.get_session()
    for attempt in range(8):
        try:
            r = session.get(url, timeout=60)
            if r.status_code == 404:
                return {}, 0, 0
            if r.status_code == 429:
                time.sleep(min(5 * (attempt + 1), 60))
                continue
            r.raise_for_status()
            months = {}
            for item in r.json().get('items', []):
                stamp = str(item.get('timestamp', ''))[:6]
                months[stamp] = months.get(stamp, 0) + item.get('views', 0)
            yearly = {}
            for stamp, n in months.items():
                yearly[stamp[:4]] = yearly.get(stamp[:4], 0) + n
            keys = sorted(months)
            return (yearly, sum(months[k] for k in keys[-12:]),
                    sum(months[k] for k in keys[-24:-12]))
        except Exception:                              # noqa: BLE001
            time.sleep(2 * (attempt + 1))
    return None, 0, 0


def fetch_views(conn, force=False):
    """Every year's readership since July 2015, one request per article.

    Measured again for every page once a new month of data is out, and for new
    pages otherwise."""
    with ug_utils.stage(conn, SCRIPT, 'fetch_views', force) as st:
        if st.skip:
            return
        _schema(conn)
        end, _last = cp.pv_window()
        if cp.meta_get(conn, 'lg_views_through') != end:
            conn.execute('UPDATE luganda_pages SET views_json = NULL')
            conn.commit()
        titles = [t for (t,) in conn.execute(
            'SELECT title FROM luganda_pages WHERE views_json IS NULL')]
        print(f'    {len(titles)} articles to measure')
        done = 0
        with ThreadPoolExecutor(max_workers=3) as pool:
            for title, (yearly, last12, prior) in zip(
                    titles, pool.map(lambda t: _measure(t, end), titles)):
                done += 1
                if yearly is None:
                    continue
                conn.execute(
                    'UPDATE luganda_pages SET views_json = ?, views_all = ?, '
                    'views = ?, views_prior = ?, months = ? WHERE title = ?',
                    (json.dumps(yearly), sum(yearly.values()), last12, prior,
                     len(yearly), title))
                if done % 20 == 0:
                    conn.commit()
                cp.tick(done, len(titles), title)
        conn.commit()
        if not conn.execute('SELECT 1 FROM luganda_pages WHERE views_json IS '
                            'NULL').fetchone():
            cp.meta_set(conn, 'lg_views_through', end)


def export(conn, force=False):
    """The pages, with views, history and where they link, as one CSV."""
    with ug_utils.stage(conn, SCRIPT, 'export', force) as st:
        if st.skip:
            return
        first = {t: ts for t, ts in conn.execute(
            "SELECT title, first_ts FROM rev_done WHERE wiki = 'lg'")} \
            if conn.execute("SELECT 1 FROM sqlite_master WHERE "
                            "name='rev_done'").fetchone() else {}
        edits = {}
        if first:
            for t, n in conn.execute(
                    "SELECT title, SUM(edits) FROM rev_edits WHERE wiki = 'lg' "
                    'GROUP BY title'):
                edits[t] = n
        about = {r[0] for r in conn.execute(
            "SELECT lg_title FROM cat_articles WHERE lg_title != '' AND "
            'title IN (SELECT title FROM cat_wanted)')}
        rows = conn.execute("""SELECT title, label, qid, enwiki, bytes, views,
            views_prior, instance_of, MAX(views_all, 0), views_json
            FROM luganda_pages ORDER BY views_all DESC, title""").fetchall()
        years = sorted({y for r in rows if r[9] for y in json.loads(r[9])})
        with open(OUT_FILE, 'w', encoding='utf-8', newline='') as handle:
            w = csv.writer(handle)
            w.writerow(['lg_title', 'english_label', 'wikidata', 'en_article',
                        'bytes', 'views_12mo', 'views_prior_12mo',
                        'views_all_time', 'instance_of', 'lg_url',
                        'wikidata_url', 'en_url', 'created', 'edits',
                        'about_uganda', 'main_page']
                       + [f'views_{y}' for y in years])
            for (title, label, qid, enwiki, size, views, prior, kinds, total,
                 blob) in rows:
                per = json.loads(blob) if blob else {}
                w.writerow([
                    title, label, qid, enwiki, size, views, prior, total,
                    kinds,
                    'https://lg.wikipedia.org/wiki/' + title.replace(' ', '_'),
                    f'https://www.wikidata.org/wiki/{qid}' if qid else '',
                    'https://en.wikipedia.org/wiki/'
                    + enwiki.replace(' ', '_') if enwiki else '',
                    (first.get(title) or '')[:10], edits.get(title, 0),
                    'Y' if title in about else 'N',
                    'Y' if qid == MAIN_PAGE else 'N']
                    + [per.get(y, 0) for y in years])
        print(f'    -> {os.path.basename(OUT_FILE)} ({len(rows)} rows)')
        read = sum(r[8] for r in rows)
        print(f'    {len(rows)} articles, {read:,} views in all')


def main(force=False):
    import revision_history as rh
    conn = ug_utils.connect()
    list_pages(conn, force)
    fetch_details(conn, force)
    fetch_wikidata(conn, force)
    fetch_views(conn, force)
    pages = [t for (t,) in conn.execute('SELECT title FROM luganda_pages')]
    rh.run(conn, [], True, pages)
    export(conn, True)
    conn.close()


if __name__ == '__main__':
    import sys
    main(force='--force' in sys.argv)
