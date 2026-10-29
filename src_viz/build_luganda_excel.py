# -*- coding: utf-8 -*-
"""Build the Luganda Wikipedia readership workbook.

Every article on lgwiki with what it has been read in all, year by year, when it
was written, how often it has been edited, what it links to and where it sits
relative to English. The same figures as the Luganda sheet of the dashboard
(luganda.py), in the dashboard's colours.

Views are the total for all time: every month the Pageviews API holds, from July
2015. The years before that are filled in from the pages' own edit histories:
articles written, edits and editors.

    python src_viz/build_luganda_excel.py
"""

import os
import sys
import time

import xlsxwriter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src_data'))

import config                                        # noqa: E402
import luganda                                       # noqa: E402
import yn                           # noqa: E402
import sheet_tidy                                    # noqa: E402
from xl_basics import bar, pie, styles, table            # noqa: E402

OUT = os.path.join(config.PROJECT_PATH, 'Luganda Wikipedia Pageviews.xlsx')

LG = 'https://lg.wikipedia.org/wiki/{}'
WIKIDATA = 'https://www.wikidata.org/wiki/{}'
WIKI = 'https://en.wikipedia.org/wiki/{}'

# the logo's colours, as on the dashboard
BLUE, GREEN, RED, GREY = '#006699', '#339966', '#990000', '#7B8794'
SOFT_RED, SOFT_BLUE = '#C27A7A', '#80B3CC'


def kpi(sheet, fmt, col, row, label, value, note='', alarm=False):
    sheet.write(row, col, value, fmt['kpi_alarm'] if alarm else fmt['kpi'])
    sheet.write(row + 1, col, label, fmt['kpi_label'])
    if note:
        sheet.write(row + 2, col, note, fmt['note'])


def sheet_summary(book, fmt, df, years, hist):
    sh = book.add_worksheet('Executive summary')
    sh.hide_gridlines(1)
    sh.set_column('A:A', 2)
    sh.set_column('B:I', 17)
    total = len(df)
    views = int(df['views_all_time'].sum())
    unread = int((df['views_all_time'] == 0).sum())
    little = int((df['views_all_time'] < luganda.LITTLE).sum())
    first = hist[0][0]
    sh.write('B2', 'Luganda Wikipedia', fmt['title'])
    sh.write('B3', 'Every article, with all-time readership since July 2015 '
                   f'and its history from {first} · cycle '
                   + config.cycle_year_month(), fmt['sub'])
    kpi(sh, fmt, 1, 5, 'Articles', total)
    kpi(sh, fmt, 3, 5, 'Total views, all time', views,
        'Luganda Wikipedia, since July 2015')
    kpi(sh, fmt, 5, 5, 'With a Wikidata item', int(df['has_wikidata'].sum()),
        f'{100.0 * df["has_wikidata"].mean():.0f}% of articles')
    kpi(sh, fmt, 7, 5, 'With an English article', int(df['has_english'].sum()),
        f'{100.0 * df["has_english"].mean():.0f}% of articles')
    kpi(sh, fmt, 1, 10, 'Read fewer than %s times in all' % f'{luganda.LITTLE:,}',
        little, f'{100.0 * little / total:.0f}% of articles', alarm=True)
    kpi(sh, fmt, 3, 10, 'Never read at all', unread,
        'no recorded views since July 2015', alarm=True)
    kpi(sh, fmt, 5, 10, 'About Uganda', int(df['about_uganda'].sum()),
        'the Luganda side of the Ugandan articles')
    kpi(sh, fmt, 7, 10, 'Median article',
        int(df['bytes'].median()), 'bytes')

    data = book.add_worksheet('_chartdata')
    data.hide()
    q = "'_chartdata'!"
    bk = luganda.buckets(df)
    for i, (lab, val) in enumerate(bk):
        data.write(i, 0, lab)
        data.write_number(i, 1, val)
    pie(book, sh, 'How much each article has been read in all',
        f'={q}$A$1:$A${len(bk)}', f'={q}$B$1:$B${len(bk)}', 'B16',
        points=[{'fill': {'color': RED}}, {'fill': {'color': SOFT_RED}},
                {'fill': {'color': SOFT_BLUE}}, {'fill': {'color': BLUE}},
                {'fill': {'color': GREEN}}])
    n_en = int(df['has_english'].sum())
    n_wd = int(df['has_wikidata'].sum())
    link = [('Wikidata item and English article', n_en),
            ('Wikidata item only', n_wd - n_en),
            ('No Wikidata item', total - n_wd)]
    for i, (lab, val) in enumerate(link):
        data.write(20 + i, 0, lab)
        data.write_number(20 + i, 1, val)
    pie(book, sh, 'How each article connects outward',
        f'={q}$A$21:$A$23', f'={q}$B$21:$B$23', 'F16',
        points=[{'fill': {'color': GREEN}}, {'fill': {'color': SOFT_BLUE}},
                {'fill': {'color': GREY}}])
    top = df.head(12)
    for i, (title, v) in enumerate(zip(top['lg_title'],
                                       top['views_all_time'])):
        data.write(40 + i, 0, title)
        data.write_number(40 + i, 1, int(v))
    bar(book, sh, 'The twelve most-read articles, all time',
        f'={q}$A$41:$A${40 + len(top)}', f'={q}$B$41:$B${40 + len(top)}',
        'B32', colour=BLUE, x_scale=1.5, y_scale=1.4)
    sz = luganda.sizes(df)
    for i, (lab, val) in enumerate(sz):
        data.write(60 + i, 0, lab)
        data.write_number(60 + i, 1, val)
    bar(book, sh, 'Article length', f'={q}$A$61:$A$64', f'={q}$B$61:$B$64',
        'F32', colour=SOFT_RED)
    return sh


def sheet_years(book, fmt, hist):
    """The year-by-year table and its two charts."""
    sh = book.add_worksheet('Year by year')
    sh.hide_gridlines(1)
    sh.set_column('A:A', 10)
    sh.set_column('B:G', 18)
    sh.write('A1', 'Luganda Wikipedia, year by year, from the first article',
             fmt['h2'])
    sh.write('A2', 'Articles written, edits and editors come from each '
             "page's edit history, so they reach back before the Pageviews "
             'API (July 2015). Editors are registered accounts, counted once '
             'a year. The last year is part-way through.', fmt['note'])
    heads = ['Year', 'Articles written', 'Articles in existence',
             'Views (all time basis)', 'Edits', 'Editors']
    for c, h in enumerate(heads):
        sh.write(3, c, h, fmt['head'])
    for r, row in enumerate(hist, 4):
        for c, v in enumerate(row):
            if v is None:
                sh.write(r, c, 'not recorded', fmt['dim'])
            elif c == 0:
                sh.write(r, c, v, fmt['cell'])
            else:
                sh.write_number(r, c, v, fmt['num'])
    end = 3 + len(hist)
    ch = book.add_chart({'type': 'column'})
    ch.add_series({'name': 'Articles written',
                   'categories': ['Year by year', 4, 0, end, 0],
                   'values': ['Year by year', 4, 1, end, 1],
                   'fill': {'color': GREEN}, 'gap': 50})
    ln = book.add_chart({'type': 'line'})
    ln.add_series({'name': 'Articles in existence (right)',
                   'categories': ['Year by year', 4, 0, end, 0],
                   'values': ['Year by year', 4, 2, end, 2], 'y2_axis': True,
                   'line': {'color': RED, 'width': 2.5}})
    ch.combine(ln)
    ch.set_title({'name': 'Articles written each year, and in existence'})
    ch.set_legend({'position': 'bottom'})
    sh.insert_chart(end + 3, 0, ch, {'x_scale': 1.6, 'y_scale': 1.2})
    cv = book.add_chart({'type': 'column'})
    cv.add_series({'name': 'Views',
                   'categories': ['Year by year', 4, 0, end, 0],
                   'values': ['Year by year', 4, 3, end, 3],
                   'fill': {'color': BLUE}, 'gap': 50})
    le = book.add_chart({'type': 'line'})
    le.add_series({'name': 'Editors (right)',
                   'categories': ['Year by year', 4, 0, end, 0],
                   'values': ['Year by year', 4, 5, end, 5], 'y2_axis': True,
                   'line': {'color': GREEN, 'width': 2.5}})
    cv.combine(le)
    cv.set_title({'name': 'Views each year, and the editors behind the pages'})
    cv.set_legend({'position': 'bottom'})
    sh.insert_chart(end + 3, 8, cv, {'x_scale': 1.6, 'y_scale': 1.2})
    return sh


def _columns(years):
    cols = ['Luganda article', 'English label', 'Total views, all time',
            'Created', 'Edits'] + [f'Views {y}' for y in years] + [
            'Bytes', 'Wikidata', 'English article', 'About Uganda']
    widths = [40, 34, 14, 10, 9] + [11] * len(years) + [10, 12, 34, 11]
    n = len(years)
    links = {0: (0, LG), 5 + n + 1: (5 + n + 1, WIKIDATA),
             5 + n + 2: (5 + n + 2, WIKI)}
    numeric = tuple([2, 3, 4] + list(range(5, 5 + n)) + [5 + n])
    return cols, widths, links, numeric


def _rows(df, years, mask=None):
    sub = df if mask is None else df[mask]
    out = []
    for _, r in sub.iterrows():
        created = int(r['created_year']) if r['created_year'] == r[
            'created_year'] else 0
        out.append([r['lg_title'], r['english_label'] or '',
                    int(r['views_all_time']), created, int(r['edits'])]
                   + [int(r[f'views_{y}']) for y in years]
                   + [int(r['bytes']), r['wikidata'] or '',
                      r['en_article'] or '',
                      yn.yn(r['about_uganda'])])
    return out


def _list_sheet(book, fmt, df, years, name, heading, note, mask=None,
                table_name='LgTable', limit=None):
    rows = _rows(df, years, mask)
    if limit:
        rows = rows[:limit]
    if not rows:
        return None
    cols, widths, links, numeric = _columns(years)
    sh = book.add_worksheet(name)
    sh.write('A1', heading, fmt['h2'])
    sh.write('A2', note, fmt['note'])
    end = table(sh, fmt, cols, rows, table_name, start=4, widths=widths,
                links=links, numeric=numeric)
    sh.conditional_format(5, 2, end, 2, {'type': 'data_bar',
                                         'bar_color': BLUE, 'bar_solid': True})
    return sh


def main():
    df, years = luganda.load()
    if df.empty:
        raise SystemExit('no Luganda pages\n'
                         'run: python src_data/luganda_pages.py')
    hist = luganda.history(df, years)

    target = OUT
    if os.path.exists(OUT):
        try:
            with open(OUT, 'r+b'):
                pass
        except PermissionError:
            target = OUT.replace('.xlsx', f' ({time.strftime("%H%M")}).xlsx')
            print(f'the workbook is open in Excel; writing '
                  f'{os.path.basename(target)} instead')

    book = xlsxwriter.Workbook(target)
    book.set_properties({
        'title': 'Luganda Wikipedia pageviews',
        'subject': 'Wikimedia content gap analysis',
        'author': 'Wikimedia Community User Group Uganda',
        'comments': 'Built by src_viz/build_luganda_excel.py'})
    fmt = styles(book)
    sheet_summary(book, fmt, df, years, hist)
    sheet_years(book, fmt, hist)
    _list_sheet(book, fmt, df, years, 'All articles',
                'Every article on Luganda Wikipedia',
                'Sorted by total views, all time. Filter any column from its '
                'header arrow. Titles link to lgwiki, ids to Wikidata, and '
                'the English column to the English article where one exists.',
                None, 'LgAllTable')
    _list_sheet(book, fmt, df, years, 'Most read',
                'The thousand most-read articles, all time',
                'Where lgwiki readers actually go. These are the pages worth '
                'getting right first.', None, 'LgTopTable', limit=1000)
    _list_sheet(book, fmt, df, years, 'Never read',
                'Articles with no recorded views since July 2015',
                'Not necessarily bad articles. An article nobody has found is '
                'a discoverability problem as often as a content one: check '
                'whether it is linked from anywhere before rewriting it.',
                df['views_all_time'] == 0, 'LgUnreadTable')
    _list_sheet(book, fmt, df, years, 'No English article',
                'What Luganda has and English does not',
                'These have a Wikidata item but no English sitelink, so the '
                'content exists in Luganda and not in English: a translation '
                'opportunity in the other direction.',
                (df['has_wikidata'] == 1) & (df['has_english'] == 0),
                'LgOnlyTable')
    _list_sheet(book, fmt, df, years, 'No Wikidata item',
                'Articles not connected to Wikidata',
                'Without an item an article is invisible to every cross-wiki '
                'tool and will not appear in any gap analysis built on '
                'Wikidata. Connecting one is a few minutes of work.',
                df['has_wikidata'] == 0, 'LgNoItemTable')
    _list_sheet(book, fmt, df, years, 'About Uganda',
                'The Luganda side of the Ugandan articles',
                'Luganda articles that match an article in the Uganda '
                'analysis, with the same all-time views.',
                df['about_uganda'] == 1, 'LgUgandaTable')
    sheet_tidy.tidy(book)
    book.close()
    print(f'wrote {os.path.basename(target)} '
          f'({os.path.getsize(target) // 1024} KB), {len(df)} articles')


if __name__ == '__main__':
    main()
