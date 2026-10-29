# -*- coding: utf-8 -*-
"""The Runyankore Wikipedia test on the Incubator, every page of it.

The Incubator holds tests of new language editions as pages whose titles begin
with the edition's code: Wp/nyn/ is the test of a Runyankore Wikipedia. Its
dashboard is about those pages and no others, so the Incubator's other tests,
which the search for "Uganda" had also picked up, are removed, and every page
under Wp/nyn/ is read instead: when it was written, how much it has been read,
how it has been edited and by whom.

    python src_data/incubator_nyn.py
"""

import time
from concurrent.futures import ThreadPoolExecutor

import project_analytics as pa
import projects_history as ph
import sister_projects as sp
import ug_utils

HOST = 'incubator.wikimedia.org'
PREFIX = ph.PREFIXES[HOST]


def reset(conn):
    """Forget what was gathered for the Incubator's other pages."""
    ph._schema(conn)
    pa._schema(conn)
    for sql in ('DELETE FROM proj_pages WHERE host = ?',
                'DELETE FROM proj_pageinfo WHERE host = ?',
                'DELETE FROM proj_views WHERE host = ?',
                'DELETE FROM rev_done WHERE wiki = ?',
                'DELETE FROM rev_edits WHERE wiki = ?',
                'DELETE FROM rev_users WHERE wiki = ?'):
        conn.execute(sql, (HOST,))
    conn.commit()


def pages(conn):
    api = f'https://{HOST}/w/api.php'
    found, cont = [], {}
    while True:
        got = sp.quick(api, dict({'action': 'query', 'list': 'allpages',
                                  'apprefix': PREFIX, 'apnamespace': 0,
                                  'aplimit': 500}, **cont))
        found += [p['title'] for p in
                  ((got or {}).get('query') or {}).get('allpages', [])]
        cont = (got or {}).get('continue') or {}
        if not cont:
            break
        time.sleep(0.2)
    print(f'    {len(found)} pages under {PREFIX}')
    # size, words and last edit for each, fifty to a request
    info = {}
    for i in range(0, len(found), 50):
        got = sp.quick(api, {'action': 'query',
                             'titles': '|'.join(found[i:i + 50]),
                             'prop': 'info|revisions', 'rvprop': 'timestamp'})
        for page in ((got or {}).get('query') or {}).get('pages', []):
            revs = page.get('revisions') or []
            info[page['title']] = (page.get('length', 0),
                                   (revs[0]['timestamp'][:10] if revs else ''))
    with ThreadPoolExecutor(max_workers=4) as pool:
        for title, ts in zip(found, pool.map(
                lambda t: ph._first_edit(HOST, t), found)):
            size, last = info.get(title, (0, ''))
            conn.execute('INSERT OR REPLACE INTO proj_pages VALUES '
                         '(?,?,?,?,?,?)', (HOST, title, size, 0, last, ts))
    conn.commit()


def main():
    conn = ug_utils.connect()
    reset(conn)
    pages(conn)
    pa.pageinfo(conn, True)
    pa.views(conn, True)
    pa.revisions(conn, True)
    conn.close()
    print('NYN_DONE')


if __name__ == '__main__':
    main()
