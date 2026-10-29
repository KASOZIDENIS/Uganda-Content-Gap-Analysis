# -*- coding: utf-8 -*-
"""A list for every category on the other Wikimedia projects, the way the
Wikipedia category lists are done.

For each project, a folder under project_categories/ with one list per
category: the pages filed in it (or, on Commons, the files), with every column
the analysis uses, as a CSV for each and an Excel workbook as well for the larger
ones, and an index of the categories with their counts. A page in two
categories is in both lists.

A category's list holds the pages the analysis covers that sit directly in it:
for Wikisource, Wikiquote and the others, the pages that mention Uganda; for the
Runyankore test, every page; for Commons, every file the crawl of Category:Uganda
found there. It does not follow sub-categories.

    python src_viz/build_project_categories.py
"""

import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src_data'))

import build_category_files as bcf                   # noqa: E402
import build_project_dashboards as bpd               # noqa: E402
import config                                        # noqa: E402
import projects_data as pdata                        # noqa: E402
import projects_history as ph                        # noqa: E402
import sheet_tidy                                    # noqa: E402
import yn                                           # noqa: E402

OUT = os.path.join(config.PROJECT_PATH, 'project_categories')
XLSX_MIN = 100            # a workbook as well as the CSV from this many rows
NONE = '(no category)'


def stem_of(name, taken):
    stem = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:80] or 'category'
    unique, k = stem, 2
    while unique in taken:
        unique, k = f'{stem}_{k}', k + 1
    taken.add(unique)
    return unique


def folder_of(label):
    return re.sub(r'[^A-Za-z0-9]+', '_', label).strip('_')


class ListBook(bcf.Book):
    """The category-file workbook, with links that go to the right project."""

    def close(self):
        sheet_tidy.tidy(self.wb)
        self.wb.close()

    def listing(self, ws, heads, rows, formats, urls, widths):
        n = len(rows)
        ws.add_table(0, 0, max(n, 1), len(heads) - 1, {
            'columns': [{'header': h, 'header_format': self.f['head']}
                        for h in heads],
            'style': 'Table Style Light 1', 'autofilter': True})
        for r, row in enumerate(rows, 1):
            for c, value in enumerate(row):
                if value is None or value == '':
                    ws.write_blank(r, c, None, self.f['cell'])
                elif c in urls:
                    ws.write_url(r, c, urls[c](row), self.f['link'], str(value))
                elif formats.get(c) == 'int' and not isinstance(value, str):
                    ws.write_number(r, c, value, self.f['num'])
                else:
                    ws.write(r, c, value, self.f['cell'])
        for c, h in enumerate(heads):
            ws.set_column(c, c, widths.get(c, max(11, min(len(h), 28))))
        ws.freeze_panes(1, 1)


def write_list(folder, stem, heads, rows, formats, urls, widths):
    pd.DataFrame(rows, columns=heads).to_csv(
        os.path.join(folder, stem + '.csv'), index=False, encoding='utf-8-sig')
    if len(rows) >= XLSX_MIN:
        book = ListBook(os.path.join(folder, stem + '.xlsx'))
        ws = book.wb.add_worksheet('List')
        book.listing(ws, heads, rows, formats, urls, widths)
        book.close()
        return stem + '.xlsx'
    return stem + '.csv'


def write_index(folder, label, rows, heads, formats, widths, note):
    pd.DataFrame(rows, columns=heads).to_csv(
        os.path.join(folder, '_Category_index.csv'), index=False,
        encoding='utf-8-sig')
    book = ListBook(os.path.join(folder, '_Category_index.xlsx'))
    ws = book.wb.add_worksheet('Categories')
    ws.write(0, 0, note, book.f['note'])
    n = len(rows)
    ws.add_table(1, 0, 1 + max(n, 1), len(heads) - 1, {
        'columns': [{'header': h, 'header_format': book.f['head']}
                    for h in heads],
        'style': 'Table Style Light 1', 'autofilter': True})
    for r, row in enumerate(rows, 2):
        for c, value in enumerate(row):
            if value is None or value == '':
                ws.write_blank(r, c, None, book.f['cell'])
            elif formats.get(c) == 'int' and not isinstance(value, str):
                ws.write_number(r, c, value, book.f['num'])
            elif formats.get(c) == 'pct' and not isinstance(value, str):
                ws.write_number(r, c, value, book.f['pct'])
            else:
                ws.write(r, c, value, book.f['cell'])
    for c, h in enumerate(heads):
        ws.set_column(c, c, widths.get(c, max(11, min(len(h), 28))))
    ws.freeze_panes(2, 1)
    book.close()


# ------------------------------------------------------------- page projects
def build_host(conn, host, label):
    try:
        df = bpd.load_host(conn, host)
    except Exception as error:                          # noqa: BLE001
        print(f'  {label}: not ready ({str(error)[:50]})')
        return 0
    if df.empty:
        return 0
    view_years = sorted({int(y) for blob in df['views_json'].dropna()
                         for y in __import__('json').loads(blob)})
    edit_cols = sorted(c for c in df.columns if c.startswith('edits_'))
    heads, rows, fmt = bpd.data_table(df, view_years, edit_cols)
    cat_col = heads.index('Categories')
    views_col = heads.index('Total views, all time')
    person_col, gender_col = len(heads) - 2, len(heads) - 1
    lg_col = len(heads) - 4
    lists = {}
    for row in rows:
        names = [c for c in str(row[cat_col]).split('; ') if c] or [NONE]
        for name in names:
            lists.setdefault(name, []).append(row)
    folder = os.path.join(OUT, folder_of(label))
    os.makedirs(folder, exist_ok=True)
    for old in os.listdir(folder):
        if old.endswith(('.csv', '.xlsx')) and not old.startswith('~$'):
            try:
                os.remove(os.path.join(folder, old))
            except OSError:
                pass
    total_views = sum(r[views_col] for r in rows if r[views_col] != '') or 1
    urls = {0: lambda row, h=host: bpd.host_link(h, row[0]),
            1: lambda row: 'https://www.wikidata.org/wiki/' + row[1]}
    widths = {0: 44, 1: 13, 2: 12, 3: 8, 4: 12, 5: 12, 6: 8, 7: 13,
              cat_col: 44}
    taken, index = {'_category_index'}, []
    for name in sorted(lists, key=lambda n: (-len(lists[n]), n)):
        sub = lists[name]
        stem = stem_of(name, taken)
        kind = write_list(folder, stem, heads, sub, fmt, urls, widths)
        views = [r[views_col] for r in sub if r[views_col] != '']
        people = [r for r in sub if r[person_col] == 'Y']
        women = sum(1 for r in people if r[gender_col] == 'female')
        known = sum(1 for r in people if r[gender_col] in ('female', 'male'))
        years = [r[3] for r in sub if r[3] != '']
        index.append([
            name, len(sub), sum(views), sum(views) / total_views,
            int(pd.Series([r[5] for r in sub]).median()),
            sum(1 for r in sub if r[5] < 1000) / len(sub),
            sum(1 for r in sub if r[lg_col] == 'Y') / len(sub),
            len(people), (women / known) if known >= 10 else None,
            min(years) if years else '', f'{folder_of(label)}/{kind}'])
    iheads = ['Category', 'Pages', 'Total views, all time',
              'Share of the project\'s views', 'Median size (bytes)',
              'Stubs, under 1,000 bytes', 'With a Luganda article', 'People',
              'Women among people', 'First page written', 'List']
    write_index(folder, label, index, iheads,
                {1: 'int', 2: 'int', 3: 'pct', 4: 'int', 5: 'pct', 6: 'pct',
                 7: 'int', 8: 'pct'}, {0: 50, 10: 44},
                f'{len(index):,} categories on {label} with a page in the '
                'analysis. A page in two categories is in both lists.')
    print(f'  {label}: {len(index)} category lists, '
          f'{sum(1 for r in index if r[-1].endswith(".xlsx"))} workbooks')
    return len(index)


# ------------------------------------------------------------------ Commons
def build_commons():
    cats, files = pdata.commons_tables()
    if cats is None:
        print('  Commons: not ready')
        return 0
    conn = pdata.connect()
    pairs = pd.read_sql('SELECT category, title FROM commons_ug_catfiles', conn)
    conn.close()
    fi = files.set_index('title')
    folder = os.path.join(OUT, 'Wikimedia_Commons')
    os.makedirs(folder, exist_ok=True)
    for old in os.listdir(folder):
        if old.endswith(('.csv', '.xlsx')) and not old.startswith('~$'):
            try:
                os.remove(os.path.join(folder, old))
            except OSError:
                pass
    heads = ['File', 'Uploaded', 'Year', 'Uploader', 'Size (bytes)',
             'MIME type', 'Media type', 'Extension',
             'Used on a Wikimedia project', 'Wikis using it']
    urls = {0: lambda row: 'https://commons.wikimedia.org/wiki/File:'
            + row[0].replace(' ', '_')}
    widths = {0: 56, 1: 12, 2: 7, 3: 22, 4: 12, 5: 14, 6: 12, 7: 10, 8: 12,
              9: 10}
    by_cat = {c: g['title'].tolist() for c, g in pairs.groupby('category')}
    taken, index = {'_category_index'}, []
    total = len(files) or 1
    for cat in cats.itertuples(index=False):
        titles = by_cat.get(cat.title, [])
        rows = []
        for t in titles:
            f = fi.loc[t]
            up = f['uploaded'] or ''
            rows.append([t[len('File:'):], up[:10], int(up[:4]) if up else '',
                         f['uploader'] or '', int(f['size'] or 0),
                         f['mime'] or '', f['mediatype'] or '',
                         ('.' + t.rsplit('.', 1)[-1].lower()) if '.' in t else '',
                         yn.yn(f['used']),
                         int(f['used_wikis']) if f['used_wikis'] == f[
                             'used_wikis'] and f['used_wikis'] is not None
                         else ''])
        rows.sort(key=lambda r: r[1], reverse=True)
        name = cat.title[len('Category:'):]
        stem = stem_of(name, taken)
        kind = write_list(folder, stem, heads, rows, {4: 'int', 9: 'int'},
                          urls, widths) if rows else None
        if not rows:
            pd.DataFrame([], columns=heads).to_csv(
                os.path.join(folder, stem + '.csv'), index=False,
                encoding='utf-8-sig')
            kind = stem + '.csv'
        unused = sum(1 for r in rows if r[8] == 'N')
        years = [r[2] for r in rows if r[2] != '']
        index.append([name, cat.depth, (cat.parent or '')[len('Category:'):],
                      len(rows), cat.subcats, cat.theme or '',
                      cat.campaign or '', len(rows) / total,
                      (unused / len(rows)) if rows else None,
                      len({r[3] for r in rows if r[3]}),
                      min(years) if years else '', max(years) if years else '',
                      f'Wikimedia_Commons/{kind}'])
    index.sort(key=lambda r: (-r[3], r[0]))
    iheads = ['Category', 'Level below Category:Uganda', 'Parent category',
              'Files directly in it', 'Sub-categories', 'Theme', 'Campaign',
              'Share of all files', 'Share used on no project', 'Uploaders',
              'First upload', 'Latest upload', 'List']
    write_index(folder, 'Wikimedia Commons', index, iheads,
                {1: 'int', 3: 'int', 4: 'int', 7: 'pct', 8: 'pct', 9: 'int'},
                {0: 50, 2: 40, 12: 44},
                f'{len(index):,} Ugandan categories on Commons, to any depth; '
                'a file in two categories is in both lists.')
    print(f'  Commons: {len(index)} category lists, '
          f'{sum(1 for r in index if r[-1].endswith(".xlsx"))} workbooks')
    return len(index)


def main():
    os.makedirs(OUT, exist_ok=True)
    conn = pdata.connect()
    n = build_commons()
    for host, label in ph.HOSTS:
        n += build_host(conn, host, label)
    conn.close()
    print(f'{n} category lists in {OUT}')


if __name__ == '__main__':
    main()
