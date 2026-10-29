# -*- coding: utf-8 -*-
"""One analysis dashboard for each Wikimedia project, on Uganda.

The analytics done on English Wikipedia, for each other project's pages that
are about Uganda: how many, how big, how much read, how they have grown, who has
edited them, what is missing and what is in Luganda. Each project gets its own
workbook, once for Excel and once for Google Sheets, in the same style as the
Wikipedia dashboard. Commons and Wikidata, which hold files and items rather
than pages, get dashboards built for what they hold.

    python src_viz/build_project_dashboards.py                 # Excel
    DASH_TARGET=sheets python src_viz/build_project_dashboards.py   # Sheets
"""

import json
import os
import sys

import pandas as pd
import xlsxwriter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src_data'))

import build_category_files as bcf                   # noqa: E402
import build_dashboard_excel as dash                 # noqa: E402
import build_projects_dashboard as bp                # noqa: E402
import config                                        # noqa: E402
import projects_data as pdata                        # noqa: E402
import projects_history as ph                        # noqa: E402
import sheet_tidy                                    # noqa: E402
import yn                                           # noqa: E402

SHEETS = dash.SHEETS
BLUE, RED, GREEN, GREY, PAPER = (dash.BLUE, dash.RED, dash.GREEN, dash.GREY,
                                 dash.PAPER)
OUT_DIR = os.path.join(config.PROJECT_PATH, 'project_dashboards')
SUFFIX = '(Google Sheets)' if SHEETS else '(Excel)'
SIZE_CLASSES = [('Stub, under 1,000 bytes', 0, 1000),
                ('Short, 1,000 to 4,999', 1000, 5000),
                ('Medium, 5,000 to 19,999', 5000, 20000),
                ('Long, 20,000 and over', 20000, 10 ** 12)]
LITTLE = 100              # read fewer times than this since July 2015
TABS = ['Dashboard', 'Growth', 'Data', 'Most read', 'Needs work', 'People']


def load_host(conn, host):
    pg = pd.read_sql('SELECT * FROM proj_pages WHERE host = ?', conn,
                     params=(host,))
    info = pd.read_sql('SELECT * FROM proj_pageinfo WHERE host = ?', conn,
                       params=(host,))
    vw = pd.read_sql('SELECT title, views_all, views_json FROM proj_views '
                     'WHERE host = ?', conn, params=(host,))
    ed = pd.read_sql('SELECT title, SUM(edits) edits FROM rev_edits WHERE wiki '
                     '= ? GROUP BY title', conn, params=(host,))
    first = pd.read_sql('SELECT title, first_ts FROM rev_done WHERE wiki = ?',
                        conn, params=(host,))
    by_year = pd.read_sql('SELECT title, year, edits FROM rev_edits WHERE wiki '
                          '= ?', conn, params=(host,))
    ey = by_year.pivot_table(index='title', columns='year', values='edits',
                             aggfunc='sum').fillna(0).astype(int)
    ey.columns = [f'edits_{int(c)}' for c in ey.columns]
    df = pg.merge(info.drop(columns='host'), on='title', how='left') \
        .merge(vw, on='title', how='left').merge(ed, on='title', how='left') \
        .merge(first, on='title', how='left')
    df = df.merge(ey, left_on='title', right_index=True, how='left')
    df['qid'] = df['qid'].fillna('')
    df['gender'] = df['gender'].fillna('')
    for col in ('lg', 'sw', 'human'):
        df[col] = df[col].fillna(0).astype(int)
    df['views_all'] = df['views_all'].fillna(-1)
    df['edits'] = df['edits'].fillna(0).astype(int)
    df['created_year'] = pd.to_numeric(
        df['created'].fillna(df['first_ts']).str[:4], errors='coerce')
    df['size'] = df['size'].fillna(0).astype(int)
    df['languages'] = df['languages'].fillna(0).astype(int)
    df['cats'] = df['cats'].fillna('')
    df['n_cats'] = df['cats'].map(lambda c: len([x for x in c.split('|') if x]))
    return df


def yearly(conn, host, df):
    """[year, written, in existence, views|None, edits, editors]."""
    edits = dict(conn.execute('SELECT year, SUM(edits) FROM rev_edits WHERE '
                              'wiki = ? GROUP BY year', (host,)).fetchall())
    users = dict(conn.execute('SELECT year, COUNT(*) FROM rev_users WHERE wiki = '
                              '? AND anon = 0 GROUP BY year', (host,)).fetchall())
    made = df['created_year'].dropna().astype(int).value_counts().to_dict()
    views = {}
    for blob in df['views_json'].dropna():
        for y, n in json.loads(blob).items():
            views[int(y)] = views.get(int(y), 0) + n
    if not made:
        return []
    first, last = min(made), max(max(made), max(views or {0: 0}),
                                 max(edits or {0: 0}))
    rows, cum = [], 0
    for y in range(first, last + 1):
        cum += made.get(y, 0)
        rows.append([y, int(made.get(y, 0)), cum, views.get(y) if y >= 2015
                     else None, int(edits.get(y, 0)), int(users.get(y, 0))])
    return rows


def size_rows(df):
    return [[name, int(((df['size'] >= lo) & (df['size'] < hi)).sum())]
            for name, lo, hi in SIZE_CLASSES]


def host_link(host, title):
    return f'https://{host}/wiki/' + title.replace(' ', '_')


def data_table(df, view_years=None, edit_cols=None):
    """(headings, rows, formats) for the pages in `df`: every column the
    analysis uses, one row per page, most read first. The years of views and
    of edits can be fixed by the caller so that many lists share one layout."""
    if view_years is None:
        view_years = sorted({int(y) for blob in df['views_json'].dropna()
                             for y in json.loads(blob)})
    if edit_cols is None:
        edit_cols = sorted(c for c in df.columns if c.startswith('edits_'))
    heads = (['Page', 'Wikidata item', 'Created', 'Created (year)',
              'Last edited', 'Size (bytes)', 'Words',
              'Total views, all time']
             + [f'Views {y}' for y in view_years]
             + ['Edits, all time'] + [f'Edits {c[6:]}' for c in edit_cols]
             + ['Categories', 'Number of categories',
                'Wikipedia languages with the subject', 'In Luganda Wikipedia',
                'In Swahili Wikipedia', 'A person', 'Gender'])
    rows = []
    for _, r_ in df.sort_values('views_all', ascending=False).iterrows():
        per = json.loads(r_['views_json']) if isinstance(
            r_['views_json'], str) else {}
        rows.append(
            [r_['title'], r_['qid'] or '',
             (r_['created'] if isinstance(r_['created'], str) else '') or '',
             int(r_['created_year']) if r_['created_year'] == r_[
                 'created_year'] else '',
             r_['last_edit'] if isinstance(r_['last_edit'], str) else '',
             int(r_['size']), int(r_['words'] or 0),
             int(r_['views_all']) if r_['views_all'] >= 0 else '']
            + [per.get(str(y), 0) if r_['views_all'] >= 0 else ''
               for y in view_years]
            + [int(r_['edits'])]
            + [int(r_[c]) if c in r_ and r_[c] == r_[c] else 0
               for c in edit_cols]
            + [r_['cats'].replace('|', '; '), int(r_['n_cats']),
               int(r_['languages']), yn.yn_flag(r_['lg'] == 1),
               yn.yn_flag(r_['sw'] == 1),
               yn.yn_flag(r_['human'] == 1),
               yn.na_blank(r_['gender'] if isinstance(
                   r_['gender'], str) else '')])
    after = 9 + len(view_years) + len(edit_cols)       # the Categories column
    fmt = {i: 'int' for i in range(5, after)}
    fmt.update({after + 1: 'int', after + 2: 'int'})
    return heads, rows, fmt


# Dashboards that are not about 'pages that mention Uganda'
SPECIAL = {'incubator.wikimedia.org': {
    'title': 'Runyankore Wikipedia on the Incubator',
    'scope': 'page of the Runyankore Wikipedia test',
    'method': 'Every page in the main namespace of the Incubator whose '
              'title begins Wp/nyn/: the test of a Runyankore '
              'Wikipedia. All of them are kept, whether or not they '
              'mention Uganda.'}}


def build_host(conn, host, label, row_data):
    try:
        df = load_host(conn, host)
    except Exception as error:                          # noqa: BLE001
        print(f'  {label}: not ready ({str(error)[:50]})')
        return None
    if df.empty:
        return None
    hist = yearly(conn, host, df)
    special = SPECIAL.get(host, {})
    name = special.get('title', f'Uganda on {label}')
    path = os.environ.get('PROJ_OUT') or os.path.join(
        OUT_DIR, f'{name} {SUFFIX}.xlsx')
    people = df[df['human'] == 1]
    tabs = [t for t in TABS if t != 'People' or len(people) >= 5]
    wb = xlsxwriter.Workbook(bcf._free(path), {'nan_inf_to_errors': True})
    wb.set_properties({'title': name,
                       'author': 'Wikimedia Community User Group Uganda'})
    B = bp.Book(wb, tabs)
    S = B.S
    first = os.environ.get('DASH_FIRST')          # test hook: render one sheet
    order = ([first] if first in tabs else []) + [t for t in tabs if t != first]
    made = {t: wb.add_worksheet(t) for t in order}
    sh = {t: made[t] for t in tabs}
    for t, colour in (('Dashboard', BLUE), ('Growth', GREEN), ('Data', BLUE),
                      ('Most read', BLUE), ('Needs work', RED),
                      ('People', GREEN)):
        if t in sh:
            sh[t].set_tab_color(colour)
    total = len(df)
    measured = df[df['views_all'] >= 0]
    views_total = int(measured['views_all'].sum())
    never = int((measured['views_all'] == 0).sum())
    has_item = int((df['qid'].fillna('') != '').sum())
    first_year = int(hist[0][0]) if hist else ''

    # ---- Dashboard
    ws = sh['Dashboard']
    B.sheet(ws, name,
            (f'Every {special["scope"]}' if special else
             f'Every page on {label} that mentions Uganda') + ': how many, how big, '
            'how read and how it has grown', 12, {1: 34})
    B.head(ws, 5, 'At a glance')
    B.tiles(ws, 6, [
        ('PAGES MENTIONING UGANDA', total, host),
        ('TOTAL VIEWS, ALL TIME', views_total, 'since July 2015'),
        ('WRITTEN FROM', str(first_year), 'the first page'),
        ('EDITORS, ALL TIME', int(conn.execute(
            'SELECT COUNT(DISTINCT editor) FROM rev_users WHERE wiki = ? AND '
            'anon = 0', (host,)).fetchone()[0]), 'registered accounts'),
        ('WITH A WIKIDATA ITEM', f'{has_item / total:.0%}',
         f'{has_item:,} pages'),
        ('NEVER READ', never, 'no views since July 2015')])
    B.head(ws, 10, 'How big the pages are', 5)
    end = B.table(ws, 11, ['Size class', 'Pages'], size_rows(df), {1: 'int'})
    B.bar(ws, 11, 4, 'Pages', f"='Dashboard'!$B$13:$B${end + 1}",
          f"='Dashboard'!$C$13:$C${end + 1}", 520, 240)
    r = end + 12
    B.head(ws, r, 'How much each page has been read in all', 5)
    v = measured['views_all']
    buckets = [['Never read', int((v == 0).sum())],
               ['1 to 99', int(((v > 0) & (v < 100)).sum())],
               ['100 to 999', int(((v >= 100) & (v < 1000)).sum())],
               ['1,000 to 9,999', int(((v >= 1000) & (v < 10000)).sum())],
               ['10,000 or more', int((v >= 10000).sum())]]
    end = B.table(ws, r + 1, ['Total views', 'Pages'], buckets, {1: 'int'})
    B.bar(ws, r + 1, 4, 'Pages', f"='Dashboard'!$B${r + 3}:$B${end + 1}",
          f"='Dashboard'!$C${r + 3}:$C${end + 1}", 520, 240, GREEN)
    r = end + 12
    B.head(ws, r, 'The ten most read pages, all time', 5)
    top = measured.sort_values('views_all', ascending=False).head(10)
    B.table(ws, r + 1, ['Page', 'Total views', 'Created', 'Size (bytes)'],
            [[t, int(vw), int(c) if c == c else '', int(sz)] for t, vw, c, sz in
             zip(top['title'], top['views_all'], top['created_year'],
                 top['size'])], {1: 'int', 3: 'int'},
            links={0: lambda row: host_link(host, row[0])})
    B.note(ws, r + 14, (special['method'] + ' ' if special else
           'Pages are those the project\'s own search returns for "Uganda", '
           'so some only mention it. ') + 'Views are from July 2015; sizes '
           'are the current size of each page.', 44)

    # ---- Growth
    ws = sh['Growth']
    B.sheet(ws, f'How {name} has grown',
            'Pages written, views, edits and editors, year by year from the '
            'first page', 8, {1: 14})
    B.head(ws, 5, 'Year by year', 7)
    heads = ['Year', 'Pages written', 'Pages in existence', 'Views', 'Edits',
             'Editors']
    rows = [[y, w, c, vw, e, u] for y, w, c, vw, e, u in hist]
    end = B.table(ws, 6, heads, rows,
                  {0: 'text', **{i: 'int' for i in range(1, 6)}})
    last = end + 1
    dash.pair(wb, ws, end + 3, 1,
              [{'name': 'Pages written', 'categories': ['Growth', 7, 1, end, 1],
                'values': ['Growth', 7, 2, end, 2], 'fill': {'color': GREEN},
                'gap': 50}],
              [{'name': 'Pages in existence (right)',
                'categories': ['Growth', 7, 1, end, 1],
                'values': ['Growth', 7, 3, end, 3], 'y2_axis': True,
                'line': {'color': RED, 'width': 2.5}}],
              700, 300, '#,##0', RED)
    dash.pair(wb, ws, end + 20, 1,
              [{'name': 'Views', 'categories': ['Growth', 7, 1, end, 1],
                'values': ['Growth', 7, 4, end, 4], 'fill': {'color': BLUE},
                'gap': 50}],
              [{'name': 'Editors (right)',
                'categories': ['Growth', 7, 1, end, 1],
                'values': ['Growth', 7, 6, end, 6], 'y2_axis': True,
                'line': {'color': GREEN, 'width': 2.5}}],
              700, 300, '#,##0', GREEN)
    B.note(ws, end + 37, 'Pages written, edits and editors come from each '
           'page\'s own edit history, so they reach back to the first page. '
           'Views are recorded only from July 2015. Editors are registered '
           'accounts, counted once a year.', 30, 8)

    # ---- Data: everything the analysis is made from, one row per page
    ws = sh['Data']
    heads, rows, fmt = data_table(df)
    B.sheet(ws, f'All the data behind this dashboard: every page on {label}',
            ('One row per page of the test' if special else
             'One row per page that mentions Uganda') + ', with every column the '
            'analysis uses. Filter or sort any column.', 11,
            {1: 46, 2: 12, 3: 12, 4: 11, 5: 12, 6: 11, 7: 9, 8: 13})
    end = B.table(ws, 5, heads, rows, fmt,
                  links={0: lambda row: host_link(host, row[0]),
                         1: lambda row: 'https://www.wikidata.org/wiki/' + row[1]})
    ws.autofilter(5, 1, end, len(heads))
    ws.freeze_panes(6, 2)

    # ---- Most read
    ws = sh['Most read']
    B.sheet(ws, f'The most read pages on {label}', 'The hundred most read '
            'since July 2015', 6, {1: 50, 2: 14, 3: 12, 4: 12})
    top = measured.sort_values('views_all', ascending=False).head(100)
    B.table(ws, 5, ['Page', 'Total views', 'Created', 'Size (bytes)', 'Edits'],
            [[t, int(vw), int(c) if c == c else '', int(sz), int(e)] for
             t, vw, c, sz, e in zip(top['title'], top['views_all'],
                                    top['created_year'], top['size'],
                                    top['edits'])],
            {1: 'int', 3: 'int', 4: 'int'},
            links={0: lambda row: host_link(host, row[0])})

    # ---- Needs work
    ws = sh['Needs work']
    B.sheet(ws, f'What needs work on {label}', 'The gaps, with the pages to '
            'start on', 8, {1: 50, 2: 14, 3: 12, 4: 12})
    checks = [
        ('Stubs, under 1,000 bytes', df['size'] < 1000, 'Expand'),
        ('Read fewer than 100 times since July 2015',
         (df['views_all'] >= 0) & (df['views_all'] < LITTLE), 'Check they can '
         'be found, or merge'),
        ('Never read', df['views_all'] == 0, 'Link them from somewhere'),
        ('In no category', df['n_cats'] == 0, 'Categorise'),
        ('No Wikidata item', df['qid'].fillna('') == '', 'Connect to Wikidata'),
        ('Only one Wikipedia language has the subject',
         (df['qid'].fillna('') != '') & (df['languages'] <= 1), 'Translate'),
        ('No Luganda article for the subject',
         (df['qid'].fillna('') != '') & (df['lg'] != 1), 'Write in Luganda')]
    B.head(ws, 5, 'The gaps', 4)
    end = B.table(ws, 6, ['Gap', 'Pages', 'Share', 'What to do'],
                  [[n, int(m.sum()), m.mean(), w] for n, m, w in checks],
                  {1: 'int', 2: 'pct'})
    r = end + 3
    B.head(ws, r, 'The most read stubs and short pages', 4)
    short = measured[measured['size'] < 5000].sort_values(
        'views_all', ascending=False).head(60)
    B.table(ws, r + 1, ['Page', 'Total views', 'Size (bytes)', 'Languages'],
            [[t, int(vw), int(sz), int(lg)] for t, vw, sz, lg in zip(
                short['title'], short['views_all'], short['size'],
                short['languages'])], {1: 'int', 2: 'int', 3: 'int'},
            links={0: lambda row: host_link(host, row[0])})

    # ---- People
    if 'People' in sh:
        ws = sh['People']
        B.sheet(ws, f'People with a page on {label}', 'Gender, from Wikidata',
                6, {1: 40, 2: 14})
        g = people['gender'].replace('', 'not recorded').value_counts()
        known = int(people['gender'].isin(['female', 'male']).sum())
        women = int((people['gender'] == 'female').sum())
        B.head(ws, 5, 'Women and men', 4)
        end = B.table(ws, 6, ['Gender', 'People'],
                      [[k, int(v)] for k, v in g.items()], {1: 'int'})
        B.note(ws, end + 2, f'{len(people)} pages are about a person; of '
               f'{known} with a recorded gender, {women} '
               f'({(women / known if known else 0):.0%}) are women.', 30, 6)

    sh[first if first in tabs else 'Dashboard'].activate()
    sheet_tidy.tidy(wb)
    wb.close()
    return path


def build_special(name, tabs, fill):
    """A workbook for Commons or Wikidata, built from the combined
    dashboard's sheets for them."""
    path = os.path.join(OUT_DIR, f'Uganda on {name} {SUFFIX}.xlsx')
    wb = xlsxwriter.Workbook(bcf._free(path), {'nan_inf_to_errors': True})
    wb.set_properties({'title': f'Uganda on {name}',
                       'author': 'Wikimedia Community User Group Uganda'})
    B = bp.Book(wb, tabs)
    sheets = {t: wb.add_worksheet(t) for t in tabs}
    fill(B, sheets)
    for t, colour in (('Commons', GREEN), ('Wikidata', RED), ('Luganda', GREEN),
                      ('Categories data', GREY), ('Files data', GREY),
                      ('Items', GREY), ('Measures', GREY)):
        if t in sheets:
            sheets[t].set_tab_color(colour)
    sheets[tabs[0]].activate()
    sheet_tidy.tidy(wb)
    wb.close()
    return path


def build_commons_wikidata():
    data, commons = bp.load()
    conn = pdata.connect()
    arts = bcf.load(conn)[1]
    conn.close()
    extra = {'commons': pdata.commons(), 'coverage': pdata.coverage(arts),
             'wd': pdata.wikidata_growth(), 'pages': pdata.other_pages()}

    def commons_sheets(B, sh):
        if (extra['commons'] or {}).get('years'):
            bp.sheet_commons_full(B, sh['Commons'], data, extra)
        else:
            bp.sheet_commons(B, sh['Commons'], data, commons)
        bp.sheet_commons_data(B, sh['Categories data'], sh['Files data'])

    def wikidata_sheets(B, sh):
        bp.sheet_wikidata(B, sh['Wikidata'], data, commons)
        bp.wd_growth(B, sh['Wikidata'], extra['wd'], sh['Wikidata'].dim_rowmax + 3)
        bp.sheet_luganda(B, sh['Luganda'], data)
        bp.sheet_wikidata_items(B, sh['Items'], sh['Measures'], data)

    return [build_special('Wikimedia Commons',
                          ['Commons', 'Categories data', 'Files data'],
                          commons_sheets),
            build_special('Wikidata', ['Wikidata', 'Luganda', 'Items',
                                       'Measures'],
                          wikidata_sheets)]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = pdata.connect()
    made = list(build_commons_wikidata())
    for host, label in ph.HOSTS:
        path = build_host(conn, host, label, None)
        if path:
            made.append(path)
            print(f'  {label}: {path}')
    conn.close()
    print(f'{len(made)} dashboards')


if __name__ == '__main__':
    main()
