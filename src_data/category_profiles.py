# -*- coding: utf-8 -*-
"""Stage 15: a full profile of every top-level Uganda category, article by article.

The analysis goes deeper than counts: people split by living or deceased and by
gender, quality class, stubs, readership per year, articles created per year,
lead images, Luganda coverage, and a way to find the articles that sit in no
category at all. `data/inputs/uganda_category_list.csv` lists the client's
Ugandan categories. This stage takes that tree and produces, for each of its
top-level categories, every article under it with all of those measures.
`src_viz/build_category_files.py` then writes one file per category.

**Which categories count.** The walk is bounded by the client's list (plus any
category whose name carries a Ugandan name), because the category graph does not
stop at the border: geography leads to African districts, and from there to the
rest of the encyclopedia.

**An article in two categories appears in both files.** Each file has to stand on
its own, so nothing is removed from one to avoid repeating it in another. The
`also_in` column names the other categories, and the index counts each article
once.

**Uncategorised.** The corpus (`ug_ccc_full_corpus.csv`) finds Uganda articles
by Wikidata rather than by category, so the ones it has that the walk did not
reach are the articles that sit in no category of the tree, and they get a file
of their own.

    python src_data/category_profiles.py
"""

import csv
import datetime
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import config
import wikiapi
import ug_utils
import yn

SCRIPT = 'category_profiles'

# The client's list of Ugandan categories: its 14 top-level categories are the
# main groups, and its names start the category walk.
COVERAGE_CSV = os.path.join(config.DATA_PATH, 'inputs',
                            'uganda_category_list.csv')
CORPUS_CSV = os.path.join(config.DATA_PATH, 'ug_ccc_full_corpus.csv')

EN_API = wikiapi.EN_API
WD_API = wikiapi.WD_API
COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
PV = ('https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/'
      '{project}/all-access/user/{title}/monthly/20150701/{end}')


def pv_window(today=None):
    """(last day the Pageviews API can hold, first and last of the twelve months).

    The API has nothing newer than the last complete month, so that is where a
    run measures to. It is worked out when asked, not fixed in the file, so a
    server left running past a month end measures the new month.
    """
    today = today or datetime.date.today()
    end = today.replace(day=1) - datetime.timedelta(days=1)
    first = (end.year - 1, end.month + 1) if end.month < 12 else (end.year, 1)
    return (end.strftime('%Y%m%d'),
            (f'{first[0]}-{first[1]:02d}', f'{end.year}-{end.month:02d}'))


# Progress. refresh.py sets REPORT to a function taking (done, total, note);
# run from the console it is None and stages just print, as they always did.
REPORT = None


def tick(done, total, note=''):
    if REPORT:
        REPORT(done, total, note)

UNCATEGORISED = 'Uncategorised'
EXTRA_MAIN = ('Sport in Uganda',)

# Top-level groups the client asked to leave out of the analysis: not shown in
# any file, workbook or chart, with every article filed beneath them. Empty now;
# Buildings was removed once and then restored as structures only.
REMOVED_TOPS = ()

# Groups that hang from more roots than the one named for them. These categories
# sit outside the group's own category but belong to it; they are opened only
# through categories whose names are Ugandan, so a root such as the African
# tallest-buildings list brings in its Ugandan entries and not the continent.
STRUCTURE_WORDS = re.compile(
    r'building|structure|tower|skyscraper|bridge|road|highway|railway|rail\b|'
    r'airport|airstrip|airline|port\b|ferry|stadium|hospital|church|cathedral|'
    r'mosque|temple|shrine|hotel|dam\b|power station|substation|pipeline|'
    r'prison|market|mall|museum|palace|tomb|fort\b|monument|memorial|'
    r'university|school|college|campus|transport|bus\b|taxi|boda|train|'
    r'station|terminal|border post|water|bridges|landmark|heritage', re.I)

# root -> a pattern its articles' titles must match, or None to take them all.
# Uganda-related lists holds lists of every kind, so only the lists about
# structures and transport are taken from it.
GROUP_ROOTS = {
    'Buildings and structures in Uganda': {
        'Category:Lists of buildings and structures in Uganda': None,
        'Category:Uganda transport-related lists': None,
        'Category:Lists of tallest buildings in Africa': None,
        'Category:Transport in Uganda': None,
        'Category:Uganda-related lists': STRUCTURE_WORDS},
}
ROOT = 'Uganda'
WORKERS = 5
BATCH = wikiapi.BATCH

FEMALE, MALE = 'Q6581072', 'Q6581097'
HUMAN = 'Q5'


# --------------------------------------------------------------- the tree
def load_tree():
    """(top-level categories, every category name) from the coverage CSV."""
    names, tops = set(), []
    with open(COVERAGE_CSV, encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            name = (row.get('Category') or '').strip()
            if not name:
                continue
            names.add(name)
            try:
                depth = int(float(row.get('Depth') or ''))
            except ValueError:
                continue
            if depth == 1 and name not in REMOVED_TOPS:
                tops.append(name)
    # Categories the client's workbook lists below the top level but that are
    # main subjects in their own right. Sport sits under Culture, Society and
    # Ugandan people at once, so it appears in none of them as a whole.
    for extra in EXTRA_MAIN:
        if extra not in tops:
            tops.append(extra)
    return tops, names


def slug(name):
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


# Words that make a category Ugandan on their own. The coverage workbook
# lists 2,885 categories, but the tree has moved since it was taken: Hospitals
# in Uganda now sits under per-city categories that never say "Uganda".
KEYWORDS = re.compile(
    r'Ugand|Kampala|Buganda|Baganda|Bunyoro|Ankole|Busoga|Basoga|Tooro|'
    r'\bToro\b|Karamoja|Acholi|\bTeso\b|\bLango\b|Entebbe|Rwenzori|'
    r'Luganda|Lugbara|Kigezi|Bugisu|Bukedi|West Nile|Jinja|Gulu|Mbarara|'
    r'Banyankole|Lusoga|Runyankore|Ateso|Alur\b')

# For judging an article's own text rather than a category name. Narrower:
# "West Nile" is also a virus, Teso and Lango are common words, and a lead
# that says "bordered by Uganda" is not about Uganda.
LEAD_WORDS = re.compile(
    r'Ugand|Kampala|Buganda|Baganda|Bunyoro|Ankole|Busoga|Basoga|Tooro|'
    r'Karamoja|Acholi|Entebbe|Luganda|Lugbara|Kigezi|Bugisu|Bukedi|Jinja|'
    r'Gulu|Mbarara|Banyankole|Lusoga|Runyankore|Ateso')
LEAD_OPENING = 250
# The lead has to say Uganda where an article says what it is about: in the
# opening, or repeatedly. A single mention further down is how Tanzania,
# Kenya and the Congo name their neighbour.
LEAD_REPEATS = 3

# Tracking and maintenance categories carry the word Uganda and no articles.
NOISE = re.compile(r'^(Wikipedia|WikiProject|Articles |Pages |Use |CS1|'
                   r'Short description|All |Commons category|Webarchive|'
                   r'Template|User )')

# How far past a category whose name is not Ugandan the walk will go. One
# hop picks up Hospitals in Kampala under Hospitals in Uganda; two would be
# the road out to the rest of the encyclopedia.
SLACK = 2
MAX_DEPTH = 10


def named(bare, names):
    return bare in names or bool(KEYWORDS.search(bare))


def reachable(edges, roots, names, slack0=SLACK):
    """Categories the walk may open from `roots`, with where each hangs.

    Returns {category: (sub, depth)}. A category whose name is Ugandan (in the
    workbook, or carrying a keyword) resets the allowance; one that is not may
    be visited only while the allowance from its named ancestor lasts.
    """
    out, best_slack = {}, {}
    queue = []
    for root in roots:
        out[root] = ('', 0)
        best_slack[root] = slack0
        queue.append(root)
    while queue:
        cat = queue.pop(0)
        sub, depth = out[cat]
        slack = best_slack[cat]
        if depth >= MAX_DEPTH:
            continue
        for child, kind in edges.get(cat, []):
            if kind != 'subcat':
                continue
            bare = child.split(':', 1)[1]
            if NOISE.match(bare):
                continue
            if named(bare, names):
                child_slack = SLACK
            elif slack > 0:
                child_slack = slack - 1
            else:
                continue
            if child in out and best_slack[child] >= child_slack:
                continue
            first = sub or bare
            out[child] = (first, depth + 1)
            best_slack[child] = child_slack
            queue.append(child)
    return out


def meta_get(conn, key, default=None):
    conn.execute("""CREATE TABLE IF NOT EXISTS refresh_meta (
        key text PRIMARY KEY, value text)""")
    row = conn.execute('SELECT value FROM refresh_meta WHERE key = ?',
                       (key,)).fetchone()
    return row[0] if row else default


def meta_set(conn, key, value):
    conn.execute("""CREATE TABLE IF NOT EXISTS refresh_meta (
        key text PRIMARY KEY, value text)""")
    conn.execute('INSERT OR REPLACE INTO refresh_meta VALUES (?, ?)',
                 (key, str(value)))
    conn.commit()


def _schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cat_edges (
            parent text, child text, kind text,
            PRIMARY KEY (parent, child));
        CREATE TABLE IF NOT EXISTS cat_fetched (category text PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS cat_members (
            top text, title text, subcat text, depth integer,
            PRIMARY KEY (top, title));
        CREATE TABLE IF NOT EXISTS cat_articles (
            title text PRIMARY KEY, qid text, bytes integer, quality text,
            quality_source text, refs integer, stub integer, tags text,
            has_image integer, lg_title text, instance_of text,
            is_human integer, gender text, born integer, died integer,
            life_status text, commons_cat text, commons_files integer,
            is_list integer, described integer DEFAULT 0,
            created text, views_en text, views_lg text);
        CREATE TABLE IF NOT EXISTS cat_info (
            category text PRIMARY KEY, size integer);
    """)


OTHER = 'Other Uganda categories'
FOUND = 'Found by search'

SEARCH_TERMS = ('Uganda', 'Ugandan', 'Kampala', 'Buganda', 'Bunyoro', 'Ankole',
                'Busoga', 'Tooro', 'Karamoja', 'Acholi', 'Teso', 'Lango',
                'Entebbe', 'Rwenzori', 'Baganda', 'Lugbara', 'Luganda',
                'Kigezi', 'Bugisu', 'Bukedi', 'West Nile')


def _search(query, namespace, limit=10000):
    """Titles matching a CirrusSearch query, paged to the API's ceiling."""
    out, offset = [], 0
    while offset < limit:
        payload = wikiapi._api(EN_API, {
            'action': 'query', 'list': 'search', 'srsearch': query,
            'srnamespace': namespace, 'srlimit': 500, 'sroffset': offset,
            'srprop': ''})
        hits = payload.get('query', {}).get('search', [])
        out.extend(h['title'] for h in hits)
        nxt = (payload.get('continue') or {}).get('sroffset')
        if not nxt or not hits:
            break
        offset = nxt
        time.sleep(wikiapi.PAUSE)
    return out


def discover(conn, names, force=False):
    """Categories and articles whose title says Uganda, wherever they are filed.

    The coverage workbook is last year's idea of the tree. A category created
    since, or one the workbook never listed, is found here by name, and so is
    any article with a Ugandan word in its title, so that nothing depends on
    someone having filed it correctly.
    """
    with ug_utils.stage(conn, SCRIPT, 'discover', force) as st:
        if st.skip:
            return
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cat_roots (
                category text PRIMARY KEY, source text);
            CREATE TABLE IF NOT EXISTS search_hits (
                title text, query text, PRIMARY KEY (title, query));
        """)
        cats = set()
        for k, term in enumerate(SEARCH_TERMS):
            tick(k, 2 * len(SEARCH_TERMS), f'categories named {term}')
            hits = _search(f'intitle:{term}', 14)
            print(f'    categories named {term}: {len(hits)}')
            cats.update(hits)
        cats = {c for c in cats if not NOISE.match(c.split(':', 1)[1])}
        conn.executemany('INSERT OR IGNORE INTO cat_roots VALUES (?,?)',
                         [(c, 'search') for c in sorted(cats)])
        for name in sorted(names):
            conn.execute('INSERT OR IGNORE INTO cat_roots VALUES (?,?)',
                         ('Category:' + name, 'workbook'))
        for k, term in enumerate(SEARCH_TERMS):
            tick(len(SEARCH_TERMS) + k, 2 * len(SEARCH_TERMS),
                 f'articles titled {term}')
            hits = _search(f'intitle:{term}', 0)
            print(f'    articles titled {term}: {len(hits)}')
            conn.executemany('INSERT OR IGNORE INTO search_hits VALUES (?,?)',
                             [(t, 'title:' + term) for t in hits])
        conn.commit()


def refresh_tree(conn):
    """Mark for re-reading only the categories whose size has changed.

    Reading all 4,000 categories takes the best part of an hour. MediaWiki will
    report the size of fifty at a time, so a refresh asks for those sizes
    (about a minute), compares them with what was seen last time, and re-reads
    only the categories that differ. The first time there is no earlier size,
    so the comparison is with the number of members already stored, which
    re-reads a category only if that disagrees. Returns (changed, checked).
    """
    _schema(conn)
    fetched = [r[0] for r in conn.execute('SELECT category FROM cat_fetched')]
    stored = dict(conn.execute(
        'SELECT parent, COUNT(*) FROM cat_edges GROUP BY parent').fetchall())
    seen = dict(conn.execute('SELECT category, size FROM cat_info'))
    now, members = {}, {}
    for i in range(0, len(fetched), 50):
        batch = fetched[i:i + 50]
        payload = wikiapi._api(EN_API, {'action': 'query', 'prop': 'categoryinfo',
                                   'titles': '|'.join(batch)})
        q = payload.get('query', {})
        norm = {n['from']: n['to'] for n in q.get('normalized', [])}
        pages = {p['title']: p for p in q.get('pages', [])}
        for c in batch:
            info = (pages.get(norm.get(c, c)) or {}).get('categoryinfo') or {}
            now[c] = info.get('size', 0)
            members[c] = info.get('pages', 0) + info.get('subcats', 0)
        tick(min(i + 50, len(fetched)), len(fetched), 'comparing sizes')
        time.sleep(wikiapi.PAUSE)
    changed = []
    for c in fetched:
        if c in seen:
            if seen[c] != now[c]:
                changed.append(c)
        elif stored.get(c, 0) != members[c]:
            changed.append(c)
    conn.executemany('DELETE FROM cat_edges WHERE parent = ?',
                     [(c,) for c in changed])
    conn.executemany('DELETE FROM cat_fetched WHERE category = ?',
                     [(c,) for c in changed])
    conn.executemany('INSERT OR REPLACE INTO cat_info VALUES (?, ?)',
                     list(now.items()))
    conn.commit()
    return len(changed), len(fetched)


def readership_is_stale(conn):
    """True when the Pageviews API now holds a month the data does not."""
    return meta_get(conn, 'views_through') != pv_window()[0][:6]


def mark_views_stale(conn):
    """Queue every wanted article for a fresh measurement of its views."""
    conn.execute("""UPDATE cat_articles SET views_en = NULL, views_lg = NULL
        WHERE title IN (SELECT title FROM cat_wanted)""")
    conn.commit()


def crawl(conn, names, tops, force=False):
    """Open every category the walk may reach, then assign members to tops."""
    with ug_utils.stage(conn, SCRIPT, 'crawl', force) as st:
        if st.skip:
            return
        _schema(conn)
        roots = ['Category:' + ROOT]
        roots += [r[0] for r in conn.execute('SELECT category FROM cat_roots')]
        roots = list(dict.fromkeys(roots))
        group_roots = [r for extra in GROUP_ROOTS.values() for r in extra]
        done = {r[0] for r in conn.execute('SELECT category FROM cat_fetched')}

        edges = {}

        def load_edges():
            edges.clear()
            for parent, child, kind in conn.execute(
                    'SELECT parent, child, kind FROM cat_edges'):
                edges.setdefault(parent, []).append((child, kind))

        load_edges()
        rounds = 0
        while True:
            rounds += 1
            reach = reachable(edges, roots, names)
            for root in group_roots:
                reach.update({c: v for c, v in reachable(
                    edges, [root], names, 0).items() if c not in reach})
            todo = [c for c in reach if c not in done]
            print(f'    round {rounds}: {len(reach)} categories reachable, '
                  f'{len(todo)} to open')
            if not todo:
                break
            for n, cat in enumerate(todo, 1):
                rows, cont = [], {}
                while True:
                    payload = wikiapi._api(EN_API, dict(
                        {'action': 'query', 'list': 'categorymembers',
                         'cmtitle': cat, 'cmtype': 'page|subcat',
                         'cmnamespace': '0|14', 'cmlimit': 500}, **cont))
                    for m in payload.get('query', {}).get(
                            'categorymembers', []):
                        kind = 'subcat' if m['ns'] == 14 else 'page'
                        rows.append((cat, m['title'], kind))
                    cont = payload.get('continue') or {}
                    if not cont:
                        break
                    time.sleep(wikiapi.PAUSE)
                conn.executemany(
                    'INSERT OR IGNORE INTO cat_edges VALUES (?,?,?)', rows)
                conn.execute('INSERT OR IGNORE INTO cat_fetched VALUES (?)',
                             (cat,))
                done.add(cat)
                tick(n, len(todo), cat.split(':', 1)[1])
                if n % 200 == 0:
                    conn.commit()
                    print(f'      {n}/{len(todo)}')
                time.sleep(wikiapi.PAUSE)
            conn.commit()
            load_edges()

        # Members per top-level category, with the first-level child each
        # hangs under as `subcat`. Whatever the fourteen do not reach is
        # grouped under the roots that did reach it.
        conn.execute('DELETE FROM cat_members')
        claimed = set()
        for top in tops:
            level = reachable(edges, ['Category:' + top], names)
            claimed.update(level)
            _store_members(conn, edges, level, top)
            for extra, pattern in GROUP_ROOTS.get(top, {}).items():
                sub_level = reachable(edges, [extra], names, 0)
                claimed.update(sub_level)
                _store_members(conn, edges, sub_level, top, pattern,
                               keep_better=True)
        other = {}
        for root in roots:
            if root in claimed:
                continue
            level = reachable(edges, [root], names)
            bare = root.split(':', 1)[1]
            for cat, (sub, d) in level.items():
                if cat not in claimed:
                    other.setdefault(cat, (sub or bare, d))
        _store_members(conn, edges, other, OTHER)
        conn.commit()


def _store_members(conn, edges, level, top, pattern=None, keep_better=False):
    best = {}
    for cat, (sub, d) in level.items():
        for child, kind in edges.get(cat, []):
            if kind != 'page' or (pattern and not pattern.search(child)):
                continue
            if child not in best or d < best[child][1]:
                best[child] = (sub, d)
    if keep_better:                  # a title already placed keeps its place
        have = {r[0] for r in conn.execute(
            'SELECT title FROM cat_members WHERE top = ?', (top,))}
        best = {t: v for t, v in best.items() if t not in have}
    conn.executemany('INSERT OR REPLACE INTO cat_members VALUES (?,?,?,?)',
                     [(top, t, s, d) for t, (s, d) in best.items()])
    print(f'    {top:<38} {len(best):6d} articles in {len(level)} categories')


def add_search_hits(conn, force=False):
    """Articles found by title that no category walk reached."""
    with ug_utils.stage(conn, SCRIPT, 'add_search_hits', force) as st:
        if st.skip:
            return
        known = {r[0] for r in conn.execute(
            'SELECT DISTINCT title FROM cat_members WHERE top != ?',
            (UNCATEGORISED,))}
        conn.execute('DELETE FROM cat_members WHERE top = ?', (FOUND,))
        rows = {}
        for title, query in conn.execute(
                'SELECT title, query FROM search_hits'):
            if title not in known and title not in rows:
                rows[title] = (FOUND, title, query, 0)
        conn.executemany('INSERT OR IGNORE INTO cat_members VALUES (?,?,?,?)',
                         list(rows.values()))
        conn.commit()
        print(f'    {len(rows)} articles found only by their title')


# Topic searches for the areas the client listed. Wikipedia files things
# unevenly: there is no category of Ugandan Acts, and the 2026 election is
# spread across titles. A full-text search for the topic plus the country finds
# the articles a category walk cannot, and every hit still has to pass the
# relevance test, so a search that over-reaches costs time, not accuracy.
TASK_QUERIES = {
    'G1': ('Uganda ministry', 'Uganda government agency', 'Uganda authority act',
           'Uganda commission government'),
    'G2': ('Uganda court judgment', 'Uganda constitutional court',
           'Uganda High Court', 'Uganda Supreme Court ruling'),
    'G3': ('Uganda local government', 'Uganda district chairperson',
           'Uganda city council', 'Uganda municipality town council'),
    'G4': ('Uganda "Act, 2" parliament', 'Uganda Act of Parliament',
           'Uganda Constitution amendment', 'Uganda law bill signed'),
    'P1': ('"2026 Ugandan general election"', 'Uganda 2026 general election',
           'Uganda 2021 general election', 'Uganda election candidate'),
    'P2': ('Member of Parliament Uganda', 'Uganda woman representative MP',
           'Uganda constituency Member of Parliament'),
    'P3': ('Uganda political party', 'Uganda opposition party',
           'National Unity Platform', 'Forum for Democratic Change'),
    'E1': ('Uganda company headquartered Kampala', 'Uganda bank limited',
           'Uganda Securities Exchange listed'),
    'E2': ('Uganda oil pipeline', 'East African Crude Oil Pipeline',
           'Uganda Tilenga Kingfisher oil', 'Uganda Lake Albert oil',
           'Uganda refinery Hoima'),
    'E3': ('Uganda coffee export', 'Uganda agriculture farmers',
           'Uganda fisheries', 'Uganda trade exports'),
    'E4': ('Uganda mobile money', 'Uganda internet provider',
           'Uganda fintech startup', 'Uganda digital economy',
           'Uganda telecommunications MTN Airtel'),
    'ED1': ('university in Uganda', 'Uganda college campus university'),
    'ED2': ('secondary school in Uganda', 'Uganda school Kampala boarding'),
    'ED3': ('Uganda vocational training', 'Uganda technical institute',
            'Uganda education policy', 'Uganda universal primary education'),
    'SO1': ('ethnic group Uganda', 'language spoken in Uganda',
            'Bantu people Uganda', 'Nilotic people Uganda'),
    'SO2': ('Ugandan musician', 'Ugandan film', 'Ugandan author novel',
            'Ugandan artist', 'Ugandan fashion designer'),
    'SO3': ('Uganda newspaper', 'Uganda radio station', 'Uganda television',
            'Ugandan journalist'),
    'SO4': ('Uganda church diocese', 'Uganda mosque', 'Uganda kingdom cultural',
            'Buganda kingdom'),
    'B1': ('Uganda heritage site', 'Uganda historic monument',
           'Uganda museum'),
    'B2': ('Uganda road highway', 'Uganda railway', 'Uganda dam bridge',
           'Uganda airport'),
    'B3': ('AFCON 2027 Uganda', '2027 Africa Cup of Nations',
           'Uganda stadium', 'Mandela National Stadium Namboole'),
    'B4': ('Uganda cathedral', 'Uganda mosque building', 'Kampala landmark',
           'Kampala skyscraper hotel'),
    'EN1': ('Uganda national park', 'Uganda forest reserve',
            'Uganda wildlife reserve'),
    'EN2': ('species found in Uganda', 'endemic to Uganda',
            'Uganda butterfly moth', 'Uganda bird species'),
    'EN3': ('Uganda landslide', 'Uganda floods', 'Uganda drought',
            'Uganda climate change', 'Uganda disaster'),
    'H1': ('hospital in Uganda', 'Uganda health centre'),
    'H2': ('Uganda Ebola outbreak', 'Uganda HIV AIDS', 'Uganda malaria',
           'Uganda COVID-19', 'Uganda epidemic'),
    'H3': ('Uganda maternal health', 'Uganda family planning',
           'Uganda reproductive health women', 'Uganda obstetric fistula'),
    'H4': ('Ugandan physician', 'Ugandan doctor surgeon', 'Ugandan nurse'),
    'HI1': ('history of Uganda', 'Uganda Protectorate colonial',
            'Ugandan Bush War', 'Idi Amin regime'),
    'HI3': ('Uganda battle', 'Uganda massacre', 'Uganda archaeological site',
            'Buganda history'),
    'SP1': ('Ugandan footballer', 'Uganda cricket', 'Uganda athlete',
            'Uganda national football team', 'Uganda Premier League'),
    'UP1': ('Ugandan politician', 'Ugandan businessperson', 'Ugandan activist',
            'Ugandan scientist', 'Ugandan lawyer'),
}


def discover_topics(conn, force=False):
    """Full-text topic searches, one page of results each."""
    with ug_utils.stage(conn, SCRIPT, 'discover_topics', force) as st:
        if st.skip:
            return
        conn.execute("""CREATE TABLE IF NOT EXISTS search_hits (
            title text, query text, PRIMARY KEY (title, query))""")
        total = 0
        for code, queries in TASK_QUERIES.items():
            for query in queries:
                hits = _search(query, 0, limit=500)
                conn.executemany(
                    'INSERT OR IGNORE INTO search_hits VALUES (?,?)',
                    [(t, f'task:{code}') for t in hits])
                total += len(hits)
            conn.commit()
        print(f'    {total} search hits across {len(TASK_QUERIES)} tasks')


def add_uncategorised(conn, force=False):
    """Articles the corpus knows about that the category walk never reached."""
    with ug_utils.stage(conn, SCRIPT, 'add_uncategorised', force) as st:
        if st.skip:
            return
        known = {r[0] for r in conn.execute(
            'SELECT DISTINCT title FROM cat_members '
            'WHERE top != ?', (UNCATEGORISED,))}
        conn.execute('DELETE FROM cat_members WHERE top = ?', (UNCATEGORISED,))
        rows = []
        with open(CORPUS_CSV, encoding='utf-8', newline='') as handle:
            for row in csv.DictReader(handle):
                title = (row.get('en_title') or '').strip()
                # Core items only: the non-core half of the corpus is title
                # keyword hits (Finland, the English language) that nothing
                # in Wikidata ties to Uganda.
                if not yn.is_yes(row.get('is_core')):
                    continue
                if title and title not in known:
                    rows.append((UNCATEGORISED, title, '', 0))
        conn.executemany('INSERT OR IGNORE INTO cat_members VALUES (?,?,?,?)',
                         rows)
        conn.commit()
        print(f'    {len(rows)} Uganda articles sit in no category of the tree')


# ---------------------------------------------------------------- details
def _year(value):
    """'+1950-00-00T00:00:00Z' -> 1950, or None."""
    match = re.match(r'[+-]?(\d{1,4})', value or '')
    return int(match.group(1)) if match else None


def describe(conn, force=False):
    """Quality, references, stub, lead image, Wikidata facts, one batch at a time."""
    with ug_utils.stage(conn, SCRIPT, 'describe', force) as st:
        if st.skip:
            return
        conn.execute("""INSERT OR IGNORE INTO cat_articles (title)
            SELECT DISTINCT title FROM cat_members""")
        conn.commit()
        todo = [r[0] for r in conn.execute(
            'SELECT title FROM cat_articles WHERE described = 0')]
        print(f'    {len(todo)} articles to describe')
        for i in range(0, len(todo), BATCH):
            batch = todo[i:i + BATCH]
            payload = wikiapi._api(EN_API, {
                'action': 'query', 'titles': '|'.join(batch),
                'prop': 'pageassessments|pageimages|pageprops|revisions',
                'rvprop': 'content', 'rvslots': 'main', 'pasubprojects': 1,
                'piprop': 'name', 'redirects': 1})
            q = payload.get('query', {})
            norm = {n['from']: n['to'] for n in q.get('normalized', [])}
            redir = {n['from']: n['to'] for n in q.get('redirects', [])}
            pages = {p['title']: p for p in q.get('pages', [])}
            for title in batch:
                resolved = redir.get(norm.get(title, title),
                                     norm.get(title, title))
                page = pages.get(resolved)
                if not page or 'missing' in page:
                    conn.execute('UPDATE cat_articles SET described = -1 '
                                 'WHERE title = ?', (title,))
                    continue
                classes = [v.get('class') for v in
                           (page.get('pageassessments') or {}).values()
                           if v.get('class')]
                text = ''
                for rev in page.get('revisions', []):
                    text = (rev.get('slots', {}).get('main', {})
                            .get('content') or '')
                size = len(text.encode())
                quality, source = wikiapi._quality(classes, size)
                refs = len(re.findall(r'<ref\b', text, re.I))
                refs += len(re.findall(r'\{\{\s*(cite|sfn)\b', text, re.I))
                tags = [n for n, pat in wikiapi.MAINTENANCE if pat.search(text)]
                stub = 1 if (quality == 'Stub' or
                             'stub template' in tags) else 0
                conn.execute("""UPDATE cat_articles SET qid=?, bytes=?,
                    quality=?, quality_source=?, refs=?, stub=?, tags=?,
                    has_image=?, is_list=?, described=1 WHERE title=?""", (
                    (page.get('pageprops') or {}).get('wikibase_item', ''),
                    size, quality, source, refs, stub, ','.join(tags),
                    1 if page.get('pageimage') else 0,
                    1 if re.match(r'(List|Lists|Outline|Index) of', title)
                    else 0, title))
            conn.commit()
            tick(min(i + BATCH, len(todo)), len(todo), 'reading articles')
            if (i // BATCH) % 20 == 0:
                print(f'    {min(i + BATCH, len(todo))}/{len(todo)}')
            time.sleep(wikiapi.PAUSE)


def wikidata_facts(conn, force=False):
    """Luganda sitelink, class, gender, life dates and the Commons category."""
    with ug_utils.stage(conn, SCRIPT, 'wikidata_facts', force) as st:
        if st.skip:
            return
        qids = [r[0] for r in conn.execute(
            "SELECT DISTINCT qid FROM cat_articles "
            "WHERE qid != '' AND instance_of IS NULL "
            "AND title IN (SELECT title FROM cat_wanted)")]
        print(f'    {len(qids)} Wikidata items')

        def claim_ids(claims, prop):
            out = []
            for c in claims.get(prop, []):
                try:
                    out.append(c['mainsnak']['datavalue']['value']['id'])
                except (KeyError, TypeError):
                    pass
            return out

        def claim_year(claims, prop):
            for c in claims.get(prop, []):
                try:
                    return _year(c['mainsnak']['datavalue']['value']['time'])
                except (KeyError, TypeError):
                    pass
            return None

        for i in range(0, len(qids), BATCH):
            batch = qids[i:i + BATCH]
            payload = wikiapi._api(WD_API, {
                'action': 'wbgetentities', 'ids': '|'.join(batch),
                'props': 'sitelinks|claims'})
            for qid, entity in (payload.get('entities') or {}).items():
                links = entity.get('sitelinks') or {}
                claims = entity.get('claims') or {}
                kinds = claim_ids(claims, 'P31')
                human = 1 if HUMAN in kinds else 0
                sex = claim_ids(claims, 'P21')
                gender = ''
                if human:
                    gender = ('female' if FEMALE in sex else
                              'male' if MALE in sex else
                              'other / unrecorded')
                born, died = claim_year(claims, 'P569'), claim_year(claims, 'P570')
                if not human:
                    life = ''
                elif died is not None:
                    life = 'deceased'
                elif born is not None and born >= 1906:
                    life = 'living'
                else:
                    life = 'unknown'
                commons = ''
                for c in claims.get('P373', []):
                    try:
                        commons = c['mainsnak']['datavalue']['value']
                    except (KeyError, TypeError):
                        pass
                conn.execute("""UPDATE cat_articles SET lg_title=?,
                    instance_of=?, is_human=?, gender=?, born=?, died=?,
                    life_status=?, commons_cat=? WHERE qid=?""", (
                    links.get('lgwiki', {}).get('title', ''), ','.join(kinds),
                    human, gender, born, died, life, commons, qid))
            conn.commit()
            tick(min(i + BATCH, len(qids)), len(qids), 'Wikidata items')
            time.sleep(wikiapi.PAUSE)
        # An article with no Wikidata item still needs to leave the queue.
        conn.execute("UPDATE cat_articles SET instance_of = '' "
                     "WHERE instance_of IS NULL AND title IN "
                     "(SELECT title FROM cat_wanted)")
        conn.commit()


def commons_files(conn, force=False):
    """File counts for each article's Commons category (direct files only)."""
    with ug_utils.stage(conn, SCRIPT, 'commons_files', force) as st:
        if st.skip:
            return
        cats = sorted({r[0] for r in conn.execute(
            "SELECT DISTINCT commons_cat FROM cat_articles "
            "WHERE commons_cat != '' AND commons_files IS NULL")})
        print(f'    {len(cats)} Commons categories')
        for i in range(0, len(cats), BATCH):
            batch = cats[i:i + BATCH]
            payload = wikiapi._api(COMMONS_API, {
                'action': 'query', 'prop': 'categoryinfo',
                'titles': '|'.join('Category:' + c for c in batch)})
            q = payload.get('query', {})
            norm = {n['from']: n['to'] for n in q.get('normalized', [])}
            pages = {p['title']: p for p in q.get('pages', [])}
            for c in batch:
                key = 'Category:' + c
                page = pages.get(norm.get(key, key)) or {}
                files = (page.get('categoryinfo') or {}).get('files', 0)
                conn.execute('UPDATE cat_articles SET commons_files = ? '
                             'WHERE commons_cat = ?', (files, c))
            conn.commit()
            tick(min(i + BATCH, len(cats)), len(cats), 'Commons categories')
            time.sleep(wikiapi.PAUSE)
        conn.execute("UPDATE cat_articles SET commons_files = 0 "
                     "WHERE commons_files IS NULL")
        conn.commit()


# ------------------------------------------------- history and readership
def _created(title):
    try:
        payload = wikiapi._api(EN_API, {
            'action': 'query', 'titles': title, 'prop': 'revisions',
            'rvprop': 'timestamp', 'rvdir': 'newer', 'rvlimit': 1,
            'redirects': 1})
        for page in payload.get('query', {}).get('pages', []):
            for rev in page.get('revisions', []):
                return rev.get('timestamp', '')[:10]
    except Exception:                                  # noqa: BLE001
        pass
    return ''


def _yearly(project, title):
    """Views per calendar year since July 2015, as {year: views}."""
    pv_end, last_year = pv_window()
    url = PV.format(project=project, end=pv_end,
                    title=title.replace(' ', '_').replace('/', '%2F')
                    .replace('?', '%3F'))
    session = ug_utils.get_session()
    for attempt in range(4):
        try:
            r = session.get(url, timeout=45)
            if r.status_code == 404:
                return {}
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            out = {}
            for item in r.json().get('items', []):
                stamp = item['timestamp']
                out[stamp[:4]] = out.get(stamp[:4], 0) + item.get('views', 0)
                # The twelve months a reader cares about, kept separately.
                month = f'{stamp[:4]}-{stamp[4:6]}'
                if last_year[0] <= month <= last_year[1]:
                    out['last12'] = out.get('last12', 0) + item.get('views', 0)
            return out
        except Exception:                              # noqa: BLE001
            time.sleep(2 * (attempt + 1))
    return None


def history(conn, force=False):
    """First-edit date: the year each article was created."""
    with ug_utils.stage(conn, SCRIPT, 'history', force) as st:
        if st.skip:
            return
        todo = [r[0] for r in conn.execute(
            'SELECT title FROM cat_articles WHERE described = 1 '
            'AND created IS NULL AND title IN (SELECT title FROM '
            'cat_wanted)')]
        print(f'    {len(todo)} articles to date')
        with ThreadPoolExecutor(WORKERS) as pool:
            for n, (title, created) in enumerate(
                    zip(todo, pool.map(_created, todo)), 1):
                conn.execute('UPDATE cat_articles SET created = ? '
                             'WHERE title = ?', (created or '', title))
                tick(n, len(todo), title)
                if n % 250 == 0:
                    conn.commit()
                    print(f'    {n}/{len(todo)}')
        conn.commit()


def readership(conn, force=False):
    """English views per year for every article, Luganda views where one exists."""
    with ug_utils.stage(conn, SCRIPT, 'readership', force) as st:
        if st.skip:
            return
        todo = [r[0] for r in conn.execute(
            'SELECT title FROM cat_articles WHERE described = 1 '
            'AND views_en IS NULL AND title IN (SELECT title FROM '
            'cat_wanted)')]
        print(f'    {len(todo)} articles to measure (English)')
        with ThreadPoolExecutor(WORKERS) as pool:
            for n, (title, views) in enumerate(
                    zip(todo, pool.map(
                        lambda t: _yearly('en.wikipedia', t), todo)), 1):
                if views is None:
                    continue              # transient failure: left for re-run
                conn.execute('UPDATE cat_articles SET views_en = ? '
                             'WHERE title = ?', (json.dumps(views), title))
                tick(n, len(todo), title)
                if n % 250 == 0:
                    conn.commit()
                    print(f'    {n}/{len(todo)}')
        conn.commit()

        lg = [r[0] for r in conn.execute(
            "SELECT lg_title FROM cat_articles WHERE lg_title != '' "
            'AND views_lg IS NULL AND title IN (SELECT title FROM '
            'cat_wanted)')]
        print(f'    {len(lg)} Luganda articles to measure')
        with ThreadPoolExecutor(WORKERS) as pool:
            for n, (title, views) in enumerate(
                    zip(lg, pool.map(
                        lambda t: _yearly('lg.wikipedia', t), lg)), 1):
                if views is None:
                    continue
                conn.execute('UPDATE cat_articles SET views_lg = ? '
                             'WHERE lg_title = ?', (json.dumps(views), title))
                tick(n, len(lg), title)
                if n % 250 == 0:
                    conn.commit()
        conn.commit()
        meta_set(conn, 'views_through', pv_window()[0][:6])


# ---------------------------------------------------------------- relevance
WD_EVIDENCE = """
SELECT ?item ?why WHERE {
  VALUES ?item { {values} }
  { ?item wdt:P17 wd:Q1036 . BIND("country" AS ?why) }
  UNION { ?item wdt:P27 wd:Q1036 . BIND("citizenship" AS ?why) }
  UNION { ?item wdt:P495 wd:Q1036 . BIND("origin" AS ?why) }
  UNION { ?item wdt:P1001 wd:Q1036 . BIND("jurisdiction" AS ?why) }
  UNION { ?item wdt:P131+ wd:Q1036 . BIND("located in" AS ?why) }
  UNION { ?item wdt:P19 ?born . ?born wdt:P17 wd:Q1036 .
          BIND("born in Uganda" AS ?why) }
  UNION { ?item wdt:P20 ?died . ?died wdt:P17 wd:Q1036 .
          BIND("died in Uganda" AS ?why) }
}
"""


def relevance_leads(conn, force=False):
    """Is each article about Uganda? Two independent tests, kept separately.

    The category tree is wider than Uganda: it files Barack Obama under
    Ugandan descent, Tanzania under a holiday Uganda observes and Casino Royale
    under films shot there. Membership of a category cannot tell those from
    the real thing, so each article is tested on its own:

      lead   the first paragraph says Uganda, Ugandan, Kampala or another
             Ugandan name. An article about Uganda says so in its opening.
      wikidata  the item's country, citizenship, origin or location chain
             reaches Uganda, or the person was born or died there.

    Either is evidence. Neither is proof, which is why both are stored and the
    reason travels into the export.
    """
    with ug_utils.stage(conn, SCRIPT, 'relevance_leads', force) as st:
        if st.skip:
            return
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cat_relevance (
                title text PRIMARY KEY, lead_hits integer,
                wd_evidence text, wd_checked integer DEFAULT 0,
                lead_first integer);
        """)
        if 'lead_first' not in [r[1] for r in conn.execute(
                'PRAGMA table_info(cat_relevance)')]:
            conn.execute('ALTER TABLE cat_relevance ADD COLUMN '
                         'lead_first integer')
        conn.execute("""INSERT OR IGNORE INTO cat_relevance (title, lead_hits)
            SELECT title, NULL FROM cat_articles WHERE described = 1""")
        conn.commit()

        todo = [r[0] for r in conn.execute(
            'SELECT title FROM cat_relevance WHERE lead_hits IS NULL '
            'OR lead_first IS NULL')]
        print(f'    {len(todo)} leads to read')
        for i in range(0, len(todo), 20):
            batch = todo[i:i + 20]
            payload = wikiapi._api(EN_API, {
                'action': 'query', 'titles': '|'.join(batch),
                'prop': 'extracts', 'exintro': 1, 'explaintext': 1,
                'exlimit': 20, 'redirects': 1})
            q = payload.get('query', {})
            norm = {n['from']: n['to'] for n in q.get('normalized', [])}
            redir = {n['from']: n['to'] for n in q.get('redirects', [])}
            text = {p['title']: p.get('extract', '') or ''
                    for p in q.get('pages', [])}
            for title in batch:
                resolved = redir.get(norm.get(title, title),
                                     norm.get(title, title))
                lead = text.get(resolved, '')
                hits = len(LEAD_WORDS.findall(lead))
                first = len(LEAD_WORDS.findall(lead[:LEAD_OPENING]))
                conn.execute('UPDATE cat_relevance SET lead_hits = ?, '
                             'lead_first = ? WHERE title = ?',
                             (hits, first, title))
            tick(min(i + 20, len(todo)), len(todo), 'reading opening sentences')
            if (i // 20) % 25 == 0:
                conn.commit()
                print(f'    {min(i + 20, len(todo))}/{len(todo)}')
            time.sleep(wikiapi.PAUSE)
        conn.commit()

        # The articles worth the expensive stages: everything the category
        # walk or the corpus found, and whatever a search found that passes
        # the lead test. A full-text search for "Uganda" returns thousands of
        # pages that merely mention it; dating and measuring those would take
        # hours to throw them away.
        conn.execute('DROP TABLE IF EXISTS cat_wanted')
        conn.execute("""CREATE TABLE cat_wanted AS
            SELECT DISTINCT title FROM cat_members WHERE top != ?
            UNION
            SELECT title FROM cat_relevance
            WHERE lead_first > 0 OR lead_hits >= ?""", (FOUND, LEAD_REPEATS))
        conn.commit()
        n = conn.execute('SELECT COUNT(*) FROM cat_wanted').fetchone()[0]
        print(f'    {n} articles go on to measurement')


COUNTRY_COUNT = """
SELECT ?item (COUNT(DISTINCT ?c) AS ?n) WHERE {
  VALUES ?item { {values} }
  ?item wdt:P17 ?c .
} GROUP BY ?item
"""


def country_counts(conn):
    """How many countries Wikidata lists for each item that cites Uganda as one.

    "Country: Uganda" proves little when the item lists a hundred: the English
    language, the Equator and the Nile all do. The count lets the relevance
    test accept Lake Victoria (three countries) and refuse the Equator.
    """
    cols = [r[1] for r in conn.execute('PRAGMA table_info(cat_relevance)')]
    if 'wd_countries' not in cols:
        conn.execute('ALTER TABLE cat_relevance ADD COLUMN wd_countries '
                     'integer')
    rows = conn.execute("""SELECT r.title, a.qid FROM cat_relevance r
        JOIN cat_articles a USING (title)
        WHERE r.wd_evidence LIKE '%country%' AND r.wd_countries IS NULL
          AND a.qid != ''""").fetchall()
    by_qid = {}
    for title, qid in rows:
        by_qid.setdefault(qid, []).append(title)
    print(f'    {len(by_qid)} items cite Uganda as their country; counting '
          f'the countries each lists')
    if not by_qid:
        return
    found = {}
    for b in ug_utils.run_sparql_chunked(COUNTRY_COUNT, list(by_qid),
                                         chunk_size=100, label='countries'):
        qid = ug_utils.qid_from_uri(ug_utils.binding_value(b, 'item', ''))
        found[qid] = int(float(ug_utils.binding_value(b, 'n', '1')))
    for qid, titles in by_qid.items():
        conn.executemany(
            'UPDATE cat_relevance SET wd_countries = ? WHERE title = ?',
            [(found.get(qid, 1), t) for t in titles])
    conn.commit()


def relevance_evidence(conn, force=False):
    """The Wikidata half of the relevance test, for the wanted articles."""
    with ug_utils.stage(conn, SCRIPT, 'relevance_evidence', force) as st:
        if st.skip:
            return

        rows = conn.execute("""SELECT r.title, a.qid FROM cat_relevance r
            JOIN cat_articles a USING (title)
            WHERE r.wd_checked = 0 AND a.qid != ''
              AND r.title IN (SELECT title FROM cat_wanted)""").fetchall()
        by_qid = {}
        for title, qid in rows:
            by_qid.setdefault(qid, []).append(title)
        print(f'    {len(by_qid)} Wikidata items to test')
        found = {}
        bindings = ug_utils.run_sparql_chunked(
            WD_EVIDENCE, list(by_qid), label='evidence')
        for b in bindings:
            qid = ug_utils.qid_from_uri(ug_utils.binding_value(b, 'item', ''))
            found.setdefault(qid, set()).add(ug_utils.binding_value(b, 'why'))
        for qid, titles in by_qid.items():
            why = '; '.join(sorted(found.get(qid, ())))
            conn.executemany(
                'UPDATE cat_relevance SET wd_evidence = ?, wd_checked = 1 '
                'WHERE title = ?', [(why, t) for t in titles])
        # An article with no item has nothing to test.
        conn.execute("""UPDATE cat_relevance SET wd_evidence = '',
            wd_checked = 1 WHERE wd_checked = 0
              AND title IN (SELECT title FROM cat_wanted)""")
        conn.commit()
        country_counts(conn)


def main(force=False):
    tops, names = load_tree()
    conn = ug_utils.connect()
    _schema(conn)
    discover(conn, names, force)
    discover_topics(conn, force)
    crawl(conn, names, tops, force)
    add_search_hits(conn, force)
    add_uncategorised(conn, force)
    describe(conn, force)
    relevance_leads(conn, force)
    wikidata_facts(conn, force)
    commons_files(conn, force)
    history(conn, force)
    readership(conn, force)
    relevance_evidence(conn, force)
    conn.close()


if __name__ == '__main__':
    import sys
    main(force='--force' in sys.argv)
