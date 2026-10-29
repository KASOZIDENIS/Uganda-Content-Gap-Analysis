# -*- coding: utf-8 -*-
"""Uganda across the other Wikimedia projects: Commons, Wikidata, Wikisource
and the rest.

Everything here comes from public endpoints (MediaWiki APIs of each project,
the Wikidata Query Service) and is written to data/projects/projects.json,
which the projects dashboard reads.

What is measured follows the Wikidata WikiProject Uganda
(https://www.wikidata.org/wiki/Wikidata:WikiProject_Uganda): the places and
people of Uganda by type, the lists the project keeps (hospitals, universities,
museums, schools, hotels, parks, monuments), the tasks it sets (items with no
Luganda label, items with no classification or no image), and the Luganda
lexemes. For Commons the existing crawl of Category:Uganda is used. For every
other project it is what each holds on Uganda and in Luganda.

    python src_data/sister_projects.py
"""

import json
import os
import time

import category_profiles as cp
import config
import wikiapi
import ug_utils

OUT_DIR = os.path.join(config.DATA_PATH, 'projects')
OUT = os.path.join(OUT_DIR, 'projects.json')
WDQS = 'https://query.wikidata.org/sparql'
WD = 'https://www.wikidata.org/w/api.php'
UGANDA, LUGANDA = 'Q1036', 'Q33368'

FAMILIES = {
    'Wikipedia': 'wikipedia.org', 'Wiktionary': 'wiktionary.org',
    'Wikibooks': 'wikibooks.org', 'Wikiquote': 'wikiquote.org',
    'Wikisource': 'wikisource.org', 'Wikinews': 'wikinews.org',
    'Wikivoyage': 'wikivoyage.org', 'Wikiversity': 'wikiversity.org'}
LANGS = (('en', 'English'), ('lg', 'Luganda'), ('sw', 'Swahili'))
SINGLE = {
    'Wikimedia Commons': 'commons.wikimedia.org',
    'Wikidata': 'www.wikidata.org', 'Wikispecies': 'species.wikimedia.org',
    'Meta-Wiki': 'meta.wikimedia.org', 'Incubator': 'incubator.wikimedia.org',
    'MediaWiki': 'www.mediawiki.org', 'Wikifunctions': 'www.wikifunctions.org'}

# the lists the WikiProject keeps, and the classes behind them
CLASSES = [
    ('Hospitals', 'Q16917'), ('Universities and colleges', 'Q3918'),
    ('Schools', 'Q3914'), ('Museums', 'Q33506'), ('Hotels', 'Q27686'),
    ('National parks', 'Q46169'), ('Monuments', 'Q4989906'),
    ('Political parties', 'Q7278'), ('Think tanks', 'Q1043'),
    ('Ethnic groups', 'Q41710'), ('Nonprofit organisations', 'Q163740'),
    ('Roads', 'Q34442'), ('Airports', 'Q1248784')]


def log(msg):
    print('   ', msg, flush=True)


# ---------------------------------------------------------------- Wikidata
def sparql(query, tries=4):
    session = ug_utils.get_session()
    delay = 5
    for attempt in range(tries):
        try:
            r = session.get(WDQS, params={'query': query, 'format': 'json'},
                            headers={'Accept': 'application/sparql-results+json'},
                            timeout=120)
            if r.status_code == 429:
                time.sleep(min(int(r.headers.get('Retry-After') or delay), 90))
                continue
            r.raise_for_status()
            return r.json()['results']['bindings']
        except Exception as error:                      # noqa: BLE001
            if attempt == tries - 1:
                log(f'query failed: {str(error)[:80]}')
                return None
            time.sleep(delay)
            delay *= 2
    return None


def count(where, var='?i'):
    rows = sparql(f'SELECT (COUNT(DISTINCT {var}) AS ?n) WHERE {{ {where} }}')
    return int(rows[0]['n']['value']) if rows else None


def grouped(where, by, label='?tLabel', limit=20, min_n=1):
    rows = sparql(f"""SELECT {by} {label} ?n WHERE {{
        {{ SELECT {by} (COUNT(DISTINCT ?i) AS ?n) WHERE {{ {where} }}
          GROUP BY {by} HAVING (COUNT(DISTINCT ?i) >= {min_n}) }}
        SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
      }} ORDER BY DESC(?n) LIMIT {limit}""")
    if rows is None:
        return None
    key = label.lstrip('?')
    return [[r.get(key, {}).get('value', r[by.lstrip('?')]['value']),
             int(r['n']['value'])] for r in rows]


def wikidata_block():
    block = {}
    in_uganda = f'?i wdt:P17 wd:{UGANDA} .'
    log('Wikidata: items about Uganda')
    block['items'] = count(in_uganda)
    block['by_type'] = grouped(in_uganda + ' ?i wdt:P31 ?t .', '?t',
                               limit=25)
    block['places'] = count(f'?i wdt:P131+ wd:{UGANDA} .')
    block['place_types'] = grouped(f'?i wdt:P131+ wd:{UGANDA} . ?i wdt:P31 ?t .',
                                   '?t', limit=15, min_n=50)
    log('Wikidata: people')
    people = f'?i wdt:P27 wd:{UGANDA} . ?i wdt:P31 wd:Q5 .'
    block['people'] = count(people)
    block['people_by_gender'] = grouped(people + ' ?i wdt:P21 ?t .', '?t',
                                        limit=6)
    block['occupations'] = grouped(people + ' ?i wdt:P106 ?t .', '?t',
                                   limit=15, min_n=10)
    block['born_in_uganda'] = count(
        f'?i wdt:P31 wd:Q5 . ?i wdt:P19 ?b . ?b wdt:P17 wd:{UGANDA} .')
    log('Wikidata: labels')
    labels = {}
    for code, name in (('en', 'English'), ('lg', 'Luganda'),
                       ('sw', 'Swahili'), ('fr', 'French'), ('de', 'German')):
        labels[name] = count(in_uganda + f' ?i rdfs:label ?l . FILTER(LANG(?l) '
                             f'= "{code}")')
    block['labels'] = labels
    block['missing_lg_label'] = count(
        in_uganda + ' ?i rdfs:label ?e . FILTER(LANG(?e) = "en") '
        'FILTER NOT EXISTS { ?i rdfs:label ?m . FILTER(LANG(?m) = "lg") } '
        'FILTER NOT EXISTS { ?i rdfs:label ?m2 . FILTER(LANG(?m2) = "mul") }')
    block['no_classification'] = count(
        in_uganda + ' FILTER NOT EXISTS { ?i wdt:P31 ?x } '
        'FILTER NOT EXISTS { ?i wdt:P279 ?y }')
    block['geographic_object'] = count(in_uganda + ' ?i wdt:P31 wd:Q618123 .')
    block['no_image'] = count(in_uganda + ' FILTER NOT EXISTS { ?i wdt:P18 ?p }')
    block['with_coordinates'] = count(in_uganda + ' ?i wdt:P625 ?c .')
    block['in_english_wikipedia'] = count(
        in_uganda + ' ?a schema:about ?i ; schema:isPartOf '
        '<https://en.wikipedia.org/> .')
    block['in_luganda_wikipedia'] = count(
        in_uganda + ' ?a schema:about ?i ; schema:isPartOf '
        '<https://lg.wikipedia.org/> .')
    log('Wikidata: the lists the project keeps')
    lists = []
    for name, qid in CLASSES:
        base = (f'?i wdt:P31/wdt:P279* wd:{qid} . ?i wdt:P17 wd:{UGANDA} .')
        row = {'name': name, 'items': count(base)}
        for key, extra in (
                ('lg_label', '?i rdfs:label ?l . FILTER(LANG(?l) = "lg")'),
                ('en_label', '?i rdfs:label ?l . FILTER(LANG(?l) = "en")'),
                ('en_article', '?a schema:about ?i ; schema:isPartOf '
                 '<https://en.wikipedia.org/> .'),
                ('lg_article', '?a schema:about ?i ; schema:isPartOf '
                 '<https://lg.wikipedia.org/> .'),
                ('coordinates', '?i wdt:P625 ?c .'),
                ('image', '?i wdt:P18 ?p .'),
                ('commons', '?i wdt:P373 ?cc .')):
            row[key] = count(base + ' ' + extra) if row['items'] else 0
        lists.append(row)
        log(f'  {name}: {row["items"]}')
    block['lists'] = lists
    heritage = f'?i wdt:P1435 wd:Q9259 . ?i wdt:P17 wd:{UGANDA} .'
    block['world_heritage'] = count(heritage)
    block['politicians'] = count(
        f'?i wdt:P106 wd:Q82955 . ?i wdt:P27 wd:{UGANDA} .')
    log('Wikidata: Luganda lexemes')
    lex = f'?l a ontolex:LexicalEntry ; dct:language wd:{LUGANDA} .'
    block['lexemes'] = count(lex, '?l')
    block['lexeme_categories'] = grouped(
        f'?i a ontolex:LexicalEntry ; dct:language wd:{LUGANDA} ; '
        'wikibase:lexicalCategory ?t .', '?t', limit=12)
    block['lexeme_forms'] = count(lex + ' ?l ontolex:lexicalForm ?f .', '?f')
    block['lexeme_senses'] = count(lex + ' ?l ontolex:sense ?s .', '?s')
    log('Wikidata: important items and properties')
    important = []
    payload = wikiapi._api(WD, {'action': 'wbgetentities',
                           'ids': f'{UGANDA}|{LUGANDA}|Q3894|Q21831016',
                           'props': 'sitelinks|claims|labels',
                           'languages': 'en'})
    for qid, ent in (payload.get('entities') or {}).items():
        important.append({'qid': qid,
                          'label': (ent.get('labels') or {}).get(
                              'en', {}).get('value', ''),
                          'sitelinks': len(ent.get('sitelinks') or {}),
                          'statements': sum(len(v) for v in
                                            (ent.get('claims') or {}).values())})
    block['important'] = important
    block['uganda_properties'] = len(wikiapi._members(
        'Category:Uganda-related properties', 'page'))
    return block


# ----------------------------------------------------------------- projects
def quick(api, params, tries=3):
    """One call to a project that may not exist: a few short tries, then None.
    (research_tasks._api keeps trying for an hour, which suits the crawl and
    not a site that is simply not there.)"""
    session = ug_utils.get_session()
    query = dict(params, format='json', formatversion=2)
    for attempt in range(tries):
        try:
            r = session.get(api, params=query, timeout=30)
            if r.status_code == 429:
                time.sleep(min(int(r.headers.get('Retry-After') or 5), 60))
                continue
            if r.status_code >= 400:
                return None
            return r.json()
        except Exception:                               # noqa: BLE001
            time.sleep(3)
    return None


def site_row(project, lang_name, host):
    api = f'https://{host}/w/api.php'
    got = quick(api, {'action': 'query', 'meta': 'siteinfo',
                      'siprop': 'statistics'})
    if not got or 'query' not in got:
        return None
    stats = got['query']['statistics']

    def hits(term, ns='0'):
        try:
            return quick(api, {
                'action': 'query', 'list': 'search', 'srsearch': term,
                'srnamespace': ns, 'srlimit': 1, 'srinfo': 'totalhits'})[
                'query']['searchinfo']['totalhits']
        except Exception:                               # noqa: BLE001
            return None

    return {'project': project, 'language': lang_name, 'host': host,
            'pages': stats.get('pages'), 'content_pages': stats.get('articles'),
            'files': stats.get('images'), 'edits': stats.get('edits'),
            'users': stats.get('users'), 'active_users': stats.get('activeusers'),
            'uganda': hits('Uganda'), 'ugandan': hits('Ugandan'),
            'luganda': hits('Luganda')}


def top_hits(host, term='Uganda', ns='0', limit=60):
    api = f'https://{host}/w/api.php'
    try:
        payload = quick(api, {
            'action': 'query', 'list': 'search', 'srsearch': term,
            'srnamespace': ns, 'srlimit': limit,
            'srprop': 'size|wordcount|timestamp'})
    except Exception:                                   # noqa: BLE001
        return []
    if not payload:
        return []
    return [[h['title'], h.get('size', 0), h.get('wordcount', 0),
             (h.get('timestamp') or '')[:10]]
            for h in payload.get('query', {}).get('search', [])]


def category_size(host, title):
    api = f'https://{host}/w/api.php'
    try:
        payload = quick(api, {'action': 'query', 'prop': 'categoryinfo',
                                'titles': title})
        page = payload['query']['pages'][0]
        info = page.get('categoryinfo') or {}
        return {'pages': info.get('pages', 0), 'subcats': info.get('subcats', 0),
                'files': info.get('files', 0)}
    except Exception:                                   # noqa: BLE001
        return None


def projects_block():
    rows = []
    for project, domain in FAMILIES.items():
        for code, name in LANGS:
            host = f'{code}.{domain}'
            row = site_row(project, name, host)
            if row:
                rows.append(row)
                log(f'{project} {name}: {row["content_pages"]:,} pages, '
                    f'{row["uganda"]} on Uganda')
    for project, host in SINGLE.items():
        row = site_row(project, 'All languages', host)
        if row:
            rows.append(row)
            log(f'{project}: {row["uganda"]} on Uganda')
    return rows


def details_block():
    out = {}
    out['wikisource_uganda'] = top_hits('en.wikisource.org', 'Uganda', '0', 100)
    out['wikisource_authors'] = top_hits('en.wikisource.org', 'Uganda', '102',
                                         50)
    out['wikisource_category'] = category_size('en.wikisource.org',
                                               'Category:Uganda')
    out['wikisource_luganda'] = top_hits('en.wikisource.org', 'Luganda', '0',
                                         50)
    for name, host in (('wikibooks', 'en.wikibooks.org'),
                       ('wikiquote', 'en.wikiquote.org'),
                       ('wikinews', 'en.wikinews.org'),
                       ('wikivoyage', 'en.wikivoyage.org'),
                       ('wikiversity', 'en.wikiversity.org'),
                       ('wikispecies', 'species.wikimedia.org'),
                       ('meta', 'meta.wikimedia.org'),
                       ('wiktionary', 'en.wiktionary.org')):
        out[name + '_hits'] = top_hits(host, 'Uganda', '0', 40)
        out[name + '_category'] = category_size(host, 'Category:Uganda')
    out['wiktionary_luganda'] = {
        'lemmas': category_size('en.wiktionary.org', 'Category:Luganda lemmas'),
        'language': category_size('en.wiktionary.org', 'Category:Luganda language'),
        'nouns': category_size('en.wiktionary.org', 'Category:Luganda nouns'),
        'verbs': category_size('en.wiktionary.org', 'Category:Luganda verbs')}
    out['incubator_luganda'] = {
        'wikipedia': len(top_hits('incubator.wikimedia.org', 'Luganda', '0', 50)),
    }
    out['commons_uganda'] = {
        'category': category_size('commons.wikimedia.org', 'Category:Uganda'),
        'files_deep': _deep_files()}
    return out


def _deep_files():
    api = 'https://commons.wikimedia.org/w/api.php'
    try:
        return quick(api, {
            'action': 'query', 'list': 'search',
            'srsearch': 'deepcategory:"Uganda"', 'srnamespace': '6',
            'srlimit': 1, 'srinfo': 'totalhits'})['query']['searchinfo'][
            'totalhits']
    except Exception:                                   # noqa: BLE001
        return None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    import datetime
    result = {'built': datetime.datetime.now().isoformat(timespec='seconds')}
    try:
        with open(OUT, encoding='utf-8') as handle:
            result = dict(json.load(handle), **result)   # keep what is held
    except (OSError, ValueError):
        pass
    for key, fn in (('projects', projects_block), ('details', details_block),
                    ('wikidata', wikidata_block)):
        cp.tick(0, 1, key)
        try:
            result[key] = fn()
        except Exception as error:                      # noqa: BLE001
            log(f'{key} failed: {error}')
        with open(OUT, 'w', encoding='utf-8') as handle:
            json.dump(result, handle, ensure_ascii=False)
    print('PROJECTS_DONE')


if __name__ == '__main__':
    main()
