# -*- coding: utf-8 -*-
"""Cell formats, tables and charts for the Luganda workbook.

The workbook's own palette (distinct from the dashboard's logo colours, which
the Luganda builder uses for its other elements) and the table and chart
helpers it draws with.
"""

# One palette for the whole workbook, so the charts read as one document.
INK = '#1F2933'
MUTED = '#7B8794'
RULE = '#D9DDE3'
BLUE = '#2A78D6'
ORANGE = '#EB6834'
GREEN = '#1BAF7A'
RED = '#D03B3B'
AMBER = '#E8A33D'
SERIES = (BLUE, ORANGE, GREEN, AMBER, RED, '#8E6FD8', '#5BA8C4', '#B07B4F')


def styles(book):
    """Every cell format the workbook uses, made once."""
    base = {'font_name': 'Calibri', 'font_size': 11}
    return {
        'title': book.add_format(dict(base, font_size=20, bold=True,
                                      font_color=INK)),
        'sub': book.add_format(dict(base, font_size=11, font_color=MUTED,
                                    text_wrap=True, valign='top')),
        'h2': book.add_format(dict(base, font_size=14, bold=True,
                                   font_color=INK)),
        'kpi': book.add_format(dict(base, font_size=26, bold=True,
                                    font_color=INK, align='left')),
        'kpi_alarm': book.add_format(dict(base, font_size=26, bold=True,
                                          font_color=RED, align='left')),
        'kpi_label': book.add_format(dict(base, font_size=10, font_color=MUTED,
                                          align='left')),
        'head': book.add_format(dict(base, bold=True, font_color='#FFFFFF',
                                     bg_color=INK, border=1,
                                     border_color=INK, text_wrap=True,
                                     valign='vcenter')),
        'cell': book.add_format(base),
        'wrap': book.add_format(dict(base, text_wrap=True, valign='top')),
        'num': book.add_format(dict(base, num_format='#,##0')),
        'pct': book.add_format(dict(base, num_format='0.0%')),
        'pct0': book.add_format(dict(base, num_format='0%')),
        'link': book.add_format(dict(base, font_color=BLUE, underline=1)),
        'dim': book.add_format(dict(base, font_color=MUTED)),
        'good': book.add_format(dict(base, font_color=GREEN, bold=True)),
        'bad': book.add_format(dict(base, font_color=RED, bold=True)),
        'note': book.add_format(dict(base, font_size=10, font_color=MUTED,
                                     text_wrap=True, valign='top')),
    }


def table(sheet, fmt, headers, rows, name, start=0, widths=None,
          links=None, numeric=()):
    """Write one Excel table: sortable, filterable, banded.

    `links` maps a column index to a URL template applied to another column's
    value, so a title reads as itself and behaves as a link.
    """
    links = links or {}
    for c, head in enumerate(headers):
        sheet.write(start, c, head, fmt['head'])
    for r, row in enumerate(rows, start + 1):
        for c, value in enumerate(row):
            if c in links and value:
                target, template = links[c]
                url = template.format(str(row[target]).replace(' ', '_'))
                sheet.write_url(r, c, url, fmt['link'], str(value))
            elif c in numeric:
                sheet.write_number(r, c, value or 0, fmt['num'])
            else:
                sheet.write(r, c, value, fmt['cell'])
    sheet.add_table(start, 0, start + len(rows), len(headers) - 1, {
        'name': name, 'style': 'Table Style Light 1',
        'columns': [{'header': h} for h in headers]})
    for c, w in enumerate(widths or []):
        sheet.set_column(c, c, w)
    sheet.freeze_panes(start + 1, 0)
    return start + len(rows)


def pie(book, sheet, title, cats, vals, anchor, points=None):
    chart = book.add_chart({'type': 'doughnut'})
    chart.add_series({
        'name': title, 'categories': cats, 'values': vals,
        'points': points or [{'fill': {'color': SERIES[i % len(SERIES)]}}
                             for i in range(24)],
        'data_labels': {'percentage': True, 'font': {'color': '#FFFFFF',
                                                     'bold': True}},
    })
    chart.set_title({'name': title, 'name_font': {'size': 12, 'color': INK}})
    chart.set_legend({'position': 'right', 'font': {'size': 9}})
    chart.set_chartarea({'border': {'none': True}, 'fill': {'none': True}})
    chart.set_hole_size(55)
    sheet.insert_chart(anchor, chart, {'x_scale': 1.05, 'y_scale': 1.05})
    return chart


def bar(book, sheet, title, cats, vals, anchor, colour=BLUE, horizontal=True,
        x_scale=1.1, y_scale=1.1):
    chart = book.add_chart({'type': 'bar' if horizontal else 'column'})
    chart.add_series({
        'name': title, 'categories': cats, 'values': vals,
        'fill': {'color': colour}, 'border': {'none': True},
        'data_labels': {'value': True, 'font': {'size': 9}},
        'gap': 40,
    })
    chart.set_title({'name': title, 'name_font': {'size': 12, 'color': INK}})
    chart.set_legend({'none': True})
    chart.set_chartarea({'border': {'none': True}, 'fill': {'none': True}})
    chart.set_y_axis({'major_gridlines': {'visible': True,
                                          'line': {'color': RULE}},
                      'num_font': {'size': 9}})
    chart.set_x_axis({'num_font': {'size': 9}})
    sheet.insert_chart(anchor, chart, {'x_scale': x_scale, 'y_scale': y_scale})
    return chart
