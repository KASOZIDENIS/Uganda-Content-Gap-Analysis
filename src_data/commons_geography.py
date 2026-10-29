# -*- coding: utf-8 -*-
"""Does Commons actually hold pictures of Ugandan places?

The Commons audit (commons_audit.py) measures the collection from the inside: how many
files there are, what kind, which categories hold them. This asks the question
from the other end, which is the one a geography analysis needs. Take the places
Uganda is made of, one by one, and check whether anybody has photographed them.

An article without a picture is a specific, fixable kind of gap. It is also the
one most likely to be invisible: a district article with an infobox, coordinates
and three paragraphs looks finished in every count until you notice there is
nothing to look at.

Three things are measured per place:

    category   does a Commons category exist for it
    files      how many files that category holds
    used       does the Wikipedia article carry a lead image

The three come apart more often than you would expect, and each gap means
something different. No category and no files means nobody has been. Files but
no lead image means the photographs exist and the article never picked one up,
which is minutes of work rather than a field trip.

    python src_data/commons_geography.py
"""

import csv
import os
import time

import config
import ug_utils
import yn

SCRIPT = 'commons_geography'

COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
BATCH = 50
PAUSE = 0.12

OUT_FILE = os.path.join(config.DATA_PATH, 'ug_commons_geography.csv')
OUT_SUMMARY = os.path.join(config.DATA_PATH, 'ug_commons_geography_summary.csv')

# Commons files a place needs before it is genuinely illustrated rather than
# merely present. One photograph proves somebody passed through; a handful is
# the least that lets an article choose an image that suits it.
THIN = 5


def _api(params):
    session = ug_utils.get_session()
    query = dict(params, format='json', formatversion=2)
    delay = 2
    for attempt in range(6):
        try:
            r = session.get(COMMONS_API, params=query, timeout=90)
            if r.status_code == 429:
                time.sleep(min(int(r.headers.get('Retry-After') or delay), 120))
                delay = min(delay * 2, 120)
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == 5:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 120)


def _probes(kind, name):
    """The Commons categories a place might plausibly sit under.

    The bare stem matters as much as the decorated forms. Ten of Uganda's
    districts are named for the city inside them, so the UBOS list calls one
    "Gulu City" while Commons files its 73 photographs under `Category:Gulu`.
    Probing only the decorated names reported Gulu, Arua, Hoima and Fort Portal
    as having no pictures at all, which was wrong by 215 files.
    """
    if kind == 'district':
        stem = name[:-5].strip() if name.lower().endswith(' city') else name
        probes = [f'Category:{name} District, Uganda',
                  f'Category:{name} District', f'Category:{name}, Uganda',
                  f'Category:{name}']
        if stem != name:
            probes += [f'Category:{stem}, Uganda', f'Category:{stem}',
                       f'Category:{stem} District, Uganda']
        return probes
    if kind == 'city':
        return [f'Category:{name}, Uganda', f'Category:{name}',
                f'Category:{name} District, Uganda']
    if kind == 'settlement':
        return [f'Category:{name} Refugee Settlement',
                f'Category:{name} refugee settlement', f'Category:{name}']
    return [f'Category:{name}, Uganda', f'Category:{name}',
            f'Category:{name} sub-region']


def _categoryinfo(titles):
    """File and subcategory counts for a batch of Commons categories."""
    out = {}
    for i in range(0, len(titles), BATCH):
        batch = titles[i:i + BATCH]
        payload = _api({'action': 'query', 'prop': 'categoryinfo',
                        'titles': '|'.join(batch), 'redirects': 1})
        query = payload.get('query', {})
        alias = {r['from']: r['to'] for r in query.get('redirects', [])}
        alias.update({n['from']: n['to'] for n in query.get('normalized', [])})
        found = {}
        for page in query.get('pages', []):
            if 'missing' in page:
                continue
            info = page.get('categoryinfo') or {}
            found[page['title']] = (info.get('files', 0),
                                    info.get('subcats', 0))
        for want in batch:
            target = alias.get(want, want)
            out[want] = found.get(target)
        time.sleep(PAUSE)
    return out


def check_places(conn, force=False):
    """Every named place, checked against Commons."""
    with ug_utils.stage(conn, SCRIPT, 'check_places', force) as st:
        if st.skip:
            return
        if not conn.execute("""SELECT 1 FROM sqlite_master
                WHERE type='table' AND name='geo_places'""").fetchone():
            raise SystemExit('no geo_places table\n'
                             'run: python src_data/geo_places.py')

        conn.execute('DROP TABLE IF EXISTS commons_geo')
        conn.execute("""CREATE TABLE commons_geo (
            kind text, name text, article text, commons_cat text,
            files integer, subcats integer, has_lead_image integer,
            PRIMARY KEY (kind, name))""")

        places = conn.execute("""SELECT kind, name, title, image
            FROM geo_places ORDER BY kind, name""").fetchall()

        # every probe for every place, resolved in one batched sweep
        wanted, owner = [], {}
        for kind, name, _title, _img in places:
            for probe in _probes(kind, name):
                wanted.append(probe)
                owner.setdefault((kind, name), []).append(probe)
        info = _categoryinfo(sorted(set(wanted)))

        rows = []
        for kind, name, title, image in places:
            best, files, subcats = '', 0, 0
            for probe in owner[(kind, name)]:
                got = info.get(probe)
                if got and got[0] >= files:
                    best, files, subcats = probe, got[0], got[1]
            rows.append((kind, name, title or '', best, files, subcats,
                         1 if image else 0))
        conn.executemany('INSERT OR REPLACE INTO commons_geo '
                         'VALUES (?,?,?,?,?,?,?)', rows)
        conn.commit()

        for kind in ('city', 'district', 'subregion', 'settlement'):
            group = [r for r in rows if r[0] == kind]
            if not group:
                continue
            has_cat = sum(1 for r in group if r[3])
            thin = sum(1 for r in group if r[4] < THIN)
            print(f'    {kind:<11} {has_cat:3d}/{len(group):3d} have a Commons '
                  f'category, {thin:3d} have fewer than {THIN} files')


def export(conn, force=False):
    with ug_utils.stage(conn, SCRIPT, 'export', force) as st:
        if st.skip:
            return

        rows = conn.execute("""SELECT kind, name, article, commons_cat, files,
            subcats, has_lead_image FROM commons_geo
            ORDER BY files ASC, kind, name""").fetchall()
        with open(OUT_FILE, 'w', encoding='utf-8', newline='') as handle:
            w = csv.writer(handle)
            w.writerow(['kind', 'place', 'article', 'commons_category',
                        'files', 'subcategories', 'article_has_lead_image'])
            w.writerows(yn.flag_rows(rows, (6,)))
        print(f'    -> {os.path.basename(OUT_FILE)} ({len(rows)} rows)')

        summary = []
        for kind in ('city', 'district', 'subregion', 'settlement'):
            group = [r for r in rows if r[0] == kind]
            if not group:
                continue
            summary += [
                (kind, 'places', len(group)),
                (kind, 'with_commons_category',
                 sum(1 for r in group if r[3])),
                (kind, 'with_no_files', sum(1 for r in group if not r[4])),
                (kind, f'with_fewer_than_{THIN}_files',
                 sum(1 for r in group if r[4] < THIN)),
                (kind, 'total_files', sum(r[4] for r in group)),
                (kind, 'article_has_lead_image',
                 sum(1 for r in group if r[6])),
                # the cheap fix: pictures exist, the article never took one
                (kind, 'files_exist_but_article_has_no_image',
                 sum(1 for r in group if r[4] and not r[6])),
            ]
        with open(OUT_SUMMARY, 'w', encoding='utf-8', newline='') as handle:
            w = csv.writer(handle)
            w.writerow(['kind', 'metric', 'value'])
            w.writerows(summary)
        print(f'    -> {os.path.basename(OUT_SUMMARY)} ({len(summary)} rows)')


def main(force=False):
    conn = ug_utils.connect()
    check_places(conn, force)
    export(conn, force)
    conn.close()


if __name__ == '__main__':
    import sys
    main(force='--force' in sys.argv)
