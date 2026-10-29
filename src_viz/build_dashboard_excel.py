# -*- coding: utf-8 -*-
"""The client dashboard, as one Excel workbook.

A presentation piece built on the same article universe as the category files,
so every figure agrees with them. The Dashboard sheet is interactive without
macros: a dropdown names a category and every tile, chart and the top-ten
table are formulas over the Data sheet that respond to it. The other sheets
are the supporting evidence, each with its own charts.

Choosing a group counts every article filed in it, as the category lists do, so
an article in three groups is in all three and the groups add up to more than
the total; "All categories" counts each article once (docs/03-methodology.md).

Colours are the Wikimedia Community User Group Uganda logo's: blue #006699,
red #990000, green #339966 and the two greys.

    python src_viz/build_dashboard_excel.py
"""

import os
import sys

import pandas as pd
import xlsxwriter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src_data'))

import build_category_files as bcf      # noqa: E402
import category_profiles as cp
import history          # noqa: E402
import yn               # noqa: E402
import sheet_tidy       # noqa: E402
import luganda          # noqa: E402
import config                           # noqa: E402
import ug_utils                         # noqa: E402

# DASH_TARGET=sheets builds the copy meant for Google Sheets. It keeps every
# formula and chart and drops what Sheets cannot use: data bars become colour
# scales, links to folders on a PC become plain names (or a link to the Drive
# folder when DRIVE_FOLDER is set), and sheet protection goes.
SHEETS = os.environ.get('DASH_TARGET') == 'sheets'
DRIVE_FOLDER = os.environ.get('DRIVE_FOLDER', '')
OUT = os.environ.get('DASH_OUT') or os.path.join(
    config.PROJECT_PATH, 'Uganda Content Gap Dashboard (Google Sheets).xlsx'
    if SHEETS else 'Uganda Content Gap Dashboard (Excel).xlsx')

if SHEETS:
    from xlsxwriter.worksheet import Worksheet

    _conditional_format = Worksheet.conditional_format
    _write_url = Worksheet.write_url

    def _colour_scale(self, *args):
        options = args[-1]
        if isinstance(options, dict) and options.get('type') == 'data_bar':
            scale = {'type': '2_color_scale', 'min_color': '#FFFFFF',
                     'max_color': options.get('bar_color', '#9CC3D5'),
                     'min_type': options.get('min_type', 'min'),
                     'max_type': options.get('max_type', 'max')}
            if 'min_value' in options:
                scale['min_value'] = options['min_value']
            if 'max_value' in options and options.get('max_type') == 'num':
                scale['max_value'] = options['max_value']
            args = args[:-1] + (scale,)
        return _conditional_format(self, *args)

    def _link(self, row, col, url, cell_format=None, string=None, tip=None):
        if isinstance(url, str) and url.startswith('external:'):
            if DRIVE_FOLDER:
                return _write_url(self, row, col, DRIVE_FOLDER, cell_format,
                                  string, 'Open the Drive folder')
            return self.write(row, col, string or url[9:], cell_format)
        return _write_url(self, row, col, url, cell_format, string, tip)

    Worksheet.conditional_format = _colour_scale
    Worksheet.write_url = _link
LOGO = os.path.join(config.PROJECT_PATH, 'assets', 'img', 'wcugu_mark.png')
ANALYSIS_DIR = os.path.join(config.DATA_PATH, 'analysis')

BLUE, RED, GREEN = '#006699', '#990000', '#339966'
DARK, GREY, SILVER = '#484848', '#808080', '#BFBFBF'
TINT_BLUE, TINT_GREEN, TINT_RED, PAPER = ('#E5F0F5', '#E9F3EE', '#F5E6E6',
                                          '#F6F7F8')
FONT = 'Calibri'
WIKI = 'https://en.wikipedia.org/wiki/{}'
WIKIDATA = 'https://www.wikidata.org/wiki/{}'

ALL = 'All categories'
DEFAULT = os.environ.get('DASH_DEFAULT', ALL)
YEARS = bcf.YEARS
YEAR_LABEL = {'2015': '2015 (Jul-Dec)', '2026': '2026 (Jan-Sep)'}
CLASS_GROUPS = ('Stub', 'Start', 'C', 'B or better')
LITTLE_TOTAL = 1000           # read fewer times than this in all
ACTIONS = ('Expand', 'Expand, then translate', 'Translate to Luganda', 'OK')


def class_group(c):
    if c in ('B', 'GA', 'A', 'FA', 'FL'):
        return 'B or better'
    return c if c in ('Stub', 'Start', 'C') else 'Unknown'


# --------------------------------------------------------------------- data
def load():
    conn = ug_utils.connect()
    members, arts, high = bcf.load(conn)
    ed_old = pd.read_sql('SELECT * FROM ug_editors', conn)
    ed_new = pd.read_sql('SELECT * FROM ug_editors_recent', conn)
    conn.close()
    arts = arts[arts['title'].isin(members['title'])].copy()
    for col in ('is_human', 'stub', 'has_image', 'has_luganda', 'refs',
                'bytes', 'expansion_gap_bytes', 'high_views_low_quality'):
        arts[col] = arts[col].fillna(0)
    arts['class_group'] = arts['quality'].map(class_group)
    arts = arts.sort_values('views_all_time', ascending=False).reset_index(
        drop=True)
    # One row per article. The paths column lists every category above it,
    # between bars, so choosing any category at any level is a single
    # wildcard match, and no article is repeated to make it work.
    anc = bcf.ANCESTORS
    held = members[members['title'].isin(arts['title'])]
    tops_of = held.groupby('title')['top'].agg(set).to_dict()

    def paths(row):
        names = set(anc.get(row['title'], ((), {}))[1])
        names |= tops_of.get(row['title'], set())
        return '|' + '|'.join(sorted(names)) + '|'

    arts['paths'] = arts.apply(paths, axis=1)
    data = arts.copy()
    data['category'] = data['primary_category']
    data['primary'] = 1
    return members, arts, data, high, ed_old, ed_new


def read_analysis(prefix):
    # A copy the author had open in Excel is written beside it as _NEW, so
    # the newest of the matches is the current one.
    found = [os.path.join(ANALYSIS_DIR, n) for n in os.listdir(ANALYSIS_DIR)
             if n.startswith(prefix + '_') and n.endswith('.csv')]
    if not found:
        return pd.DataFrame()
    return pd.read_csv(max(found, key=os.path.getmtime))


# ------------------------------------------------------------------- styles
class Styles:
    def __init__(self, wb):
        self.wb = wb
        self.cache = {}

    def __call__(self, **kw):
        if kw.get('bg_color') in ('#FFFFFF', PAPER) and 'border' not in kw:
            kw = dict(kw, border=1, border_color='#D5DADF')
        key = tuple(sorted(kw.items()))
        if key not in self.cache:
            base = {'font_name': FONT, 'font_size': 10, 'font_color': DARK,
                    'valign': 'vcenter'}
            base.update(kw)
            self.cache[key] = self.wb.add_format(base)
        return self.cache[key]


# ----------------------------------------------------------------- builders
def banner(ws, S, title, subtitle, width_cols, logo=True, start=1,
           indent=9):
    """The band across the top of a sheet.

    White, with a blue rule beneath, so the whole logo shows: its blue ring and
    red arc vanish on a blue band. `start` is the column the text begins in and
    `indent` keeps it clear of the logo when that column is wide.
    """
    last = width_cols
    ws.set_row(0, 32)
    ws.set_row(1, 24)
    ws.set_row(2, 20)
    rule = dict(bottom=5, bottom_color=BLUE)
    for r in range(3):
        for c in range(last + 1):
            ws.write_blank(r, c, None, S(bg_color='#FFFFFF', border=0,
                                         **(rule if r == 2 else {})))

    def line(row, text, **kw):
        extra = rule if row == 2 else {}
        fmt = S(bg_color='#FFFFFF', border=0, indent=indent, **extra, **kw)
        if last > start:
            ws.merge_range(row, start, row, last, text, fmt)
        else:
            ws.write(row, start, text, fmt)

    line(0, title, font_color=BLUE, font_size=22, bold=True)
    line(1, subtitle, font_color='#5F6B73', font_size=11)
    line(2, 'Wikimedia Community User Group Uganda', font_color=GREEN,
         font_size=9, italic=True)
    if logo and os.path.exists(LOGO):
        ws.insert_image(0, 1, LOGO, {'x_scale': 0.13, 'y_scale': 0.13,
                                     'x_offset': 6, 'y_offset': 4,
                                     'object_position': 1})


NAV = (('Dashboard', 'Dashboard', 2), ('Categories', 'Categories', 1),
       ('All categories', 'All categories', 2),
       ('Representation', 'Representation', 2),
       ('Readership', 'Readership', 2), ('Editors', 'Editors', 1),
       ('Editor community', 'Editor community', 2),
       ('Priorities', 'Priorities', 1), ('Gaps', 'Gaps', 1),
       ('Luganda', 'Luganda', 1))


def nav(ws, S, row, current, first_col=1):
    """The tab bar on the Dashboard; other sheets get a way back."""
    ws.set_row(row, 22)
    if current != 'Dashboard':
        for c in range(first_col, first_col + 6):
            ws.write_blank(row, c, None, S(bg_color=PAPER))
        ws.write_url(row, first_col, "internal:'Dashboard'!A1", S(
            font_color=BLUE, underline=1, bold=True, bg_color=PAPER),
            string='\u25C2  Back to the Dashboard')
        return
    col = first_col
    for label, sheet, span in NAV:
        end = col + span - 1
        if sheet == current:
            fmt = S(bold=True, font_color='#FFFFFF', bg_color=GREEN,
                    align='center')
            if span > 1:
                ws.merge_range(row, col, row, end, label, fmt)
            else:
                ws.write(row, col, label, fmt)
        else:
            blank = S(bg_color=PAPER)
            if span > 1:
                ws.merge_range(row, col, row, end, '', blank)
            ws.write_url(row, col, f"internal:'{sheet}'!A1", S(
                font_color=BLUE, underline=1, align='center',
                bg_color=PAPER), string=label)
        col = end + 1


def heading(ws, S, row, c0, c1, text):
    fmt = S(bold=True, font_size=12, font_color=BLUE, bottom=2,
            bottom_color=BLUE)
    ws.merge_range(row, c0, row, c1, text, fmt)


def note(ws, S, row, c0, c1, text, height=30):
    ws.set_row(row, height)
    ws.merge_range(row, c0, row, c1, text, S(
        italic=True, font_color=GREY, text_wrap=True, valign='top'))


def styled_chart(wb, kind, subtype=None, **extra):
    spec = {'type': kind}
    if subtype:
        spec['subtype'] = subtype
    return wb.add_chart(spec)


def finish_chart(ch, width, height, legend=None, x_name=None, y_name=None,
                 y_fmt=None, x_rotate=None, gap=60):
    ch.set_title({'none': True})
    ch.set_size({'width': width, 'height': height})
    ch.set_chartarea({'border': {'none': True}, 'fill': {'color': '#FFFFFF'}})
    ch.set_plotarea({'fill': {'none': True}})
    if legend:
        ch.set_legend({'position': legend, 'font': {'name': FONT, 'size': 9,
                                                    'color': DARK}})
    else:
        ch.set_legend({'none': True})
    xa = {'num_font': {'name': FONT, 'size': 9, 'color': DARK},
          'line': {'color': SILVER}, 'major_tick_mark': 'none'}
    if x_rotate is not None:
        xa['num_font']['rotation'] = x_rotate
    ya = {'num_font': {'name': FONT, 'size': 9, 'color': GREY},
          'major_gridlines': {'visible': True,
                              'line': {'color': '#E4E6E8', 'width': 0.75}},
          'line': {'none': True}, 'major_tick_mark': 'none', 'min': 0}
    if y_fmt:
        ya['num_format'] = y_fmt
    ch.set_x_axis(xa)
    ch.set_y_axis(ya)


# ------------------------------------------------------------- the workbook
def pair(wb, ws, row, col, bars, lines, width, height, y_fmt,
         y2_color=None):
    """Bars with one or more lines. In Excel the lines share the chart, on a
    right-hand axis where a series asks for one. Google Sheets drops or
    misreads series on a second axis, so there the lines go in a second chart
    beside the bars, each on its own axis."""
    first = styled_chart(wb, 'column')
    for spec in bars:
        first.add_series(spec)
    if not SHEETS:
        second = styled_chart(wb, 'line')
        for spec in lines:
            second.add_series(spec)
        first.combine(second)
        finish_chart(first, width, height, legend='bottom', y_fmt=y_fmt,
                     x_rotate=-45)
        if any(sp.get('y2_axis') for sp in lines):
            second.set_y2_axis({
                'num_font': {'name': FONT, 'size': 9,
                             'color': y2_color or GREY},
                'num_format': '#,##0', 'line': {'none': True},
                'major_gridlines': {'visible': False}})
        ws.insert_chart(row, col, first)
        return
    half = width // 2 - 6
    finish_chart(first, half, height, legend='bottom', y_fmt=y_fmt,
                 x_rotate=-45)
    ws.insert_chart(row, col, first)
    second = styled_chart(wb, 'line')
    for spec in lines:
        second.add_series({k: v for k, v in spec.items() if k != 'y2_axis'})
    finish_chart(second, half, height, legend='bottom', y_fmt='#,##0',
                 x_rotate=-45)
    ws.insert_chart(row, col, second, {'x_offset': half + 10})


def build():
    members, arts, data, high, ed_old, ed_new = load()
    n = len(arts)
    rows_n = len(data)
    last = rows_n + 1                                  # last Data row, 1-based
    tops = [t for t in cp.load_tree()[0] + [cp.OTHER, cp.FOUND,
                                            cp.UNCATEGORISED]
            if t in set(arts['primary_category'])]
    target = bcf._free(OUT)                 # Excel locks a workbook it has open
    wb = xlsxwriter.Workbook(target, {'nan_inf_to_errors': True})
    wb.set_properties({
        'title': 'Uganda Content Gap Dashboard',
        'subject': 'Content gap analysis of English Wikipedia articles about '
                   'Uganda',
        'author': 'Wikimedia Community User Group Uganda',
        'comments': 'Interactive: choose a category on the Dashboard sheet.'})
    S = Styles(wb)

    sh = {}
    order = ['Dashboard', 'Categories', 'All categories', 'Representation',
             'Readership',
             'Editors', 'Editor community', 'Priorities', 'Gaps', 'Luganda',
             'Data', 'Calc', 'Lists']
    first = os.environ.get('DASH_FIRST')       # test hook: render one sheet
    if first in order:
        order.remove(first)
        order.insert(0, first)
    for name in order:
        sh[name] = wb.add_worksheet(name)
    for name, colour in (('Dashboard', BLUE), ('Categories', BLUE),
                         ('All categories', BLUE),
                         ('Representation', GREEN), ('Readership', BLUE),
                         ('Editors', GREEN), ('Editor community', GREEN), ('Priorities', RED),
                         ('Gaps', RED), ('Luganda', GREEN),
                         ('Data', SILVER)):
        sh[name].set_tab_color(colour)
    sh['Dashboard'].activate()

    # ------------------------------------------------------------- Data
    ws = sh['Data']
    cols = (['Article', 'Category', 'Class group', 'Class', 'Stub',
             'Total views, all time', 'Luganda article', 'Lead image', 'Person',
             'Gender', 'Living / deceased', 'Created']
            + [f'Views {YEAR_LABEL.get(y, y)}' for y in YEARS]
            + [f'Luganda views {YEAR_LABEL.get(y, y)}' for y in YEARS]
            + ['Action', 'High views low quality', 'Bytes to reach C',
               'References', 'Wikipedia categories', 'Why it is about Uganda', 'Key',
               'Counts toward the total', 'Categories (every level)'])
    head = S(bold=True, font_color='#FFFFFF', bg_color=BLUE, text_wrap=True)
    ws.set_row(0, 32)
    for c, h in enumerate(cols):
        ws.write(0, c, h, head)
    plain = S()
    numf = S(num_format='#,##0')
    for i, r in enumerate(data.itertuples(index=False)):
        row = i + 1
        ws.write_string(row, 0, r.title, plain)
        ws.write_string(row, 1, r.category, plain)
        ws.write_string(row, 2, r.class_group, plain)
        ws.write_string(row, 3, r.quality, plain)
        ws.write_string(row, 4, yn.yn(r.stub), plain)
        ws.write_number(row, 5, int(r.views_all_time), numf)
        ws.write_string(row, 6, yn.yn(r.has_luganda), plain)
        ws.write_string(row, 7, yn.yn(r.has_image), plain)
        ws.write_string(row, 8, yn.yn(r.is_human), plain)
        ws.write_string(row, 9, yn.na_blank(r.gender if isinstance(
            r.gender, str) else ''), plain)
        ws.write_string(row, 10, yn.na_blank(r.life_status if isinstance(
            r.life_status, str) else ''), plain)
        if pd.notna(r.created_year):
            ws.write_number(row, 11, int(r.created_year), plain)
    for j, y in enumerate(YEARS):
        ws.write_column(1, 12 + j, [int(v) for v in data[f'v_{y}']], numf)
        ws.write_column(1, 24 + j, [int(v) for v in data[f'lg_{y}']], numf)
    ws.write_column(1, 36, list(data['action']), plain)
    ws.write_column(1, 37, [yn.yn(v) for v in data['high_views_low_quality']],
                    plain)
    ws.write_column(1, 38, [int(v) for v in data['expansion_gap_bytes']],
                    numf)
    ws.write_column(1, 39, [int(v) for v in data['refs']], plain)
    ws.write_column(1, 40, list(data['direct_cats'].fillna('')), plain)
    ws.write_column(1, 41, list(data['basis']), plain)
    ws.write_column(1, 43, [int(v) for v in data['primary']], plain)
    ws.write_column(1, 44, list(data['paths']), plain)
    for i, v in enumerate(data['views_all_time']):
        row = i + 1
        ws.write_formula(
            row, 42, f'=IF(OR(Calc!$B$2="{ALL}",ISNUMBER(FIND("|"&'
                     f'Calc!$B$2&"|",AS{row + 1}))),'
                     f'F{row + 1}+ROW()/10000000,0)', plain,
            int(v) + (row + 1) / 1e7)
    ws.freeze_panes(1, 1)
    ws.print_area(0, 0, 40, 11)          # a printout of 8,879 rows helps no one
    ws.autofilter(0, 0, rows_n, len(cols) - 1)
    ws.set_column(0, 0, 38)
    ws.set_column(1, 1, 30)
    ws.set_column(2, 11, 12)
    ws.set_column(12, 35, 11)
    ws.set_column(36, 36, 24)
    ws.set_column(37, 41, 14)
    ws.set_column(41, 41, 34)
    ws.set_column(42, 43, 14)
    ws.set_column(44, 44, 40)
    ws.set_column(45, 45, 16)

    def name(label, col_a, col_b=None):
        end = col_b or col_a
        wb.define_name(label, f"=Data!${col_a}$2:${end}${last}")

    name('d_article', 'A'); name('d_cat', 'B'); name('d_cgrp', 'C')
    name('d_stub', 'E'); name('d_v12', 'F'); name('d_lg', 'G')
    name('d_img', 'H'); name('d_person', 'I'); name('d_gender', 'J')
    name('d_life', 'K'); name('d_created', 'L'); name('d_views', 'M', 'X')
    name('d_lgviews', 'Y', 'AJ'); name('d_action', 'AK')
    name('d_hl', 'AL'); name('d_gap', 'AM'); name('d_key', 'AQ')
    name('d_paths', 'AS')

    # ------------------------------------------------------------ Lists
    idx_path = os.path.join(config.PROJECT_PATH, 'all_categories',
                            '_Category_index.csv')
    cat_index = (pd.read_csv(idx_path) if os.path.exists(idx_path)
                 else pd.DataFrame(columns=['Category', 'Group', 'Articles']))
    cat_index['Group'] = cat_index['Group'].fillna('')
    size_of = dict(zip(cat_index['Category'], cat_index['Articles']))
    anc = bcf.ANCESTORS

    groups = [ALL] + tops
    ws = sh['Lists']
    ws.write(0, 0, 'Group', S(bold=True))
    ws.write(0, 1, 'List', S(bold=True))
    for i, g in enumerate(groups):
        ws.write(i + 1, 0, g)
        if g == ALL:
            # With no group chosen the list offers every category, so the
            # dropdown is never empty and any category is one pick away.
            subs = list(cat_index['Category'])
        elif g in (cp.FOUND, cp.UNCATEGORISED):
            subs = []
        else:
            mine = cat_index[cat_index['Group'].map(
                lambda v: g in [x.strip() for x in v.split(';')])
                & (cat_index['Category'] != g)]
            subs = list(mine.sort_values(['Articles', 'Category'],
                                         ascending=[False, True])['Category'])
        if g.startswith('Sport') and g != 'Sport in Uganda':
            subs = [c for c in subs if c != g]
        subs = sorted(set(subs), key=lambda c: (-size_of.get(c, 0), c))
        col = 3 + i
        ws.write(0, col, g, S(bold=True))
        for k, c in enumerate(subs):
            ws.write(1 + k, col, c)
        letter = xlsxwriter.utility.xl_col_to_name(col)
        address = f'Lists!${letter}$2:${letter}${max(2, len(subs) + 1)}'
        ws.write(i + 1, 1, address)
    ws.hide()

    # ------------------------------------------- Calc: the formulas
    ws = sh['Calc']
    group_cell, sub_cell = 'Dashboard!$D$6', 'Dashboard!$L$6'
    sel_cell = 'Calc!$B$2'
    DEFAULT_SUB = os.environ.get('DASH_SUB', '')
    effective = DEFAULT_SUB or DEFAULT
    ws.write(0, 0, 'criteria')
    ws.write_formula(
        0, 1, '=IF(B2="%s","*","*|"&SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(B2,'
              '"~","~~"),"*","~*"),"?","~?")&"|*")' % ALL, None,
        '*' if effective == ALL else f'*|{effective}|*')
    ws.write(1, 0, 'selection')
    if SHEETS:
        selection = f'=IF({sub_cell}="",{group_cell},{sub_cell})'
    else:
        selection = (f'=IF(OR({sub_cell}="",COUNTIF(INDIRECT(VLOOKUP('
                     f'{group_cell},Lists!$A$2:$B$40,2,FALSE)),{sub_cell})=0)'
                     f',{group_cell},{sub_cell})')
    ws.write_formula(1, 1, selection, None, effective)

    crit = 'Calc!$B$1'
    cnt = arts            # default selection is everything

    # quality groups
    ws.write(3, 0, 'Quality'); ws.write(3, 1, 'Articles')
    for i, g in enumerate(CLASS_GROUPS):
        ws.write(4 + i, 0, g)
        ws.write_formula(4 + i, 1,
                         f'=COUNTIFS(d_paths,$B$1,d_cgrp,A{5 + i})', None,
                         int((cnt['class_group'] == g).sum()))
    # views per year
    ws.write(10, 0, 'Year'); ws.write(10, 1, 'English')
    ws.write(10, 2, 'Luganda')
    for j, y in enumerate(YEARS):
        ws.write(11 + j, 0, YEAR_LABEL.get(y, y))
        ws.write_formula(11 + j, 1,
                         f'=SUMIFS(INDEX(d_views,0,{j + 1}),d_paths,$B$1)',
                         None, int(cnt[f'v_{y}'].sum()))
        ws.write_formula(11 + j, 2,
                         f'=SUMIFS(INDEX(d_lgviews,0,{j + 1}),d_paths,$B$1)',
                         None, int(cnt[f'lg_{y}'].sum()))
    # created per year
    ws.write(25, 0, 'Created'); ws.write(25, 1, 'Articles')
    created_years = list(range(2001, 2027))
    for j, y in enumerate(created_years):
        ws.write(26 + j, 0, str(y))
        ws.write_formula(26 + j, 1,
                         f'=COUNTIFS(d_paths,$B$1,d_created,{y})', None,
                         int((cnt['created_year'] == y).sum()))
    # people
    ws.write(54, 0, 'People'); ws.write(54, 1, 'Living')
    ws.write(54, 2, 'Deceased'); ws.write(54, 3, 'Unknown')
    genders = (('Women', 'female'), ('Men', 'male'),
               ('Other / unrecorded', 'other / unrecorded'))
    for i, (label, g) in enumerate(genders):
        ws.write(55 + i, 0, label)
        for k, life in enumerate(('living', 'deceased', 'unknown')):
            ws.write_formula(
                55 + i, 1 + k,
                f'=COUNTIFS(d_paths,$B$1,d_gender,"{g}",d_life,"{life}")',
                None, int(((cnt['gender'] == g)
                           & (cnt['life_status'] == life)).sum()))
    # actions
    ws.write(60, 0, 'Action'); ws.write(60, 1, 'Articles')
    for i, a in enumerate(ACTIONS):
        ws.write(61 + i, 0, a)
        ws.write_formula(61 + i, 1,
                         f'=COUNTIFS(d_paths,$B$1,d_action,A{62 + i})', None,
                         int((cnt['action'] == a).sum()))
    # top ten
    ws.write(67, 0, 'Key'); ws.write(67, 1, 'Row')
    prim_rows = data[data['primary'] == 1]
    keys = (prim_rows['views_all_time'] + (prim_rows.index + 2) / 1e7
            ).sort_values(ascending=False)
    for k in range(10):
        r = 68 + k
        ws.write_formula(r, 0, f'=LARGE(d_key,{k + 1})', None,
                         float(keys.iloc[k]))
        ws.write_formula(r, 1, f'=IF(A{r + 1}>0,MATCH(A{r + 1},d_key,0),"")',
                         None, int(keys.index[k]) + 1)
    ws.hide()

    # ------------------------------------------------------- Dashboard
    ws = sh['Dashboard']
    ws.hide_gridlines(1)
    ws.set_zoom(90)
    ws.set_column(0, 0, 2)
    ws.set_column(1, 16, 10.7)
    ws.set_column(17, 17, 2)
    banner(ws, S, 'Uganda Content Gap Analysis',
           'English Wikipedia articles about Uganda: what exists, how good '
           'it is, who reads it and what is missing', 17, start=2, indent=0)
    nav(ws, S, 3, 'Dashboard')
    ws.set_row(4, 8)

    ws.set_row(5, 32)
    pick = S(bold=True, font_size=13, font_color=DARK, bg_color='#FFF8DC',
             border=2, border_color=GREEN, align='center', locked=False)
    ws.merge_range(5, 1, 5, 2, 'SELECT A GROUP  \u25B8',
                   S(bold=True, font_color=BLUE, font_size=11, align='right'))
    ws.merge_range(5, 3, 5, 7, DEFAULT, pick)
    ws.data_validation(5, 3, 5, 7, {
        'validate': 'list', 'source': f'=Lists!$A$2:$A${len(groups) + 1}',
        'input_title': 'Choose a group',
        'input_message': 'The 14 top-level categories, the other groups and '
                         'the sport topics.',
        'error_title': 'Pick from the list',
        'error_message': 'Choose one of the groups in the dropdown.'})
    ws.merge_range(5, 8, 5, 10, 'AND A SUB-CATEGORY  \u25B8',
                   S(bold=True, font_color=BLUE, font_size=11, align='right'))
    ws.merge_range(5, 11, 5, 16, DEFAULT_SUB if 'DEFAULT_SUB' in dir()
                   else '', pick)
    ws.data_validation(5, 11, 5, 16, {
        'validate': 'list',
        # Sheets does not reliably import a list that depends on another
        # cell, so there the sub-category list is one plain range of every
        # category; Excel narrows it to the chosen group.
        'source': (f'=Lists!$D$2:$D${len(cat_index) + 1}' if SHEETS else
                   '=INDIRECT(VLOOKUP($D$6,Lists!$A$2:$B$40,2,FALSE))'),
        'ignore_blank': True,
        'input_title': 'Optional: pick a sub-category',    # 32 characters at most
        'input_message': 'Largest first. With All categories chosen it '
                         'lists every category; with a group chosen, the '
                         'categories beneath it. Clear it to go back.',
        'error_title': 'Not in this group',
        'error_message': 'Choose a sub-category from the list, or clear the '
                         'cell.'})
    ws.set_row(6, 20)
    ws.merge_range(6, 1, 6, 16,
                   ('To use your own selection: File \u25B8 Make a copy. '
                    if SHEETS else '')
                   + 'Pick a group, a sub-category, or both. A category '
                   'counts every article filed in it or beneath it.',
                   S(italic=True, font_color=GREY, font_size=9,
                     align='center'))

    stubs = int(cnt['stub'].sum())
    lg = int(cnt['has_luganda'].sum())
    noimg = int((cnt['has_image'] == 0).sum())
    people = int(cnt['is_human'].sum())
    women = int((cnt['gender'] == 'female').sum())
    men = int((cnt['gender'] == 'male').sum())
    hl = int(cnt['high_views_low_quality'].sum())
    views = int(cnt['views_all_time'].sum())
    tiles = [
        ('ARTICLES', f'=COUNTIFS(d_paths,{crit})', n, '#,##0',
         'about Uganda, counted once', BLUE),
        ('TOTAL VIEWS, ALL TIME', f'=SUMIFS(d_v12,d_paths,{crit})', views,
         '#,##0', 'English Wikipedia, since July 2015', BLUE),
        ('STUBS', f'=IFERROR(COUNTIFS(d_paths,{crit},d_stub,"Y")/'
                  f'COUNTIFS(d_paths,{crit}),0)', stubs / n, '0%',
         'of articles are stubs', RED),
        ('IN LUGANDA', f'=IFERROR(COUNTIFS(d_paths,{crit},d_lg,"Y")/'
                       f'COUNTIFS(d_paths,{crit}),0)', lg / n, '0%',
         'have a Luganda article', GREEN),
        ('NO LEAD IMAGE', f'=IFERROR(COUNTIFS(d_paths,{crit},d_img,"N")/'
                          f'COUNTIFS(d_paths,{crit}),0)', noimg / n, '0%',
         'have no lead image', RED),
        ('PEOPLE', f'=COUNTIFS(d_paths,{crit},d_person,"Y")', people, '#,##0',
         'biographies', BLUE),
        ('WOMEN AMONG PEOPLE',
         f'=IFERROR(COUNTIFS(d_paths,{crit},d_gender,"female")/'
         f'(COUNTIFS(d_paths,{crit},d_gender,"female")+'
         f'COUNTIFS(d_paths,{crit},d_gender,"male")),0)',
         women / max(women + men, 1), '0%', 'of those with a recorded gender',
         GREEN),
        ('READ A LOT, WRITTEN LITTLE',
         f'=COUNTIFS(d_paths,{crit},d_hl,"Y")', hl, '#,##0',
         'high views, still stub or start', RED),
    ]
    ws.set_row(7, 20); ws.set_row(8, 38); ws.set_row(9, 20)
    for i, (label, formula, value, nf, sub, colour) in enumerate(tiles):
        c = 1 + 2 * i
        ws.merge_range(7, c, 7, c + 1, label, S(
            bold=True, font_size=8, font_color=GREY, align='center',
            top=5, top_color=colour, left=1, right=1, left_color='#DADDE0',
            right_color='#DADDE0', bg_color='#FFFFFF'))
        ws.merge_range(8, c, 8, c + 1, '', S(
            font_size=24, bold=True, font_color=colour, align='center',
            num_format=nf, left=1, right=1, left_color='#DADDE0',
            right_color='#DADDE0', bg_color='#FFFFFF'))
        ws.write_formula(8, c, formula, S(
            font_size=24, bold=True, font_color=colour, align='center',
            num_format=nf, left=1, right=1, left_color='#DADDE0',
            right_color='#DADDE0', bg_color='#FFFFFF'), value)
        ws.merge_range(9, c, 9, c + 1, sub, S(
            font_size=8, font_color=GREY, align='center', bottom=1,
            left=1, right=1, bottom_color='#DADDE0', left_color='#DADDE0',
            right_color='#DADDE0', bg_color='#FFFFFF', text_wrap=True))
    ws.set_row(10, 8)

    ws.set_row(11, 36)
    insight = (
        f'="Showing "&{sel_cell}&": "&TEXT(COUNTIFS(d_paths,{crit}),"#,##0")'
        f'&" articles drawing "&TEXT(SUMIFS(d_v12,d_paths,{crit}),"#,##0")'
        f'&" views in total. "&TEXT(IFERROR(COUNTIFS(d_paths,{crit},d_stub,"Y")/'
        f'COUNTIFS(d_paths,{crit}),0),"0%")&" are stubs, "&'
        f'TEXT(IFERROR(COUNTIFS(d_paths,{crit},d_lg,"Y")/COUNTIFS(d_paths,{crit}),'
        f'0),"0%")&" have a Luganda article and "&'
        f'TEXT(IFERROR(COUNTIFS(d_paths,{crit},d_img,"N")/COUNTIFS(d_paths,{crit}),'
        f'0),"0%")&" have no lead image."')
    text = (f'Showing {ALL}: {n:,} articles drawing {views:,} views in total. '
            f'{stubs / n:.0%} are stubs, {lg / n:.0%} have a Luganda article '
            f'and {noimg / n:.0%} have no lead image.')
    ws.merge_range(11, 1, 11, 16, '', S(
        italic=True, font_size=11, font_color=DARK, bg_color=TINT_BLUE,
        text_wrap=True, indent=1))
    ws.write_formula(11, 1, insight, S(
        italic=True, font_size=11, font_color=DARK, bg_color=TINT_BLUE,
        text_wrap=True, indent=1), text)
    ws.set_row(12, 8)

    cw, ch_h = 636, 300
    # chart 1: quality
    heading(ws, S, 13, 1, 8, 'How good are the articles?')
    heading(ws, S, 13, 9, 16, 'How much are they read each year?')
    c1 = styled_chart(wb, 'column')
    c1.add_series({
        'categories': '=Calc!$A$5:$A$8', 'values': '=Calc!$B$5:$B$8',
        'points': [{'fill': {'color': RED}}, {'fill': {'color': GREY}},
                   {'fill': {'color': BLUE}}, {'fill': {'color': GREEN}}],
        'data_labels': {'value': True, 'num_format': '#,##0',
                        'font': {'name': FONT, 'size': 9, 'color': DARK}},
        'gap': 70})
    finish_chart(c1, cw, ch_h)
    ws.insert_chart(14, 1, c1, {'x_offset': 2, 'y_offset': 4})

    c2 = styled_chart(wb, 'column')
    c2.add_series({'name': 'English Wikipedia',
                   'categories': '=Calc!$A$12:$A$23',
                   'values': '=Calc!$B$12:$B$23',
                   'fill': {'color': BLUE}, 'gap': 50})
    l2 = styled_chart(wb, 'line')
    l2.add_series({'name': 'Luganda Wikipedia (right axis)',
                   'categories': '=Calc!$A$12:$A$23',
                   'values': '=Calc!$C$12:$C$23', 'y2_axis': True,
                   'line': {'color': GREEN, 'width': 2.5},
                   'marker': {'type': 'circle', 'size': 6,
                              'fill': {'color': GREEN},
                              'border': {'color': GREEN}}})
    c2.combine(l2)
    finish_chart(c2, cw, ch_h, legend='bottom', y_fmt='0,,"M"', x_rotate=-45)
    l2.set_y2_axis({'num_font': {'name': FONT, 'size': 9, 'color': GREEN},
                    'num_format': '#,##0,"k"', 'line': {'none': True},
                    'major_gridlines': {'visible': False}})
    ws.insert_chart(14, 9, c2, {'x_offset': 2, 'y_offset': 4})

    heading(ws, S, 30, 1, 8, 'When were the articles written?')
    heading(ws, S, 30, 9, 16, 'Who are the people written about?')
    c3 = styled_chart(wb, 'column')
    c3.add_series({'categories': '=Calc!$A$27:$A$52',
                   'values': '=Calc!$B$27:$B$52', 'fill': {'color': BLUE},
                   'gap': 40})
    finish_chart(c3, cw, ch_h, x_rotate=-90)
    ws.insert_chart(31, 1, c3, {'x_offset': 2, 'y_offset': 4})

    c4 = styled_chart(wb, 'bar', 'stacked')
    for col, nm, colour in ((1, 'Living', GREEN), (2, 'Deceased', GREY),
                            (3, 'Date unknown', SILVER)):
        c4.add_series({'name': nm, 'categories': '=Calc!$A$56:$A$58',
                       'values': ['Calc', 55, col, 57, col],
                       'fill': {'color': colour}, 'gap': 60,
                       'data_labels': {'value': True,
                                       'num_format': '#,##0;;',
                                       'font': {'name': FONT, 'size': 9,
                                                'color': '#FFFFFF'}}})
    finish_chart(c4, cw, ch_h, legend='bottom')
    c4.set_y_axis({'reverse': True, 'num_font': {'name': FONT, 'size': 10,
                                                 'color': DARK},
                   'line': {'none': True}, 'major_tick_mark': 'none'})
    c4.set_x_axis({'num_font': {'name': FONT, 'size': 9, 'color': GREY},
                   'major_gridlines': {'visible': True,
                                       'line': {'color': '#E4E6E8'}},
                   'line': {'none': True}})
    ws.insert_chart(31, 9, c4, {'x_offset': 2, 'y_offset': 4})

    heading(ws, S, 47, 1, 8, 'The ten most read articles')
    heading(ws, S, 47, 9, 16, 'What the articles need')
    th = S(bold=True, font_color='#FFFFFF', bg_color=BLUE, align='center')
    ws.write(48, 1, '#', th)
    ws.merge_range(48, 2, 48, 6, 'Article', S(
        bold=True, font_color='#FFFFFF', bg_color=BLUE))
    ws.write(48, 7, 'Views', th)
    ws.write(48, 8, 'Class', th)
    for k in range(10):
        r = 49 + k
        band = TINT_BLUE if k % 2 == 0 else '#FFFFFF'
        ws.write(r, 1, k + 1, S(align='center', bg_color=band, bold=True,
                                font_color=BLUE))
        r_idx = int(keys.index[k])
        title = data.iloc[r_idx]['title']
        ws.merge_range(r, 2, r, 6, '', S(bg_color=band))
        ws.write_formula(
            r, 2, f'=IF(Calc!B{69 + k}="","",INDEX(d_article,Calc!B{69 + k}))',
            S(bg_color=band), title)
        ws.write_formula(
            r, 7, f'=IF(Calc!B{69 + k}="","",INDEX(d_v12,Calc!B{69 + k}))',
            S(bg_color=band, num_format='#,##0', align='right'),
            int(data.iloc[r_idx]['views_all_time']))
        ws.write_formula(
            r, 8, f'=IF(Calc!B{69 + k}="","",INDEX(d_cgrp,Calc!B{69 + k}))',
            S(bg_color=band, align='center'),
            data.iloc[r_idx]['class_group'])

    c5 = styled_chart(wb, 'bar')
    c5.add_series({
        'categories': '=Calc!$A$62:$A$65', 'values': '=Calc!$B$62:$B$65',
        'points': [{'fill': {'color': RED}}, {'fill': {'color': '#C27A7A'}},
                   {'fill': {'color': BLUE}}, {'fill': {'color': GREEN}}],
        'data_labels': {'value': True, 'num_format': '#,##0',
                        'font': {'name': FONT, 'size': 9, 'color': DARK}},
        'gap': 50})
    finish_chart(c5, 636, 270)
    c5.set_y_axis({'reverse': True, 'num_font': {'name': FONT, 'size': 10,
                                                 'color': DARK},
                   'line': {'none': True}, 'major_tick_mark': 'none'})
    c5.set_x_axis({'num_font': {'name': FONT, 'size': 9, 'color': GREY},
                   'major_gridlines': {'visible': True,
                                       'line': {'color': '#E4E6E8'}},
                   'line': {'none': True}})
    ws.insert_chart(48, 9, c5, {'x_offset': 2, 'y_offset': 2})
    note(ws, S, 62, 1, 16,
         'Expand: a stub, start-class or uncited article. Translate: a sound '
         'English article with no Luganda counterpart. Quality is the '
         'WikiProject class where one exists and an estimate from length '
         'otherwise (under 2 KB stub, under 10 KB start, under 25 KB C).', 34)
    ws.set_landscape(); ws.fit_to_pages(1, 0); ws.set_paper(9)
    ws.print_area(0, 0, 63, 17)
    if not SHEETS:
      ws.protect('', {'select_locked_cells': True,
                    'select_unlocked_cells': True, 'objects': False,
                    'format_columns': False, 'format_rows': False})

    # ---------------------------------------------------- Categories
    ws = sh['Categories']
    ws.hide_gridlines(1); ws.set_zoom(90)
    ws.set_column(0, 0, 2); ws.set_column(1, 1, 36)
    ws.set_column(2, 12, 13); ws.set_column(13, 13, 2)
    banner(ws, S, 'Category by category',
           'Every group of articles side by side', 13)
    nav(ws, S, 3, 'Categories')
    ws.set_row(4, 8)
    total_views = arts['views_all_time'].sum()
    rows = []
    for t in tops:
        g = data[data['paths'].str.contains('|' + t + '|', regex=False)]
        ppl = g[g['is_human'] == 1]
        wm = int((ppl['gender'] == 'female').sum())
        known = int(ppl['gender'].isin(['female', 'male']).sum())
        rows.append({
            'Category': t, 'Articles': len(g),
            'Share of articles': len(g) / n,
            'Share of views': g['views_all_time'].sum() / total_views,
            'Stubs': g['stub'].mean(), 'In Luganda': g['has_luganda'].mean(),
            'No lead image': (g['has_image'] == 0).mean(),
            'People': len(ppl),
            'Women among people': wm / known if known >= 20 else None,
            'Read a lot, written little': int(g['high_views_low_quality']
                                              .sum()),
            'Words to reach C': round(
                g['expansion_gap_bytes'].sum() / bcf.BYTES_PER_WORD, -3)})
    cat = pd.DataFrame(rows)
    hdr = S(bold=True, font_color='#FFFFFF', bg_color=BLUE, text_wrap=True,
            align='center', border=1, border_color='#FFFFFF')
    ws.set_row(5, 34)
    for c, h in enumerate(cat.columns):
        ws.write(5, 1 + c, h, hdr)
    fm = {'Articles': '#,##0',
          'Share of articles': '0.0%', 'Share of views': '0.0%',
          'Stubs': '0%', 'In Luganda': '0%', 'No lead image': '0%',
          'People': '#,##0', 'Women among people': '0%',
          'Read a lot, written little': '#,##0', 'Words to reach C': '#,##0'}
    for r, row in cat.iterrows():
        band = '#FFFFFF' if r % 2 else PAPER
        for c, h in enumerate(cat.columns):
            v = row[h]
            if h == 'Category':
                target = f'external:category_files/{cp.slug(v)}.xlsx'
                ws.write_url(6 + r, 1 + c, target,
                             S(font_color=BLUE, underline=1, bg_color=band,
                               bold=True), string=v)
            elif pd.isna(v):
                ws.write(6 + r, 1 + c, '', S(bg_color=band))
            else:
                ws.write_number(6 + r, 1 + c, float(v),
                                S(num_format=fm[h], bg_color=band,
                                  align='right'))
    last_r = 6 + len(cat) - 1
    soft = {'blue': '#9CC3D5', 'red': '#DDA9A9', 'green': '#A7D3BC'}
    for col, colour in ((2, 'blue'), (3, 'blue'), (4, 'blue'), (5, 'red'),
                        (6, 'green'), (7, 'red'), (9, 'green')):
        ws.conditional_format(6, col, last_r, col, {
            'type': 'data_bar', 'bar_color': soft[colour],
            'bar_solid': True, 'min_type': 'num', 'min_value': 0,
            'max_type': 'num' if col in (3, 4, 5, 6, 7, 9) else 'max',
            'max_value': 1})
    ws.autofilter(5, 1, last_r, len(cat.columns))
    ws.freeze_panes(6, 2)
    note(ws, S, last_r + 2, 1, 12,
         'An article is counted in every category it sits in, as in that '
         'category\'s own workbook, so the shares add to more than 100%: '
         f'{n:,} articles in all, each once. Women among people is left '
         'blank where fewer than twenty people have a recorded gender. Click '
         'a category to open its workbook (keep the category_files folder '
         'beside this file).', 46)
    ch = styled_chart(wb, 'bar')
    ch.add_series({'name': 'Share of articles', 'categories': [
        'Categories', 6, 1, last_r, 1], 'values': [
        'Categories', 6, 3, last_r, 3], 'fill': {'color': BLUE}, 'gap': 60})
    ch.add_series({'name': 'Share of views', 'categories': [
        'Categories', 6, 1, last_r, 1], 'values': [
        'Categories', 6, 4, last_r, 4], 'fill': {'color': GREEN}})
    finish_chart(ch, 980, 520, legend='top', y_fmt='0%')
    ch.set_y_axis({'reverse': True, 'num_font': {'name': FONT, 'size': 9,
                                                 'color': DARK},
                   'line': {'none': True}, 'major_tick_mark': 'none'})
    ch.set_x_axis({'num_format': '0%', 'num_font': {'name': FONT, 'size': 9,
                                                    'color': GREY},
                   'major_gridlines': {'visible': True,
                                       'line': {'color': '#E4E6E8'}},
                   'line': {'none': True}})
    heading(ws, S, last_r + 4, 1, 12,
            'Where the readers go compared with where the articles are')
    ws.insert_chart(last_r + 5, 1, ch)
    ws.set_landscape(); ws.fit_to_pages(1, 0)

    # ------------------------------------------------ All categories
    ws = sh['All categories']
    ws.hide_gridlines(1); ws.set_zoom(90)
    ws.set_column(0, 0, 2); ws.set_column(1, 1, 46)
    ws.set_column(2, 3, 30); ws.set_column(4, 13, 12); ws.set_column(14, 14, 2)
    banner(ws, S, 'Every category and sub-category',
           f'{len(cat_index):,} categories with an article about Uganda, each '
           'with its own file', 14)
    nav(ws, S, 3, 'All categories')
    ws.set_row(4, 8)
    note(ws, S, 5, 1, 13,
         'A category counts the articles filed in it and in everything '
         'beneath it. Filter with the arrows on the header row; click a name '
         'to open its file (CSV for every category, a full workbook for the '
         'larger ones; keep the all_categories folder beside this file). To '
         'see one on the Dashboard, choose its group and then pick it in the '
         'sub-category list.', 46)
    cols_ = ['Category', 'Group', 'Parent', 'Articles', 'Filed directly',
             'Share of views', 'Stubs', 'In Luganda', 'No lead image',
             'People', 'Women among people', 'Read a lot, written little',
             'Words to reach C']
    ws.set_row(6, 34)
    for c, h in enumerate(cols_):
        ws.write(6, 1 + c, h, hdr)
    nf = {'Articles': '#,##0', 'Filed directly': '#,##0',
          'Share of views': '0.0%', 'Stubs': '0%', 'In Luganda': '0%',
          'No lead image': '0%', 'People': '#,##0',
          'Women among people': '0%', 'Read a lot, written little': '#,##0',
          'Words to reach C': '#,##0'}
    for r, row in cat_index.reset_index(drop=True).iterrows():
        band = '#FFFFFF' if r % 2 else PAPER
        for c, h in enumerate(cols_):
            v = row[h]
            if h == 'Category':
                ws.write_url(7 + r, 1, f'external:{row["File"]}', S(
                    font_color=BLUE, underline=1, bg_color=band,
                    bold=bool(row.get('Top level'))), string=str(v))
            elif h in ('Group', 'Parent'):
                ws.write(7 + r, 1 + c, '' if pd.isna(v) else str(v),
                         S(bg_color=band, font_color=GREY))
            elif pd.isna(v):
                ws.write(7 + r, 1 + c, '', S(bg_color=band))
            else:
                ws.write_number(7 + r, 1 + c, float(v), S(
                    num_format=nf[h], bg_color=band, align='right'))
    end_r = 7 + len(cat_index) - 1
    for col, colour in ((4, 'blue'), (6, 'blue'), (7, 'red'), (8, 'green'),
                        (9, 'red')):
        ws.conditional_format(7, col, end_r, col, {
            'type': 'data_bar', 'bar_color': {'blue': '#9CC3D5',
                                              'red': '#DDA9A9',
                                              'green': '#A7D3BC'}[colour],
            'bar_solid': True, 'min_type': 'num', 'min_value': 0,
            'max_type': 'num' if col != 4 else 'max', 'max_value': 1})
    ws.autofilter(6, 1, end_r, len(cols_))
    ws.freeze_panes(7, 2)
    ws.set_landscape(); ws.fit_to_pages(1, 0)

    # ------------------------------------------------ Representation
    ws = sh['Representation']
    ws.hide_gridlines(1); ws.set_zoom(90)
    ws.set_column(0, 0, 2); ws.set_column(1, 1, 38)
    ws.set_column(2, 14, 12); ws.set_column(15, 15, 2)
    banner(ws, S, 'Who and what is represented',
           'Women and men, living and deceased, rural and urban, and the four '
           'regions', 15)
    nav(ws, S, 3, 'Representation')
    ws.set_row(4, 8)
    bi1 = read_analysis('BI1')
    r0 = 5
    heading(ws, S, r0, 1, 14, 'Women and men with an article, compared')
    if len(bi1):
        shown = bi1[['Category', 'Women', 'Men', 'Women share', 'Women stubs',
                     'Men stubs', 'Women with lead image',
                     'Men with lead image', 'Women with Luganda',
                     'Men with Luganda', 'Women median views',
                     'Men median views']]
        # A category of nine people says nothing about women and men.
        keep = (shown.index == 0) | ((shown['Women'] + shown['Men']) >= 30)
        shown = shown[keep].reset_index(drop=True)
        ws.set_row(r0 + 1, 44)
        for c, h in enumerate(shown.columns):
            ws.write(r0 + 1, 1 + c, h, hdr)
        for i, row in shown.iterrows():
            band = '#FFFFFF' if i % 2 else PAPER
            for c, h in enumerate(shown.columns):
                v = row[h]
                if h == 'Category':
                    ws.write(r0 + 2 + i, 1 + c, v, S(
                        bg_color=band, bold=(i == 0)))
                elif pd.isna(v):
                    ws.write(r0 + 2 + i, 1 + c, '', S(bg_color=band))
                else:
                    nf = ('#,##0' if h in ('Women', 'Men') or 'views' in h
                          else '0%')
                    ws.write_number(r0 + 2 + i, 1 + c, float(v), S(
                        num_format=nf, bg_color=band, align='right',
                        bold=(i == 0)))
        end = r0 + 2 + len(shown) - 1
        ws.conditional_format(r0 + 2, 4, end, 4, {
            'type': 'data_bar', 'bar_color': GREEN, 'bar_solid': True,
            'min_type': 'num', 'min_value': 0, 'max_type': 'num',
            'max_value': 1})
        ws.conditional_format(r0 + 2, 5, end, 6, {
            'type': '2_color_scale', 'min_color': '#FFFFFF',
            'max_color': '#E3B4B4'})
        note(ws, S, end + 1, 1, 14,
             'Shares are of each group: "Women stubs" is the share of '
             'women\'s articles that are stubs. A person with no recorded '
             'binary gender is left out of the comparison. Categories '
             'with fewer than thirty such people are omitted. Women are less '
             'often stubs and far more often in Luganda than men; they are '
             'the minority of biographies and are read less.', 46)
        # The charts read from the hidden Calc sheet, so the page shows the
        # table and the charts and no scaffolding.
        calc = sh['Calc']
        allp = shown.iloc[0]
        labels = ['Stubs', 'With lead image', 'With Luganda article']
        wvals = [allp['Women stubs'], allp['Women with lead image'],
                 allp['Women with Luganda']]
        mvals = [allp['Men stubs'], allp['Men with lead image'],
                 allp['Men with Luganda']]
        for i, lab in enumerate(labels):
            calc.write(80 + i, 7, lab)
            calc.write_number(80 + i, 8, float(wvals[i]))
            calc.write_number(80 + i, 9, float(mvals[i]))
        labels_ref = ['Calc', 80, 7, 82, 7]
        chg = styled_chart(wb, 'column')
        chg.add_series({'name': 'Women', 'categories': labels_ref,
                        'values': ['Calc', 80, 8, 82, 8],
                        'fill': {'color': GREEN}, 'gap': 80,
                        'data_labels': {'value': True, 'num_format': '0%',
                                        'font': {'name': FONT, 'size': 10}}})
        chg.add_series({'name': 'Men', 'categories': labels_ref,
                        'values': ['Calc', 80, 9, 82, 9],
                        'fill': {'color': BLUE},
                        'data_labels': {'value': True, 'num_format': '0%',
                                        'font': {'name': FONT, 'size': 10}}})
        finish_chart(chg, 690, 300, legend='bottom', y_fmt='0%')
        heading(ws, S, end + 3, 1, 6, 'Women and men on three measures')
        ws.insert_chart(end + 4, 1, chg, {'x_offset': 2, 'y_offset': 4})

        bycat = shown.iloc[1:].dropna(subset=['Women share']).sort_values(
            'Women share')
        for i, (_, r) in enumerate(bycat.iterrows()):
            calc.write(90 + i, 7, r['Category'])
            calc.write_number(90 + i, 8, float(r['Women share']))
        chs = styled_chart(wb, 'bar')
        chs.add_series({'categories': ['Calc', 90, 7, 89 + len(bycat), 7],
                        'values': ['Calc', 90, 8, 89 + len(bycat), 8],
                        'fill': {'color': GREEN}, 'gap': 50,
                        'data_labels': {'value': True, 'num_format': '0%',
                                        'font': {'name': FONT, 'size': 9}}})
        finish_chart(chs, 600, 300, y_fmt='0%')
        chs.set_y_axis({'num_font': {'name': FONT, 'size': 9, 'color': DARK},
                        'line': {'none': True}, 'major_tick_mark': 'none'})
        chs.set_x_axis({'min': 0, 'max': 1, 'num_format': '0%',
                        'num_font': {'name': FONT, 'size': 9, 'color': GREY},
                        'major_gridlines': {'visible': True,
                                            'line': {'color': '#E4E6E8'}},
                        'line': {'none': True}})
        heading(ws, S, end + 3, 8, 14, 'Women among biographies, by category')
        ws.insert_chart(end + 4, 8, chs, {'x_offset': 2, 'y_offset': 4})
        nxt = end + 4 + 17
    else:
        nxt = r0 + 4

    # gender x living, whole corpus
    people = arts[arts['is_human'] == 1]
    heading(ws, S, nxt, 1, 7, 'Living and deceased, by gender')
    ws.write(nxt + 1, 1, 'Gender', hdr)
    for k, h in enumerate(('Living', 'Deceased', 'Date unknown', 'Total')):
        ws.write(nxt + 1, 2 + k, h, hdr)
    for i, (label, g) in enumerate(genders):
        sub = people[people['gender'] == g]
        vals = [int((sub['life_status'] == x).sum())
                for x in ('living', 'deceased', 'unknown')]
        ws.write(nxt + 2 + i, 1, label, S(bold=True))
        for k, v in enumerate(vals + [sum(vals)]):
            ws.write_number(nxt + 2 + i, 2 + k, v, S(num_format='#,##0'))
    note(ws, S, nxt + 5, 1, 7,
         'Living means no death date and born in 1906 or later. Many '
         'Ugandan biographies carry neither date on Wikidata, which is itself '
         'a gap.', 32)

    # regions and urban/rural
    ge8 = read_analysis('GE8')
    bi2 = read_analysis('BI2')
    r1 = nxt + 7
    heading(ws, S, r1, 1, 7, 'Regional balance')
    if len(ge8):
        for c, h in enumerate(['Region', 'Articles', 'Share', 'Stubs',
                               'No lead image', 'With Luganda',
                               'Total views, all time']):
            ws.write(r1 + 1, 1 + c, h, hdr)
        for i, row in ge8.iterrows():
            ws.write(r1 + 2 + i, 1, row['Region'], S(bold=True))
            ws.write_number(r1 + 2 + i, 2, int(row['Articles']),
                            S(num_format='#,##0'))
            ws.write_number(r1 + 2 + i, 3, float(
                row['Share of regional articles']), S(num_format='0%'))
            ws.write_number(r1 + 2 + i, 4, int(row['Stubs']),
                            S(num_format='#,##0'))
            ws.write_number(r1 + 2 + i, 5, int(row['No lead image']),
                            S(num_format='#,##0'))
            ws.write_number(r1 + 2 + i, 6, int(row['With Luganda']),
                            S(num_format='#,##0'))
            ws.write_number(r1 + 2 + i, 7, int(row['Total views, all time']),
                            S(num_format='#,##0'))
        chr_ = styled_chart(wb, 'column')
        chr_.add_series({'categories': ['Representation', r1 + 2, 1,
                                        r1 + 1 + len(ge8), 1],
                         'values': ['Representation', r1 + 2, 3,
                                    r1 + 1 + len(ge8), 3],
                         'points': [{'fill': {'color': BLUE}},
                                    {'fill': {'color': GREEN}},
                                    {'fill': {'color': RED}},
                                    {'fill': {'color': GREY}}],
                         'gap': 70, 'data_labels': {
                             'value': True, 'num_format': '0%',
                             'font': {'name': FONT, 'size': 9}}})
        finish_chart(chr_, 470, 260, y_fmt='0%')
        ws.insert_chart(r1 + 2, 9, chr_)
        note(ws, S, r1 + 7, 1, 7,
             'Articles under each region\'s categories. The Central Region '
             'holds Kampala and most of the writing.', 30)
    r2 = r1 + 20
    heading(ws, S, r2, 1, 7, 'Rural and urban places')
    if len(bi2):
        for c, h in enumerate(['Setting', 'Wikidata items',
                               'With English article',
                               'With Luganda article', 'Share with English']):
            ws.write(r2 + 1, 1 + c, h, hdr)
        for i, row in bi2.iterrows():
            ws.write(r2 + 2 + i, 1, row['Setting'], S(text_wrap=True))
            ws.set_row(r2 + 2 + i, 32)
            ws.write_number(r2 + 2 + i, 2, int(row['Wikidata items']),
                            S(num_format='#,##0'))
            ws.write_number(r2 + 2 + i, 3, int(row['With English article']),
                            S(num_format='#,##0'))
            ws.write_number(r2 + 2 + i, 4, int(row['With Luganda article']),
                            S(num_format='#,##0'))
            ws.write_number(r2 + 2 + i, 5, float(row['Share with English']),
                            S(num_format='0.0%', bold=True, font_color=RED))
        note(ws, S, r2 + 5, 1, 7,
             'Wikidata items tied to Uganda that have an article in any '
             'language. A rural place is far less likely than an urban one to '
             'have an English article.', 32)
    ws.set_landscape(); ws.fit_to_pages(1, 0)

    # -------------------------------------------------- Readership
    ws = sh['Readership']
    ws.hide_gridlines(1); ws.set_zoom(90)
    ws.set_column(0, 0, 2); ws.set_column(1, 1, 30)
    ws.set_column(2, 14, 14); ws.set_column(15, 15, 2)
    banner(ws, S, 'Readership and writing over time',
           'What is read, what is not, and how the content has grown', 13)
    nav(ws, S, 3, 'Readership')
    ws.set_row(4, 8)
    hist_rows = history.history_block(arts, YEARS)[0]['rows']
    wp_rows = {r_[0]: r_ for r_ in history.wikipedians(
        hist_rows[0][0], hist_rows[-1][0])['rows']}
    n_yr = len(hist_rows)
    dy = n_yr - 12 + 17            # rows the longer table and 2nd chart add
    t_end = 7 + n_yr - 1
    heading(ws, S, 5, 1, 12, 'Views against the content we have, by year, '
            'from the first article')
    for c, h in enumerate(['Year', 'English views', 'Luganda views',
                           'English articles created',
                           'English articles in existence',
                           'Luganda articles created',
                           'Luganda articles in existence',
                           'Edits, English', 'Editors, English',
                           'Edits, Luganda', 'Editors, Luganda',
                           'Wikipedians in Uganda: new accounts',
                           'Wikipedians in Uganda: edited that year',
                           'Wikipedians in Uganda: edits']):
        ws.write(6, 1 + c, h, hdr)
    ws.set_row(6, 34)
    for i, r_ in enumerate(hist_rows):
        band = '#FFFFFF' if i % 2 else PAPER
        yr, made, cm, lmade, lcm, ee, eed, le, led, ev, lv = r_
        label = YEAR_LABEL.get(str(yr), YEAR_LABEL.get(yr, yr))
        ws.write(7 + i, 1, label, S(bg_color=band, bold=True))
        wp_ = wp_rows.get(yr)
        for k, v in enumerate((ev, lv, made, cm, lmade, lcm, ee, eed, le,
                               led, wp_[1] if wp_ else 0,
                               wp_[2] if wp_ else 0, wp_[4] if wp_ else 0)):
            if v is None and SHEETS:        # text in a chart range upsets Sheets
                ws.write_blank(7 + i, 2 + k, None, S(bg_color=band))
            elif v is None:
                ws.write(7 + i, 2 + k, 'not recorded',
                         S(bg_color=band, font_color=GREY, align='right'))
            else:
                ws.write_number(7 + i, 2 + k, v, S(num_format='#,##0',
                                                    bg_color=band))
    t_cats = ['Readership', 7, 1, t_end, 1]
    chart_row = t_end + 2
    pair(wb, ws, chart_row, 1,
         [{'name': 'English views (left)', 'categories': t_cats,
           'values': ['Readership', 7, 2, t_end, 2],
           'fill': {'color': BLUE}, 'gap': 50}],
         [{'name': 'English articles in existence (right)',
           'categories': t_cats, 'values': ['Readership', 7, 5, t_end, 5],
           'y2_axis': True, 'line': {'color': RED, 'width': 2.5},
           'marker': {'type': 'circle', 'size': 6, 'fill': {'color': RED},
                      'border': {'color': RED}}},
          {'name': 'Luganda articles in existence (right)',
           'categories': t_cats, 'values': ['Readership', 7, 7, t_end, 7],
           'y2_axis': True,
           'line': {'color': GREEN, 'width': 2.5, 'dash_type': 'dash'}}],
         900, 330, '0,,"M"', RED)
    pair(wb, ws, chart_row + 17, 1,
         [{'name': 'Editors, English', 'categories': t_cats,
           'values': ['Readership', 7, 9, t_end, 9],
           'fill': {'color': BLUE}, 'gap': 50}],
         [{'name': 'Editors, Luganda (right)', 'categories': t_cats,
           'values': ['Readership', 7, 11, t_end, 11], 'y2_axis': True,
           'line': {'color': GREEN, 'width': 2.5}}],
         900, 300, '#,##0', GREEN)
    note(ws, S, chart_row + 34, 1, 12,
         'Articles written, edits and editors come from the edit history of '
         'each page, so they reach back to the first Ugandan article; editors '
         'are registered accounts counted once a year across every article. '
         'Page views are recorded only from July 2015, so earlier years show '
         'none, and the last year is part-way through.', 30)

    heading(ws, S, 39 + dy, 1, 5, 'Readers go where the quality is')
    for c, h in enumerate(['Class', 'Articles', 'Total views',
                           'Views per article']):
        ws.write(40 + dy, 1 + c, h, hdr)
    for i, g in enumerate(CLASS_GROUPS):
        sub = arts[arts['class_group'] == g]
        band = '#FFFFFF' if i % 2 else PAPER
        ws.write(41 + dy + i, 1, g, S(bg_color=band, bold=True))
        ws.write_number(41 + dy + i, 2, len(sub), S(num_format='#,##0',
                                                    bg_color=band))
        ws.write_number(41 + dy + i, 3, int(sub['views_all_time'].sum()),
                        S(num_format='#,##0', bg_color=band))
        ws.write_number(41 + dy + i, 4, float(sub['views_all_time'].mean()),
                        S(num_format='#,##0', bg_color=band, bold=True))
    cq = styled_chart(wb, 'column')
    cq.add_series({'categories': ['Readership', 41 + dy, 1, 44 + dy, 1],
                   'values': ['Readership', 41 + dy, 4, 44 + dy, 4],
                   'points': [{'fill': {'color': RED}},
                              {'fill': {'color': GREY}},
                              {'fill': {'color': BLUE}},
                              {'fill': {'color': GREEN}}], 'gap': 70,
                   'data_labels': {'value': True, 'num_format': '#,##0',
                                   'font': {'name': FONT, 'size': 9}}})
    finish_chart(cq, 460, 260, y_fmt='#,##0')
    ws.insert_chart(39 + dy, 7, cq)
    little = int((arts['views_all_time'] < LITTLE_TOTAL).sum())
    note(ws, S, 46 + dy, 1, 5,
         f'{little:,} articles ({little / n:.0%}) have been read fewer '
         f'than {LITTLE_TOTAL:,} times in all.', 44)

    heading(ws, S, 58 + dy, 1, 12, 'The twenty-five most read articles')
    for c, h in enumerate(['Article', 'Total views', 'Class',
                           'Luganda article', 'Category']):
        ws.write(59 + dy, 1 + c, h, hdr)
    for i in range(25):
        r = arts.iloc[i]
        band = '#FFFFFF' if i % 2 else PAPER
        ws.write_url(60 + dy + i, 1, WIKI.format(r['title'].replace(' ', '_')),
                     S(font_color=BLUE, underline=1, bg_color=band),
                     string=r['title'])
        ws.write_number(60 + dy + i, 2, int(r['views_all_time']),
                        S(num_format='#,##0', bg_color=band))
        ws.write(60 + dy + i, 3, r['class_group'], S(bg_color=band,
                                                align='center'))
        ws.write(60 + dy + i, 4, yn.yn(r['has_luganda']),
                 S(bg_color=band, align='center',
                   font_color=GREEN if r['has_luganda'] else RED))
        ws.merge_range(60 + dy + i, 5, 60 + dy + i, 7, r['primary_category'],
                       S(bg_color=band, font_color=GREY))
    ws.set_landscape(); ws.fit_to_pages(1, 0)

    # ----------------------------------------------------- Editors
    ws = sh['Editors']
    ws.hide_gridlines(1); ws.set_zoom(90)
    ws.set_column(0, 0, 2); ws.set_column(1, 1, 24)
    ws.set_column(2, 11, 14); ws.set_column(12, 12, 2)
    banner(ws, S, 'Editors in Uganda over time',
           'Wikimedia Foundation public data, January 2018 to date', 12)
    nav(ws, S, 3, 'Editors')
    ws.set_row(4, 8)
    heading(ws, S, 5, 1, 11, 'Editors making 5 or more edits a month')
    old = ed_old.copy()
    old['year'] = old['month'].str[:4]
    years = sorted(old['year'].unique())

    def yearly(wiki, level):
        out = []
        for y in years:
            sub = old[(old['year'] == y) & (old['wiki'] == wiki)
                      & (old['activity'] == level)]
            if sub.empty:
                out.append((None, None))
                continue
            m = sub.groupby('month').agg(lo=('editors_low', 'sum'),
                                         hi=('editors_high', 'sum'))
            out.append((float(m['lo'].mean()), float(m['hi'].mean())))
        return out

    en = yearly('enwiki', '5 to 99')
    lgw = yearly('lgwiki', '5 to 99')
    swk = yearly('swwiki', '5 to 99')
    for c, h in enumerate(['Year', 'English: low', 'English: high',
                           'English: middle', 'Luganda: low',
                           'Luganda: high', 'Luganda: middle']):
        ws.write(6, 1 + c, h, hdr)
    ws.set_row(6, 32)
    for i, y in enumerate(years):
        band = '#FFFFFF' if i % 2 else PAPER
        ws.write(7 + i, 1, y, S(bg_color=band, bold=True))
        for k, (series, off) in enumerate(((en, 2), (lgw, 5))):
            lo, hi = series[i]
            if lo is None:
                for t in range(3):
                    ws.write(7 + i, off + t, '', S(bg_color=band))
            else:
                ws.write_number(7 + i, off, lo, S(num_format='0',
                                                  bg_color=band))
                ws.write_number(7 + i, off + 1, hi, S(num_format='0',
                                                      bg_color=band))
                ws.write_number(7 + i, off + 2, (lo + hi) / 2,
                                S(num_format='0', bg_color=band, bold=True))
    cl = styled_chart(wb, 'line')
    end = 7 + len(years) - 1
    cl.add_series({'name': 'English Wikipedia',
                   'categories': ['Editors', 7, 1, end, 1],
                   'values': ['Editors', 7, 4, end, 4],
                   'line': {'color': BLUE, 'width': 3},
                   'marker': {'type': 'circle', 'size': 7,
                              'fill': {'color': BLUE},
                              'border': {'color': BLUE}},
                   'data_labels': {'value': True, 'num_format': '0',
                                   'position': 'above',
                                   'font': {'name': FONT, 'size': 9,
                                            'color': BLUE}}})
    cl.add_series({'name': 'Luganda Wikipedia',
                   'categories': ['Editors', 7, 1, end, 1],
                   'values': ['Editors', 7, 7, end, 7],
                   'line': {'color': GREEN, 'width': 3},
                   'marker': {'type': 'circle', 'size': 7,
                              'fill': {'color': GREEN},
                              'border': {'color': GREEN}},
                   'data_labels': {'value': True, 'num_format': '0',
                                   'position': 'above',
                                   'font': {'name': FONT, 'size': 9,
                                            'color': GREEN}}})
    finish_chart(cl, 900, 320, legend='bottom', y_fmt='0')
    ws.insert_chart(end + 2, 1, cl)
    note(ws, S, end + 19, 1, 11,
         'Counts are published as ranges to protect privacy (for example '
         '41 to 50), so the chart plots the middle of each range averaged '
         'across the year\'s months. Luganda counts below ten are shown by '
         'the Foundation as 1 to 10.', 44)

    rec = ed_new.copy()
    rec['year'] = rec['month'].str[:4]
    r3 = end + 21
    heading(ws, S, r3, 1, 11, 'Casual and new contributors, since mid-2023')
    wikis = (('enwiki', 'English'), ('lgwiki', 'Luganda'),
             ('commonswiki', 'Commons'), ('wikidatawiki', 'Wikidata'))
    ryears = sorted(rec['year'].unique())
    ws.write(r3 + 1, 1, 'Year (monthly average)', hdr)
    for k, (_, lab) in enumerate(wikis):
        ws.write(r3 + 1, 2 + k, f'{lab}: 1-4 edits', hdr)
    ws.set_row(r3 + 1, 32)
    for i, y in enumerate(ryears):
        months = int(rec[rec['year'] == y]['month'].nunique())
        ws.write(r3 + 2 + i, 1, f'{y} ({months} months)', S(bold=True))
        for k, (wk_, _) in enumerate(wikis):
            sub = rec[(rec['year'] == y) & (rec['wiki'] == wk_)
                      & (rec['activity'] == '1 to 4')]
            if sub.empty:
                ws.write(r3 + 2 + i, 2 + k, '')
            else:
                ws.write_number(r3 + 2 + i, 2 + k,
                                float(sub['editors'].mean()),
                                S(num_format='0'))
    cc = styled_chart(wb, 'column')
    for k, ((_, lab), colour) in enumerate(zip(wikis, (BLUE, GREEN, RED,
                                                      GREY))):
        cc.add_series({'name': lab,
                       'categories': ['Editors', r3 + 2, 1,
                                      r3 + 1 + len(ryears), 1],
                       'values': ['Editors', r3 + 2, 2 + k,
                                  r3 + 1 + len(ryears), 2 + k],
                       'fill': {'color': colour}, 'gap': 80})
    finish_chart(cc, 700, 300, legend='bottom', y_fmt='0')
    ws.insert_chart(r3 + 3 + len(ryears), 1, cc)
    note(ws, S, r3 + 21 + len(ryears), 1, 11,
         'This counts editors located in Uganda, not editors of Ugandan '
         'content. Nothing public ties an editor\'s country to the articles '
         'they touched. From mid-2023 the figures carry deliberate noise of a '
         'few editors either way.', 44)
    ws.set_landscape(); ws.fit_to_pages(1, 0)

    # --------------------------------------------------- Priorities
    ws = sh['Priorities']
    ws.hide_gridlines(1); ws.set_zoom(90)
    ws.set_column(0, 0, 2); ws.set_column(1, 1, 7)
    ws.set_column(2, 2, 40); ws.set_column(3, 3, 30)
    ws.set_column(4, 8, 13); ws.set_column(9, 9, 24)
    ws.set_column(10, 10, 22)
    banner(ws, S, 'Where to put the effort',
           'Articles that are read a great deal and are still stubs or '
           'start-class', 10, start=2, indent=4)
    nav(ws, S, 3, 'Priorities')
    ws.set_row(4, 8)
    flagged = arts[arts['high_views_low_quality'] == 1].sort_values(
        'views_all_time', ascending=False).head(400)
    note(ws, S, 5, 1, 10,
         f'{int(arts["high_views_low_quality"].sum()):,} articles are in the '
         f'top quarter of readership (at least {int(high):,} views in total) '
         f'and still a stub or start. The {len(flagged)} most read are '
         f'below; filter by category with the arrows on the header row.', 36)
    ws.set_row(6, 34)
    for c, h in enumerate(['#', 'Article', 'Category', 'Class',
                           'Total views', 'References', 'Luganda',
                           'Words to reach C', 'Action']):
        ws.write(6, 1 + c, h, hdr)
    for i, (_, r) in enumerate(flagged.iterrows()):
        band = '#FFFFFF' if i % 2 else PAPER
        row = 7 + i
        ws.write_number(row, 1, i + 1, S(bg_color=band, font_color=GREY))
        ws.write_url(row, 2, WIKI.format(r['title'].replace(' ', '_')),
                     S(font_color=BLUE, underline=1, bg_color=band),
                     string=r['title'])
        ws.write(row, 3, r['primary_category'], S(bg_color=band))
        ws.write(row, 4, r['quality'], S(bg_color=band, align='center'))
        ws.write_number(row, 5, int(r['views_all_time']),
                        S(num_format='#,##0', bg_color=band))
        ws.write_number(row, 6, int(r['refs']), S(bg_color=band))
        ws.write(row, 7, yn.yn(r['has_luganda']),
                 S(bg_color=band, align='center',
                   font_color=GREEN if r['has_luganda'] else RED))
        ws.write_number(row, 8, round(r['expansion_gap_bytes'] /
                                      bcf.BYTES_PER_WORD, -1),
                        S(num_format='#,##0', bg_color=band))
        ws.write(row, 9, r['action'], S(bg_color=band))
    endp = 7 + len(flagged) - 1
    ws.conditional_format(7, 5, endp, 5, {
        'type': 'data_bar', 'bar_color': '#DDA9A9', 'bar_solid': True})
    ws.autofilter(6, 1, endp, 9)
    ws.freeze_panes(7, 3)
    ws.set_landscape(); ws.fit_to_pages(1, 0)

    # -------------------------------------------------------- Gaps
    ws = sh['Gaps']
    ws.hide_gridlines(1); ws.set_zoom(90)
    ws.set_column(0, 0, 2); ws.set_column(1, 1, 42)
    ws.set_column(2, 7, 16); ws.set_column(8, 8, 2)
    banner(ws, S, 'What is missing', 'Uganda topics with no English '
           'article, and articles in no category', 8)
    nav(ws, S, 3, 'Gaps')
    ws.set_row(4, 8)
    row = 5
    unc = arts[arts['primary_category'] == cp.UNCATEGORISED].sort_values(
        'views_all_time', ascending=False)
    heading(ws, S, row, 1, 7, f'{len(unc)} articles about Uganda that sit in '
                              f'no category')
    for c, h in enumerate(['Article', 'Total views', 'Class',
                           'Luganda article']):
        ws.write(row + 1, 1 + c, h, hdr)
    for i, (_, r) in enumerate(unc.iterrows()):
        band = '#FFFFFF' if i % 2 else PAPER
        ws.write_url(row + 2 + i, 1, WIKI.format(r['title'].replace(' ',
                                                                    '_')),
                     S(font_color=BLUE, underline=1, bg_color=band),
                     string=r['title'])
        ws.write_number(row + 2 + i, 2, int(r['views_all_time']),
                        S(num_format='#,##0', bg_color=band))
        ws.write(row + 2 + i, 3, r['class_group'], S(bg_color=band,
                                                    align='center'))
        ws.write(row + 2 + i, 4, yn.yn(r['has_luganda']),
                 S(bg_color=band, align='center'))
    row = row + 2 + len(unc) + 2
    corpus = pd.read_csv(cp.CORPUS_CSV)
    noen = corpus[corpus['en_title'].isna() & corpus['is_core'].map(yn.is_yes)] \
        .sort_values('sitelink_count', ascending=False).head(150)
    heading(ws, S, row, 1, 7, 'Uganda items with articles in other '
                              'languages but not in English')
    for c, h in enumerate(['Item', 'Languages with an article', 'Luganda',
                           'Swahili', 'Type']):
        ws.write(row + 1, 1 + c, h, hdr)
    for i, (_, r) in enumerate(noen.iterrows()):
        band = '#FFFFFF' if i % 2 else PAPER
        ws.write_url(row + 2 + i, 1, WIKIDATA.format(r['qitem']),
                     S(font_color=BLUE, underline=1, bg_color=band),
                     string=str(r['label']))
        ws.write_number(row + 2 + i, 2, int(r['sitelink_count']),
                        S(bg_color=band))
        ws.write(row + 2 + i, 3, str(r['lg_title']) if pd.notna(
            r['lg_title']) else '', S(bg_color=band))
        ws.write(row + 2 + i, 4, str(r['sw_title']) if pd.notna(
            r['sw_title']) else '', S(bg_color=band))
        ws.write(row + 2 + i, 5, str(r['type_labels']) if pd.notna(
            r['type_labels']) else '', S(bg_color=band, font_color=GREY))
    row = row + 2 + len(noen) + 2
    up3 = read_analysis('UP3')
    if len(up3):
        up3 = up3.head(100)
        heading(ws, S, row, 1, 7, 'Notable people with no English article')
        for c, h in enumerate(['Person', 'Languages with an article',
                               'Gender', 'Born']):
            ws.write(row + 1, 1 + c, h, hdr)
        for i, (_, r) in enumerate(up3.iterrows()):
            band = '#FFFFFF' if i % 2 else PAPER
            ws.write_url(row + 2 + i, 1, WIKIDATA.format(r['qitem']),
                         S(font_color=BLUE, underline=1, bg_color=band),
                         string=str(r['label']))
            ws.write_number(row + 2 + i, 2, int(r['sitelink_count']),
                            S(bg_color=band))
            ws.write(row + 2 + i, 3, str(r['gender']) if pd.notna(
                r['gender']) else '', S(bg_color=band))
            ws.write(row + 2 + i, 4, str(r['date_of_birth'])[:4]
                     if pd.notna(r['date_of_birth']) else '',
                     S(bg_color=band))
    ws.set_landscape(); ws.fit_to_pages(1, 0)

    # ---------------------------------------------- Editor community
    ws = sh['Editor community']
    comm = history.community()
    ws.hide_gridlines(1); ws.set_zoom(90)
    ws.set_column(0, 0, 2); ws.set_column(1, 1, 26)
    ws.set_column(2, 9, 16); ws.set_column(10, 10, 34)
    banner(ws, S, 'The editing community, from the first account to today',
           'Editors who list themselves in Category:Wikipedians in Uganda, '
           'followed through their own edits from the day they created an '
           'account', 10)
    nav(ws, S, 3, 'Editor community')
    ws.set_row(4, 8)
    heading(ws, S, 5, 1, 10, 'The community at a glance')
    c_ed = comm['editors']
    tiles = [('EDITORS IN THE LIST', f'{len(c_ed):,}', 'Category:Wikipedians in Uganda'),
             ('ACTIVE IN THE LAST YEAR', f"{comm['active']:,}",
              f"{comm['active'] / max(len(c_ed), 1):.0%} of them"),
             ('NEW ACCOUNTS THIS YEAR', f"{comm['growth'][-1][1]:,}" if comm['growth'] else '0',
              f"to {comm['today']}"),
             ('MEDIAN ACCOUNT AGE', f"{comm.get('median_age', 0):.1f} years",
              'since the account was created'),
             ('EDITS SO FAR', f"{comm['edits']:,}", 'all of Wikipedia')]
    ws.set_row(6, 20); ws.set_row(7, 34); ws.set_row(8, 18)
    for i, (lab, val, sub) in enumerate(tiles):
        c0, c1 = 1 + i * 2, 2 + i * 2
        ws.merge_range(6, c0, 6, c1, lab, S(font_size=9, bold=True,
                                            font_color=GREY, bg_color=PAPER))
        ws.merge_range(7, c0, 7, c1, val, S(font_size=22, bold=True,
                                            font_color=BLUE, bg_color=PAPER))
        ws.merge_range(8, c0, 8, c1, sub, S(font_size=9, font_color=GREY,
                                            bg_color=PAPER))
    heading(ws, S, 10, 1, 7, 'How the community has grown, year by year')
    for c, h in enumerate(['Year', 'New accounts', 'Accounts to date',
                           'Edited that year', 'Edited 5+ times', 'Edits']):
        ws.write(11, 1 + c, h, hdr)
    ws.set_row(11, 30)
    for i, row_ in enumerate(comm['growth']):
        band = '#FFFFFF' if i % 2 else PAPER
        ws.write(12 + i, 1, row_[0], S(bg_color=band, bold=True))
        for c, v in enumerate(row_[1:]):
            ws.write_number(12 + i, 2 + c, v, S(num_format='#,##0',
                                                 bg_color=band))
    g_end = 12 + len(comm['growth']) - 1
    ec_cats = ['Editor community', 12, 1, g_end, 1]
    pair(wb, ws, g_end + 2, 1,
         [{'name': 'New accounts', 'categories': ec_cats,
           'values': ['Editor community', 12, 2, g_end, 2],
           'fill': {'color': BLUE}, 'gap': 50}],
         [{'name': 'Accounts to date (right)', 'categories': ec_cats,
           'values': ['Editor community', 12, 3, g_end, 3], 'y2_axis': True,
           'line': {'color': RED, 'width': 2.5}},
          {'name': 'Edited that year', 'categories': ec_cats,
           'values': ['Editor community', 12, 4, g_end, 4],
           'line': {'color': GREEN, 'width': 2.5, 'dash_type': 'dash'}}],
         760, 320, '#,##0', RED)
    k0 = g_end + 20
    heading(ws, S, k0, 1, 4, 'Who stayed: accounts by year created')
    for c, h in enumerate(['Created in', 'Accounts', 'Still active',
                           'No longer active']):
        ws.write(k0 + 1, 1 + c, h, hdr)
    for i, row_ in enumerate(comm['cohorts']):
        band = '#FFFFFF' if i % 2 else PAPER
        ws.write(k0 + 2 + i, 1, row_[0], S(bg_color=band, bold=True))
        for c, v in enumerate(row_[1:]):
            ws.write_number(k0 + 2 + i, 2 + c, v, S(num_format='#,##0',
                                                     bg_color=band))
    k_end = k0 + 2 + len(comm['cohorts']) - 1
    ck = styled_chart(wb, 'column', 'stacked')
    ck.add_series({'name': 'Still active',
                   'categories': ['Editor community', k0 + 2, 1, k_end, 1],
                   'values': ['Editor community', k0 + 2, 3, k_end, 3],
                   'fill': {'color': GREEN}, 'gap': 50})
    ck.add_series({'name': 'No longer active',
                   'categories': ['Editor community', k0 + 2, 1, k_end, 1],
                   'values': ['Editor community', k0 + 2, 4, k_end, 4],
                   'fill': {'color': GREY}})
    finish_chart(ck, 520, 300, legend='bottom', y_fmt='#,##0', x_rotate=-45)
    ws.insert_chart(k0, 6, ck)
    l0 = k_end + 3
    heading(ws, S, l0, 1, 10, 'Every editor, from account creation to today')
    heads = ['Editor', 'Account created', 'First edit', 'Latest edit',
             'Account age (years)', 'Years with edits', 'Edits, all of '
             'Wikipedia', 'Status', 'Rights']
    for c, h in enumerate(heads):
        ws.write(l0 + 1, 1 + c, h, hdr)
    ws.set_row(l0 + 1, 30)
    status_col = {'Active': GREEN, 'Quiet': BLUE, 'Inactive': GREY,
                  'No edits': GREY}
    for i, (user, reg, first_, last_, edits_, yrs, status, rights,
            age) in enumerate(c_ed):
        band = '#FFFFFF' if i % 2 else PAPER
        r_ = l0 + 2 + i
        ws.write_url(r_, 1, 'https://en.wikipedia.org/wiki/User:'
                     + user.replace(' ', '_'),
                     S(font_color=BLUE, underline=1, bg_color=band),
                     string=user)
        for c, v in enumerate((reg, first_, last_)):
            ws.write(r_, 2 + c, v, S(bg_color=band, align='center'))
        ws.write_number(r_, 5, age, S(num_format='0.0', bg_color=band))
        ws.write_number(r_, 6, yrs, S(bg_color=band))
        ws.write_number(r_, 7, edits_, S(num_format='#,##0', bg_color=band))
        ws.write(r_, 8, status, S(bg_color=band, bold=True,
                                  font_color=status_col.get(status, GREY)))
        ws.write(r_, 9, rights.replace(',', ', '), S(bg_color=band,
                                                      font_color=GREY))
    ws.autofilter(l0 + 1, 1, l0 + 1 + len(c_ed), 9)
    ws.freeze_panes(5, 0)
    note(ws, S, l0 + len(c_ed) + 3, 1, 10,
         'The list is self-declared (Category:Wikipedians in Uganda), so it '
         'is not every editor in Uganda. Active means an edit in the last '
         'year; quiet, one to three years ago; inactive, longer.', 30)
    ws.set_landscape(); ws.fit_to_pages(1, 0)

    # ------------------------------------------------------- Luganda
    ws = sh['Luganda']
    lg, lg_years = luganda.load()
    lg_hist = luganda.history(lg, lg_years)
    ws.hide_gridlines(1); ws.set_zoom(90)
    ws.set_column(0, 0, 2); ws.set_column(1, 1, 36)
    ws.set_column(2, 12, 15); ws.set_column(13, 13, 2)
    banner(ws, S, 'Luganda Wikipedia on its own',
           'Every article on Luganda Wikipedia: what it has been read in all, '
           'how it has grown, and who has written it', 13)
    nav(ws, S, 3, 'Luganda')
    ws.set_row(4, 8)
    heading(ws, S, 5, 1, 12, 'Luganda Wikipedia at a glance')
    lg_total = len(lg)
    tiles = [('ARTICLES', f'{lg_total:,}', 'every content page'),
             ('TOTAL VIEWS, ALL TIME', f"{int(lg['views_all_time'].sum()):,}",
              'since July 2015'),
             ('WITH A WIKIDATA ITEM', f"{lg['has_wikidata'].mean():.0%}",
              f"{int(lg['has_wikidata'].sum()):,} articles"),
             ('WITH AN ENGLISH ARTICLE', f"{lg['has_english'].mean():.0%}",
              f"{int(lg['has_english'].sum()):,} articles"),
             ('NEVER READ', f"{int((lg['views_all_time'] == 0).sum()):,}",
              'no views since July 2015'),
             ('ABOUT UGANDA', f"{int(lg['about_uganda'].sum()):,}",
              'matching a Ugandan article')]
    ws.set_row(6, 20); ws.set_row(7, 34); ws.set_row(8, 18)
    for i, (lab, val, sub) in enumerate(tiles):
        c0, c1 = 1 + i * 2, 2 + i * 2
        ws.merge_range(6, c0, 6, c1, lab, S(font_size=9, bold=True,
                                            font_color=GREY, bg_color=PAPER))
        ws.merge_range(7, c0, 7, c1, val, S(font_size=22, bold=True,
                                            font_color=BLUE, bg_color=PAPER))
        ws.merge_range(8, c0, 8, c1, sub, S(font_size=9, font_color=GREY,
                                            bg_color=PAPER))
    heading(ws, S, 10, 1, 12, 'Year by year, from the first Luganda article')
    for c, h in enumerate(['Year', 'Articles written', 'Articles in existence',
                           'Views', 'Edits', 'Editors']):
        ws.write(11, 1 + c, h, hdr)
    ws.set_row(11, 30)
    for i, row_ in enumerate(lg_hist):
        band = '#FFFFFF' if i % 2 else PAPER
        for c, v in enumerate(row_):
            if v is None and SHEETS:
                ws.write_blank(12 + i, 1 + c, None, S(bg_color=band))
            elif v is None:
                ws.write(12 + i, 1 + c, 'not recorded',
                         S(bg_color=band, font_color=GREY, align='right'))
            elif c == 0:
                ws.write(12 + i, 1, v, S(bg_color=band, bold=True))
            else:
                ws.write_number(12 + i, 1 + c, v, S(num_format='#,##0',
                                                     bg_color=band))
    l_end = 12 + len(lg_hist) - 1
    lg_cats = ['Luganda', 12, 1, l_end, 1]
    pair(wb, ws, l_end + 2, 1,
         [{'name': 'Articles written', 'categories': lg_cats,
           'values': ['Luganda', 12, 2, l_end, 2],
           'fill': {'color': GREEN}, 'gap': 50}],
         [{'name': 'Articles in existence (right)', 'categories': lg_cats,
           'values': ['Luganda', 12, 3, l_end, 3], 'y2_axis': True,
           'line': {'color': RED, 'width': 2.5}}],
         620, 300, '#,##0', RED)
    pair(wb, ws, l_end + 2, 7,
         [{'name': 'Views', 'categories': lg_cats,
           'values': ['Luganda', 12, 4, l_end, 4],
           'fill': {'color': BLUE}, 'gap': 50}],
         [{'name': 'Editors (right)', 'categories': lg_cats,
           'values': ['Luganda', 12, 6, l_end, 6], 'y2_axis': True,
           'line': {'color': GREEN, 'width': 2.5}}],
         620, 300, '#,##0', GREEN)
    r0 = l_end + 19
    note(ws, S, r0, 1, 12,
         'Views are recorded only from July 2015, so earlier years show none. '
         'Articles written, edits and editors come from each page edit '
         'history and reach back to the first article; editors are registered '
         'accounts counted once a year. The last year is part-way through.',
         32)
    heading(ws, S, r0 + 2, 1, 5, 'How much each article has been read in all')
    for c, h in enumerate(['Total views', 'Articles']):
        ws.write(r0 + 3, 1 + c, h, hdr)
    for i, (lab, val) in enumerate(luganda.buckets(lg)):
        band = '#FFFFFF' if i % 2 else PAPER
        ws.write(r0 + 4 + i, 1, lab, S(bg_color=band, bold=True))
        ws.write_number(r0 + 4 + i, 2, val, S(num_format='#,##0',
                                              bg_color=band))
    c3_ = styled_chart(wb, 'column')
    c3_.add_series({'categories': ['Luganda', r0 + 4, 1, r0 + 8, 1],
                    'values': ['Luganda', r0 + 4, 2, r0 + 8, 2],
                    'fill': {'color': BLUE}, 'gap': 60,
                    'data_labels': {'value': True, 'num_format': '#,##0',
                                    'font': {'name': FONT, 'size': 9}}})
    finish_chart(c3_, 460, 240, y_fmt='#,##0')
    ws.insert_chart(r0 + 2, 5, c3_)
    r1 = r0 + 20
    heading(ws, S, r1, 1, 12, 'The twenty-five most read articles, all time')
    for c, h in enumerate(['Article', 'Total views', 'Created', 'Edits',
                           'English article']):
        ws.write(r1 + 1, 1 + c, h, hdr)
    for i, (_, a) in enumerate(lg.head(25).iterrows()):
        band = '#FFFFFF' if i % 2 else PAPER
        ws.write_url(r1 + 2 + i, 1, 'https://lg.wikipedia.org/wiki/'
                     + a['lg_title'].replace(' ', '_'),
                     S(font_color=BLUE, underline=1, bg_color=band),
                     string=a['lg_title'])
        ws.write_number(r1 + 2 + i, 2, int(a['views_all_time']),
                        S(num_format='#,##0', bg_color=band))
        ws.write(r1 + 2 + i, 3, int(a['created_year'])
                 if a['created_year'] == a['created_year'] else '',
                 S(bg_color=band, align='center'))
        ws.write_number(r1 + 2 + i, 4, int(a['edits']),
                        S(num_format='#,##0', bg_color=band))
        ws.merge_range(r1 + 2 + i, 5, r1 + 2 + i, 7, a['en_article'] or '',
                       S(bg_color=band, font_color=GREY))
    note(ws, S, r1 + 29, 1, 12,
         'The full list, with every year of views, is in the workbook '
         'Luganda Wikipedia Pageviews.xlsx beside this file.', 24)
    ws.set_landscape(); ws.fit_to_pages(1, 0)

    sheet_tidy.tidy(wb)
    wb.close()
    print(f'wrote {OUT}  ({os.path.getsize(OUT) // 1024:,} KB, '
          f'{n:,} articles)')


if __name__ == '__main__':
    build()
