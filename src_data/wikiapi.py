# -*- coding: utf-8 -*-
"""Shared plumbing for the MediaWiki and Wikidata APIs.

What every data stage needs: one API call that backs off properly when the
server says "too many requests", the category-member walk, the article quality
class, and the maintenance tags that are read from an article's wikitext.
"""

import re
import time

import ug_utils

EN_API = 'https://en.wikipedia.org/w/api.php'
WD_API = 'https://www.wikidata.org/w/api.php'
BATCH = 50              # titles per API request
PAUSE = 0.15            # seconds between requests, to be a good citizen

# Maintenance tags read from the wikitext. A stub template also marks a stub.
MAINTENANCE = (
    ('citation needed', r'\{\{\s*(citation needed|cn|fact)\b'),
    ('unreferenced', r'\{\{\s*(unreferenced|unref|no footnotes)\b'),
    ('update', r'\{\{\s*update\b'),
    ('more citations', r'\{\{\s*(more citations needed|refimprove)\b'),
    ('stub template', r'\{\{[^}]*-stub\s*\}\}'),
)
MAINTENANCE = tuple((n, re.compile(p, re.I)) for n, p in MAINTENANCE)


def _api(base, params):
    """One API call, backing off properly when the server says to.

    A crawl of this size will be rate limited at some point. This honours
    Retry-After when the server sends it, backs off exponentially when it does
    not, and keeps trying for long enough to outlast a throttle rather than
    dying inside one.
    """
    session = ug_utils.get_session()
    query = dict(params, format='json', formatversion=2)
    delay = 2
    for attempt in range(30):
        try:
            r = session.get(base, params=query, timeout=90)
            if r.status_code == 429:
                wait = int(r.headers.get('Retry-After') or delay)
                print(f'      rate limited, waiting {wait}s')
                time.sleep(min(wait, 120))
                delay = min(delay * 2, 120)
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == 29:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 120)


def _members(title, kind):
    """The members of one category: pages, sub-categories or both."""
    out, cont = [], {}
    while True:
        payload = _api(EN_API, dict(
            {'action': 'query', 'list': 'categorymembers', 'cmtitle': title,
             'cmtype': kind, 'cmlimit': 500}, **cont))
        out.extend(payload.get('query', {}).get('categorymembers', []))
        cont = payload.get('continue') or {}
        if not cont:
            return out
        time.sleep(PAUSE)


def _quality(classes, size_bytes):
    """The assessed class, or an explicit fallback when there is none.

    Most Uganda articles carry no WikiProject banner at all, so an assessed
    class alone would describe only a fraction of them. The fallback is a rule
    on the article's length, and it is labelled as such in quality_source so
    the two are never mixed up in a chart.
    """
    order = ['FA', 'FL', 'A', 'GA', 'B', 'C', 'Start', 'Stub']
    for cls in order:
        if cls in classes:
            return cls, 'assessed'
    if not size_bytes:
        return 'Unknown', 'none'
    if size_bytes < 2000:
        return 'Stub', 'size'
    if size_bytes < 10000:
        return 'Start', 'size'
    if size_bytes < 25000:
        return 'C', 'size'
    return 'B', 'size'
