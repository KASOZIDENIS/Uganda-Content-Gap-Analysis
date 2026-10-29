# -*- coding: utf-8 -*-
"""Luganda Wikipedia as a whole: its articles, readership and history.

Shared by the Luganda workbook and the Luganda sheet of the dashboard, so the
two agree. Views are the total for all time
(every month the Pageviews API holds, from July 2015) with each calendar year
beside it; articles written, edits and editors come from the pages' own edit
histories and reach back to the first Luganda article.

The wiki's front page is left out: it is not an article and is far the most
viewed page, so it would dominate every total.
"""

import os
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src_data'))

import config  # noqa: E402

CSV = os.path.join(config.DATA_PATH, 'ug_luganda_pages.csv')
LITTLE = 1000            # read fewer times than this in all


def load():
    """(articles, years) with one row per article, front page removed."""
    df = pd.read_csv(CSV, keep_default_na=False)
    for col in ('about_uganda', 'main_page'):           # Y / N in the file
        df[col] = df[col].astype(str).str.upper().isin(['Y', '1']).astype(int)
    df = df[df['main_page'] == 0].copy()
    years = sorted(int(c[6:]) for c in df.columns
                   if c.startswith('views_') and c[6:].isdigit())
    df['created_year'] = pd.to_numeric(df['created'].str[:4], errors='coerce')
    for col in ('bytes', 'views_all_time', 'edits', 'about_uganda'):
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    df['has_wikidata'] = (df['wikidata'] != '').astype(int)
    df['has_english'] = (df['en_article'] != '').astype(int)
    return df.sort_values(['views_all_time', 'lg_title'],
                          ascending=[False, True]).reset_index(drop=True), years


def history(df, years):
    """One row per year from the first article:
    [year, written, in existence, views or None, edits, editors]."""
    conn = sqlite3.connect(config.DB_FILE)
    edits = dict(conn.execute(
        "SELECT year, SUM(edits) FROM rev_edits WHERE wiki = 'lg' "
        'GROUP BY year'))
    users = dict(conn.execute(
        "SELECT year, COUNT(*) FROM rev_users WHERE wiki = 'lg' AND anon = 0 "
        'GROUP BY year'))
    conn.close()
    made = df['created_year'].dropna().astype(int).value_counts().to_dict()
    first = min(made) if made else years[0]
    last = max(years[-1], max(edits) if edits else years[-1])
    rows, cum = [], 0
    for y in range(first, last + 1):
        cum += made.get(y, 0)
        views = int(df[f'views_{y}'].sum()) if y in years else None
        rows.append([y, int(made.get(y, 0)), cum, views, int(edits.get(y, 0)),
                     int(users.get(y, 0))])
    return rows


def buckets(df):
    """How much each article has been read in all."""
    v = df['views_all_time']
    return [('Never read', int((v == 0).sum())),
            ('1 to 99', int(((v > 0) & (v < 100)).sum())),
            ('100 to 999', int(((v >= 100) & (v < 1000)).sum())),
            ('1,000 to 9,999', int(((v >= 1000) & (v < 10000)).sum())),
            ('10,000 or more', int((v >= 10000).sum()))]


def sizes(df):
    b = df['bytes']
    return [('Under 1,000 bytes', int((b < 1000).sum())),
            ('1,000 to 4,999', int(((b >= 1000) & (b < 5000)).sum())),
            ('5,000 to 19,999', int(((b >= 5000) & (b < 20000)).sum())),
            ('20,000 or more', int((b >= 20000).sum()))]
