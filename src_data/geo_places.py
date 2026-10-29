# -*- coding: utf-8 -*-
"""The places of Uganda, checked against Wikipedia.

Takes the cities, the districts (from the UBOS census hierarchy that
official_registers.py parsed into `register_entries`), the sub-regions and the
larger refugee settlements, and for each finds its English Wikipedia article:
its size, whether it has an infobox, coordinates and a lead image, its Wikidata
item and which census it quotes.

The list of places is what the Commons dashboard checks Commons against (see
commons_geography.py): a district with no files on Commons, or an article with
no picture, is a specific and fixable gap.

    python src_data/geo_places.py
"""

import re
import time

import ug_utils

SCRIPT = 'geo_places'

EN_API = 'https://en.wikipedia.org/w/api.php'
BATCH = 50
PAUSE = 0.05

# The ten cities granted city status from 2020, plus the capital. Curated
# because there is no single machine-readable list of them, and each is checked
# against Wikipedia below rather than asserted.
CITIES = ('Kampala', 'Arua', 'Fort Portal', 'Gulu', 'Hoima', 'Jinja', 'Lira',
          'Masaka', 'Mbale', 'Mbarara', 'Soroti')

# Sub-regions and the traditional areas that share their names.
SUBREGIONS = ('Acholi', 'Ankole', 'Buganda', 'Bugisu', 'Bukedi', 'Bunyoro',
              'Busoga', 'Karamoja', 'Kigezi', 'Lango', 'Rwenzori', 'Sebei',
              'Teso', 'Tooro', 'West Nile')

# The larger refugee settlements. Uganda hosts one of the biggest refugee
# populations in the world and the settlements are permanent in all but name.
SETTLEMENTS = ('Bidibidi', 'Nakivale', 'Kyangwali', 'Rhino Camp', 'Palorinya',
               'Imvepi', 'Kiryandongo', 'Oruchinga', 'Palabek', 'Lobule',
               'Kyaka II', 'Rwamwanja', 'Adjumani')

INFOBOX = re.compile(r'\{\{\s*infobox', re.I)
COORD = re.compile(r'\{\{\s*coord|\|\s*coordinates\s*=|\{\{\s*location map', re.I)
CENSUS_2014 = re.compile(r'2014\s+(national\s+)?(population|census)|census[^.]{0,40}2014', re.I)
CENSUS_2024 = re.compile(r'2024\s+(national\s+)?(population|census)|census[^.]{0,40}2024', re.I)


def _api(base, params):
    session = ug_utils.get_session()
    query = dict(params, format='json', formatversion=2)
    for attempt in range(4):
        try:
            r = session.get(base, params=query, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def _describe(titles):
    """Wikitext-derived facts for a batch of titles."""
    out = {}
    for i in range(0, len(titles), BATCH):
        batch = titles[i:i + BATCH]
        payload = _api(EN_API, {
            'action': 'query', 'titles': '|'.join(batch),
            'prop': 'revisions|pageimages|pageprops', 'rvprop': 'content',
            'rvslots': 'main', 'piprop': 'name', 'redirects': 1})
        query = payload.get('query', {})
        # a redirect means the title a reader types reaches a real article
        alias = {r['from']: r['to'] for r in query.get('redirects', [])}
        alias.update({n['from']: n['to'] for n in query.get('normalized', [])})
        found = {}
        for page in query.get('pages', []):
            if 'missing' in page:
                found[page['title']] = None
                continue
            text = ''
            for rev in page.get('revisions', []):
                text = rev.get('slots', {}).get('main', {}).get('content') or ''
            found[page['title']] = {
                'title': page['title'],
                'bytes': len(text.encode()),
                'infobox': bool(INFOBOX.search(text)),
                'coord': bool(COORD.search(text)),
                'image': bool(page.get('pageimage')),
                'qid': (page.get('pageprops') or {}).get('wikibase_item', ''),
                'census2014': bool(CENSUS_2014.search(text)),
                'census2024': bool(CENSUS_2024.search(text)),
            }
        for want in batch:
            target = alias.get(want, want)
            out[want] = found.get(target)
        time.sleep(PAUSE)
    return out


KIND_HINT = {'city': 'Uganda city', 'district': 'Uganda district',
             'subregion': 'Uganda sub-region', 'settlement':
             'Uganda refugee settlement'}


def _search_fallback(name, kind):
    """A search hit whose title actually carries the place name."""
    try:
        payload = _api(EN_API, {
            'action': 'query', 'list': 'search',
            'srsearch': f'{name} {KIND_HINT.get(kind, "Uganda")}',
            'srlimit': 5, 'srnamespace': 0})
    except Exception:
        return ''
    want = name.lower().replace(' ', '')
    for hit in payload.get('query', {}).get('search', []):
        if want in hit['title'].lower().replace(' ', ''):
            return hit['title']
    return ''


def check_places(conn, force=False):
    """The named places, checked article by article."""
    with ug_utils.stage(conn, SCRIPT, 'check_places', force) as st:
        if st.skip:
            return
        conn.execute('DROP TABLE IF EXISTS geo_places')
        conn.execute("""CREATE TABLE geo_places (
            kind text, name text, probe text, title text, bytes integer,
            infobox integer, coord integer, image integer, qid text,
            census2014 integer, census2024 integer,
            PRIMARY KEY (kind, name))""")

        # districts come from the UBOS hierarchy this project already parsed
        districts = [r[0].title() for r in conn.execute(
            "SELECT DISTINCT name FROM register_entries WHERE kind = 'district'")]

        # Capitalisation is part of the title. MediaWiki only case-folds the
        # first character, so "Bidibidi refugee settlement" is a red link while
        # "Bidibidi Refugee Settlement" is the article about the largest
        # refugee settlement in the world. Probing the lowercase form reported
        # all but five settlements as undocumented when every one has an
        # article, which is why _search_fallback exists below.
        jobs = [('city', c, c) for c in CITIES]
        jobs += [('district', d, f'{d} District') for d in districts]
        jobs += [('subregion', s, f'{s} sub-region') for s in SUBREGIONS]
        jobs += [('settlement', s, f'{s} Refugee Settlement')
                 for s in SETTLEMENTS]

        rows = []
        for kind in ('city', 'district', 'subregion', 'settlement'):
            batch = [j for j in jobs if j[0] == kind]
            probes = [j[2] for j in batch]
            got = _describe(probes)
            # a sub-region or settlement often sits under its bare name
            retry = [j for j in batch if not got.get(j[2])]
            if retry:
                fallback = _describe([j[1] for j in retry])
                for j in retry:
                    if fallback.get(j[1]):
                        got[j[2]] = fallback[j[1]]
            # last resort: search, so a place filed under a title nobody would
            # guess still counts as documented
            still = [j for j in batch if not got.get(j[2])]
            for j in still:
                found = _search_fallback(j[1], kind)
                if found:
                    described = _describe([found])
                    if described.get(found):
                        got[j[2]] = described[found]
            have = 0
            for _k, name, probe in batch:
                d = got.get(probe)
                if d:
                    have += 1
                    rows.append((kind, name, probe, d['title'], d['bytes'],
                                 int(d['infobox']), int(d['coord']),
                                 int(d['image']), d['qid'],
                                 int(d['census2014']), int(d['census2024'])))
                else:
                    rows.append((kind, name, probe, '', 0, 0, 0, 0, '', 0, 0))
            print(f'    {kind:<11} {have:3d}/{len(batch):3d} have an article')

        conn.executemany(
            'INSERT OR REPLACE INTO geo_places VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            rows)
        conn.commit()


def main(force=False):
    conn = ug_utils.connect()
    check_places(conn, force)
    conn.close()


if __name__ == '__main__':
    import sys
    main(force='--force' in sys.argv)
