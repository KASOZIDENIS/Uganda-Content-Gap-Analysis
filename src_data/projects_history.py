# -*- coding: utf-8 -*-
"""Where Uganda lives on the Wikimedia projects, and how it has grown.

Three things the projects dashboard needs beyond counts:

1. sitelinks   for every Ugandan Wikipedia article, which other projects hold
               the same subject (Commons, Wikiquote, Wikisource, Wikivoyage,
               Wikispecies, Wikinews, Wikibooks, Wikiversity, Wiktionary) and
               in how many Wikipedia languages. Read from the article's
               Wikidata item.
2. wikidata    when Wikidata's items about Uganda were created. Wikidata gives
               item numbers out in order, so an item number says roughly when it
               was made: the date of a few hundred items spread across the
               number range fixes the curve, and the Uganda items are counted
               by number. This is an estimate from the numbering, not each
               item's own history.
3. pages       every page on each of the other projects that mentions Uganda,
               with its size and the date it was first written.

    python src_data/projects_history.py
"""

import bisect
import datetime
import time
from concurrent.futures import ThreadPoolExecutor

import category_profiles as cp
import wikiapi
import sister_projects as sp
import ug_utils

SCRIPT = 'projects_history'
WD = 'https://www.wikidata.org/w/api.php'
BUCKET = 250000

FAMILY = {'commonswiki': 'Commons', 'specieswiki': 'Wikispecies',
          'metawiki': 'Meta-Wiki'}
SUFFIX = {'wikiquote': 'Wikiquote', 'wikisource': 'Wikisource',
          'wikivoyage': 'Wikivoyage', 'wikinews': 'Wikinews',
          'wikibooks': 'Wikibooks', 'wikiversity': 'Wikiversity',
          'wiktionary': 'Wiktionary'}


def _schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS art_sitelinks (
            qid text PRIMARY KEY, languages integer, lg integer, sw integer,
            commons integer, wikiquote integer, wikisource integer,
            wikivoyage integer, wikispecies integer, wikinews integer,
            wikibooks integer, wikiversity integer, wiktionary integer);
        CREATE TABLE IF NOT EXISTS wd_qdates (num integer PRIMARY KEY,
            created text);
        CREATE TABLE IF NOT EXISTS wd_ug_buckets (bucket integer PRIMARY KEY,
            items integer);
        CREATE TABLE IF NOT EXISTS proj_pages (
            host text, title text, size integer, words integer,
            last_edit text, created text, PRIMARY KEY (host, title));""")


# -------------------------------------------------------------- sitelinks
def sitelinks(conn, titles, force=False):
    with ug_utils.stage(conn, SCRIPT, 'sitelinks', force) as st:
        if st.skip:
            return
        _schema(conn)
        wanted = [q for (q,) in conn.execute(
            "SELECT DISTINCT qid FROM cat_articles WHERE qid LIKE 'Q%' AND "
            'title IN (SELECT title FROM cat_wanted)')]
        have = {q for (q,) in conn.execute('SELECT qid FROM art_sitelinks')}
        todo = [q for q in wanted if q not in have]
        print(f'    {len(todo)} items to read')
        for i in range(0, len(todo), 50):
            batch = todo[i:i + 50]
            payload = wikiapi._api(WD, {'action': 'wbgetentities',
                                   'ids': '|'.join(batch),
                                   'props': 'sitelinks'})
            rows = []
            for qid, ent in (payload.get('entities') or {}).items():
                links = ent.get('sitelinks') or {}
                counts = {k: 0 for k in ('commons', 'wikiquote', 'wikisource',
                                         'wikivoyage', 'wikispecies',
                                         'wikinews', 'wikibooks',
                                         'wikiversity', 'wiktionary')}
                languages = 0
                for key in links:
                    if key == 'commonswiki':
                        counts['commons'] = 1
                    elif key == 'specieswiki':
                        counts['wikispecies'] = 1
                    elif key.endswith('wiki') and key not in (
                            'commonswiki', 'specieswiki', 'metawiki',
                            'wikidatawiki', 'mediawikiwiki', 'sourceswiki',
                            'incubatorwiki', 'outreachwiki', 'wikimaniawiki'):
                        languages += 1
                    else:
                        for suffix in SUFFIX:
                            if key.endswith(suffix):
                                counts[suffix] = 1
                rows.append((qid, languages, int('lgwiki' in links),
                             int('swwiki' in links), counts['commons'],
                             counts['wikiquote'], counts['wikisource'],
                             counts['wikivoyage'], counts['wikispecies'],
                             counts['wikinews'], counts['wikibooks'],
                             counts['wikiversity'], counts['wiktionary']))
            conn.executemany('INSERT OR REPLACE INTO art_sitelinks VALUES '
                             '(?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
            conn.commit()
            cp.tick(min(i + 50, len(todo)), len(todo), 'sitelinks')
            time.sleep(0.1)


# --------------------------------------------------------------- wikidata
def _created(num):
    try:
        payload = wikiapi._api(WD, {'action': 'query', 'titles': f'Q{num}',
                               'prop': 'revisions', 'rvdir': 'newer',
                               'rvlimit': 1, 'rvprop': 'timestamp'})
        for page in payload['query']['pages']:
            for rev in page.get('revisions') or []:
                return rev['timestamp'][:10]
    except Exception:                                   # noqa: BLE001
        pass
    return None


def wikidata(conn, force=False):
    with ug_utils.stage(conn, SCRIPT, 'wikidata', force) as st:
        if st.skip:
            return
        _schema(conn)
        # the highest item number, by doubling then halving
        lo, hi = 100_000_000, 200_000_000
        while hi - lo > 1_000_000:
            mid = (lo + hi) // 2
            if _created(mid):
                lo = mid
            else:
                hi = mid
        top = lo
        print(f'    item numbers run to about {top:,}')
        probes = sorted({int(top * (k / 120) ** 1.6) + 1 for k in range(1, 121)}
                        | {1000, 100000, 1000000})
        have = {n for (n,) in conn.execute('SELECT num FROM wd_qdates')}
        todo = [n for n in probes if n not in have]
        with ThreadPoolExecutor(max_workers=3) as pool:
            for num, ts in zip(todo, pool.map(_created, todo)):
                if ts:
                    conn.execute('INSERT OR REPLACE INTO wd_qdates VALUES '
                                 '(?,?)', (num, ts))
        conn.commit()
        rows = sp.sparql(f"""SELECT ?b (COUNT(DISTINCT ?i) AS ?n) WHERE {{
            ?i wdt:P17 wd:Q1036 .
            BIND(xsd:integer(STRAFTER(STR(?i),
                 "http://www.wikidata.org/entity/Q")) AS ?num)
            BIND(FLOOR(?num / {BUCKET}) AS ?b) }} GROUP BY ?b""")
        if rows:
            conn.execute('DELETE FROM wd_ug_buckets')
            conn.executemany('INSERT INTO wd_ug_buckets VALUES (?,?)',
                             [(int(float(r['b']['value'])),
                               int(r['n']['value'])) for r in rows])
        conn.commit()


def wikidata_years(conn):
    """{year: items} for Uganda's items, by item number."""
    cal = conn.execute('SELECT num, created FROM wd_qdates ORDER BY num'
                       ).fetchall()
    if not cal:
        return {}
    nums = [n for n, _ in cal]
    days = [datetime.date.fromisoformat(c).toordinal() for _, c in cal]
    out = {}
    for bucket, items in conn.execute('SELECT bucket, items FROM wd_ug_buckets'):
        mid = bucket * BUCKET + BUCKET // 2
        k = bisect.bisect_left(nums, mid)
        if k <= 0:
            day = days[0]
        elif k >= len(nums):
            day = days[-1]
        else:
            frac = (mid - nums[k - 1]) / max(nums[k] - nums[k - 1], 1)
            day = days[k - 1] + frac * (days[k] - days[k - 1])
        year = datetime.date.fromordinal(int(day)).year
        out[year] = out.get(year, 0) + items
    return dict(sorted(out.items()))


# ------------------------------------------------------------------ pages
HOSTS = [('en.wiktionary.org', 'Wiktionary (English)'),
         ('sw.wiktionary.org', 'Wiktionary (Swahili)'),
         ('en.wikibooks.org', 'Wikibooks'), ('en.wikiquote.org', 'Wikiquote'),
         ('en.wikisource.org', 'Wikisource'), ('en.wikinews.org', 'Wikinews'),
         ('en.wikivoyage.org', 'Wikivoyage'), ('en.wikiversity.org', 'Wikiversity'),
         ('species.wikimedia.org', 'Wikispecies'),
         ('meta.wikimedia.org', 'Meta-Wiki'),
         ('incubator.wikimedia.org', 'Incubator'),
         ('www.mediawiki.org', 'MediaWiki'),
         ('www.wikifunctions.org', 'Wikifunctions')]


# Hosts whose pages are listed by title prefix, not found by searching for
# Uganda: the Incubator's Runyankore Wikipedia test, Wp/nyn/, is all of
# interest, whatever a page mentions.
PREFIXES = {'incubator.wikimedia.org': 'Wp/nyn/'}

# content namespaces, not talk or user pages: Wikisource's Author, Index and
# Page namespaces hold its texts and proofreading
NAMESPACES = {'en.wikisource.org': '0|102|104|106'}


def _first_edit(host, title):
    got = sp.quick(f'https://{host}/w/api.php', {
        'action': 'query', 'titles': title, 'prop': 'revisions',
        'rvdir': 'newer', 'rvlimit': 1, 'rvprop': 'timestamp'})
    try:
        for page in got['query']['pages']:
            for rev in page.get('revisions') or []:
                return rev['timestamp'][:10]
    except Exception:                                   # noqa: BLE001
        pass
    return None


def pages(conn, force=False):
    with ug_utils.stage(conn, SCRIPT, 'pages', force) as st:
        if st.skip:
            return
        _schema(conn)
        for host, label in HOSTS:
            api = f'https://{host}/w/api.php'
            found, offset = [], 0
            if host in PREFIXES:
                cont = {}
                while True:
                    got = sp.quick(api, dict({
                        'action': 'query', 'list': 'allpages',
                        'apprefix': PREFIXES[host], 'apnamespace': 0,
                        'aplimit': 500}, **cont))
                    pages_ = ((got or {}).get('query') or {}).get('allpages', [])
                    found += [(p['title'], 0, 0, '') for p in pages_]
                    cont = (got or {}).get('continue') or {}
                    if not cont:
                        break
                    time.sleep(0.2)
            while offset < 10000 and host not in PREFIXES:
                got = sp.quick(api, {
                    'action': 'query', 'list': 'search', 'srsearch': 'Uganda',
                    'srnamespace': NAMESPACES.get(host, '0'), 'srlimit': 500,
                    'sroffset': offset,
                    'srprop': 'size|wordcount|timestamp'})
                hits = ((got or {}).get('query') or {}).get('search') or []
                found += [(h['title'], h.get('size', 0), h.get('wordcount', 0),
                           (h.get('timestamp') or '')[:10]) for h in hits]
                if len(hits) < 500:
                    break
                offset += 500
                time.sleep(0.2)
            have = {t for (t,) in conn.execute(
                'SELECT title FROM proj_pages WHERE host = ? AND created '
                'IS NOT NULL', (host,))}
            todo = [f for f in found if f[0] not in have]
            print(f'    {label}: {len(found)} pages, {len(todo)} to date')
            with ThreadPoolExecutor(max_workers=4) as pool:
                for row, ts in zip(todo, pool.map(
                        lambda r: _first_edit(host, r[0]), todo)):
                    conn.execute(
                        'INSERT OR REPLACE INTO proj_pages VALUES (?,?,?,?,?,?)',
                        (host, row[0], row[1], row[2], row[3], ts))
            conn.commit()


def main(force=False):
    conn = ug_utils.connect()
    sitelinks(conn, [], force)
    wikidata(conn, force)
    pages(conn, force)
    conn.close()
    print('HISTORY_DONE')


if __name__ == '__main__':
    import sys
    main(force='--force' in sys.argv)
