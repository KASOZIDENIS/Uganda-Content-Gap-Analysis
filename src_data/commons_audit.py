# -*- coding: utf-8 -*-
"""Stage 12: what Wikimedia Commons holds about Uganda.

Deliverable 3 of the WCUGU content gap analysis is a Commons audit, and Commons
is a different kind of archive from the ones the earlier stages read. Wikidata
and Wikipedia are item and article shaped, so a gap there is a missing row. On
Commons the unit is a file, files are organised only by category, and the
category graph is built by hand. That shapes everything below.

Three properties of that graph decide the design:

  it is a graph, not a tree   a category can sit under several parents, and
                              cycles exist, so the crawl keeps a visited set and
                              records the depth at which a category was first
                              reached rather than assuming one path to it

  it is unbounded             `Category:Uganda` reaches the whole of Commons if
                              followed far enough, because some child eventually
                              leads to a continent, a century or a file format.
                              MAX_DEPTH stops the walk, and the count of
                              categories cut off at the limit is reported rather
                              than hidden

  membership is many to many  one file sits in many categories, so files are
                              deduplicated by title and the category recorded is
                              the first one that reached the file, not its only
                              home

What the stage measures, in the terms the scoping document asks for: total files
and categories, the media type distribution behind the "at least 96% photos"
claim, and how much of the collection arrived through the Wiki Loves campaigns.

One honest limit on media type. The authoritative value is `imageinfo.mediatype`,
one API round trip per 50 files, which is tens of thousands of extra requests for
a number that the file extension already answers. The extension is used instead
and `verify_mediatype` samples the real API to measure how often that is wrong,
so the error is reported rather than assumed to be zero.

    python src_data/commons_audit.py
"""

import csv
import os
import re
import time

import config
import ug_utils
import yn

SCRIPT = 'commons_audit'

COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
ROOT = 'Category:Uganda'

# Commons categories reach the rest of the world if followed far enough, and
# measurement shows how fast: from Category:Uganda the walk finds 33 categories
# at depth 1, 390 at depth 2 and 1,689 at depth 3, roughly quadrupling each
# level. Nothing about that curve converges on "Uganda", so a category total
# quoted without the depth that produced it is not a fact about Uganda.
#
# Four is the working limit: WCUGU's own baseline of 1,936 categories falls just
# past depth 3, so this stays at the scale their figure was taken at. export()
# writes the count at every depth so the number is reproducible and the leak
# past the Ugandan tree stays visible.
MAX_DEPTH = 4

PAUSE = 0.05          # courtesy gap between calls
BATCH = 50            # titles per categoryinfo call, the API maximum
PAGE = 500            # members per categorymembers page, the API maximum

CATEGORY_FILE = os.path.join(config.DATA_PATH, 'ug_commons_categories.csv')
MEDIA_FILE = os.path.join(config.DATA_PATH, 'ug_commons_media.csv')
SUMMARY_FILE = os.path.join(config.DATA_PATH, 'ug_commons_summary.csv')

# Extension to Commons media type. The names match what imageinfo returns so the
# two can be compared directly in verify_mediatype().
MEDIA_TYPES = {
    'BITMAP': ('jpg', 'jpeg', 'png', 'gif', 'tif', 'tiff', 'webp', 'xcf'),
    'DRAWING': ('svg',),
    'AUDIO': ('ogg', 'oga', 'wav', 'flac', 'mp3', 'opus', 'mid'),
    'VIDEO': ('ogv', 'webm', 'mpg', 'mpeg', 'mp4', 'mov'),
    'OFFICE': ('pdf', 'djvu'),
    '3D': ('stl',),
}
EXT_TO_TYPE = {ext: kind for kind, exts in MEDIA_TYPES.items() for ext in exts}

# The photographic campaigns the scoping document names, plus the two sister
# campaigns that run in Uganda, matched on the category title.
CAMPAIGNS = (
    ('Wiki Loves Earth', re.compile(r'wiki\s+loves\s+earth', re.I)),
    ('Wiki Loves Monuments', re.compile(r'wiki\s+loves\s+monuments', re.I)),
    ('Wiki Loves Africa', re.compile(r'wiki\s+loves\s+africa', re.I)),
    ('Wiki Loves Folklore', re.compile(r'wiki\s+loves\s+folklore', re.I)),
)

# Thematic buckets for the distribution the scoping document asks for. First
# match wins, so the order is the priority order, and the narrow buckets come
# before the broad ones.
#
# This matches on the category title alone, which is the only text a crawl has.
# It cannot classify a category named for a place or a person, so "Kampala" and
# "Ruwenzori Range" fall to Other however many keywords are added. The size of
# Other is reported on the page rather than disguised.
THEMES = (
    # WCUGU's own programmes, kept apart from the subject themes because they
    # describe who produced a file rather than what it shows.
    ('Wikimedia community',
     re.compile(r'\b(wikimedia|wikied|wikiproject|wiki\s+for|wiki\s+club|'
                r'mentorship|edit[\s-]?a[\s-]?thon|user\s+group)\b', re.I)),
    # Auto-generated indicator charts, which are files about Uganda without
    # being images of it. Worth separating for exactly that reason.
    ('Charts and data',
     re.compile(r'\b(our\s+world\s+in\s+data|graphs?|charts?|statistics|'
                r'diagrams?)\b', re.I)),
    ('People', re.compile(r'\b(people|persons?|women|men|children|politicians?|'
                          r'writers?|musicians?|artists?|footballers?|'
                          r'portraits?|clans?|families)\b', re.I)),
    ('Culture', re.compile(r'\b(culture|cultural|music|dance|art|crafts?|'
                           r'festivals?|celebrations?|religion|churches|'
                           r'mosques|basilica|food|cuisine|clothing|folklore|'
                           r'drums?|graves?|burial)\b', re.I)),
    ('Geography', re.compile(r'\b(geography|districts?|cities|towns|villages|'
                             r'maps|mountains?|ranges?|lakes?|rivers?|'
                             r'islands?|regions?|counties|settlements?|'
                             r'refugee)\b', re.I)),
    ('Environment', re.compile(r'\b(nature|environment|wildlife|birds|flora|'
                               r'fauna|national\s+parks?|forests?|'
                               r'conservation|plants?|animals?|insects?|'
                               r'fruits?|bananas?|crops?|trees?)\b',
                               re.I)),
    ('Sports', re.compile(r'\b(sports?|football|athletics?|cricket|rugby|'
                          r'netball|boxing|olympics?|stadiums?|cup|league|'
                          r'tournaments?|teams?)\b', re.I)),
    ('Buildings', re.compile(r'\b(buildings?|architecture|structures?|'
                             r'monuments?|bridges?|roads?|infrastructure|'
                             r'transport|railways?|airports?|schools?|'
                             r'hospitals?|museums?)\b', re.I)),
    ('History', re.compile(r'\b(history|historical|archives?|heritage|'
                           r'\d{4}s?\sin\suganda)\b', re.I)),
    ('Economy', re.compile(r'\b(economy|economic|business|companies|industry|'
                           r'agriculture|markets?|banks?|mining|tourism)\b',
                           re.I)),
    ('Government', re.compile(r'\b(government|politics|political|elections?|'
                              r'ministr|parliament|military|police|law)\b',
                              re.I)),
    ('Education', re.compile(r'\b(education|universit|colleges?|students?|'
                             r'libraries)\b', re.I)),
    ('Health', re.compile(r'\b(health|medical|hospitals?|disease|medicine|'
                          r'malaria|hiv|aids|covid|pandemics?|epidemics?|'
                          r'famines?|nutrition)\b', re.I)),
)


def _api(params):
    """One Commons API call, with the project's session and User-Agent."""
    session = ug_utils.get_session()
    query = dict(params, format='json', formatversion=2)
    for attempt in range(4):
        try:
            response = session.get(COMMONS_API, params=query, timeout=60)
            response.raise_for_status()
            payload = response.json()
            if 'error' in payload:
                raise RuntimeError(payload['error'].get('info', 'api error'))
            return payload
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def _members(title, kind):
    """Every member of one category, following continuation."""
    out, cont = [], {}
    while True:
        payload = _api(dict({'action': 'query', 'list': 'categorymembers',
                             'cmtitle': title, 'cmtype': kind,
                             'cmlimit': PAGE}, **cont))
        out.extend(payload.get('query', {}).get('categorymembers', []))
        cont = payload.get('continue') or {}
        if not cont:
            return out
        time.sleep(PAUSE)


def theme_of(title):
    """The thematic bucket a category title falls in, or 'Other'."""
    for name, pattern in THEMES:
        if pattern.search(title):
            return name
    return 'Other'


def campaign_of(title):
    """The Wiki Loves campaign a title names, or '' for none."""
    for name, pattern in CAMPAIGNS:
        if pattern.search(title):
            return name
    return ''


def extension_of(title):
    """The lowercase file extension of a File: title, or '' if it has none."""
    base = title.rsplit('.', 1)
    return base[1].lower() if len(base) == 2 and len(base[1]) <= 5 else ''


def crawl_categories(conn, force=False):
    """Walk the category graph from Category:Uganda, breadth first."""
    with ug_utils.stage(conn, SCRIPT, 'crawl_categories', force) as st:
        if st.skip:
            return
        conn.execute('DROP TABLE IF EXISTS commons_categories')
        conn.execute("""CREATE TABLE commons_categories (
            title text PRIMARY KEY, depth integer, parent text,
            files integer, subcats integer, theme text, campaign text,
            truncated integer)""")

        # depth is the shortest path from the root, because the walk is
        # breadth first and a title is only ever claimed once
        seen = {ROOT: (0, '')}
        frontier = [ROOT]
        truncated = set()
        for depth in range(1, MAX_DEPTH + 1):
            nxt = []
            for parent in frontier:
                for member in _members(parent, 'subcat'):
                    title = member['title']
                    if title not in seen:
                        seen[title] = (depth, parent)
                        nxt.append(title)
                time.sleep(PAUSE)
            print(f'    depth {depth}: +{len(nxt)} categories '
                  f'({len(seen)} total)')
            frontier = nxt
            if not frontier:
                break
        else:
            # the loop ran out of depth rather than out of categories
            truncated = set(frontier)
            if truncated:
                print(f'    depth limit {MAX_DEPTH} reached with '
                      f'{len(truncated)} categories still unexplored')

        # file and subcategory counts, fifty titles per call
        titles = list(seen)
        counts = {}
        for i in range(0, len(titles), BATCH):
            batch = titles[i:i + BATCH]
            payload = _api({'action': 'query', 'prop': 'categoryinfo',
                            'titles': '|'.join(batch)})
            for page in payload.get('query', {}).get('pages', []):
                info = page.get('categoryinfo') or {}
                counts[page['title']] = (info.get('files', 0),
                                         info.get('subcats', 0))
            time.sleep(PAUSE)

        rows = []
        for title, (depth, parent) in seen.items():
            files, subcats = counts.get(title, (0, 0))
            rows.append((title, depth, parent, files, subcats,
                         theme_of(title), campaign_of(title),
                         1 if title in truncated else 0))
        conn.executemany('INSERT INTO commons_categories VALUES (?,?,?,?,?,?,?,?)',
                         rows)
        conn.commit()
        print(f'    {len(rows)} categories, '
              f'{sum(r[3] for r in rows)} file memberships')


def crawl_files(conn, force=False):
    """List the files in every category found, deduplicated by title."""
    with ug_utils.stage(conn, SCRIPT, 'crawl_files', force) as st:
        if st.skip:
            return
        conn.execute('DROP TABLE IF EXISTS commons_files')
        conn.execute("""CREATE TABLE commons_files (
            title text PRIMARY KEY, extension text, mediatype text,
            first_category text, theme text, campaign text)""")

        cats = [r[0] for r in conn.execute(
            'SELECT title FROM commons_categories WHERE files > 0 ORDER BY title')]
        files = {}
        for n, cat in enumerate(cats, 1):
            for member in _members(cat, 'file'):
                title = member['title']
                if title not in files:
                    files[title] = cat
            if n % 200 == 0:
                print(f'    {n}/{len(cats)} categories, {len(files)} files')
            time.sleep(PAUSE)

        rows = []
        for title, cat in files.items():
            ext = extension_of(title)
            rows.append((title, ext, EXT_TO_TYPE.get(ext, 'UNKNOWN'), cat,
                         theme_of(cat), campaign_of(cat)))
        conn.executemany('INSERT INTO commons_files VALUES (?,?,?,?,?,?)', rows)
        conn.commit()
        print(f'    {len(rows)} distinct files')


def reclassify(conn, force=False):
    """Recompute themes and campaigns from the titles already stored.

    theme_of() and campaign_of() read nothing but the category title, so
    changing them does not need the crawl again. The walk costs an hour and a
    half; this costs a second, and keeps tuning the classifier from being a
    reason to re-hammer the API.
    """
    with ug_utils.stage(conn, SCRIPT, 'reclassify', force) as st:
        if st.skip:
            return
        cats = conn.execute('SELECT title FROM commons_categories').fetchall()
        conn.executemany('UPDATE commons_categories SET theme = ?, campaign = ? '
                         'WHERE title = ?',
                         [(theme_of(t), campaign_of(t), t) for (t,) in cats])
        files = conn.execute(
            'SELECT DISTINCT first_category FROM commons_files').fetchall()
        conn.executemany('UPDATE commons_files SET theme = ?, campaign = ? '
                         'WHERE first_category = ?',
                         [(theme_of(c), campaign_of(c), c) for (c,) in files])
        conn.commit()
        other = conn.execute("""SELECT COUNT(*) FROM commons_files
                                WHERE theme = 'Other'""").fetchone()[0]
        total = conn.execute('SELECT COUNT(*) FROM commons_files').fetchone()[0]
        print(f'    {len(cats)} categories and {total} files reclassified, '
              f'{other} ({100.0 * other / total:.1f}%) still Other'
              if total else f'    {len(cats)} categories reclassified')


def verify_mediatype(conn, force=False, sample=300):
    """Measure how often the extension disagrees with the real media type.

    The distribution reported by this stage is derived from file extensions.
    That is a heuristic, so this samples the authoritative imageinfo value and
    records the disagreement rate instead of leaving it unstated.
    """
    with ug_utils.stage(conn, SCRIPT, 'verify_mediatype', force) as st:
        if st.skip:
            return
        rows = conn.execute("""SELECT title, mediatype FROM commons_files
                               ORDER BY random() LIMIT ?""", (sample,)).fetchall()
        if not rows:
            print('    no files to sample')
            return
        guessed = dict(rows)
        agree = disagree = unknown = 0
        titles = list(guessed)
        for i in range(0, len(titles), BATCH):
            batch = titles[i:i + BATCH]
            payload = _api({'action': 'query', 'prop': 'imageinfo',
                            'iiprop': 'mediatype', 'titles': '|'.join(batch)})
            for page in payload.get('query', {}).get('pages', []):
                info = (page.get('imageinfo') or [{}])[0]
                actual = info.get('mediatype')
                if not actual:
                    unknown += 1
                elif actual == guessed.get(page['title']):
                    agree += 1
                else:
                    disagree += 1
            time.sleep(PAUSE)
        checked = agree + disagree
        rate = (100.0 * agree / checked) if checked else 0.0
        conn.execute('DROP TABLE IF EXISTS commons_mediatype_check')
        conn.execute("""CREATE TABLE commons_mediatype_check (
            sampled integer, agreed integer, disagreed integer,
            unresolved integer, accuracy real)""")
        conn.execute('INSERT INTO commons_mediatype_check VALUES (?,?,?,?,?)',
                     (len(rows), agree, disagree, unknown, rate))
        conn.commit()
        print(f'    extension matched imageinfo on {agree}/{checked} '
              f'sampled files ({rate:.1f}%)')


def export(conn, force=False):
    """Write the three CSVs behind the Commons audit."""
    with ug_utils.stage(conn, SCRIPT, 'export', force) as st:
        if st.skip:
            return

        def dump(path, header, rows, flags=()):
            rows = yn.flag_rows(rows, flags) if flags else rows
            with open(path, 'w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(header)
                writer.writerows(rows)
            print(f'    -> {os.path.basename(path)} ({len(rows)} rows)')

        dump(CATEGORY_FILE,
             ['title', 'depth', 'parent', 'files', 'subcats', 'theme',
              'campaign', 'truncated'],
             conn.execute("""SELECT title, depth, parent, files, subcats, theme,
                                    campaign, truncated
                             FROM commons_categories
                             ORDER BY files DESC, title""").fetchall(),
             flags=(7,))

        dump(MEDIA_FILE, ['mediatype', 'files', 'share_percent'],
             conn.execute("""SELECT mediatype, count(*),
                                    round(100.0 * count(*) /
                                          (SELECT count(*) FROM commons_files), 2)
                             FROM commons_files
                             GROUP BY mediatype ORDER BY 2 DESC""").fetchall())

        totals = conn.execute("""SELECT
                (SELECT count(*) FROM commons_categories),
                (SELECT count(*) FROM commons_files),
                (SELECT count(*) FROM commons_categories WHERE truncated = 1)
            """).fetchone()
        photos = conn.execute("""SELECT count(*) FROM commons_files
                                 WHERE mediatype = 'BITMAP'""").fetchone()[0]
        check = conn.execute('SELECT accuracy FROM commons_mediatype_check'
                             ).fetchone()
        summary = [
            ('categories', totals[0]),
            ('files', totals[1]),
            ('crawl_depth_limit', MAX_DEPTH),
            ('categories_unexplored_at_depth_limit', totals[2]),
            ('photo_share_percent',
             round(100.0 * photos / totals[1], 2) if totals[1] else 0),
            ('mediatype_accuracy_percent', round(check[0], 1) if check else ''),
        ]
        for name, pattern in CAMPAIGNS:
            n = conn.execute('SELECT count(*) FROM commons_files WHERE campaign = ?',
                             (name,)).fetchone()[0]
            summary.append((f'files_from_{name.lower().replace(" ", "_")}', n))
        for theme, n in conn.execute("""SELECT theme, count(*) FROM commons_files
                                        GROUP BY theme ORDER BY 2 DESC"""):
            summary.append((f'files_theme_{theme.lower()}', n))
        # the count at each depth, so the totals above can be read against the
        # depth that produced them rather than taken as a fact about Uganda
        for depth, n in conn.execute("""SELECT depth, count(*)
                                        FROM commons_categories
                                        GROUP BY depth ORDER BY depth"""):
            summary.append((f'categories_at_depth_{depth}', n))
        dump(SUMMARY_FILE, ['metric', 'value'], summary)


def main(force=False):
    conn = ug_utils.connect()
    crawl_categories(conn, force)
    crawl_files(conn, force)
    reclassify(conn, force)
    verify_mediatype(conn, force)
    export(conn, force)
    conn.close()


if __name__ == '__main__':
    import sys
    main(force='--force' in sys.argv)
