# -*- coding: utf-8 -*-
"""Everything on Wikimedia Commons about Uganda, with no depth limit.

The first Commons audit stopped four levels below Category:Uganda, because a
category walk with no stop leaks into the rest of the world: Commons files
Uganda's lakes, rivers and mountains under categories it shares with Kenya,
Tanzania, Congo and Rwanda. This walks every level instead and stops the leak
by name, the way the Wikipedia category walk does: a category is followed when
its own name is Ugandan, or when it is within two steps of one that is.

For every category it keeps the files directly in it, and for every file when it
was uploaded, by whom, how big it is and what kind of file it is. That is what
shows how the collection has grown, year by year, who has added to it, and
where it is thin.

    commons_ug_cats   one row per category: depth, parent, files, subcategories,
                      theme, campaign, and whether its name is Ugandan
    commons_ug_files  one row per file: uploaded, uploader, size, mime, type,
                      the first category it was found in, and how many other
                      wikis use it (once stage `usage` has run)

    python src_data/commons_full.py
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor

import category_profiles as cp
import commons_audit as ca
import wikiapi
import ug_utils

SCRIPT = 'commons_full'
API = 'https://commons.wikimedia.org/w/api.php'
ROOT = 'Category:Uganda'
SLACK = 2                 # steps past a Ugandan name that are still followed
MAX_DEPTH = 60            # a guard, not a limit: the slack rule ends the walk

# Commons names that say Uganda without using the word
EXTRA = (r'Kampala|Buganda|Bunyoro|Ankole|Busoga|Tooro|Karamoja|Acholi|Lango|'
         r'Teso|Kigezi|Rwenzori|Ruwenzori|Entebbe|Jinja|Gulu|Mbarara|Mbale|'
         r'Kasese|Hoima|Masaka|Lira|Arua|Soroti|Tororo|Fort Portal|Murchison|'
         r'Bwindi|Kidepo|Mgahinga|Semuliki|Mabira|Budongo|Kibale|Elgon|'
         r'Baganda|Basoga|Luganda|Lusoga|Ugandan|Uganda')
import re
NAMED = re.compile(EXTRA, re.I)


def _schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS commons_ug_cats (
            title text PRIMARY KEY, depth integer, parent text,
            files integer, subcats integer, theme text, campaign text,
            named integer, slack integer, done integer DEFAULT 0);
        CREATE TABLE IF NOT EXISTS commons_ug_files (
            title text PRIMARY KEY, category text, uploaded text,
            uploader text, size integer, mime text, mediatype text,
            used integer, used_wikis integer);
        CREATE TABLE IF NOT EXISTS commons_ug_catfiles (
            category text, title text, PRIMARY KEY (category, title));""")


def _named(title):
    return bool(NAMED.search(title.split(':', 1)[-1]))


def crawl_categories(conn, force=False):
    """Every category under Category:Uganda that is Ugandan or near one."""
    with ug_utils.stage(conn, SCRIPT, 'categories', force) as st:
        if st.skip:
            return
        _schema(conn)
        if not conn.execute('SELECT 1 FROM commons_ug_cats').fetchone():
            root = wikiapi._api(API, {'action': 'query', 'prop': 'categoryinfo',
                                 'titles': ROOT})['query']['pages'][0]
            info = root.get('categoryinfo') or {}
            conn.execute('INSERT INTO commons_ug_cats VALUES (?,?,?,?,?,?,?,?,?,0)',
                         (ROOT, 0, '', info.get('files', 0),
                          info.get('subcats', 0), ca.theme_of(ROOT),
                          ca.campaign_of(ROOT), 1, SLACK))
            conn.commit()

        def children(parent):
            out, cont = [], {}
            while True:
                payload = wikiapi._api(API, dict({
                    'action': 'query', 'generator': 'categorymembers',
                    'gcmtitle': parent, 'gcmtype': 'subcat', 'gcmlimit': 500,
                    'prop': 'categoryinfo'}, **cont))
                for page in payload.get('query', {}).get('pages', []):
                    info = page.get('categoryinfo') or {}
                    out.append((page['title'], info.get('files', 0),
                                info.get('subcats', 0)))
                cont = payload.get('continue') or {}
                if not cont:
                    return out
            return out

        level = 0
        while True:
            todo = conn.execute(
                'SELECT title, depth, slack FROM commons_ug_cats WHERE done = 0'
                ' ORDER BY depth').fetchall()
            if not todo:
                break
            level += 1
            known = {t for (t,) in conn.execute(
                'SELECT title FROM commons_ug_cats')}
            print(f'    round {level}: {len(todo)} categories to open, '
                  f'{len(known)} known')
            done = 0
            with ThreadPoolExecutor(max_workers=2) as pool:
                for (parent, depth, slack), kids in zip(
                        todo, pool.map(lambda r: children(r[0]), todo)):
                    done += 1
                    for title, files, subs in kids:
                        if title in known or depth + 1 > MAX_DEPTH:
                            continue
                        named = _named(title)
                        if named:
                            child_slack = SLACK
                        elif slack > 0:
                            child_slack = slack - 1
                        else:
                            continue
                        known.add(title)
                        conn.execute(
                            'INSERT OR IGNORE INTO commons_ug_cats VALUES '
                            '(?,?,?,?,?,?,?,?,?,0)',
                            (title, depth + 1, parent, files, subs,
                             ca.theme_of(title), ca.campaign_of(title),
                             int(named), child_slack))
                    conn.execute('UPDATE commons_ug_cats SET done = 1 '
                                 'WHERE title = ?', (parent,))
                    if done % 25 == 0:
                        conn.commit()
                    cp.tick(done, len(todo), parent[9:])
            conn.commit()
        n, f = conn.execute('SELECT COUNT(*), SUM(files) FROM '
                            'commons_ug_cats').fetchone()
        deepest = conn.execute('SELECT MAX(depth) FROM commons_ug_cats'
                               ).fetchone()[0]
        print(f'    {n} categories, {f} file memberships, deepest level '
              f'{deepest}')


def crawl_files(conn, force=False):
    """The files in every category, with who uploaded them and when."""
    with ug_utils.stage(conn, SCRIPT, 'files', force) as st:
        if st.skip:
            return
        _schema(conn)
        have = {c for (c,) in conn.execute(
            'SELECT DISTINCT category FROM commons_ug_catfiles')}
        cats = [t for (t,) in conn.execute(
            'SELECT title FROM commons_ug_cats WHERE files > 0 ORDER BY title')
            if t not in have]
        print(f'    {len(cats)} categories to list')

        def read(cat):
            out, cont = [], {}
            while True:
                try:
                    payload = wikiapi._api(API, dict({
                        'action': 'query', 'generator': 'categorymembers',
                        'gcmtitle': cat, 'gcmtype': 'file', 'gcmlimit': 50,
                        'prop': 'imageinfo',
                        'iiprop': 'timestamp|user|size|mime|mediatype'},
                        **cont))
                except Exception:                      # noqa: BLE001
                    return cat, None
                for page in payload.get('query', {}).get('pages', []):
                    ii = (page.get('imageinfo') or [{}])[0]
                    out.append((page['title'], ii.get('timestamp', ''),
                                ii.get('user', ''), ii.get('size', 0),
                                ii.get('mime', ''), ii.get('mediatype', '')))
                cont = payload.get('continue') or {}
                if not cont:
                    return cat, out

        done = 0
        with ThreadPoolExecutor(max_workers=2) as pool:
            for cat, rows in pool.map(read, cats):
                done += 1
                if rows is None:
                    continue
                conn.executemany(
                    'INSERT OR IGNORE INTO commons_ug_files (title, category, '
                    'uploaded, uploader, size, mime, mediatype) VALUES '
                    '(?,?,?,?,?,?,?)',
                    [(t, cat, ts, u, sz, mi, mt) for t, ts, u, sz, mi, mt in rows])
                conn.executemany(
                    'INSERT OR IGNORE INTO commons_ug_catfiles VALUES (?,?)',
                    [(cat, r[0]) for r in rows])
                if done % 25 == 0:
                    conn.commit()
                cp.tick(done, len(cats), cat[9:])
        conn.commit()
        n = conn.execute('SELECT COUNT(*) FROM commons_ug_files').fetchone()[0]
        print(f'    {n} distinct files')


def usage(conn, force=False):
    """Whether each file is used on any wiki, and on how many."""
    with ug_utils.stage(conn, SCRIPT, 'usage', force) as st:
        if st.skip:
            return
        todo = [t for (t,) in conn.execute(
            'SELECT title FROM commons_ug_files WHERE used IS NULL')]
        print(f'    {len(todo)} files to check for use')

        def check(batch):
            seen = {t: set() for t in batch}
            cont = {}
            while True:
                try:
                    payload = wikiapi._api(API, dict({
                        'action': 'query', 'prop': 'globalusage',
                        'titles': '|'.join(batch), 'gulimit': 500,
                        'guprop': 'url'}, **cont))
                except Exception:                      # noqa: BLE001
                    return batch, None
                for page in payload.get('query', {}).get('pages', []):
                    for use in page.get('globalusage') or []:
                        seen.setdefault(page['title'], set()).add(use['wiki'])
                cont = payload.get('continue') or {}
                if not cont:
                    return batch, seen

        batches = [todo[i:i + 25] for i in range(0, len(todo), 25)]
        done = 0
        with ThreadPoolExecutor(max_workers=2) as pool:
            for batch, seen in pool.map(check, batches):
                done += 1
                if seen is None:
                    continue
                conn.executemany(
                    'UPDATE commons_ug_files SET used = ?, used_wikis = ? '
                    'WHERE title = ?',
                    [(int(bool(w)), len(w), t) for t, w in seen.items()])
                if done % 20 == 0:
                    conn.commit()
                cp.tick(done, len(batches), 'usage')
        conn.commit()


def main(force=False):
    conn = ug_utils.connect()
    crawl_categories(conn, force)
    crawl_files(conn, force)
    usage(conn, force)
    conn.close()
    print('COMMONS_DONE')


if __name__ == '__main__':
    import sys
    main(force='--force' in sys.argv)
