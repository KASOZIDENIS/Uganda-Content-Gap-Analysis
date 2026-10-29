# -*- coding: utf-8 -*-
"""Stage 1: the Uganda corpus and its features, from Wikidata.

The corpus is every Wikidata item about Uganda that has a Wikipedia article.
It is sourced from the public Wikidata Query Service and the MediaWiki API, so
it runs anywhere without credentials.

Each retrieval strategy independently proposes items. An item's strategy count
becomes a confidence signal: the more strategies agree, the surer the link to
Uganda.
"""

import time

import config
import ug_utils
from ug_utils import binding_value, qid_from_uri, run_sparql, run_sparql_chunked

SCRIPT = 'content_retrieval'

# ---------------------------------------------------------------------------
# Retrieval strategies. Each returns items that have at least one Wikipedia
# article; the article-less mass is counted separately by count_wikidata_only.
# ---------------------------------------------------------------------------

STRATEGIES = {
    # Anything whose country is Uganda.
    'country_wd': """
        SELECT ?item WHERE {
          ?item wdt:P17 wd:Q1036 ; wikibase:sitelinks ?sl .
          FILTER(?sl > 0)
        }""",

    # Anything located anywhere inside Uganda's administrative hierarchy,
    # or whose narrative/filming/HQ location sits in Uganda.
    #
    # Places reached via P17 must be in Uganda and *only* Uganda. Transnational
    # features (the Nile, Lake Victoria, the Great Rift Valley) list Uganda
    # among several countries, so without the guard everything located at one
    # of them inherits a spurious Ugandan connection. P131+ needs no guard:
    # an administrative chain to Uganda is unambiguous.
    'location_wd': """
        SELECT DISTINCT ?item WHERE {
          { ?item wdt:P131+ wd:Q1036 }
          UNION {
            { ?item wdt:P276 ?place } UNION { ?item wdt:P159 ?place }
            ?place wdt:P17 wd:Q1036 .
            FILTER NOT EXISTS { ?place wdt:P17 ?other .
                                FILTER(?other != wd:Q1036) }
          }
          ?item wikibase:sitelinks ?sl . FILTER(?sl > 0)
        }""",

    # People holding Ugandan citizenship.
    'citizenship_wd': """
        SELECT ?item WHERE {
          ?item wdt:P27 wd:Q1036 ; wikibase:sitelinks ?sl .
          FILTER(?sl > 0)
        }""",

    # People born or died in Uganda even without citizenship recorded.
    # Same single-country guard as location_wd, and for the same reason:
    # Antinous and Ptolemy XIII both drowned in the Nile, which counts Uganda
    # among its countries, and both were landing at the top of the worklists.
    'birth_death_wd': """
        SELECT DISTINCT ?item WHERE {
          { ?item wdt:P19 ?place } UNION { ?item wdt:P20 ?place }
          ?place wdt:P17 wd:Q1036 .
          FILTER NOT EXISTS { ?place wdt:P17 ?other .
                              FILTER(?other != wd:Q1036) }
          ?item wikibase:sitelinks ?sl . FILTER(?sl > 0)
        }""",

    # Members of, and topics about, ethnic groups indigenous to Uganda.
    'ethnic_group_wd': """
        SELECT DISTINCT ?item WHERE {
          ?group wdt:P17 wd:Q1036 ; wdt:P31/wdt:P279* wd:Q41710 .
          { ?item wdt:P172 ?group } UNION { ?item wdt:P361 ?group }
          ?item wikibase:sitelinks ?sl . FILTER(?sl > 0)
        }""",

    # Works in, or about, the languages of Uganda.
    'language_wd': """
        SELECT DISTINCT ?item WHERE {
          VALUES ?lang { %s }
          { ?item wdt:P407 ?lang } UNION { ?item wdt:P103 ?lang }
          UNION { ?item wdt:P1412 ?lang } UNION { ?item wdt:P2936 ?lang }
          ?item wikibase:sitelinks ?sl . FILTER(?sl > 0)
        }""" % ' '.join('wd:' + q for q in config.UGANDAN_LANGUAGE_QIDS),

    # Things Uganda is a part of / that are part of Uganda, plus
    # organisations and events explicitly tied to the country.
    'part_of_wd': """
        SELECT DISTINCT ?item WHERE {
          { ?item wdt:P361 wd:Q1036 } UNION { wd:Q1036 wdt:P527 ?item }
          UNION { ?item wdt:P1001 wd:Q1036 }
          UNION { ?item wdt:P17 ?c . ?c wdt:P131+ wd:Q1036 }
          ?item wikibase:sitelinks ?sl . FILTER(?sl > 0)
        }""",
}


def retrieve_strategy_hits(conn, force=False):
    """Run every SPARQL strategy and record which items each one proposes."""
    with ug_utils.stage(conn, SCRIPT, 'retrieve_strategy_hits', force) as st:
        if st.skip:
            return

        conn.execute('DROP TABLE IF EXISTS strategy_hits')
        conn.execute("""CREATE TABLE strategy_hits (
            qitem text, strategy text, PRIMARY KEY (qitem, strategy))""")

        for name, query in STRATEGIES.items():
            print(f'  strategy {name} ...', end=' ', flush=True)
            try:
                rows = run_sparql(query, timeout=300)
            except Exception as error:                 # noqa: BLE001
                print(f'FAILED ({type(error).__name__}) - strategy skipped')
                continue
            qitems = {qid_from_uri(binding_value(b, 'item')) for b in rows}
            conn.executemany(
                'INSERT OR IGNORE INTO strategy_hits VALUES (?,?)',
                [(q, name) for q in qitems])
            conn.commit()
            print(f'{len(qitems)} items with articles')

        total = conn.execute(
            'SELECT COUNT(DISTINCT qitem) FROM strategy_hits').fetchone()[0]
        print(f'  union of all strategies: {total} items')


def retrieve_keyword_hits(conn, force=False):
    """Title-keyword strategy, via enwiki CirrusSearch intitle: search.

    Catches articles that name Uganda or a major Ugandan place but carry no
    Wikidata statement linking them to the country - a common gap for
    history, politics and 'List of ...' articles.
    """
    with ug_utils.stage(conn, SCRIPT, 'retrieve_keyword_hits', force) as st:
        if st.skip:
            return

        session = ug_utils.get_session()
        api = 'https://en.wikipedia.org/w/api.php'
        titles = set()

        for keyword in config.TITLE_KEYWORDS:
            offset, found = 0, 0
            while True:
                params = {
                    'action': 'query', 'list': 'search', 'format': 'json',
                    'srsearch': f'intitle:"{keyword}"', 'srlimit': 500,
                    'sroffset': offset, 'srnamespace': 0,
                    'srprop': '', 'srinfo': '',
                }
                try:
                    payload = session.get(api, params=params, timeout=90).json()
                except Exception as error:             # noqa: BLE001
                    print(f'    search failed for {keyword}: {error}')
                    break
                hits = payload.get('query', {}).get('search', [])
                titles.update(h['title'] for h in hits)
                found += len(hits)
                if 'continue' not in payload:
                    break
                offset = payload['continue']['sroffset']
                time.sleep(0.2)
            print(f'    intitle:"{keyword}" -> {found} enwiki titles')

        print(f'  resolving {len(titles)} titles to Wikidata items ...')
        qitems = set()
        titles = sorted(titles)
        for i in range(0, len(titles), 50):
            batch = titles[i:i + 50]
            params = {
                'action': 'query', 'format': 'json', 'prop': 'pageprops',
                'ppprop': 'wikibase_item', 'titles': '|'.join(batch),
            }
            try:
                payload = session.get(api, params=params, timeout=90).json()
            except Exception:                          # noqa: BLE001
                continue
            for page in payload.get('query', {}).get('pages', {}).values():
                qid = page.get('pageprops', {}).get('wikibase_item')
                if qid:
                    qitems.add(qid)
            time.sleep(0.1)

        conn.executemany('INSERT OR IGNORE INTO strategy_hits VALUES (?,?)',
                         [(q, 'keyword_title') for q in qitems])
        conn.commit()
        print(f'  keyword_title -> {len(qitems)} items')


def count_wikidata_only(conn, force=False):
    """Count Uganda items that exist in Wikidata but in no Wikipedia.

    This is the headline structural finding, so it gets its own table.
    """
    with ug_utils.stage(conn, SCRIPT, 'count_wikidata_only', force) as st:
        if st.skip:
            return

        conn.execute('DROP TABLE IF EXISTS wikidata_only')
        conn.execute("""CREATE TABLE wikidata_only (
            type_qid text, type_label text, no_article int, with_article int)""")

        query = """
        SELECT ?type ?typeLabel ?none ?some WHERE {
          {
            SELECT ?type
                   (SUM(IF(?sl = 0, 1, 0)) AS ?none)
                   (SUM(IF(?sl > 0, 1, 0)) AS ?some)
            WHERE {
              ?item wdt:P17 wd:Q1036 ; wdt:P31 ?type ; wikibase:sitelinks ?sl .
            } GROUP BY ?type
          }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        } ORDER BY DESC(?none) LIMIT 60
        """
        rows = run_sparql(query, timeout=300)
        conn.executemany('INSERT INTO wikidata_only VALUES (?,?,?,?)', [
            (qid_from_uri(binding_value(b, 'type')),
             binding_value(b, 'typeLabel', ''),
             int(binding_value(b, 'none', 0)),
             int(binding_value(b, 'some', 0))) for b in rows])
        conn.commit()

        totals = run_sparql("""
        SELECT (SUM(IF(?sl = 0, 1, 0)) AS ?none) (SUM(IF(?sl > 0, 1, 0)) AS ?some)
        WHERE { ?item wdt:P17 wd:Q1036 ; wikibase:sitelinks ?sl . }
        """, timeout=300)
        conn.execute('DROP TABLE IF EXISTS wikidata_only_totals')
        conn.execute('CREATE TABLE wikidata_only_totals (no_article int, with_article int)')
        conn.execute('INSERT INTO wikidata_only_totals VALUES (?,?)',
                     (int(binding_value(totals[0], 'none', 0)),
                      int(binding_value(totals[0], 'some', 0))))
        conn.commit()
        print(f'  no article anywhere: {binding_value(totals[0], "none")} | '
              f'with article: {binding_value(totals[0], "some")}')


# ---------------------------------------------------------------------------
# Feature retrieval for the CCC union
# ---------------------------------------------------------------------------

SCALARS_QUERY = """
SELECT ?item (SAMPLE(?sl) AS ?sitelinks) (SAMPLE(?lab) AS ?label)
       (SAMPLE(?gen) AS ?gender) (SAMPLE(?crd) AS ?coord)
       (SAMPLE(?adm) AS ?admin) (SAMPLE(?inc) AS ?inception)
       (SAMPLE(?born) AS ?dob) (SAMPLE(?occ) AS ?occupation)
WHERE {
  VALUES ?item { {values} }
  ?item wikibase:sitelinks ?sl .
  OPTIONAL { ?item rdfs:label ?lab . FILTER(LANG(?lab) = "en") }
  OPTIONAL { ?item wdt:P21 ?gen }
  OPTIONAL { ?item wdt:P625 ?crd }
  OPTIONAL { ?item wdt:P131 ?adm }
  OPTIONAL { ?item wdt:P571 ?inc }
  OPTIONAL { ?item wdt:P569 ?born }
  OPTIONAL { ?item wdt:P106 ?occ }
} GROUP BY ?item
"""

TYPES_QUERY = """
SELECT ?item (GROUP_CONCAT(DISTINCT ?t; separator="|") AS ?types) WHERE {
  VALUES ?item { {values} }
  ?item wdt:P31 ?t .
} GROUP BY ?item
"""

SITELINKS_QUERY = """
SELECT ?item ?wiki ?title WHERE {
  VALUES ?item { {values} }
  ?article schema:about ?item ; schema:isPartOf ?wiki ; schema:name ?title .
  FILTER(STRENDS(STR(?wiki), ".wikipedia.org/"))
}
"""

LABELS_QUERY = """
SELECT ?item ?itemLabel WHERE {
  VALUES ?item { {values} }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""


def retrieve_ccc_features(conn, force=False):
    """Fetch per item features for every item in the CCC union."""
    with ug_utils.stage(conn, SCRIPT, 'retrieve_ccc_features', force) as st:
        if st.skip:
            return

        qitems = [r[0] for r in conn.execute(
            'SELECT DISTINCT qitem FROM strategy_hits ORDER BY qitem')]
        print(f'  fetching features for {len(qitems)} items')

        conn.execute('DROP TABLE IF EXISTS ccc_items')
        conn.execute("""CREATE TABLE ccc_items (
            qitem text PRIMARY KEY, label text, sitelink_count int,
            gender_qid text, latitude real, longitude real,
            admin_qid text, inception text, date_of_birth text,
            occupation_qid text, types text,
            strategies text, num_strategies int)""")

        scalars = {}
        for b in run_sparql_chunked(SCALARS_QUERY, qitems, label='features'):
            qid = qid_from_uri(binding_value(b, 'item'))
            coord = binding_value(b, 'coord')
            lat = lon = None
            if coord and coord.startswith('Point('):
                try:
                    lon_s, lat_s = coord[6:-1].split()
                    lat, lon = float(lat_s), float(lon_s)
                except ValueError:
                    pass
            gender = binding_value(b, 'gender')
            admin = binding_value(b, 'admin')
            occupation = binding_value(b, 'occupation')
            scalars[qid] = {
                'label': binding_value(b, 'label'),
                'sitelink_count': int(binding_value(b, 'sitelinks', 0)),
                'gender_qid': qid_from_uri(gender) if gender else None,
                'latitude': lat, 'longitude': lon,
                'admin_qid': qid_from_uri(admin) if admin else None,
                'inception': binding_value(b, 'inception'),
                'date_of_birth': binding_value(b, 'dob'),
                'occupation_qid': qid_from_uri(occupation) if occupation else None,
            }

        types = {}
        for b in run_sparql_chunked(TYPES_QUERY, qitems, label='types'):
            qid = qid_from_uri(binding_value(b, 'item'))
            raw = binding_value(b, 'types', '') or ''
            types[qid] = '|'.join(qid_from_uri(u) for u in raw.split('|') if u)

        strategies = {}
        for qid, name in conn.execute('SELECT qitem, strategy FROM strategy_hits'):
            strategies.setdefault(qid, []).append(name)

        rows = []
        for qid in qitems:
            s = scalars.get(qid, {})
            names = sorted(strategies.get(qid, []))
            rows.append((
                qid, s.get('label'), s.get('sitelink_count', 0),
                s.get('gender_qid'), s.get('latitude'), s.get('longitude'),
                s.get('admin_qid'), s.get('inception'), s.get('date_of_birth'),
                s.get('occupation_qid'), types.get(qid, ''),
                '|'.join(names), len(names)))

        conn.executemany(
            'INSERT OR REPLACE INTO ccc_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
        conn.commit()
        print(f'  stored {len(rows)} CCC items')


def retrieve_sitelinks(conn, force=False):
    """Fetch which Wikipedia language editions carry each CCC item."""
    with ug_utils.stage(conn, SCRIPT, 'retrieve_sitelinks', force) as st:
        if st.skip:
            return

        qitems = [r[0] for r in conn.execute(
            'SELECT qitem FROM ccc_items ORDER BY qitem')]

        conn.execute('DROP TABLE IF EXISTS sitelinks')
        conn.execute("""CREATE TABLE sitelinks (
            qitem text, languagecode text, title text,
            PRIMARY KEY (qitem, languagecode))""")

        rows = []
        for b in run_sparql_chunked(SITELINKS_QUERY, qitems,
                                    chunk_size=300, label='sitelinks'):
            wiki = binding_value(b, 'wiki', '')
            # https://lg.wikipedia.org/ -> lg
            code = wiki.replace('https://', '').split('.wikipedia.org')[0]
            rows.append((qid_from_uri(binding_value(b, 'item')), code,
                         binding_value(b, 'title')))

        conn.executemany('INSERT OR IGNORE INTO sitelinks VALUES (?,?,?)', rows)
        conn.execute('CREATE INDEX IF NOT EXISTS idx_sl_lang ON sitelinks(languagecode)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_sl_item ON sitelinks(qitem)')
        conn.commit()

        langs = conn.execute(
            'SELECT COUNT(DISTINCT languagecode) FROM sitelinks').fetchone()[0]
        print(f'  stored {len(rows)} sitelinks across {langs} language editions')


def resolve_entity_labels(conn, force=False):
    """Resolve every referenced QID (types, genders, districts) to a label."""
    with ug_utils.stage(conn, SCRIPT, 'resolve_entity_labels', force) as st:
        if st.skip:
            return

        needed = set()
        for gender, admin, occupation, types in conn.execute(
                'SELECT gender_qid, admin_qid, occupation_qid, types FROM ccc_items'):
            needed.update(q for q in (gender, admin, occupation) if q)
            needed.update(q for q in (types or '').split('|') if q)
        needed = sorted(needed)
        print(f'  resolving {len(needed)} entity labels')

        conn.execute("""CREATE TABLE IF NOT EXISTS entity_labels (
            qitem text PRIMARY KEY, label text)""")

        rows = []
        for b in run_sparql_chunked(LABELS_QUERY, needed,
                                    chunk_size=400, label='labels'):
            rows.append((qid_from_uri(binding_value(b, 'item')),
                         binding_value(b, 'itemLabel')))
        conn.executemany('INSERT OR REPLACE INTO entity_labels VALUES (?,?)', rows)
        conn.commit()
        print(f'  stored {len(rows)} labels')


def main(force=False):
    conn = ug_utils.connect()
    retrieve_strategy_hits(conn, force)
    retrieve_keyword_hits(conn, force)
    count_wikidata_only(conn, force)
    retrieve_ccc_features(conn, force)
    retrieve_sitelinks(conn, force)
    resolve_entity_labels(conn, force)
    conn.close()


if __name__ == '__main__':
    import sys
    main(force='--force' in sys.argv)
