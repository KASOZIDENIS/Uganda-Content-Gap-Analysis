# -*- coding: utf-8 -*-
"""The analytics done on English Wikipedia, for the pages of the other
Wikimedia projects that are about Uganda.

For every page found by projects_history.pages() (a page that mentions Uganda
on Wiktionary, Wikibooks, Wikiquote, Wikisource, Wikinews, Wikivoyage,
Wikiversity, Wikispecies, Meta-Wiki, the Incubator, MediaWiki and
Wikifunctions) this gathers what the English Wikipedia analysis holds for an
article:

    proj_pageinfo   the page's categories, its Wikidata item, how many
                    Wikipedia languages the subject has, whether it has a
                    Luganda or Swahili article, and for a person their gender
    proj_views      views for every year from July 2015 and in all
    rev_*           when it was written, and the edits and editors of each year
                    (the same tables as the Wikipedia pages, keyed by host)

    python src_data/project_analytics.py
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor

import category_profiles as cp
import projects_history as ph
import wikiapi
import revision_history as rh
import sister_projects as sp
import ug_utils

SCRIPT = 'project_analytics'
WD = 'https://www.wikidata.org/w/api.php'
PV = ('https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/'
      '{project}/all-access/user/{title}/monthly/20150701/{end}')
HUMAN, FEMALE, MALE = 'Q5', 'Q6581072', 'Q6581097'


def _schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS proj_pageinfo (
            host text, title text, qid text, cats text, languages integer,
            lg integer, sw integer, human integer, gender text,
            PRIMARY KEY (host, title));
        CREATE TABLE IF NOT EXISTS proj_views (
            host text, title text, views_all integer, views_json text,
            PRIMARY KEY (host, title));""")


def project_of(host):
    return host[:-4] if host.endswith('.org') else host


def pages(conn):
    return conn.execute('SELECT host, title FROM proj_pages').fetchall()


def pageinfo(conn, force=False):
    with ug_utils.stage(conn, SCRIPT, 'pageinfo', force) as st:
        if st.skip:
            return
        _schema(conn)
        have = {(h, t) for h, t in conn.execute(
            'SELECT host, title FROM proj_pageinfo')}
        todo = [p for p in pages(conn) if p not in have]
        by_host = {}
        for h, t in todo:
            by_host.setdefault(h, []).append(t)
        print(f'    {len(todo)} pages to read')
        done = 0
        for host, titles in by_host.items():
            api = f'https://{host}/w/api.php'
            for i in range(0, len(titles), 50):
                batch = titles[i:i + 50]
                got = sp.quick(api, {
                    'action': 'query', 'titles': '|'.join(batch),
                    'prop': 'pageprops|categories', 'ppprop': 'wikibase_item',
                    'cllimit': 500, 'clshow': '!hidden'})
                info = {}
                for page in ((got or {}).get('query') or {}).get('pages', []):
                    info[page['title']] = (
                        (page.get('pageprops') or {}).get('wikibase_item', ''),
                        '|'.join(c['title'].split(':', 1)[-1]
                                 for c in page.get('categories') or []))
                qids = [q for q, _ in info.values() if q]
                facts = _wikidata(qids)
                for title in batch:
                    qid, cats = info.get(title, ('', ''))
                    f = facts.get(qid, (0, 0, 0, 0, ''))
                    conn.execute(
                        'INSERT OR REPLACE INTO proj_pageinfo VALUES '
                        '(?,?,?,?,?,?,?,?,?)', (host, title, qid, cats) + f)
                conn.commit()
                done += len(batch)
                cp.tick(done, len(todo), host)
                time.sleep(0.1)


def _wikidata(qids):
    out = {}
    for i in range(0, len(qids), 50):
        payload = wikiapi._api(WD, {'action': 'wbgetentities',
                               'ids': '|'.join(qids[i:i + 50]),
                               'props': 'sitelinks|claims'})
        for qid, ent in (payload.get('entities') or {}).items():
            links = ent.get('sitelinks') or {}
            langs = sum(1 for k in links if k.endswith('wiki') and k not in (
                'commonswiki', 'specieswiki', 'metawiki', 'wikidatawiki',
                'mediawikiwiki', 'sourceswiki', 'incubatorwiki'))
            claims = ent.get('claims') or {}

            def first(prop):
                for c in claims.get(prop, []):
                    try:
                        return c['mainsnak']['datavalue']['value']['id']
                    except Exception:                  # noqa: BLE001
                        pass
                return ''
            human = int(any(
                c['mainsnak'].get('datavalue', {}).get('value', {}).get('id')
                == HUMAN for c in claims.get('P31', [])
                if c.get('mainsnak')))
            gender = {FEMALE: 'female', MALE: 'male'}.get(first('P21'), '')
            out[qid] = (langs, int('lgwiki' in links), int('swwiki' in links),
                        human, gender if human else '')
    return out


def _measure(project, title, end):
    url = PV.format(project=project, end=end,
                    title=title.replace(' ', '_').replace('/', '%2F')
                    .replace('?', '%3F'))
    session = ug_utils.get_session()
    for attempt in range(6):
        try:
            r = session.get(url, timeout=60)
            if r.status_code == 404:
                return {}
            if r.status_code == 429:
                time.sleep(min(5 * (attempt + 1), 60))
                continue
            r.raise_for_status()
            yearly = {}
            for item in r.json().get('items', []):
                y = str(item['timestamp'])[:4]
                yearly[y] = yearly.get(y, 0) + item.get('views', 0)
            return yearly
        except Exception:                              # noqa: BLE001
            time.sleep(2 * (attempt + 1))
    return None


def views(conn, force=False):
    with ug_utils.stage(conn, SCRIPT, 'views', force) as st:
        if st.skip:
            return
        _schema(conn)
        end, _ = cp.pv_window()
        if cp.meta_get(conn, 'proj_views_through') != end:
            conn.execute('DELETE FROM proj_views')
            conn.commit()
        have = {(h, t) for h, t in conn.execute(
            'SELECT host, title FROM proj_views')}
        todo = [p for p in pages(conn) if p not in have]
        print(f'    {len(todo)} pages to measure')
        done = 0
        with ThreadPoolExecutor(max_workers=3) as pool:
            for (host, title), yearly in zip(todo, pool.map(
                    lambda p: _measure(project_of(p[0]), p[1], end), todo)):
                done += 1
                if yearly is None:
                    continue
                conn.execute('INSERT OR REPLACE INTO proj_views VALUES (?,?,?,?)',
                             (host, title, sum(yearly.values()),
                              json.dumps(yearly)))
                if done % 40 == 0:
                    conn.commit()
                cp.tick(done, len(todo), host)
        conn.commit()
        cp.meta_set(conn, 'proj_views_through', end)


def revisions(conn, force=False):
    rh.run(conn, [], True, (), extra=[(h, t) for h, t in pages(conn)])


def main(force=False):
    conn = ug_utils.connect()
    ph.pages(conn, force)
    pageinfo(conn, force)
    views(conn, force)
    revisions(conn, force)
    conn.close()
    print('ANALYTICS_DONE')


if __name__ == '__main__':
    import sys
    main(force='--force' in sys.argv)
