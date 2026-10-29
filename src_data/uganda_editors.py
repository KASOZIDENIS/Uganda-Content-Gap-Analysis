# -*- coding: utf-8 -*-
"""Stage 16: how many editors in Uganda, month by month since January 2018.

Minute 5 of the way-forward table asks for "the number of editors over time who
have been editing Ugandan content and are from Uganda, with a trend". The
Wikimedia Foundation publishes exactly the second half of that: editors per
country, per wiki, per month, in three activity bands, from
https://dumps.wikimedia.org/other/geoeditors/ .

**What this can and cannot say.** It counts editors located in Uganda on a wiki,
whatever they edited. Nothing public ties an editor's country to the articles
they touched, so "editing Ugandan content" is not recoverable and the output
does not claim it. For lg.wikipedia the two are close, since the wiki is
Luganda; for en.wikipedia and Commons they are not, and an editor in Kampala may
be writing about anything.

The counts are published as ranges (1-10, 11-50, ...) to protect privacy, so the
export keeps the bounds and adds a midpoint for charting. Treat the midpoint as
a plotting convenience, not a measurement.

    python src_data/uganda_editors.py
"""

import csv
import os
import sqlite3
import re
import time

import config
import ug_utils

SCRIPT = 'uganda_editors'

BASE = 'https://dumps.wikimedia.org/other/geoeditors/'
COUNTRY = 'Uganda'
WIKIS = ('enwiki', 'lgwiki', 'swwiki', 'commonswiki', 'wikidatawiki')
LEVELS = ('1 to 4', '5 to 99', '100 or more')
OUT = os.path.join(config.DATA_PATH, 'ug_editors_monthly.csv')


def _stored(conn, table):
    """Rows already in the database, empty the first time."""
    try:
        return conn.execute(f'SELECT * FROM {table}').fetchall()
    except sqlite3.OperationalError:
        return []


def _progress(done, total, note):
    if ug_utils.PROGRESS:
        ug_utils.PROGRESS(done, total, note)


def fetch(conn, force=False):
    with ug_utils.stage(conn, SCRIPT, 'fetch', force) as st:
        if st.skip:
            return
        session = ug_utils.get_session()
        index = session.get(BASE, timeout=60).text
        names = sorted(set(re.findall(r'href="(geoeditors-monthly-[^"]+\.tsv)"',
                                      index)))
        print(f'    {len(names)} monthly files')
        # Only the months not already held, and the newest again, since a
        # month's file is only final once the next has begun. The first run
        # reads them all; every run after reads one or two.
        rows = _stored(conn, 'ug_editors')
        newest = re.search(r'(\d{4}-\d{2})', names[-1]).group(1)
        rows = [r for r in rows if r[0] != newest]
        have = {r[0] for r in rows}
        for k, name in enumerate(names, 1):
            month = re.search(r'(\d{4}-\d{2})', name).group(1)
            if month in have:
                continue
            _progress(k, len(names), f'editors, {month}')
            text = session.get(BASE + name, timeout=120).text
            for line in text.splitlines():
                parts = line.split('\t')
                if len(parts) < 5 or parts[1] != COUNTRY:
                    continue
                if parts[0] not in WIKIS or parts[2] not in LEVELS:
                    continue
                low, high = int(parts[3]), int(parts[4])
                rows.append((month, parts[0], parts[2], low, high,
                             (low + high) / 2))
            time.sleep(0.2)
        rows.sort()
        with open(OUT, 'w', encoding='utf-8', newline='') as handle:
            w = csv.writer(handle)
            w.writerow(['month', 'wiki', 'activity', 'editors_low',
                        'editors_high', 'editors_mid'])
            w.writerows(rows)
        conn.execute('DROP TABLE IF EXISTS ug_editors')
        conn.execute("""CREATE TABLE ug_editors (
            month text, wiki text, activity text, editors_low integer,
            editors_high integer, editors_mid real)""")
        conn.executemany('INSERT INTO ug_editors VALUES (?,?,?,?,?,?)', rows)
        conn.commit()
        print(f'    {len(rows)} rows -> {os.path.basename(OUT)}')


DP_BASE = ('https://analytics.wikimedia.org/published/datasets/'
           'geoeditors_monthly/')
DP_WIKIS = WIKIS
OUT_DP = os.path.join(config.DATA_PATH, 'ug_editors_recent.csv')


def fetch_recent(conn, force=False):
    """July 2023 onward, from the differentially-private release.

    It adds what the older dumps lack: the 1-4 edit band, which is the nearest
    thing public data has to "new and casual contributors", and Commons and
    Wikidata. Counts carry Laplace noise (a few editors either way), which is
    why they are rounded to whole numbers and never summed across projects.
    """
    with ug_utils.stage(conn, SCRIPT, 'fetch_recent', force) as st:
        if st.skip:
            return
        session = ug_utils.get_session()
        index = session.get(DP_BASE, timeout=60).text
        names = sorted(set(re.findall(r'href="(\d{4}-\d{2}\.tsv)"', index)))
        print(f'    {len(names)} monthly files')
        rows = _stored(conn, 'ug_editors_recent')
        newest = re.search(r'(\d{4}-\d{2})', names[-1]).group(1)
        rows = [r for r in rows if r[0] != newest]
        have = {r[0] for r in rows}
        for k, name in enumerate(names, 1):
            month = name[:7]
            if month in have:
                continue
            _progress(k, len(names), f'casual editors, {month}')
            text = session.get(DP_BASE + name, timeout=180).text
            for line in text.splitlines():
                p = line.split('\t')
                if (len(p) < 11 or p[2] != COUNTRY or p[0] not in DP_WIKIS
                        or p[4] not in LEVELS):
                    continue
                rows.append((p[10], p[0], p[4], int(float(p[8])),
                             int(float(p[9])) if p[9] not in ('', 'NA') else 0))
            time.sleep(0.2)
        rows.sort()
        with open(OUT_DP, 'w', encoding='utf-8', newline='') as handle:
            w = csv.writer(handle)
            w.writerow(['month', 'wiki', 'activity', 'editors', 'edits'])
            w.writerows(rows)
        conn.execute('DROP TABLE IF EXISTS ug_editors_recent')
        conn.execute("""CREATE TABLE ug_editors_recent (
            month text, wiki text, activity text, editors integer,
            edits integer)""")
        conn.executemany('INSERT INTO ug_editors_recent VALUES (?,?,?,?,?)',
                         rows)
        conn.commit()
        print(f'    {len(rows)} rows -> {os.path.basename(OUT_DP)}')


def main(force=False):
    conn = ug_utils.connect()
    fetch(conn, force)
    fetch_recent(conn, force)
    conn.close()


if __name__ == '__main__':
    import sys
    main(force='--force' in sys.argv)
