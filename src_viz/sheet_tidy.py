# -*- coding: utf-8 -*-
"""Make a workbook end where its data ends.

An empty grid of a thousand rows under a table reads, on a quick look, as if the
sheet were still waiting for its data, and the data is sitting above. Before a
workbook is closed this hides every row below the last one used and every
column beyond the last one used, leaving two spare rows and columns so the end
of the data is plain. Rows and columns that a chart covers are left visible, or
the chart would be squeezed flat.
"""

SPARE_ROWS = 2
SPARE_COLS = 2
LAST_COLUMN = 16383          # XFD


def tidy(wb):
    for ws in wb.worksheets():
        if getattr(ws, 'is_chartsheet', False):
            continue
        last_row = ws.dim_rowmax if ws.dim_rowmax is not None else 0
        last_col = ws.dim_colmax if ws.dim_colmax is not None else 0

        # a chart is cells too: keep the rows and columns under it
        for item in ws.charts:
            row, col, chart = item[0], item[1], item[2]
            x_scale, y_scale = item[5], item[6]
            need_h = chart.height * y_scale + item[4]
            need_w = chart.width * x_scale + item[3]
            r, acc = row, 0
            while acc < need_h:
                if r not in ws.row_sizes:
                    ws.set_row(r, 15)
                acc += ws._size_row(r)
                r += 1
            c, acc = col, 0
            while acc < need_w:
                acc += ws._size_col(c)
                c += 1
            last_row = max(last_row, r - 1)
            last_col = max(last_col, c - 1)

        for r in range(last_row + 1, last_row + 1 + SPARE_ROWS):
            if r not in ws.row_sizes:
                ws.set_row(r, 15)
        ws.set_default_row(hide_unused_rows=True)
        first_hidden = last_col + SPARE_COLS + 1
        if first_hidden <= LAST_COLUMN:
            ws.set_column(first_hidden, LAST_COLUMN, None, None,
                          {'hidden': True})
