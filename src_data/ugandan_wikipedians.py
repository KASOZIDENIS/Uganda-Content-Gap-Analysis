# -*- coding: utf-8 -*-
"""Editors who say they are in Uganda, tracked through their own edits.

English Wikipedia's Category:Wikipedians in Uganda lists the user pages of
editors who have declared they are in Uganda. It is self-declared and so not
every editor in Uganda, but it is the one list of named editors there is, and
unlike the Foundation's location counts (2018 onwards, in ranges) it can be
followed from each person's first edit.

For every editor in the category this reads the account (registered when, how
many edits, rights held) and the timestamp of every edit, and keeps:

    wp_users       one row per editor: registered, edit count, first and last
                   edit seen, groups
    wp_user_years  edits per editor per calendar year

Later runs read only the edits made since the last one.

    python src_data/ugandan_wikipedians.py
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor

import category_profiles as cp
import wikiapi
import ug_utils

SCRIPT = 'ugandan_wikipedians'
CATEGORY = 'Category:Wikipedians in Uganda'
BATCH = 50


def _schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS wp_users (
            user text PRIMARY KEY, registration text, editcount integer,
            first_edit text, last_edit text, groups text);
        CREATE TABLE IF NOT EXISTS wp_user_years (
            user text, year integer, edits integer,
            PRIMARY KEY (user, year));""")


def members():
    """Account names from the category's user pages (and their subpages)."""
    names = set()
    for page in wikiapi._members(CATEGORY, 'page'):
        title = page['title']
        if ':' not in title:
            continue
        name = title.split(':', 1)[1].split('/')[0].strip()
        if name:
            names.add(name.replace('_', ' '))
    return sorted(names)


def _accounts(names):
    out = {}
    for i in range(0, len(names), BATCH):
        batch = names[i:i + BATCH]
        payload = wikiapi._api(wikiapi.EN_API, {
            'action': 'query', 'list': 'users', 'ususers': '|'.join(batch),
            'usprop': 'editcount|registration|groups'})
        for u in payload.get('query', {}).get('users', []):
            if 'missing' in u or 'invalid' in u:
                continue
            out[u['name']] = (
                (u.get('registration') or '')[:10], u.get('editcount', 0),
                ','.join(g for g in u.get('groups', [])
                         if g not in ('*', 'user', 'autoconfirmed')))
        time.sleep(0.1)
    return out


def _contributions(name, since):
    """Timestamps of the editor's edits after `since`, oldest first."""
    out, cont = [], {}
    while True:
        params = {'action': 'query', 'list': 'usercontribs',
                  'ucuser': name, 'uclimit': 500, 'ucprop': 'timestamp',
                  'ucdir': 'newer'}
        if since:
            params['ucstart'] = since
        payload = wikiapi._api(wikiapi.EN_API, dict(params, **cont))
        for c in payload.get('query', {}).get('usercontribs', []):
            if not since or c['timestamp'] > since:
                out.append(c['timestamp'])
        cont = payload.get('continue') or {}
        if not cont:
            return out
        time.sleep(0.05)


def run(conn, force=False):
    with ug_utils.stage(conn, SCRIPT, 'wikipedians', force) as st:
        if st.skip:
            return
        _schema(conn)
        names = members()
        print(f'    {len(names)} editors in {CATEGORY}')
        accounts = _accounts(names)
        held = {u: last for u, last in conn.execute(
            'SELECT user, last_edit FROM wp_users')}
        # editors who have left the category are dropped from the tables
        gone = [u for u in held if u not in accounts]
        for u in gone:
            conn.execute('DELETE FROM wp_users WHERE user = ?', (u,))
            conn.execute('DELETE FROM wp_user_years WHERE user = ?', (u,))
        done = 0

        def work(name):
            try:
                return name, _contributions(name, held.get(name)), None
            except Exception as error:                 # noqa: BLE001
                return name, [], error

        todo = sorted(accounts)
        with ThreadPoolExecutor(max_workers=3) as pool:
            for name, stamps, error in pool.map(work, todo):
                done += 1
                if error is not None:
                    print(f'      {name}: {error}')
                    continue
                reg, count, groups = accounts[name]
                years = {}
                for ts in stamps:
                    years[int(ts[:4])] = years.get(int(ts[:4]), 0) + 1
                for y, n in years.items():
                    conn.execute(
                        'INSERT INTO wp_user_years VALUES (?,?,?) ON CONFLICT'
                        '(user, year) DO UPDATE SET edits = edits + '
                        'excluded.edits', (name, y, n))
                prev = conn.execute('SELECT first_edit, last_edit FROM '
                                    'wp_users WHERE user = ?',
                                    (name,)).fetchone()
                first = (prev[0] if prev and prev[0]
                         else (stamps[0] if stamps else None))
                last = stamps[-1] if stamps else (prev[1] if prev else None)
                conn.execute('INSERT OR REPLACE INTO wp_users VALUES '
                             '(?,?,?,?,?,?)',
                             (name, reg, count, first, last, groups))
                conn.commit()
                cp.tick(done, len(todo), name)
        conn.commit()
        print(f'    {done} editors read')


if __name__ == '__main__':
    conn = ug_utils.connect()
    run(conn, True)
    conn.close()
    print('WP_DONE')
