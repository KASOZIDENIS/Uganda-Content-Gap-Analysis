# -*- coding: utf-8 -*-
"""The record from the first Ugandan article onwards, in English and Luganda.

Shared by the dashboard workbooks. Articles written, edits and
editors per year come from each page's own revision history (revision_history.py)
and so reach back before the Pageviews API (July 2015) and the Foundation's
editor-location releases (2018).
"""

import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src_data'))

import config  # noqa: E402


def history_block(data, years):
    """The record from the first article onwards: how many were written, in
    English and in Luganda, how many edits and editors, and the views where
    the Pageviews API has them (from July 2015). Edits come from each page's
    revision history, so they reach back before views and editor releases."""
    import sqlite3
    conn = sqlite3.connect(os.path.join(config.DATA_PATH,
                                        'uganda_diversity.db'))
    titles = set(data['title'])
    lg_of = dict(conn.execute(
        "SELECT title, lg_title FROM cat_articles WHERE lg_title != ''"))
    lg_of = {t: g for t, g in lg_of.items() if t in titles}
    first = {(w, t): ts for w, t, ts in conn.execute(
        'SELECT wiki, title, first_ts FROM rev_done')}
    edits = {}
    for w, t, y, n in conn.execute(
            'SELECT wiki, title, year, edits FROM rev_edits'):
        edits.setdefault((w, t), {})[y] = n
    users = {}
    for w, y, n in conn.execute(
            'SELECT wiki, year, COUNT(*) FROM rev_users WHERE anon = 0 '
            'GROUP BY wiki, year'):
        users[(w, y)] = n
    conn.close()

    created = data['created_year'].dropna().astype(int)
    lg_made = {}
    for g in set(lg_of.values()):
        ts = first.get(('lg', g))
        if ts:
            lg_made[int(ts[:4])] = lg_made.get(int(ts[:4]), 0) + 1
    y0 = min(int(created.min()), min(lg_made) if lg_made else 9999)
    y1 = int(years[-1])
    en_made = created.value_counts().to_dict()
    en_edits = {y: 0 for y in range(y0, y1 + 1)}
    lg_edits = dict(en_edits)
    for (w, t), per in edits.items():
        tab = en_edits if w == 'en' else lg_edits
        for y, n in per.items():
            if y in tab:
                tab[y] += n
    views = {int(y): (int(data[f'v_{y}'].sum()), int(data[f'lg_{y}'].sum()))
             for y in years}
    rows, cum_en, cum_lg = [], 0, 0
    for y in range(y0, y1 + 1):
        made, lmade = int(en_made.get(y, 0)), int(lg_made.get(y, 0))
        cum_en, cum_lg = cum_en + made, cum_lg + lmade
        v = views.get(y)
        rows.append([y, made, cum_en, lmade, cum_lg, en_edits[y],
                     users.get(('en', y), 0), lg_edits[y],
                     users.get(('lg', y), 0),
                     v[0] if v else None, v[1] if v else None])
    span = y1 - y0 + 1
    per_en = {t: [edits.get(('en', t), {}).get(y, 0)
                  for y in range(y0, y1 + 1)] for t in titles}
    per_lg = {t: ([edits.get(('lg', g), {}).get(y, 0)
                   for y in range(y0, y1 + 1)] if g in {x for x in lg_of.values()} else [])
              for t, g in lg_of.items()}
    return ({'y0': y0, 'rows': rows,
             'note': 'Edits and editors come from the revision history of each page, '
                     'so they reach back to the first article; '
                     'editors are registered accounts, counted once a year '
                     'across every Ugandan article. Page views are only '
                     'recorded from July 2015.'},
            per_en, per_lg, span)


def wikipedians(y0, y1):
    """Editors who declare themselves in Uganda (Category:Wikipedians in
    Uganda), by year: [year, registered that year, edited that year, edited 5
    or more times, edits]. Counts only, no names."""
    import sqlite3
    conn = sqlite3.connect(os.path.join(config.DATA_PATH,
                                        'uganda_diversity.db'))
    try:
        reg = dict(conn.execute(
            "SELECT CAST(substr(registration, 1, 4) AS integer), COUNT(*) "
            "FROM wp_users WHERE registration != '' GROUP BY 1"))
        act = {}
        for y, n, e in conn.execute(
                'SELECT year, COUNT(*), SUM(edits >= 5) FROM wp_user_years '
                'GROUP BY year'):
            act[y] = (n, e or 0)
        edits = dict(conn.execute(
            'SELECT year, SUM(edits) FROM wp_user_years GROUP BY year'))
        total = conn.execute('SELECT COUNT(*), SUM(editcount) FROM wp_users'
                             ).fetchone()
    except sqlite3.OperationalError:
        return {'rows': [], 'editors': 0, 'edits': 0}
    finally:
        conn.close()
    rows = [[y, int(reg.get(y, 0)), int(act.get(y, (0, 0))[0]),
             int(act.get(y, (0, 0))[1]), int(edits.get(y, 0))]
            for y in range(y0, y1 + 1)]
    return {'rows': rows, 'editors': int(total[0] or 0),
            'edits': int(total[1] or 0)}


def community(today=None):
    """The editors in Category:Wikipedians in Uganda, from the day each
    created an account to today: who they are, how long they have been
    around, and how the community has grown.

    Returns {'editors': [[user, registered, first edit, last edit, edits,
    years with edits, status, rights, account age in years]], 'growth':
    [[year, new accounts, accounts to date, edited that year, edited 5+
    times, edits]], 'cohorts': [[year, accounts, still active, no longer]],
    'today': date, ...}."""
    import datetime
    import sqlite3
    today = today or datetime.date.today()
    conn = sqlite3.connect(os.path.join(config.DATA_PATH,
                                        'uganda_diversity.db'))
    try:
        users = conn.execute(
            'SELECT user, registration, editcount, first_edit, last_edit, '
            'groups FROM wp_users').fetchall()
        per = {}
        for u, y, n in conn.execute(
                'SELECT user, year, edits FROM wp_user_years'):
            per.setdefault(u, {})[y] = n
    except sqlite3.OperationalError:
        return {'editors': [], 'growth': [], 'cohorts': [],
                'today': str(today)}
    finally:
        conn.close()

    def day(v):
        return (v or '')[:10]

    rows = []
    for user, reg, count, first, last, groups in users:
        reg, first, last = day(reg), day(first), day(last)
        start = reg or first
        if not start:
            continue
        end = last or ''
        age = (today - datetime.date.fromisoformat(start)).days / 365.25
        if not end:
            status = 'No edits'
        else:
            gap = (today - datetime.date.fromisoformat(end)).days
            status = ('Active' if gap <= 365 else
                      'Quiet' if gap <= 3 * 365 else 'Inactive')
        rows.append([user, start, first, last, int(count or 0),
                     len(per.get(user, {})), status, groups or '',
                     round(age, 1)])
    rows.sort(key=lambda r: (r[1], r[0]))

    y0 = int(rows[0][1][:4]) if rows else today.year
    y1 = today.year
    growth, cum = [], 0
    for y in range(y0, y1 + 1):
        new = sum(1 for r in rows if r[1][:4] == str(y))
        cum += new
        active = sum(1 for r in rows if per.get(r[0], {}).get(y, 0) >= 1)
        active5 = sum(1 for r in rows if per.get(r[0], {}).get(y, 0) >= 5)
        edits = sum(per.get(r[0], {}).get(y, 0) for r in rows)
        growth.append([y, new, cum, active, active5, edits])
    cohorts = []
    for y in range(y0, y1 + 1):
        grp = [r for r in rows if r[1][:4] == str(y)]
        if grp:
            now = sum(1 for r in grp if r[6] == 'Active')
            cohorts.append([y, len(grp), now, len(grp) - now])
    ages = sorted(r[8] for r in rows)
    return {'editors': rows, 'growth': growth, 'cohorts': cohorts,
            'today': str(today),
            'median_age': ages[len(ages) // 2] if ages else 0,
            'active': sum(1 for r in rows if r[6] == 'Active'),
            'edits': sum(r[4] for r in rows)}
