# -*- coding: utf-8 -*-
"""The Uganda dashboard for the other Wikimedia projects: Commons, Wikidata,
Wikisource and the rest.

An independent workbook beside the Wikipedia dashboard, built the same way and
in the same colours, once for Excel and once for Google Sheets:

    python src_viz/build_projects_dashboard.py                  # Excel
    DASH_TARGET=sheets python src_viz/build_projects_dashboard.py   # Sheets

It reads data/projects/projects.json (src_data/sister_projects.py) and the
Commons crawl of Category:Uganda (data/ug_commons_*.csv). The Wikidata sheet
follows what the Wikidata WikiProject Uganda tracks.
"""

import json
import os
import sys

import pandas as pd
import xlsxwriter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src_data'))

import build_category_files as bcf                  # noqa: E402
import build_dashboard_excel as dash                # noqa: E402
import sheet_tidy                                   # noqa: E402
import yn                                           # noqa: E402
import config                                       # noqa: E402
import projects_data as pdata                      # noqa: E402
import ug_utils                                     # noqa: E402

S_ = dash.SHEETS
BLUE, RED, GREEN = dash.BLUE, dash.RED, dash.GREEN
GREY, PAPER, SILVER = dash.GREY, dash.PAPER, dash.SILVER
FONT = dash.FONT
OUT = os.path.join(
    config.PROJECT_PATH, 'Uganda Wikimedia Projects Dashboard (Google Sheets).xlsx'
    if S_ else 'Uganda Wikimedia Projects Dashboard (Excel).xlsx')
JSON = os.path.join(config.DATA_PATH, 'projects', 'projects.json')

TABS = ['Overview', 'Commons', 'Wikidata', 'Wikisource', 'Other projects',
        'Where Uganda lives', 'Luganda', 'Needs work',
        'Projects data', 'Coverage data']
LINKS = {'Wikipedia': 'https://{host}/wiki/{t}',
         'Wikimedia Commons': 'https://commons.wikimedia.org/wiki/{t}'}


def n(v):
    return '' if v is None else v


def pct(a, b):
    return (a / b) if a is not None and b else None


class Book:
    """Shared drawing helpers for one workbook."""

    def __init__(self, wb, tabs=None):
        self.wb = wb
        self.names = tabs or TABS
        self.S = dash.Styles(wb)
        self.hdr = self.S(bold=True, font_color='#FFFFFF', bg_color=BLUE,
                          text_wrap=True, align='center', border=1,
                          border_color='#FFFFFF')

    def sheet(self, ws, title, subtitle, width, widths=None):
        ws.hide_gridlines(1)
        ws.set_zoom(90)
        ws.set_column(0, 0, 2)
        ws.set_column(1, 1, 34)
        ws.set_column(2, width, 15)
        for col, w in (widths or {}).items():
            ws.set_column(col, col, w)
        dash.banner(ws, self.S, title, subtitle, width)
        self.tabs(ws)
        ws.set_row(4, 8)
        ws.set_landscape()
        ws.fit_to_pages(1, 0)

    def tabs(self, ws):
        ws.set_row(3, 22)
        col = 1
        for name in self.names:
            span = 1
            cur = ws.get_name() == name
            fmt = self.S(bold=True, font_color='#FFFFFF', bg_color=GREEN,
                         align='center') if cur else self.S(
                font_color=BLUE, underline=1, align='center', bg_color=PAPER)
            if cur:
                ws.write(3, col, name, fmt)
            else:
                ws.write_url(3, col, f"internal:'{name}'!A1", fmt, string=name)
            col += span

    def tiles(self, ws, row, items, first=1, step=2):
        ws.set_row(row, 20)
        ws.set_row(row + 1, 34)
        ws.set_row(row + 2, 18)
        for i, (label, value, sub) in enumerate(items):
            c0, c1 = first + i * step, first + i * step + step - 1
            ws.merge_range(row, c0, row, c1, label, self.S(
                font_size=9, bold=True, font_color=GREY, bg_color=PAPER))
            ws.merge_range(row + 1, c0, row + 1, c1,
                           f'{value:,}' if isinstance(value, int) else value,
                           self.S(font_size=22, bold=True, font_color=BLUE,
                                  bg_color=PAPER))
            ws.merge_range(row + 2, c0, row + 2, c1, sub, self.S(
                font_size=9, font_color=GREY, bg_color=PAPER))

    def head(self, ws, row, text, c1=12, c0=1):
        dash.heading(ws, self.S, row, c0, c1, text)

    def table(self, ws, row, headers, rows, formats=None, col=1, links=None):
        """Write a banded table; returns the last row used. `formats` maps a
        column index to 'int', 'pct' or 'text'; `links` maps a column to a
        function giving the URL for that row."""
        formats = formats or {}
        links = links or {}
        for c, h in enumerate(headers):
            ws.write(row, col + c, h, self.hdr)
        ws.set_row(row, 32)
        for i, r in enumerate(rows):
            band = '#FFFFFF' if i % 2 else PAPER
            for c, v in enumerate(r):
                kind = formats.get(c, 'text')
                if c in links and v not in (None, ''):
                    ws.write_url(row + 1 + i, col + c, links[c](r), self.S(
                        font_color=BLUE, underline=1, bg_color=band),
                        string=str(v))
                elif v is None or v == '':
                    ws.write_blank(row + 1 + i, col + c, None,
                                   self.S(bg_color=band))
                elif kind == 'int':
                    ws.write_number(row + 1 + i, col + c, v, self.S(
                        num_format='#,##0', bg_color=band))
                elif kind == 'dec':
                    ws.write_number(row + 1 + i, col + c, v, self.S(
                        num_format='#,##0.0', bg_color=band))
                elif kind == 'pct':
                    ws.write_number(row + 1 + i, col + c, v, self.S(
                        num_format='0%', bg_color=band))
                else:
                    ws.write(row + 1 + i, col + c, v, self.S(bg_color=band))
        return row + len(rows)

    def bar(self, ws, row, col, title_series, cats, vals, width=520,
            height=300, colour=BLUE, horizontal=True, fmt='#,##0'):
        ch = self.wb.add_chart({'type': 'bar' if horizontal else 'column'})
        ch.add_series({'name': title_series, 'categories': cats,
                       'values': vals, 'fill': {'color': colour}, 'gap': 40})
        dash.finish_chart(ch, width, height, y_fmt=fmt,
                          x_rotate=None if horizontal else -45)
        if horizontal:
            ch.set_y_axis({'reverse': True, 'num_font': {
                'name': FONT, 'size': 9, 'color': dash.DARK}})
            ch.set_x_axis({'num_format': fmt, 'num_font': {
                'name': FONT, 'size': 9, 'color': GREY}, 'line': {'none': True},
                'major_gridlines': {'visible': True,
                                    'line': {'color': '#E3E6E8'}}})
        ws.insert_chart(row, col, ch)

    def note(self, ws, row, text, height=30, c1=12):
        dash.note(ws, self.S, row, 1, c1, text, height)


def load():
    with open(JSON, encoding='utf-8') as handle:
        data = json.load(handle)
    cdir = config.DATA_PATH
    commons = {
        'cats': pd.read_csv(os.path.join(cdir, 'ug_commons_categories.csv')),
        'media': pd.read_csv(os.path.join(cdir, 'ug_commons_media.csv')),
        'summary': dict(pd.read_csv(os.path.join(
            cdir, 'ug_commons_summary.csv')).values),
        'geo': pd.read_csv(os.path.join(
            cdir, 'ug_commons_geography_summary.csv'))}
    return data, commons


# ------------------------------------------------------------------ sheets
def sheet_overview(B, ws, data, commons, extra=None):
    rows = data.get('projects', [])
    B.sheet(ws, 'Uganda across the Wikimedia projects',
            'Commons, Wikidata, Wikisource and every other project: what '
            'each holds on Uganda and in Luganda', 12,
            {1: 26, 2: 16})
    wd = data.get('wikidata', {})
    cs = commons['summary']
    full = (extra or {}).get('commons') or {}
    other = sum(r['uganda'] or 0 for r in rows
                if r['project'] not in ('Wikipedia', 'Wikimedia Commons',
                                        'Wikidata'))
    B.head(ws, 5, 'At a glance')
    lg_items = (wd.get('labels') or {}).get('Luganda')
    items = wd.get('items')
    B.tiles(ws, 6, [
        ('FILES ON COMMONS',
         int(full.get('files') or cs.get('files', 0)),
         f"in {int((full.get('categories') or {}).get('n') or cs.get('categories', 0)):,}"
         ' Uganda categories'),
        ('WIKIDATA ITEMS', n(items) if items is None else items,
         'with Uganda as the country'),
        ('LUGANDA LABELS', f'{pct(lg_items, items):.0%}' if items and lg_items
         is not None else '', 'of those items'),
        ('LUGANDA LEXEMES', n(wd.get('lexemes')) if wd.get('lexemes') is None
         else wd['lexemes'], 'words in Wikidata'),
        ('PAGES ON UGANDA ELSEWHERE', other,
         'Wikisource, Wikiquote, Wikivoyage and the rest'),
        ('PROJECTS WITH A LUGANDA EDITION',
         sum(1 for r in rows if r['language'] == 'Luganda'),
         'Luganda Wikipedia, and what else')])
    B.head(ws, 10, 'Every project and edition checked')
    table_rows = []
    for r in sorted(rows, key=lambda r: -(r['uganda'] or 0)):
        base = r['content_pages']
        label = (r['project'] if r['language'] == 'All languages'
                 else f"{r['project']} ({r['language']})")
        table_rows.append([label, r['language'], base, r['edits'],
                           r['active_users'], r['uganda'], r['luganda'],
                           pct(r['uganda'], base)])
    heads = ['Project', 'Edition', 'Content pages', 'Edits', 'Active editors',
             'Pages mentioning Uganda', 'Pages mentioning Luganda',
             'Share mentioning Uganda']
    end = B.table(ws, 11, heads, table_rows,
                  {2: 'int', 3: 'int', 4: 'int', 5: 'int', 6: 'int',
                   7: 'pct'})
    B.bar(ws, 11, 10, 'Pages mentioning Uganda', f"='Overview'!$B$13:$B$"
          f"{min(end, 12 + 14) + 1}", f"='Overview'!$G$13:$G$"
          f"{min(end, 12 + 14) + 1}", 560, 420)
    B.note(ws, end + 2, 'Counts come from each project\'s own search for the '
           'word "Uganda", so they include every page that mentions it, not '
           'only pages about it. Content pages are the project\'s own count. '
           'A project with no Luganda or Swahili edition is simply not '
           'listed for that language.', 44)
    r = end + 5
    B.head(ws, r, 'A dashboard for each project', 8)
    suffix = '(Google Sheets)' if S_ else '(Excel)'
    names = ['Wikimedia Commons', 'Wikidata'] + [
        label for _, label in __import__('projects_history').HOSTS]
    for i, label in enumerate(names):
        fname = ('Runyankore Wikipedia on the Incubator' if label == 'Incubator'
                 else f'Uganda on {label}') + f' {suffix}.xlsx'
        band = '#FFFFFF' if i % 2 else PAPER
        ws.write(r + 1 + i, 1, label, B.S(bg_color=band, bold=True))
        if S_:
            ws.write(r + 1 + i, 2, fname, B.S(bg_color=band, font_color=GREY))
        else:
            ws.write_url(r + 1 + i, 2, f'external:project_dashboards/{fname}',
                         B.S(font_color=BLUE, underline=1, bg_color=band),
                         string=fname)
    B.note(ws, r + 2 + len(names), 'Each is an analysis dashboard like the '
           'Wikipedia one: how many pages, how big, how read, how they have '
           'grown, who edited them and what needs work. Keep the '
           'project_dashboards folder beside this file for the links to work.',
           30, 8)
    ws.freeze_panes(5, 0)


def sheet_commons(B, ws, data, commons):
    B.sheet(ws, 'Wikimedia Commons: Uganda',
            'The crawl of Category:Uganda and what is in it', 12, {1: 40})
    cs = commons['summary']
    det = (data.get('details') or {}).get('commons_uganda') or {}
    B.head(ws, 5, 'At a glance')
    B.tiles(ws, 6, [
        ('CATEGORIES CRAWLED', int(cs.get('categories', 0)),
         f"to depth {int(cs.get('crawl_depth_limit', 0))}"),
        ('FILES IN THEM', int(cs.get('files', 0)), 'directly in those categories'),
        ('PHOTOGRAPHS', f"{cs.get('photo_share_percent', 0):.0f}%",
         'of the files are bitmap images'),
        ('FILES FROM WIKI LOVES',
         int(sum(v for k, v in cs.items()
                 if str(k).startswith('files_from_wiki_loves'))),
         'Earth, Monuments, Africa, Folklore'),
        ('CATEGORIES NOT OPENED', int(cs.get('categories_unexplored_at_depth_limit', 0)),
         'at the depth limit: more files lie below')])
    # files by theme
    themes = commons['cats'].groupby('theme').agg(
        categories=('title', 'count'), files=('files', 'sum')).reset_index()
    themes = themes.sort_values('files', ascending=False)
    B.head(ws, 10, 'What is in the Uganda categories, by theme', 5)
    end = B.table(ws, 11, ['Theme', 'Categories', 'Files'],
                  themes.values.tolist(), {1: 'int', 2: 'int'})
    B.bar(ws, 11, 5, 'Files by theme', f"='Commons'!$B$13:$B${end + 1}",
          f"='Commons'!$D$13:$D${end + 1}", 560, 330)
    # campaigns
    cats = commons['cats']
    camp = cats[cats['campaign'].notna()].copy()
    camp['year'] = camp['title'].str.extract(r'(20\d\d)')[0]
    camp = camp.groupby(['campaign', 'year']).agg(
        categories=('title', 'count'), files=('files', 'sum')).reset_index()
    r0 = max(end, 12 + 16) + 3
    B.head(ws, r0, 'Wiki Loves campaigns in Uganda, year by year', 5)
    camp_rows = camp.sort_values(['campaign', 'year']).values.tolist()
    end2 = B.table(ws, r0 + 1, ['Campaign', 'Year', 'Categories', 'Files'],
                   camp_rows, {2: 'int', 3: 'int'})
    # media types
    B.head(ws, r0, 'What kind of files', 12) if False else None
    media = commons['media'].copy()
    B.table(ws, r0 + 1, ['Media type', 'Files', 'Share of files'],
            [[r.mediatype, int(r.files), r.share_percent / 100]
             for r in media.itertuples()], {1: 'int', 2: 'pct'}, col=7)
    # geography
    geo = commons['geo'].pivot(index='kind', columns='metric', values='value')
    r1 = end2 + 3
    B.head(ws, r1, 'Places of Uganda and their Commons categories', 8)
    geo_rows = []
    for kind, g in geo.iterrows():
        geo_rows.append([kind.title(), int(g.get('places', 0)),
                         int(g.get('with_commons_category', 0)),
                         int(g.get('with_no_files', 0)),
                         int(g.get('with_fewer_than_5_files', 0)),
                         int(g.get('total_files', 0)),
                         int(g.get('article_has_lead_image', 0)),
                         int(g.get('files_exist_but_article_has_no_image', 0))])
    end3 = B.table(ws, r1 + 1, ['Kind of place', 'Places', 'With a Commons category',
                                'With no files', 'With under 5 files',
                                'Files', 'Article has a lead image',
                                'Has files, article has no image'],
                   geo_rows, {i: 'int' for i in range(1, 8)})
    # biggest categories
    r2 = end3 + 3
    B.head(ws, r2, 'The twenty-five largest categories', 8)
    top = cats.sort_values('files', ascending=False).head(25)
    B.table(ws, r2 + 1, ['Category', 'Files', 'Sub-categories', 'Theme',
                         'Depth'],
            [[t[len('Category:'):], int(f), int(s), th, int(d)]
             for t, f, s, th, d in zip(top['title'], top['files'],
                                       top['subcats'], top['theme'],
                                       top['depth'])],
            {1: 'int', 2: 'int', 4: 'int'},
            links={0: lambda r: 'https://commons.wikimedia.org/wiki/Category:'
                   + r[0].replace(' ', '_')})
    B.note(ws, r2 + 29, 'Counts are files filed directly in each category, '
           'so a file in two categories is counted twice, and the crawl '
           'stops at four levels below Category:Uganda: more lie beneath the '
           'categories it did not open.' + (
               f' A search of Commons for everything under Uganda finds '
               f'{det["files_deep"]:,} files.' if det.get('files_deep')
               else ''), 44, 8)


def sheet_wikidata(B, ws, data, commons):
    wd = data.get('wikidata') or {}
    B.sheet(ws, 'Wikidata: Uganda',
            'What the Wikidata WikiProject Uganda tracks: places, people, '
            'lists, labels and Luganda lexemes', 12, {1: 38, 7: 36})
    items = wd.get('items')
    labels = wd.get('labels') or {}
    B.head(ws, 5, 'At a glance')
    B.tiles(ws, 6, [
        ('ITEMS ABOUT UGANDA', n(items) if items is None else items,
         'country = Uganda'),
        ('PLACES IN UGANDA', n(wd.get('places')) if wd.get('places') is None
         else wd['places'], 'located within Uganda'),
        ('PEOPLE', n(wd.get('people')) if wd.get('people') is None
         else wd['people'], 'citizens of Uganda'),
        ('LUGANDA LEXEMES', n(wd.get('lexemes')) if wd.get('lexemes') is None
         else wd['lexemes'], 'words with forms and senses'),
        ('MISSING A LUGANDA LABEL', n(wd.get('missing_lg_label'))
         if wd.get('missing_lg_label') is None else wd['missing_lg_label'],
         'items with an English label but no Luganda one'),
        ('NO CLASSIFICATION', n(wd.get('no_classification'))
         if wd.get('no_classification') is None else wd['no_classification'],
         'no instance of, no subclass of')])
    r = 10
    B.head(ws, r, 'Labels: how many Ugandan items can be read in each language', 5)
    lrows = [[k, v, pct(v, items)] for k, v in labels.items()]
    end = B.table(ws, r + 1, ['Language', 'Items with a label', 'Share of items'],
                  lrows, {1: 'int', 2: 'pct'})
    B.bar(ws, r + 1, 5, 'Items with a label', f"='Wikidata'!$B${r + 3}:$B${end + 1}",
          f"='Wikidata'!$C${r + 3}:$C${end + 1}", 480, 250, GREEN)
    r = end + 5
    B.head(ws, r, 'Items about Uganda, by what they are', 5)
    end = B.table(ws, r + 1, ['Type', 'Items'], wd.get('by_type') or [],
                  {1: 'int'})
    B.head(ws, r, 'Places in Uganda, by type', 8, 7)
    B.table(ws, r + 1, ['Type of place', 'Places'], wd.get('place_types') or [],
            {1: 'int'}, col=7)
    r = max(end, r + 18) + 3
    B.head(ws, r, 'People of Uganda', 5)
    end = B.table(ws, r + 1, ['Gender', 'People'],
                  wd.get('people_by_gender') or [], {1: 'int'})
    B.head(ws, r, 'Occupations', 8, 7)
    B.table(ws, r + 1, ['Occupation', 'People'], wd.get('occupations') or [],
            {1: 'int'}, col=7)
    r = max(end, r + 18) + 3
    B.head(ws, r, 'The lists the WikiProject keeps', 12)
    lrows = []
    for x in wd.get('lists') or []:
        tot = x.get('items') or 0
        lrows.append([x['name'], tot, pct(x.get('lg_label'), tot) if tot else None,
                      pct(x.get('en_label'), tot) if tot else None,
                      pct(x.get('en_article'), tot) if tot else None,
                      pct(x.get('lg_article'), tot) if tot else None,
                      pct(x.get('coordinates'), tot) if tot else None,
                      pct(x.get('image'), tot) if tot else None,
                      pct(x.get('commons'), tot) if tot else None])
    end = B.table(ws, r + 1, ['List', 'Items', 'With a Luganda label',
                              'With an English label', 'In English Wikipedia',
                              'In Luganda Wikipedia', 'With coordinates',
                              'With an image', 'With a Commons category'],
                  lrows, {1: 'int', **{i: 'pct' for i in range(2, 9)}})
    r = end + 3
    B.head(ws, r, 'Luganda lexemes (the words)', 5)
    lex = [['Lexemes', wd.get('lexemes')], ['Forms', wd.get('lexeme_forms')],
           ['Senses', wd.get('lexeme_senses')]]
    end = B.table(ws, r + 1, ['Measure', 'Count'], lex, {1: 'int'})
    B.head(ws, r, 'By lexical category', 8, 7)
    B.table(ws, r + 1, ['Lexical category', 'Lexemes'],
            wd.get('lexeme_categories') or [], {1: 'int'}, col=7)
    r = max(end, r + 8) + 3
    B.head(ws, r, 'Tasks the WikiProject sets', 8)
    tasks = [
        ['Items with an English label and no Luganda label',
         wd.get('missing_lg_label'), 'Translate the label into Luganda'],
        ['Items with no instance of or subclass of',
         wd.get('no_classification'), 'Classify them'],
        ['Items that are only a "geographical object"',
         wd.get('geographic_object'), 'Replace with a specific type'],
        ['Items with no image', wd.get('no_image'), 'Add a Commons image'],
        ['Items with coordinates', wd.get('with_coordinates'), 'For the map'],
        ['Items in English Wikipedia', wd.get('in_english_wikipedia'),
         'Linked to an English article'],
        ['Items in Luganda Wikipedia', wd.get('in_luganda_wikipedia'),
         'Linked to a Luganda article'],
        ['World Heritage Sites', wd.get('world_heritage'), ''],
        ['Politicians', wd.get('politicians'), 'Every politician project']]
    end = B.table(ws, r + 1, ['Task or measure', 'Items', 'What to do'], tasks,
                  {1: 'int'})
    r = end + 3
    B.head(ws, r, 'Important items', 8)
    B.table(ws, r + 1, ['Item', 'Wikidata id', 'Languages it is linked in',
                        'Statements'],
            [[x['label'], x['qid'], x['sitelinks'], x['statements']]
             for x in wd.get('important') or []], {2: 'int', 3: 'int'},
            links={1: lambda row: 'https://www.wikidata.org/wiki/' + row[1]})
    B.note(ws, r + 8, 'From the Wikidata Query Service. The WikiProject '
           'is at wikidata.org/wiki/Wikidata:WikiProject_Uganda. Figures '
           'change daily.', 30, 8)


def sheet_wikisource(B, ws, data):
    det = data.get('details') or {}
    projects = [r for r in data.get('projects', []) if r['project'] == 'Wikisource']
    B.sheet(ws, 'Wikisource: Uganda',
            'Texts that mention Uganda or Luganda, and the Wikisource editions '
            'there are', 8, {1: 46, 2: 14, 3: 14, 4: 14})
    en = next((r for r in projects if r['language'] == 'English'), {})
    B.head(ws, 5, 'At a glance', 8)
    cat = det.get('wikisource_category') or {}
    B.tiles(ws, 6, [
        ('TEXTS MENTIONING UGANDA', n(en.get('uganda')) if en.get('uganda')
         is None else en['uganda'], 'English Wikisource'),
        ('TEXTS MENTIONING LUGANDA', n(en.get('luganda')) if en.get('luganda')
         is None else en['luganda'], 'English Wikisource'),
        ('IN CATEGORY UGANDA', int(cat.get('pages', 0)),
         f"and {int(cat.get('subcats', 0))} sub-categories"),
        ('WIKISOURCE EDITIONS', len(projects),
         ', '.join(r['language'] for r in projects) or 'none checked')],
        step=2)
    B.head(ws, 10, 'The Wikisource editions checked', 8)
    end = B.table(ws, 11, ['Edition', 'Content pages', 'Edits', 'Active editors',
                           'Mention Uganda', 'Mention Luganda'],
                  [[r['language'], r['content_pages'], r['edits'],
                    r['active_users'], r['uganda'], r['luganda']]
                   for r in projects], {i: 'int' for i in range(1, 6)})
    r = end + 3
    B.head(ws, r, 'Texts that mention Uganda, most relevant first', 8)
    hits = det.get('wikisource_uganda') or []
    end = B.table(ws, r + 1, ['Title', 'Size (bytes)', 'Words', 'Last edited'],
                  hits, {1: 'int', 2: 'int'},
                  links={0: lambda row: 'https://en.wikisource.org/wiki/'
                         + row[0].replace(' ', '_')})
    r = end + 3
    B.head(ws, r, 'Author pages that mention Uganda', 8)
    end = B.table(ws, r + 1, ['Author page', 'Size (bytes)', 'Words',
                              'Last edited'],
                  det.get('wikisource_authors') or [], {1: 'int', 2: 'int'},
                  links={0: lambda row: 'https://en.wikisource.org/wiki/'
                         + row[0].replace(' ', '_')})
    r = end + 3
    B.head(ws, r, 'Texts that mention Luganda', 8)
    end = B.table(ws, r + 1, ['Title', 'Size (bytes)', 'Words', 'Last edited'],
                  det.get('wikisource_luganda') or [], {1: 'int', 2: 'int'},
                  links={0: lambda row: 'https://en.wikisource.org/wiki/'
                         + row[0].replace(' ', '_')})
    B.note(ws, end + 2, 'There is no Luganda Wikisource. Texts in Luganda '
           'would be proofread on the Incubator or on a language edition '
           'once one is approved. Search counts are of mentions, not of '
           'works about Uganda.', 44, 8)


def sheet_other(B, ws, data):
    det = data.get('details') or {}
    B.sheet(ws, 'The other projects: Uganda',
            'Wiktionary, Wikibooks, Wikiquote, Wikinews, Wikivoyage, '
            'Wikiversity, Wikispecies, Meta-Wiki and the rest', 8,
            {1: 44, 2: 14, 3: 14, 4: 14})
    B.head(ws, 5, 'What each holds on Uganda', 8)
    rows = []
    for r in sorted(data.get('projects', []), key=lambda r: -(r['uganda'] or 0)):
        if r['project'] in ('Wikipedia', 'Wikimedia Commons', 'Wikidata',
                            'Wikisource'):
            continue
        key = {'Wiktionary': 'wiktionary', 'Wikibooks': 'wikibooks',
               'Wikiquote': 'wikiquote', 'Wikinews': 'wikinews',
               'Wikivoyage': 'wikivoyage', 'Wikiversity': 'wikiversity',
               'Wikispecies': 'wikispecies', 'Meta-Wiki': 'meta'}.get(
            r['project'])
        cat = det.get(f'{key}_category') if key and r['language'] in (
            'English', 'All languages') else None
        rows.append([r['project'], r['language'], r['content_pages'],
                     r['active_users'], r['uganda'], r['luganda'],
                     (cat or {}).get('pages')])
    end = B.table(ws, 6, ['Project', 'Edition', 'Content pages',
                          'Active editors', 'Mention Uganda',
                          'Mention Luganda', 'In Category:Uganda'],
                  rows, {i: 'int' for i in range(2, 7)})
    r = end + 3
    for name, host, label in (
            ('wikivoyage', 'en.wikivoyage.org', 'Wikivoyage (travel guide)'),
            ('wikibooks', 'en.wikibooks.org', 'Wikibooks'),
            ('wikiquote', 'en.wikiquote.org', 'Wikiquote'),
            ('wikinews', 'en.wikinews.org', 'Wikinews'),
            ('wikiversity', 'en.wikiversity.org', 'Wikiversity'),
            ('wikispecies', 'species.wikimedia.org', 'Wikispecies'),
            ('wiktionary', 'en.wiktionary.org', 'Wiktionary'),
            ('meta', 'meta.wikimedia.org', 'Meta-Wiki')):
        hits = (det.get(name + '_hits') or [])[:15]
        if not hits:
            continue
        B.head(ws, r, f'{label}: pages that mention Uganda', 8)
        end = B.table(ws, r + 1, ['Title', 'Size (bytes)', 'Words',
                                  'Last edited'], hits, {1: 'int', 2: 'int'},
                      links={0: (lambda h: lambda row: f'https://{h}/wiki/'
                                 + row[0].replace(' ', '_'))(host)})
        r = end + 3
    B.note(ws, r, 'Counts and titles are the project\'s own search results '
           'for "Uganda", so they include pages that only mention it.', 30, 8)


def sheet_luganda(B, ws, data):
    wd = data.get('wikidata') or {}
    det = data.get('details') or {}
    B.sheet(ws, 'Luganda across the projects',
            'Where Luganda exists on the Wikimedia projects, and how much of '
            'Uganda can be read in it', 8, {1: 46, 2: 16, 3: 16, 4: 16})
    rows = data.get('projects', [])
    lg = [r for r in rows if r['language'] == 'Luganda']
    B.head(ws, 5, 'At a glance', 8)
    items, lg_lab = wd.get('items'), (wd.get('labels') or {}).get('Luganda')
    B.tiles(ws, 6, [
        ('LUGANDA EDITIONS', len(lg), ', '.join(r['project'] for r in lg) or ''),
        ('WIKIDATA ITEMS WITH A LUGANDA LABEL', n(lg_lab) if lg_lab is None
         else lg_lab, f'of {items:,}' if items else ''),
        ('LUGANDA LEXEMES', n(wd.get('lexemes')) if wd.get('lexemes') is None
         else wd['lexemes'], 'words'),
        ('LUGANDA LEMMAS ON WIKTIONARY',
         ((det.get('wiktionary_luganda') or {}).get('lemmas') or {}).get('pages', 0),
         'English Wiktionary')], step=2)
    B.head(ws, 10, 'Luganda editions that exist', 8)
    end = B.table(ws, 11, ['Project', 'Content pages', 'Edits',
                           'Active editors', 'Mention Uganda'],
                  [[r['project'], r['content_pages'], r['edits'],
                    r['active_users'], r['uganda']] for r in lg],
                  {i: 'int' for i in range(1, 5)})
    r = end + 3
    B.head(ws, r, 'Luganda on English Wiktionary', 8)
    wl = det.get('wiktionary_luganda') or {}
    end = B.table(ws, r + 1, ['Category', 'Pages', 'Sub-categories'],
                  [[k.title(), (v or {}).get('pages'), (v or {}).get('subcats')]
                   for k, v in wl.items()], {1: 'int', 2: 'int'})
    r = end + 3
    B.head(ws, r, 'How much of Wikidata about Uganda is readable in Luganda', 8)
    lab = wd.get('labels') or {}
    end = B.table(ws, r + 1, ['Language', 'Items with a label', 'Share'],
                  [[k, v, pct(v, items)] for k, v in lab.items()],
                  {1: 'int', 2: 'pct'})
    r = end + 3
    B.head(ws, r, 'Pages mentioning Luganda, by project', 8)
    mention = sorted([x for x in rows if x['luganda']],
                     key=lambda x: -x['luganda'])
    end = B.table(ws, r + 1, ['Project', 'Edition', 'Pages mentioning Luganda'],
                  [[x['project'], x['language'], x['luganda']] for x in mention],
                  {2: 'int'})
    B.note(ws, end + 2, 'Luganda editions are checked by name; a project not '
           'listed has none. Luganda Wikipedia has its own dashboard sheet in '
           'the Wikipedia dashboard.', 30, 8)


def sheet_commons_full(B, ws, data, extra):
    c = extra['commons']
    cats = c['categories']
    B.sheet(ws, 'Wikimedia Commons: everything about Uganda',
            'Category:Uganda and every Ugandan category beneath it, to any '
            'depth: how the collection has grown, who adds to it, and where it '
            'is thin', 12, {1: 40, 4: 24})
    used = c.get('used') or {}
    checked = used.get('used', 0) + used.get('unused', 0)
    B.head(ws, 5, 'At a glance')
    B.tiles(ws, 6, [
        ('CATEGORIES', cats['n'], f"down to level {cats['deepest']}"),
        ('FILES', c.get('files', cats['files']), 'distinct files'),
        ('UPLOADERS', c.get('uploaders', 0), 'accounts that added them'),
        ('ADDED IN THE LAST YEAR', c.get('recent', 0), 'files'),
        ('NOT USED ANYWHERE',
         f"{used['unused'] / checked:.0%}" if checked else 'not yet checked',
         'of files, on any Wikimedia project')])
    r = 10
    B.head(ws, r, 'How the collection has grown, year by year', 6)
    rows = c.get('years') or []
    end = B.table(ws, r + 1, ['Year', 'Files added', 'Uploaders', 'Files to date',
                              'Gigabytes added'], rows,
                  {0: 'text', 1: 'int', 2: 'int', 3: 'int', 4: 'dec'})
    if rows:
        ws.write(r, 7, 'Files added each year', B.S(bold=True, font_color=BLUE))
        ws.write(r + 17, 7, 'Accounts that added files each year',
                 B.S(bold=True, font_color=BLUE))
        last = end + 1
        ch = B.wb.add_chart({'type': 'column'})
        ch.add_series({'name': 'Files added', 'categories': f"='Commons'!$B$13:$B${last}",
                       'values': f"='Commons'!$C$13:$C${last}",
                       'fill': {'color': BLUE}, 'gap': 40})
        dash.finish_chart(ch, 620, 320, y_fmt='#,##0', x_rotate=-45)
        ws.insert_chart(r + 1, 7, ch)
        ch2 = B.wb.add_chart({'type': 'line'})
        ch2.add_series({'name': 'Uploaders', 'categories': f"='Commons'!$B$13:$B${last}",
                        'values': f"='Commons'!$D$13:$D${last}",
                        'line': {'color': GREEN, 'width': 2.5}})
        dash.finish_chart(ch2, 620, 260, y_fmt='#,##0', x_rotate=-45)
        ws.insert_chart(r + 18, 7, ch2)
    r = max(end, r + 28) + 3
    B.head(ws, r, 'What kind of files', 3)
    end1 = B.table(ws, r + 1, ['Media type', 'Files'], c.get('types') or [],
                   {1: 'int'})
    B.head(ws, r, 'By theme', 6, 4)
    B.head(ws, r, 'By file extension', 10, 8)
    B.table(ws, r + 1, ['Media type', 'Extension', 'Files'],
            c.get('extensions') or [], {2: 'int'}, col=8)
    B.table(ws, r + 1, ['Theme', 'Files', 'Categories'], c.get('themes') or [],
            {1: 'int', 2: 'int'}, col=4)
    r = max(end1, r + 14) + 3
    B.head(ws, r, 'Wiki Loves and other campaigns, by year uploaded', 4)
    camp = c.get('campaigns') or []
    end = B.table(ws, r + 1, ['Campaign', 'Year', 'Files'],
                  [[a, b, n] for a, b, n in camp], {2: 'int'})
    B.table(ws, r + 1, ['Level below Category:Uganda', 'Categories', 'Files'],
            c.get('by_depth') or [], {0: 'text', 1: 'int', 2: 'int'}, col=5)
    r = max(end, r + 12) + 3
    B.head(ws, r, 'The twenty-five largest categories', 6)
    end = B.table(ws, r + 1, ['Category', 'Files', 'Level', 'Theme'],
                  [[t[9:], f, d, th] for t, f, d, th in c.get('biggest') or []],
                  {1: 'int', 2: 'int'},
                  links={0: lambda row: 'https://commons.wikimedia.org/wiki/'
                         'Category:' + row[0].replace(' ', '_')})
    r = end + 3
    B.head(ws, r, 'Where Commons is thin', 6)
    rows = [['Categories with no files and no sub-categories', cats['empty_leaves'],
             'Fill or merge'],
            ['Categories with 1 to 4 files', cats['thin'], 'Few to choose from'],
            ['Files used on no Wikimedia project', used.get('unused'),
             'Put them to use or improve their descriptions'],
            ['Files not yet checked for use', used.get('unchecked'), ''],
            ['Uploaders who added a single file', c.get('one_file_uploaders'),
             'One-time contributors to invite back'],
            ['Share of files from the ten busiest uploaders',
             c.get('top10_share'), 'How concentrated the collection is']]
    pct_row = len(rows) - 1
    end = B.table(ws, r + 1, ['Measure', 'Value', 'What it means'], rows,
                  {1: 'int'})
    ws.write_number(r + 1 + 1 + pct_row - 0, 2 - 1 + 1, c.get('top10_share') or 0,
                    B.S(num_format='0%', bg_color=PAPER)) if False else None
    B.note(ws, end + 2, 'Every Ugandan category is followed to any depth. A '
           'category is followed when its own name is Ugandan or is within two '
           'steps of one, so the walk does not wander into Kenya or Congo. '
           'Upload dates are those of each file\'s latest version. Media '
           'types are Commons\' own: BITMAP is a raster picture (JPEG, PNG, '
           'GIF, TIFF, WebP), DRAWING is a vector drawing (SVG), VIDEO is '
           'WebM, OGV or MPG (Commons does not take MOV), AUDIO is OGG, WAV, '
           'FLAC or Opus, and OFFICE is PDF or DjVu.', 58, 8)


def sheet_where(B, ws, data, extra):
    cov = extra.get('coverage') or {}
    B.sheet(ws, 'Where Uganda lives across the projects',
            'For every Ugandan Wikipedia article, which other projects hold the '
            'same subject, and what is not where it should be', 10, {1: 44})
    if not cov:
        B.note(ws, 5, 'The sitelinks have not been collected yet.', 24, 8)
        return
    B.head(ws, 5, 'At a glance', 8)
    B.tiles(ws, 6, [
        ('ARTICLES CHECKED', cov['articles'], 'Ugandan Wikipedia articles'),
        ('MEDIAN LANGUAGES', f"{cov['languages_median']:.0f}",
         'Wikipedia editions that have the subject'),
        ('IN ENGLISH ONLY', cov['one_language_only'],
         'no other Wikipedia has the subject')], step=2)
    B.head(ws, 10, 'The share of Ugandan articles each project also covers', 8)
    end = B.table(ws, 11, ['Project', 'Articles with a page there', 'Share'],
                  cov['overall'], {1: 'int', 2: 'pct'})
    B.bar(ws, 11, 6, 'Share', f"='Where Uganda lives'!$B$13:$B${end + 1}",
          f"='Where Uganda lives'!$D$13:$D${end + 1}", 520, 320, GREEN,
          fmt='0%')
    r = end + 3
    B.head(ws, r, 'By main group of articles', 8)
    heads = ['Group', 'Articles', 'On Commons', 'On Wikiquote', 'On Wikisource',
             'In Luganda Wikipedia', 'In Swahili Wikipedia']
    end = B.table(ws, r + 1, heads, cov['groups'],
                  {1: 'int', **{i: 'pct' for i in range(2, 7)}})
    r = end + 3
    B.head(ws, r, 'Most-read articles with no Commons page', 8)
    end = B.table(ws, r + 1, ['Article', 'Group', 'Total views', 'Languages'],
                  cov['no_commons'], {2: 'int', 3: 'int'},
                  links={0: lambda row: 'https://en.wikipedia.org/wiki/'
                         + row[0].replace(' ', '_')})
    r = end + 3
    B.head(ws, r, 'Most-read articles that exist only in English', 8)
    B.table(ws, r + 1, ['Article', 'Group', 'Total views', 'Languages'],
            cov['english_only'], {2: 'int', 3: 'int'},
            links={0: lambda row: 'https://en.wikipedia.org/wiki/'
                   + row[0].replace(' ', '_')})


def sheet_needs(B, ws, data, extra, commons):
    wd = data.get('wikidata') or {}
    c = extra.get('commons') or {}
    cov = extra.get('coverage') or {}
    B.sheet(ws, 'What needs work',
            'The gaps, in one place, with where to start', 8,
            {1: 18, 2: 62, 3: 12, 4: 10, 5: 50})
    items = wd.get('items')
    rows = []

    def add(area, what, value, base, where):
        if value is not None:
            rows.append([area, what, value,
                         (value / base) if base else None, where])

    add('Wikidata', 'Items with an English label and no Luganda label',
        wd.get('missing_lg_label'), items,
        'Wikidata WikiProject Uganda, Tasks and Queries')
    add('Wikidata', 'Items with no instance of or subclass of',
        wd.get('no_classification'), items, 'Classify them')
    add('Wikidata', 'Items with no image', wd.get('no_image'), items,
        'Add a Commons image')
    add('Wikidata', 'Items that are only a "geographical object"',
        wd.get('geographic_object'), items, 'Give a specific type')
    for x in wd.get('lists') or []:
        tot = x.get('items') or 0
        if tot and x.get('lg_label') is not None:
            add('Wikidata lists', f"{x['name']} with no Luganda label",
                tot - x['lg_label'], tot, 'Add Luganda labels')
        if tot and x.get('coordinates') is not None and x['name'] in (
                'Hospitals', 'Schools', 'Hotels', 'Universities and colleges'):
            add('Wikidata lists', f"{x['name']} with no coordinates",
                tot - x['coordinates'], tot, 'Add P625')
    if c:
        add('Commons', 'Categories with no files and no sub-categories',
            c['categories']['empty_leaves'], c['categories']['n'],
            'Fill or merge')
        add('Commons', 'Categories with only 1 to 4 files',
            c['categories']['thin'], c['categories']['n'], 'Upload more')
        used = c.get('used') or {}
        checked = used.get('used', 0) + used.get('unused', 0)
        if checked:
            add('Commons', 'Files used on no Wikimedia project',
                used['unused'], checked, 'Use them in articles')
    geo = commons['geo'].pivot(index='kind', columns='metric', values='value')
    if 'district' in geo.index:
        g = geo.loc['district']
        add('Commons', 'Districts with no files on Commons',
            int(g['with_no_files']), int(g['places']), 'Photograph them')
        add('Commons', 'Districts with fewer than five files',
            int(g['with_fewer_than_5_files']), int(g['places']),
            'Photograph them')
    if cov:
        for label, have, share in cov['overall']:
            if label in ('Commons', 'Wikivoyage', 'Wikiquote', 'Luganda Wikipedia',
                         'Swahili Wikipedia'):
                add('Across projects', f'Ugandan articles with no {label} page',
                    cov['articles'] - have, cov['articles'], 'See Where Uganda lives')
        add('Across projects', 'Ugandan articles that exist in English only',
            cov['one_language_only'], cov['articles'], 'Translate')
    B.head(ws, 5, 'What is missing, and where to start', 8)
    B.table(ws, 6, ['Area', 'What is missing', 'How many', 'Share', 'Where to start'],
            [[a, b, v, s, w] for a, b, v, s, w in rows], {2: 'int', 3: 'pct'})
    B.note(ws, 8 + len(rows), 'Shares are of the whole group each line is '
           'measured against: all Ugandan Wikidata items, a list, the '
           'Commons categories, or the Ugandan Wikipedia articles.', 30, 8)


def sheet_growth_other(B, ws, extra, start_row):
    pg = extra.get('pages') or {}
    if not pg:
        return start_row
    years = pg['years']
    allyears = sorted({y for d in years.values() for y in d})
    labels = {h: n for h, n in __import__('projects_history').HOSTS}
    B.head(ws, start_row, 'Pages mentioning Uganda, by the year they were first written', 8)
    heads = ['Year'] + [labels.get(h, h) for h in years]
    rows = [[y] + [years[h].get(y, 0) for h in years] for y in allyears]
    ws.set_column(2, 1 + len(years), 13)
    return B.table(ws, start_row + 1, heads, rows,
                   {i: 'int' for i in range(1, 1 + len(years))}) + 3


def data_sheet(B, ws, title, subtitle, heads, rows, formats=None, links=None,
               widths=None):
    """A sheet that is nothing but the data: one row per record, every column
    the analysis uses, filterable. The twin of the Data sheet of the Wikipedia
    dashboard."""
    B.sheet(ws, title, subtitle, min(max(len(heads), 8), 14), widths or {})
    end = B.table(ws, 5, heads, rows, formats, links=links)
    ws.autofilter(5, 1, end, len(heads))
    ws.freeze_panes(6, 2)
    return end


def sheet_commons_data(B, ws_cats, ws_files):
    cats, files = pdata.commons_tables()
    if cats is None:
        for ws in (ws_cats, ws_files):
            B.sheet(ws, 'Commons data', 'Not collected yet.', 8)
        return
    rows = [[t[len('Category:'):], int(d), (p or '')[len('Category:'):], int(f),
             int(s), th or '', ca or '', yn.yn_flag(nm)]
            for t, d, p, f, s, th, ca, nm in zip(
                cats['title'], cats['depth'], cats['parent'], cats['files'],
                cats['subcats'], cats['theme'], cats['campaign'],
                cats['named'])]
    data_sheet(
        B, ws_cats, 'All the data behind this dashboard: the categories',
        'Every Ugandan Commons category found, to any depth', ['Category',
        'Level below Category:Uganda', 'Parent category',
        'Files directly in it', 'Sub-categories', 'Theme', 'Campaign',
        'Its own name is Ugandan'], rows, {1: 'int', 3: 'int', 4: 'int'},
        {0: lambda r: 'https://commons.wikimedia.org/wiki/Category:'
         + r[0].replace(' ', '_')}, {1: 52, 2: 16, 3: 44, 4: 14, 5: 14,
                                      6: 18, 7: 22, 8: 14})
    rows = []
    for t, c, up, who, size, mime, mt, used, uw in zip(
            files['title'], files['category'], files['uploaded'],
            files['uploader'], files['size'], files['mime'],
            files['mediatype'], files['used'], files['used_wikis']):
        ext = ('.' + t.rsplit('.', 1)[-1].lower()) if '.' in t else ''
        rows.append([t[len('File:'):], (c or '')[len('Category:'):],
                     (up or '')[:10], int(up[:4]) if up else '', who or '',
                     int(size or 0), mime or '', mt or '', ext,
                     yn.yn(used),
                     int(uw) if uw == uw and uw is not None else ''])
    data_sheet(
        B, ws_files, 'All the data behind this dashboard: the files',
        'Every file found in those categories, with who added it, when, and '
        'whether any Wikimedia project uses it',
        ['File', 'Found in category', 'Uploaded', 'Year', 'Uploader',
         'Size (bytes)', 'MIME type', 'Media type', 'Extension',
         'Used on a Wikimedia project', 'Wikis using it'], rows,
        {3: 'text', 5: 'int', 10: 'int'},
        {0: lambda r: 'https://commons.wikimedia.org/wiki/File:'
         + r[0].replace(' ', '_')},
        {1: 56, 2: 40, 3: 12, 4: 8, 5: 22, 6: 12, 7: 16, 8: 12, 9: 11,
         10: 14, 11: 12})


def sheet_wikidata_items(B, ws, ws_measures, data):
    items = pdata.wikidata_items()
    if items is None:
        B.sheet(ws, 'Wikidata items', 'Not collected yet.', 8)
    else:
        def val(v):
            return '' if v is None or v != v else v
        rows = []
        for r in items.itertuples(index=False):
            rows.append([r.qid, val(r.label_en), val(r.label_lg),
                         val(r.label_sw), val(r.label_fr), val(r.label_de),
                         val(r.type_labels), val(r.types), val(r.admin_label),
                         val(r.admin), val(r.lat), val(r.lon), val(r.image),
                         val(r.commons), val(r.enwiki), val(r.lgwiki),
                         val(r.swwiki), val(r.gender), val(r.born),
                         val(r.died), val(r.est_year),
                         yn.yn_flag(val(r.label_lg) != ''),
                         val(r.basis)])
        data_sheet(
            B, ws, 'All the data behind this dashboard: the items',
            'Every Wikidata item about Uganda (its country is Uganda, it is a Ugandan '
            'citizen, or it lies within Uganda), with every column the counts '
            'are made from', [
                'Item', 'Label, English', 'Label, Luganda', 'Label, Swahili',
                'Label, French', 'Label, German', 'Instance of',
                'Instance of (codes)', 'Located in', 'Located in (code)',
                'Latitude', 'Longitude', 'Image', 'Commons category',
                'English Wikipedia article', 'Luganda Wikipedia article',
                'Swahili Wikipedia article', 'Gender', 'Born', 'Died',
                'Created (estimated year)', 'Has a Luganda label',
                'Included because'], rows,
            {10: 'text', 11: 'text', 18: 'text', 19: 'text', 20: 'text'},
            {0: lambda r: 'https://www.wikidata.org/wiki/' + r[0]},
            {1: 14, 2: 40, 3: 30, 4: 26, 5: 26, 6: 26, 7: 36, 8: 28, 9: 30,
             10: 12, 11: 11, 12: 11, 13: 28, 14: 28, 15: 34, 16: 30, 17: 30,
             18: 11, 19: 8, 20: 8, 21: 12, 22: 12, 23: 26})
    # every aggregate the Wikidata sheet shows, as rows
    wd = data.get('wikidata') or {}
    rows = []
    for key, value in wd.items():
        if isinstance(value, dict):
            for k, v in value.items():
                rows.append([key, k, v])
        elif isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    name = entry.get('name') or entry.get('label') or ''
                    for k, v in entry.items():
                        if k not in ('name', 'label'):
                            rows.append([f'{key}: {name}', k, v])
                elif isinstance(entry, (list, tuple)) and len(entry) == 2:
                    rows.append([key, entry[0], entry[1]])
        else:
            rows.append(['totals', key, value])
    data_sheet(B, ws_measures, 'All the data behind this dashboard: the measures',
               'Every figure the Wikidata sheet reports, as it came from the '
               'Wikidata Query Service', ['Group', 'Measure', 'Value'], rows,
               None, widths={1: 40, 2: 36, 3: 16})


def sheet_projects_data(B, ws, data):
    rows = []
    for r in sorted(data.get('projects', []),
                    key=lambda r: -(r['uganda'] or 0)):
        rows.append([r['project'], r['language'], r['host'],
                     r['content_pages'], r['pages'], r['files'], r['edits'],
                     r['users'], r['active_users'], r['uganda'],
                     r['ugandan'], r['luganda'],
                     (r['uganda'] / r['content_pages'])
                     if r['uganda'] is not None and r['content_pages'] else ''])
    data_sheet(B, ws, 'All the data behind this dashboard: the projects',
               'Every project edition checked, with every count taken',
               ['Project', 'Edition', 'Site', 'Content pages', 'All pages',
                'Files', 'Edits', 'Registered users', 'Active editors',
                'Pages mentioning Uganda', 'Pages mentioning Ugandan',
                'Pages mentioning Luganda', 'Share mentioning Uganda'],
               rows, {3: 'int', 4: 'int', 5: 'int', 6: 'int', 7: 'int',
                      8: 'int', 9: 'int', 10: 'int', 11: 'int', 12: 'pct'},
               widths={1: 22, 2: 14, 3: 26, 4: 14, 5: 14, 6: 12, 7: 16,
                       8: 14, 9: 14, 10: 16, 11: 16, 12: 16, 13: 16})


def sheet_coverage_data(B, ws, arts):
    df = pdata.coverage_table(arts)
    if df is None:
        B.sheet(ws, 'Coverage data', 'Not collected yet.', 8)
        return
    rows = [[r.title, r.qid, r.primary_category, int(r.views_all_time),
             r.quality, int(r.languages), yn.yn_flag(r.lg),
             yn.yn_flag(r.sw), yn.yn_flag(r.commons),
             yn.yn_flag(r.wikiquote), yn.yn_flag(r.wikisource),
             yn.yn_flag(r.wikivoyage), yn.yn_flag(r.wikispecies),
             yn.yn_flag(r.wikinews), yn.yn_flag(r.wikibooks),
             yn.yn_flag(r.wikiversity), yn.yn_flag(r.wiktionary)]
            for r in df.itertuples(index=False)]
    data_sheet(B, ws, 'All the data behind this dashboard: where each article lives',
               'One row per Ugandan Wikipedia article, and which other projects '
               'hold the same subject', [
                   'Article', 'Wikidata item', 'Main group',
                   'Total views, all time', 'Class',
                   'Wikipedia languages with the subject', 'Luganda Wikipedia',
                   'Swahili Wikipedia', 'Commons', 'Wikiquote', 'Wikisource',
                   'Wikivoyage', 'Wikispecies', 'Wikinews', 'Wikibooks',
                   'Wikiversity', 'Wiktionary'], rows, {3: 'int', 5: 'int'},
               {0: lambda r: 'https://en.wikipedia.org/wiki/'
                + r[0].replace(' ', '_'),
                1: lambda r: 'https://www.wikidata.org/wiki/' + r[1]},
               {1: 46, 2: 14, 3: 26, 4: 16, 5: 10, 6: 14})


def wd_growth(B, ws, years, row):
    if not years:
        return
    B.head(ws, row, 'How Wikidata\'s items about Uganda have grown (estimated from item numbers)', 8)
    cum, rows = 0, []
    for y, n in years.items():
        cum += n
        rows.append([y, n, cum])
    end = B.table(ws, row + 1, ['Year', 'Items created', 'Items to date'], rows,
                  {0: 'text', 1: 'int', 2: 'int'})
    ch = B.wb.add_chart({'type': 'column'})
    ch.add_series({'name': 'Items created',
                   'categories': f"='Wikidata'!$B${row + 3}:$B${end + 1}",
                   'values': f"='Wikidata'!$C${row + 3}:$C${end + 1}",
                   'fill': {'color': RED}, 'gap': 40})
    dash.finish_chart(ch, 520, 300, y_fmt='#,##0', x_rotate=-45)
    ws.insert_chart(row + 1, 5, ch)
    B.note(ws, end + 2, 'Wikidata numbers its items in the order they are made, '
           'so an item\'s number says roughly when it was created: the dates of '
           'a few hundred items fix the curve and Uganda\'s items are counted by '
           'number. An estimate, not each item\'s own history.', 44, 8)


def main():
    data, commons = load()
    conn = ug_utils.connect()
    arts = bcf.load(conn)[1]
    conn.close()
    extra = {'commons': pdata.commons(), 'coverage': pdata.coverage(arts),
             'wd': pdata.wikidata_growth(), 'pages': pdata.other_pages()}
    target = os.environ.get('PROJ_OUT') or bcf._free(OUT)
    wb = xlsxwriter.Workbook(target, {'nan_inf_to_errors': True})
    wb.set_properties({
        'title': 'Uganda on the Wikimedia projects',
        'author': 'Wikimedia Community User Group Uganda'})
    B = Book(wb)
    first = os.environ.get('DASH_FIRST')       # test hook: render one sheet
    order = ([first] if first in TABS else []) + [
        t for t in TABS if t != first]
    made = {name: wb.add_worksheet(name) for name in order}
    sheets = {name: made[name] for name in TABS}
    sheet_overview(B, sheets['Overview'], data, commons, extra)
    if (extra['commons'] or {}).get('years'):
        sheet_commons_full(B, sheets['Commons'], data, extra)
    else:
        sheet_commons(B, sheets['Commons'], data, commons)
    sheet_wikidata(B, sheets['Wikidata'], data, commons)
    wd_growth(B, sheets['Wikidata'], extra['wd'],
              sheets['Wikidata'].dim_rowmax + 3)
    sheet_wikisource(B, sheets['Wikisource'], data)
    sheet_other(B, sheets['Other projects'], data)
    sheet_growth_other(B, sheets['Other projects'], extra,
                       sheets['Other projects'].dim_rowmax + 3)
    sheet_where(B, sheets['Where Uganda lives'], data, extra)
    sheet_luganda(B, sheets['Luganda'], data)
    sheet_needs(B, sheets['Needs work'], data, extra, commons)
    sheet_projects_data(B, sheets['Projects data'], data)
    sheet_coverage_data(B, sheets['Coverage data'], arts)
    for name, colour in (('Overview', BLUE), ('Commons', GREEN),
                         ('Wikidata', RED), ('Wikisource', BLUE),
                         ('Other projects', GREY), ('Where Uganda lives', GREEN),
                         ('Luganda', GREEN), ('Needs work', RED),
                         ('Projects data', GREY),
                         ('Coverage data', GREY)):
        sheets[name].set_tab_color(colour)
    sheets[first if first in TABS else 'Overview'].activate()
    sheet_tidy.tidy(wb)
    wb.close()
    print(f'wrote {target}')


if __name__ == '__main__':
    main()
