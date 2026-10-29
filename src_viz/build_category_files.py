# -*- coding: utf-8 -*-
"""Write one list of articles (a workbook and a CSV) per Uganda category.

Reads what src_data/category_profiles.py left in the database and writes, to
`category_files/`:

    <category>.xlsx   one sheet, Articles: every article in the category with
                      every column, and no analysis
    <category>.csv    the same list, for your own slicing
    _Index.xlsx       one row per category, plus the de-duplicated totals
    _All_articles.csv every article once, with its primary category

The analysis (quality, readership, people, gaps) is in the dashboard, not in
these files. Views come as a total for all time, which is since July 2015 when
the Pageviews record begins or since the article was written if that is later,
beside the last twelve months and each year.

    python src_viz/build_category_files.py
"""

import csv
import json
import os
import sys

import pandas as pd
import xlsxwriter

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src_data'))

import category_profiles as cp      # noqa: E402
import config                       # noqa: E402
import ug_utils                     # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet_tidy                   # noqa: E402
import structures                   # noqa: E402
import universe                     # noqa: E402
import yn                           # noqa: E402

OUT_DIR = os.path.join(config.PROJECT_PATH, 'category_files')

WIKI = 'https://en.wikipedia.org/wiki/{}'
LG = 'https://lg.wikipedia.org/wiki/{}'
WIKIDATA = 'https://www.wikidata.org/wiki/{}'

# The years the Pageviews API holds, to the last complete month. Worked out
# from the calendar so the columns grow when a new year starts.
_END = cp.pv_window()[0]
_LAST_YEAR, _LAST_MONTH = int(_END[:4]), int(_END[4:6])
_MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep',
           'Oct', 'Nov', 'Dec')
YEARS = [str(y) for y in range(2015, _LAST_YEAR + 1)]
YEAR_LABEL = {'2015': '2015 (Jul-Dec)'}
if _LAST_MONTH < 12:
    YEAR_LABEL[str(_LAST_YEAR)] = (
        f'{_LAST_YEAR} (Jan-{_MONTHS[_LAST_MONTH - 1]})')
QUALITY_ORDER = ['FA', 'FL', 'A', 'GA', 'B', 'C', 'Start', 'Stub', 'Unknown']
LOW_QUALITY = ('Stub', 'Start')

# A "good" article, for the purposes of effort, is a C-class one. These are
# the byte floors that wikiapi._quality uses, so the estimate and the class agree.
TARGET_BYTES = 10000
BYTES_PER_WORD = 6
LITTLE_READ = 100                 # the older pages: under this in twelve months
HIGH_VIEW_PERCENTILE = 0.75

INK, MUTED, BLUE, ORANGE, GREEN = ('#1F2933', '#7B8794', '#2A78D6',
                                   '#EB6834', '#1BAF7A')

PRIMARY_SKIP = ('Uganda stubs', 'Uganda-related lists')
STRUCTURES = 'Buildings and structures in Uganda'


# ------------------------------------------------------------------- data
EXCLUDED = pd.DataFrame()
ANCESTORS = {}
ALL_MEMBERS = pd.DataFrame()


def removed_categories(conn):
    """The removed groups and every category beneath them that no kept group
    reaches, so that they appear nowhere as a category either."""
    edges = {}
    for parent, child, kind in conn.execute(
            'SELECT parent, child, kind FROM cat_edges'):
        edges.setdefault(parent, []).append((child, kind))
    tops, names = cp.load_tree()

    def reach(starts):
        found = cp.reachable(edges, ['Category:' + t for t in starts], names)
        return {c.split(':', 1)[1] for c in found}

    return (reach(cp.REMOVED_TOPS) - reach(tops)) | set(cp.REMOVED_TOPS)


def load(conn):
    """Every article about Uganda, measured. What fails the relevance test is
    kept in EXCLUDED so it can be shown rather than silently dropped."""
    global EXCLUDED, ANCESTORS, ALL_MEMBERS
    members = pd.read_sql('SELECT * FROM cat_members', conn)
    # Groups taken out of the analysis on request: the group, every article
    # filed beneath it, and the categories only it reached all disappear.
    dropped = set(members.loc[members['top'].isin(cp.REMOVED_TOPS), 'title'])
    members = members[~members['title'].isin(dropped)]
    arts = pd.read_sql("SELECT * FROM cat_articles WHERE described = 1", conn)
    arts = arts[~arts['title'].isin(dropped)]
    # The buildings group holds structures, not the people named in its
    # categories: a person stays only through some other group.
    people = set(arts.loc[arts['is_human'].fillna(0) == 1, 'title'])
    members = members[~((members['top'] == STRUCTURES)
                        & members['title'].isin(people))]
    ALL_MEMBERS = members

    arts = universe.merge_relevance(conn, arts)
    ANCESTORS = universe.ancestors(conn, arts['title'])
    gone = removed_categories(conn)
    ANCESTORS = {t: ([c for c in direct if c not in gone],
                     {c: d for c, d in above.items() if c not in gone})
                 for t, (direct, above) in ANCESTORS.items()}
    arts = universe.judge(arts, ANCESTORS)
    arts['direct_cats'] = arts['title'].map(
        lambda t: '; '.join(ANCESTORS[t][0]))
    # Only real structures stay in the buildings group; films, attacks,
    # parks and dioceses filed there keep the groups that suit them.
    keep = {t: structures.is_structure(t, d) for t, d in
            zip(arts['title'], arts['direct_cats'])}
    members = members[~((members['top'] == STRUCTURES)
                        & ~members['title'].map(keep).fillna(True).astype(bool))]
    ALL_MEMBERS = members
    EXCLUDED = arts[arts['basis'] == ''].copy()
    # An article described on an earlier run and no longer held by any
    # category, corpus or search result of this one is stale, not missing.
    held = set(members['title'])
    arts = arts[(arts['basis'] != '') & arts['title'].isin(held)] \
        .reset_index(drop=True)
    members = members[members['title'].isin(arts['title'])]

    def unpack(column, prefix):
        parsed = arts[column].map(lambda v: json.loads(v) if isinstance(v, str) and v else {})
        for y in YEARS:
            arts[f'{prefix}{y}'] = parsed.map(lambda d, y=y: d.get(y, 0))
        arts[f'{prefix}last12'] = parsed.map(lambda d: d.get('last12', 0))

    unpack('views_en', 'v_')
    unpack('views_lg', 'lg_')
    arts['views_last12'] = arts['v_last12']
    # Every month the Pageviews API holds. It starts in July 2015, so for an
    # article older than that this is its views since then, not since it was
    # written; for every later article it is its whole life.
    arts['views_all_time'] = arts[[f'v_{y}' for y in YEARS]].sum(axis=1)
    arts['lg_all_time'] = arts[[f'lg_{y}' for y in YEARS]].sum(axis=1)
    arts['created_year'] = pd.to_numeric(
        arts['created'].str[:4], errors='coerce')
    arts['has_luganda'] = (arts['lg_title'].fillna('') != '').astype(int)

    # Flags are judged against the whole corpus, not each category, so the
    # same article is flagged the same way in every file it appears in.
    high = arts['views_all_time'].quantile(HIGH_VIEW_PERCENTILE)
    low_q = arts['quality'].isin(LOW_QUALITY)
    arts['high_views_low_quality'] = (
        (arts['views_all_time'] >= high) & low_q).astype(int)

    def action(row):
        if row['is_list']:
            return 'OK'
        if row['quality'] in LOW_QUALITY or row['refs'] == 0:
            return ('Expand, then translate' if not row['has_luganda']
                    else 'Expand')
        if not row['has_luganda']:
            return 'Translate to Luganda'
        return 'OK'

    arts['action'] = arts.apply(action, axis=1)
    gap = (TARGET_BYTES - arts['bytes']).clip(lower=0)
    needs_growth = arts['action'].str.startswith('Expand')
    arts['expansion_gap_bytes'] = gap.where(needs_growth, 0).astype(int)
    arts['effort'] = pd.cut(
        arts['expansion_gap_bytes'], [-1, 0, 3000, 7000, 10 ** 9],
        labels=['', 'Small', 'Medium', 'Large']).astype(str)
    arts['effort'] = arts['effort'].replace('nan', '')

    sizes = members.groupby('top')['title'].count()
    where = members.groupby('title')['top'].agg(list)

    def primary(tops):
        real = [t for t in tops if t not in PRIMARY_SKIP] or tops
        return min(real, key=lambda t: sizes[t])

    arts['primary_category'] = arts['title'].map(where.map(primary))
    built = set(members.loc[members['top'] == STRUCTURES, 'title'])
    arts['structure_type'] = [
        structures.classify(t, d) if t in built else ''
        for t, d in zip(arts['title'], arts['direct_cats'])]
    arts['in_categories'] = arts['title'].map(where)
    return members, arts, high


def category_frame(top, members, arts):
    m = members[members['top'] == top][['title', 'subcat', 'depth']]
    df = m.merge(arts, on='title', how='inner')
    df['also_in'] = df['in_categories'].map(
        lambda tops: '; '.join(t for t in tops if t != top))
    return df.sort_values('views_all_time', ascending=False).reset_index(
        drop=True)


# ----------------------------------------------------------------- columns
ARTICLE_COLUMNS = [
    ('title', 'Article'), ('qid', 'Wikidata'),
    ('basis', 'Why it is about Uganda'), ('subcat', 'Subcategory'),
    ('depth', 'Depth'), ('quality', 'Class'),
    ('quality_source', 'Class from'), ('bytes', 'Size (bytes)'),
    ('refs', 'References'), ('stub', 'Stub'), ('tags', 'Maintenance tags'),
    ('has_image', 'Lead image'), ('has_luganda', 'Luganda article'),
    ('lg_title', 'Luganda title'), ('commons_cat', 'Commons category'),
    ('commons_files', 'Commons files'), ('created_year', 'Created'),
    ('views_all_time', 'Total views, all time'),
    ('views_last12', 'Views, last 12 months'),
    ('lg_all_time', 'Luganda views, all time'),
    ('lg_last12', 'Luganda views, last 12 months')] + [
    (f'v_{y}', f'Views {YEAR_LABEL.get(y, y)}') for y in YEARS] + [
    ('is_human', 'Person'), ('gender', 'Gender'),
    ('life_status', 'Living / deceased'), ('born', 'Born'), ('died', 'Died'),
    ('high_views_low_quality', 'High views, low quality'),
    ('action', 'Action'), ('effort', 'Expansion effort'),
    ('expansion_gap_bytes', 'Bytes to reach C'),
    ('structure_type', 'Building type'),
    ('also_in', 'Also in'), ('direct_cats', 'Wikipedia categories')]

def columns_for(df):
    """The article columns, without 'Building type' where nothing has one."""
    return [(c, h) for c, h in ARTICLE_COLUMNS
            if c != 'structure_type' or df[c].fillna('').ne('').any()]


def csv_frame(df):
    cols = columns_for(df)
    out = df[[c for c, _ in cols]].copy()
    out.columns = [h for _, h in cols]
    return yn.frame(out)


# ------------------------------------------------------------------ writer
def _free(path):
    """The path itself, or a `_NEW` sibling when the file is locked.

    A workbook open in Excel cannot be overwritten. Closing someone's Excel is
    not this script's call, so it writes beside the locked file and says so.
    """
    try:
        open(path, 'ab').close()
        return path
    except PermissionError:
        root, ext = os.path.splitext(path)
        for k in range(1, 50):
            alt = f'{root}_NEW{"" if k == 1 else k}{ext}'
            try:
                open(alt, 'ab').close()
            except PermissionError:
                continue
            print(f'  ! {os.path.basename(path)} is open elsewhere; '
                  f'writing {os.path.basename(alt)} instead')
            return alt
        raise


_to_csv = pd.DataFrame.to_csv


def _safe_to_csv(self, path=None, *args, **kwargs):
    """Every CSV this project writes goes through the same locked-file rule."""
    if isinstance(path, str):
        path = _free(path)
    return _to_csv(self, path, *args, **kwargs)


pd.DataFrame.to_csv = _safe_to_csv


class Book:
    def __init__(self, path):
        self.wb = xlsxwriter.Workbook(_free(path), {'nan_inf_to_errors': True})
        base = {'font_name': 'Calibri', 'font_size': 11}
        grid = dict(base, border=1, border_color='#D5DADF')
        f = self.wb.add_format
        self.f = {
            'title': f(dict(base, font_size=20, bold=True, font_color=INK)),
            'h2': f(dict(base, font_size=14, bold=True, font_color=INK)),
            'sub': f(dict(base, font_color=MUTED, text_wrap=True,
                          valign='top')),
            'kpi': f(dict(base, font_size=22, bold=True, font_color=INK)),
            'kpil': f(dict(base, font_size=10, font_color=MUTED)),
            'head': f(dict(base, bold=True, font_color='#FFFFFF',
                           bg_color=INK, text_wrap=True, valign='vcenter')),
            'cell': f(grid),
            'num': f(dict(grid, num_format='#,##0')),
            'pct': f(dict(grid, num_format='0.0%')),
            'link': f(dict(grid, font_color=BLUE, underline=1)),
            'note': f(dict(base, font_size=10, font_color=MUTED,
                           text_wrap=True, valign='top')),
        }

    def close(self):
        """End the workbook where its data ends, then write it."""
        sheet_tidy.tidy(self.wb)
        self.wb.close()

    def table(self, ws, row, df, headers, link_col=None, widths=None):
        """An Excel table at (row, 0); returns the next free row."""
        n = len(df)
        ws.add_table(row, 0, row + max(n, 1), len(headers) - 1, {
            'columns': [{'header': h, 'header_format': self.f['head']}
                        for h in headers],
            'style': 'Table Style Light 1', 'autofilter': True})
        cols = list(df.columns)
        for r, values in enumerate(df.itertuples(index=False), row + 1):
            for c, value in enumerate(values):
                if pd.isna(value):
                    value = ''
                if c == link_col and value:
                    ws.write_url(r, c, WIKI.format(
                        str(value).replace(' ', '_')), self.f['link'],
                        str(value))
                elif cols[c] == 'qid' and value:
                    ws.write_url(r, c, WIKIDATA.format(value),
                                 self.f['link'], str(value))
                elif isinstance(value, (int, float)):
                    ws.write_number(r, c, value, self.f[
                        'pct' if headers[c] == 'Share' else 'num'])
                else:
                    ws.write(r, c, str(value), self.f['cell'])
        if widths is not None:
            for c, h in enumerate(headers):
                ws.set_column(c, c, widths.get(c, max(11, min(len(h), 30))))
            ws.freeze_panes(row + 1, 1)
        return row + n + 3


# --------------------------------------------------------------- workbook
def write_workbook(top, df, high, path):
    """One sheet: the category's articles, every column, no analysis.

    The analysis (quality, readership, people, gaps) is in the dashboard. A
    category file is a list people can sort, filter and work through, so that
    is all it holds.
    """
    book = Book(path)
    heads = [h for _, h in columns_for(df)]
    cols = [c for c, _ in columns_for(df)]
    widths = {0: 38, 2: 30, 3: 26, 10: 22, 13: 24, 14: 24,
              len(heads) - 1: 40}
    ws = book.wb.add_worksheet('Articles')
    shown = df[cols].copy()
    for c, h in zip(cols, heads):
        if h in yn.FLAG_HEADS:
            shown[c] = shown[c].map(yn.yn)
        elif h in yn.NA_HEADS:
            shown[c] = shown[c].map(yn.na_blank)
    book.table(ws, 0, shown, heads, 0, widths)
    book.close()


def reconcile(members, arts, gone, searched):
    """How the articles in the category tree became the articles about Uganda.

    The walk finds every article in the tree; the relevance test removes what is
    not about Uganda; the Wikidata corpus and the searches add what the tree
    missed. Written to `_Reconciliation.csv`.
    """
    tree = ALL_MEMBERS[ALL_MEMBERS['top'] != cp.FOUND]['title'].nunique()
    about = arts[arts['title'].isin(
        ALL_MEMBERS[ALL_MEMBERS['top'] != cp.FOUND]['title'])]
    rows = [
        ('Distinct articles anywhere in the walked tree', tree,
         'every article in a category the walk reached'),
        ('  of which fail the test for being about Uganda', len(gone),
         'listed in _Excluded_not_about_Uganda.csv'),
        ('  of which are about Uganda', len(about), ''),
        ('Added by the Wikidata corpus and by search', len(arts) - len(about),
         'passed the same tests'),
        ('ARTICLES ABOUT UGANDA, in total', len(arts),
         'the _All_articles file'),
        ('Search results rejected for not being about Uganda', searched,
         'pages that mention Uganda without being about it'),
    ]
    pd.DataFrame(rows, columns=['Measure', 'Value', 'Note']).to_csv(
        os.path.join(OUT_DIR, '_Reconciliation.csv'), index=False,
        encoding='utf-8-sig')
    for r in rows:
        print(f'    {r[0]:<62} {r[1]:>8,}')


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = ug_utils.connect()
    members, arts, high = load(conn)
    conn.close()

    tops, _names = cp.load_tree()
    order = tops + [cp.OTHER, cp.FOUND, cp.UNCATEGORISED]
    index = []
    for top in order:
        df = category_frame(top, members, arts)
        if df.empty:
            print(f'  {top}: nothing found, skipped')
            continue
        name = cp.slug(top)
        csv_frame(df).to_csv(os.path.join(OUT_DIR, name + '.csv'),
                             index=False, encoding='utf-8-sig')
        write_workbook(top, df, high, os.path.join(OUT_DIR, name + '.xlsx'))
        n = len(df)
        people = df[df['is_human'] == 1]
        index.append({
            'Category': top, 'File': name + '.xlsx', 'Articles': n,
            'Not also in another category':
                int((df['also_in'] == '').sum()),
            'Stubs': int(df['stub'].sum()),
            'Total views, all time': int(df['views_all_time'].sum()),
            'With Luganda': int(df['has_luganda'].sum()),
            'Without lead image': int((df['has_image'] == 0).sum()),
            'People': len(people),
            'Women': int((people['gender'] == 'female').sum()),
            'Men': int((people['gender'] == 'male').sum()),
            'Living': int((people['life_status'] == 'living').sum()),
            'Deceased': int((people['life_status'] == 'deceased').sum()),
            'High views, low quality': int(df['high_views_low_quality'].sum()),
        })
        print(f'  {top:<38} {n:6d} articles -> {name}.xlsx')

    idx = pd.DataFrame(index)
    unique = arts[arts['title'].isin(members['title'])]
    unique_in_tree = unique[unique['primary_category'] != cp.UNCATEGORISED]
    print(f'\n  {len(unique)} distinct articles in all files '
          f'({len(unique_in_tree)} categorised, '
          f'{len(unique) - len(unique_in_tree)} uncategorised)')

    arts_out = unique.copy()
    arts_out['in_categories'] = arts_out['in_categories'].map('; '.join)
    csv_cols = [c for c, _ in ARTICLE_COLUMNS
                if c not in ('subcat', 'depth', 'also_in')]
    flat = arts_out[['primary_category', 'in_categories'] + csv_cols]
    flat.columns = (['Primary category', 'In categories']
                    + [h for c, h in ARTICLE_COLUMNS
                       if c not in ('subcat', 'depth', 'also_in')])
    yn.frame(flat.sort_values(['Primary category', 'Total views, all time'],
                              ascending=[True, False])).to_csv(
        os.path.join(OUT_DIR, '_All_articles.csv'), index=False,
        encoding='utf-8-sig')

    # What failed the relevance test, shown rather than dropped, so a missing
    # article can be checked against the reason it was left out.
    gone = EXCLUDED.merge(
        ALL_MEMBERS.groupby('title')['top'].agg('; '.join).rename('groups'),
        left_on='title', right_index=True, how='left')
    # Only what the category tree or the corpus put forward. The full-text
    # searches return thousands of pages that merely mention Uganda, and
    # listing those as "filed under Ugandan categories" would be untrue.
    filed = gone['groups'].fillna('').ne('Found by search') & \
        gone['groups'].notna()
    searched = int((~filed).sum())
    gone = gone[filed]
    if len(gone):
        gone = gone[['title', 'qid', 'groups', 'direct_cats', 'lead_hits',
                     'wd_evidence']]
        gone.columns = ['Article', 'Wikidata', 'Filed under',
                        'Wikipedia categories', 'Uganda words in lead',
                        'Wikidata evidence']
        gone.to_csv(os.path.join(OUT_DIR, '_Excluded_not_about_Uganda.csv'),
                    index=False, encoding='utf-8-sig')
        print(f'  {len(gone)} articles filed under Ugandan categories but '
              f'not about Uganda -> _Excluded_not_about_Uganda.csv '
              f'({searched} search results that merely mention Uganda were '
              f'also rejected and are not listed)')

    reconcile(members, arts, gone, searched)

    # Uganda articles that exist in other languages and not in English.
    corpus = pd.read_csv(cp.CORPUS_CSV)
    elsewhere = corpus[corpus['en_title'].isna() & corpus['is_core'].map(yn.is_yes)]
    elsewhere = elsewhere.sort_values('sitelink_count', ascending=False)[
        ['qitem', 'label', 'sitelink_count', 'lg_title', 'sw_title',
         'type_labels', 'gender', 'date_of_birth', 'admin_label']]
    elsewhere.to_csv(os.path.join(
        OUT_DIR, '_Uganda_articles_not_in_English.csv'), index=False,
        encoding='utf-8-sig')
    print(f'  {len(elsewhere)} Uganda items have articles in other languages '
          f'but not English -> _Uganda_articles_not_in_English.csv')

    book = Book(os.path.join(OUT_DIR, '_Index.xlsx'))
    ws = book.wb.add_worksheet('Categories')
    ws.write(0, 0, 'Articles in two categories are counted in both, so the '
             f'rows sum to more than the {len(unique):,} distinct articles.',
             book.f['note'])
    book.table(ws, 1, idx, list(idx.columns), None, {0: 36, 1: 30})
    book.close()
    print(f'\nwrote {len(index)} category files to {OUT_DIR}')


if __name__ == '__main__':
    main()
