# -*- coding: utf-8 -*-
"""One way to write a yes/no answer in every file: Y, N, or N/A.

Y for yes, N for no, N/A where the question does not apply or the answer is
not known. The analysis itself keeps 1 and 0; this is only what a reader sees.
"""

import pandas as pd

Y, N, NA = 'Y', 'N', 'N/A'

# Article-list columns (by heading) holding a yes/no flag, and those where a
# blank means the question does not apply.
FLAG_HEADS = ('Stub', 'Lead image', 'Luganda article', 'Person',
              'High views, low quality')
NA_HEADS = ('Gender', 'Living / deceased')


def yn(value):
    """1/True/'yes' -> Y; 0/False/'no' -> N; blank, NaN or None -> N/A."""
    if value is None:
        return NA
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ('y', 'yes', '1', 'true'):
            return Y
        if v in ('n', 'no', '0', 'false'):
            return N
        return NA
    try:
        if pd.isna(value):
            return NA
    except (TypeError, ValueError):
        pass
    return Y if value else N


def yn_flag(value):
    """As yn(), for a flag where blank is a plain no (it was only ever
    written as 'yes' or left empty)."""
    return Y if yn(value) == Y else N


def na_blank(value):
    """Text that is blank where the question does not apply -> N/A."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return NA
    return NA if str(value).strip() == '' else value


def frame(df):
    """A list's DataFrame (readable headings) with its flags as Y / N / N/A."""
    out = df.copy()
    for h in FLAG_HEADS:
        if h in out.columns:
            out[h] = out[h].map(yn)
    for h in NA_HEADS:
        if h in out.columns:
            out[h] = out[h].map(na_blank)
    return out


def is_yes(value):
    """True for Y / yes / 1 / True however a file or a database wrote it."""
    return yn(value) == Y


def export_frame(df, flags=()):
    """A copy of `df` for a CSV: boolean columns, and the named 0/1 columns,
    written as Y / N (N/A where empty)."""
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == bool or col in flags:
            out[col] = out[col].map(yn)
    return out


def flag_rows(rows, columns):
    """`rows` (tuples) with the 0/1 values in the given positions as Y / N."""
    columns = set(columns)
    return [[yn(v) if i in columns else v for i, v in enumerate(row)]
            for row in rows]
