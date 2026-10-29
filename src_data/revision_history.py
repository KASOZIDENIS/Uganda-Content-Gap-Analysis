# -*- coding: utf-8 -*-
"""Who edited Ugandan articles, and when, from the first article onwards.

The Pageviews API starts in July 2015 and the Foundation's editor-location
releases in 2018, but a page's edit history is kept from its first edit. So the
years before those start can still be filled in from what happened to the
articles themselves: how many were written each year, how many edits they had
and how many different people made them, in English and in Luganda.

For every article in the analysis, and for its Luganda counterpart, this reads
the revision list (timestamp and editor) and stores three small tables:

    rev_done    one row per page: first and last edit seen
    rev_edits   edits per page per calendar year
    rev_users   each distinct editor per wiki per year (IP addresses flagged)

It resumes where it stopped and, once a page is done, reads only the edits made
since, so a monthly update costs one request per page.
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor

import category_profiles as cp
import wikiapi
import ug_utils

SCRIPT = 'revision_history'
APIS = {'en': 'https://en.wikipedia.org/w/api.php',
        'lg': 'https://lg.wikipedia.org/w/api.php'}
def api_of(wiki):
    """The API of a wiki: en and lg are Wikipedias; anything else is a host."""
    return APIS.get(wiki) or f'https://{wiki}/w/api.php'


IP = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$|:')


def _schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS rev_done (
            wiki text, title text, first_ts text, last_ts text,
            PRIMARY KEY (wiki, title));
        CREATE TABLE IF NOT EXISTS rev_edits (
            wiki text, title text, year integer, edits integer,
            PRIMARY KEY (wiki, title, year));
        CREATE TABLE IF NOT EXISTS rev_users (
            wiki text, year integer, editor text, anon integer,
            PRIMARY KEY (wiki, year, editor));""")


def _read(wiki, title, since):
    """[(timestamp, editor)] for edits after `since`, oldest first."""
    out, cont = [], {}
    while True:
        params = {'action': 'query', 'titles': title, 'prop': 'revisions',
                  'rvprop': 'timestamp|user', 'rvlimit': 500,
                  'rvdir': 'newer', 'redirects': 1}
        if since:
            params['rvstart'] = since
        payload = wikiapi._api(api_of(wiki), dict(params, **cont))
        for page in payload.get('query', {}).get('pages', []):
            for rev in page.get('revisions', []) or []:
                if since and rev['timestamp'] <= since:
                    continue
                out.append((rev['timestamp'], rev.get('user') or ''))
        cont = payload.get('continue') or {}
        if not cont:
            return out
        time.sleep(0.05)


def _changed(wiki, held):
    """The held pages that have been edited since they were last read.

    Fifty titles to a request: the API returns each page's latest edit, which
    is all that is needed to see whether anything is new."""
    titles = sorted(held)
    changed = set()
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        payload = wikiapi._api(api_of(wiki), {
            'action': 'query', 'titles': '|'.join(batch),
            'prop': 'revisions', 'rvprop': 'timestamp'})
        for page in payload.get('query', {}).get('pages', []):
            revs = page.get('revisions') or []
            if revs and revs[0]['timestamp'] > held.get(page['title'], ''):
                changed.add(page['title'])
        time.sleep(0.1)
    return changed


def _targets(conn, titles):
    """(wiki, title) for each analysed article and its Luganda counterpart."""
    rows = [r for r in conn.execute(
        'SELECT title, lg_title FROM cat_articles') if r[0] in titles]
    out = [('en', t) for t, _ in rows]
    out += [('lg', g) for _, g in rows if g]
    return out


def run(conn, titles, force=False, lg_pages=(), extra=()):
    """Read new pages in full, and the new edits of pages already held."""
    with ug_utils.stage(conn, SCRIPT, 'revisions', force) as st:
        if st.skip:
            return
        _schema(conn)
        have = {(w, t): last for w, t, last in conn.execute(
            'SELECT wiki, title, last_ts FROM rev_done')}
        wanted = _targets(conn, set(titles))
        # every Luganda page, whether or not it is about Uganda
        seen = set(wanted)
        wanted += [('lg', t) for t in lg_pages if ('lg', t) not in seen]
        wanted += [p for p in dict.fromkeys(extra) if p not in seen]
        todo = [(w, t) for w, t in wanted if (w, t) not in have]
        for wiki in sorted({w for w, _ in wanted}):
            held = {t: have[(w, t)] for w, t in wanted
                    if w == wiki and (w, t) in have and have[(w, t)]}
            if held:
                todo += [(wiki, t) for t in _changed(wiki, held)]
        print(f'    {len(todo)} pages to read ({len(have)} already held)')
        done = 0

        def work(item):
            wiki, title = item
            try:
                return item, _read(wiki, title, have.get(item)), None
            except Exception as error:                  # noqa: BLE001
                return item, [], error

        with ThreadPoolExecutor(max_workers=cp.WORKERS) as pool:
            for (wiki, title), revs, error in pool.map(work, todo):
                done += 1
                if error is not None:
                    print(f'      {wiki}:{title}: {error}')
                    continue
                years = {}
                for ts, user in revs:
                    y = int(ts[:4])
                    years[y] = years.get(y, 0) + 1
                    if user:
                        conn.execute(
                            'INSERT OR IGNORE INTO rev_users VALUES (?,?,?,?)',
                            (wiki, y, user, int(bool(IP.search(user)))))
                for y, n in years.items():
                    conn.execute(
                        'INSERT INTO rev_edits VALUES (?,?,?,?) ON CONFLICT'
                        '(wiki, title, year) DO UPDATE SET edits = edits + '
                        'excluded.edits', (wiki, title, y, n))
                old = have.get((wiki, title))
                first = revs[0][0] if revs else None
                prev = conn.execute('SELECT first_ts FROM rev_done WHERE '
                                    'wiki = ? AND title = ?',
                                    (wiki, title)).fetchone()
                conn.execute(
                    'INSERT OR REPLACE INTO rev_done VALUES (?,?,?,?)',
                    (wiki, title, (prev[0] if prev and prev[0] else first),
                     revs[-1][0] if revs else old))
                if done % 10 == 0:
                    conn.commit()
                cp.tick(done, len(todo), f'{wiki}: {title}')
        conn.commit()
        print(f'    {done} pages read')
