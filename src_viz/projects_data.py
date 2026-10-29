# -*- coding: utf-8 -*-
"""Figures for the projects dashboard that come from the database: Commons in
full and by year, where each Ugandan article lives across the projects, how
Wikidata's items about Uganda have grown, and the other projects' pages by year.

Each function returns what it can and an empty result when its tables are not
there yet, so the dashboard builds while the data is still being collected.
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src_data'))

import config  # noqa: E402


def connect():
    return sqlite3.connect(os.environ.get('UG_DB') or config.DB_FILE,
                           timeout=60)


def _has(conn, table):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE name = ?",
                             (table,)).fetchone())


def commons():
    """The whole Category:Uganda tree: by year, type, theme and campaign."""
    conn = connect()
    out = {}
    try:
        if not _has(conn, 'commons_ug_cats'):
            return out
        cats = conn.execute(
            'SELECT COUNT(*), SUM(files), MAX(depth), SUM(files = 0 AND '
            'subcats = 0), SUM(files BETWEEN 1 AND 4) FROM commons_ug_cats'
        ).fetchone()
        out['categories'] = {'n': cats[0], 'files': cats[1] or 0,
                             'deepest': cats[2], 'empty_leaves': cats[3] or 0,
                             'thin': cats[4] or 0}
        by_depth = conn.execute('SELECT depth, COUNT(*), SUM(files) FROM '
                                'commons_ug_cats GROUP BY depth ORDER BY depth'
                                ).fetchall()
        out['by_depth'] = [list(r) for r in by_depth]
        if not _has(conn, 'commons_ug_files'):
            return out
        total = conn.execute('SELECT COUNT(*) FROM commons_ug_files').fetchone()[0]
        out['files'] = total
        years = conn.execute(
            "SELECT substr(uploaded, 1, 4) y, COUNT(*), COUNT(DISTINCT uploader),"
            " SUM(size) FROM commons_ug_files WHERE uploaded != '' GROUP BY y "
            'ORDER BY y').fetchall()
        cum, rows = 0, []
        for y, n, u, size in years:
            cum += n
            rows.append([int(y), n, u, cum, round((size or 0) / 1e9, 2)])
        out['years'] = rows
        out['types'] = [list(r) for r in conn.execute(
            "SELECT mediatype, COUNT(*) FROM commons_ug_files GROUP BY "
            'mediatype ORDER BY 2 DESC')]
        ext = {}
        for mt, title in conn.execute(
                'SELECT mediatype, title FROM commons_ug_files'):
            e = title.rsplit('.', 1)[-1].lower() if '.' in title else ''
            ext[(mt, e)] = ext.get((mt, e), 0) + 1
        out['extensions'] = [[mt, '.' + e, n] for (mt, e), n in sorted(
            ext.items(), key=lambda kv: (kv[0][0], -kv[1]))]
        out['themes'] = [list(r) for r in conn.execute(
            'SELECT c.theme, COUNT(DISTINCT f.title), COUNT(DISTINCT c.title) '
            'FROM commons_ug_files f JOIN commons_ug_cats c ON c.title = '
            'f.category GROUP BY c.theme ORDER BY 2 DESC')]
        out['campaigns'] = [list(r) for r in conn.execute(
            "SELECT c.campaign, substr(f.uploaded, 1, 4), COUNT(*) FROM "
            'commons_ug_files f JOIN commons_ug_cats c ON c.title = f.category '
            "WHERE c.campaign != '' AND c.campaign IS NOT NULL GROUP BY 1, 2 "
            'ORDER BY 1, 2')]
        uploaders = conn.execute(
            "SELECT uploader, COUNT(*) n FROM commons_ug_files WHERE uploader "
            "!= '' GROUP BY uploader ORDER BY n DESC").fetchall()
        out['uploaders'] = len(uploaders)
        top10 = sum(n for _, n in uploaders[:10])
        out['top10_share'] = top10 / total if total else 0
        out['one_file_uploaders'] = sum(1 for _, n in uploaders if n == 1)
        used = conn.execute(
            'SELECT SUM(used = 1), SUM(used = 0), SUM(used IS NULL) FROM '
            'commons_ug_files').fetchone()
        out['used'] = {'used': used[0] or 0, 'unused': used[1] or 0,
                       'unchecked': used[2] or 0}
        out['biggest'] = [list(r) for r in conn.execute(
            'SELECT title, files, depth, theme FROM commons_ug_cats '
            'ORDER BY files DESC LIMIT 25')]
        out['recent'] = conn.execute(
            "SELECT COUNT(*) FROM commons_ug_files WHERE uploaded >= "
            "date('now', '-1 year')").fetchone()[0]
    finally:
        conn.close()
    return out


def coverage(arts):
    """How many of the Ugandan Wikipedia articles each other project also
    holds, from their Wikidata items, overall and by main group."""
    import pandas as pd
    conn = connect()
    try:
        if not _has(conn, 'art_sitelinks'):
            return {}
        sl = pd.read_sql('SELECT * FROM art_sitelinks', conn)
    finally:
        conn.close()
    df = arts[['title', 'qid', 'primary_category', 'views_all_time',
               'has_luganda']].merge(sl, on='qid', how='left')
    have = df['languages'].notna()
    df = df[have]
    cols = [('Commons', 'commons'), ('Wikiquote', 'wikiquote'),
            ('Wikisource', 'wikisource'), ('Wikivoyage', 'wikivoyage'),
            ('Wikispecies', 'wikispecies'), ('Wikinews', 'wikinews'),
            ('Wikibooks', 'wikibooks'), ('Wikiversity', 'wikiversity'),
            ('Wiktionary', 'wiktionary'), ('Luganda Wikipedia', 'lg'),
            ('Swahili Wikipedia', 'sw')]
    out = {'articles': int(len(df)),
           'overall': [[label, int(df[c].sum()), float(df[c].mean())]
                       for label, c in cols],
           'languages_median': float(df['languages'].median()),
           'one_language_only': int((df['languages'] <= 1).sum())}
    groups = []
    for g, sub in df.groupby('primary_category'):
        if len(sub) >= 30:
            groups.append([g, len(sub)] + [float(sub[c].mean())
                                           for _, c in cols[:3] + cols[9:]])
    out['groups'] = sorted(groups, key=lambda r: -r[1])
    top = df.sort_values('views_all_time', ascending=False)
    out['no_commons'] = top[top['commons'] == 0].head(100)[
        ['title', 'primary_category', 'views_all_time', 'languages']
    ].values.tolist()
    out['english_only'] = top[(top['languages'] <= 1)].head(100)[
        ['title', 'primary_category', 'views_all_time', 'languages']
    ].values.tolist()
    return out


def wikidata_growth():
    import projects_history as ph
    conn = connect()
    try:
        if not _has(conn, 'wd_qdates') or not _has(conn, 'wd_ug_buckets'):
            return {}
        return ph.wikidata_years(conn)
    finally:
        conn.close()


def other_pages():
    """{project: {year: pages first written that year}} and the totals."""
    conn = connect()
    try:
        if not _has(conn, 'proj_pages'):
            return {}
        rows = conn.execute(
            "SELECT host, substr(created, 1, 4), COUNT(*) FROM proj_pages "
            "WHERE created IS NOT NULL GROUP BY 1, 2 ORDER BY 1, 2").fetchall()
        tot = dict(conn.execute('SELECT host, COUNT(*) FROM proj_pages '
                                'GROUP BY host').fetchall())
    finally:
        conn.close()
    out = {}
    for host, year, n in rows:
        out.setdefault(host, {})[int(year)] = n
    return {'years': out, 'totals': tot}


# ------------------------------------------------- the data behind the sheets
def commons_tables():
    """(categories, files) as DataFrames: every row the Commons analysis uses."""
    import pandas as pd
    conn = connect()
    try:
        if not _has(conn, 'commons_ug_files'):
            return None, None
        cats = pd.read_sql(
            'SELECT title, depth, parent, files, subcats, theme, campaign, '
            'named FROM commons_ug_cats ORDER BY files DESC, title', conn)
        files = pd.read_sql(
            'SELECT title, category, uploaded, uploader, size, mime, '
            'mediatype, used, used_wikis FROM commons_ug_files ORDER BY '
            'uploaded DESC, title', conn)
    finally:
        conn.close()
    return cats, files


def wikidata_items():
    """Every item about Uganda, one row, with the columns the analysis counts."""
    import pandas as pd
    conn = connect()
    try:
        if not _has(conn, 'wd_items'):
            return None
        return pd.read_sql('SELECT * FROM wd_items ORDER BY CAST(substr(qid, 2) '
                           'AS integer)', conn)
    finally:
        conn.close()


def coverage_table(arts):
    """One row per Ugandan Wikipedia article: where else its subject lives."""
    import pandas as pd
    conn = connect()
    try:
        if not _has(conn, 'art_sitelinks'):
            return None
        sl = pd.read_sql('SELECT * FROM art_sitelinks', conn)
    finally:
        conn.close()
    df = arts[['title', 'qid', 'primary_category', 'views_all_time',
               'quality', 'has_luganda']].merge(sl, on='qid', how='inner')
    return df.sort_values('views_all_time', ascending=False)
