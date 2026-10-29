# -*- coding: utf-8 -*-
"""Shared plumbing: WDQS access, chunking, SQLite helpers, run checkpointing.

Checkpointing: a monthly cycle over thousands of items will get interrupted, so
each stage records that it finished and is skipped on a re-run unless forced.
"""

import datetime
import sqlite3
import time

import requests

import config


# ------------------------------------------------------------------ session
_session = None


def get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({'User-Agent': config.USER_AGENT})
    return _session


# Moved to config so the presentation layer can reach it without importing
# this module, and therefore without requests. Re-exported for the stages.
cycle_year_month = config.cycle_year_month


# ------------------------------------------------------------------ sparql
# Set by refresh.py to follow a long query's progress; None on the console.
PROGRESS = None


def run_sparql(query, retries=None, timeout=180):
    """POST a SPARQL query to WDQS and return the bindings list.

    Raises the final exception if every retry fails, so callers can decide
    whether to back off with a smaller chunk.
    """
    retries = retries if retries is not None else config.SPARQL_RETRIES
    session = get_session()
    last_error = None

    for attempt in range(retries):
        try:
            response = session.post(
                config.WDQS_ENDPOINT,
                data={'query': query},
                headers={'Accept': 'application/sparql-results+json'},
                timeout=timeout,
            )
            if response.status_code == 429:
                wait = int(response.headers.get('Retry-After', 30))
                print(f'    rate limited, waiting {wait}s')
                time.sleep(wait)
                continue
            response.raise_for_status()
            time.sleep(config.SPARQL_PAUSE)
            return response.json()['results']['bindings']
        except Exception as error:                     # noqa: BLE001
            last_error = error
            backoff = 3 * (attempt + 1)
            print(f'    sparql attempt {attempt + 1}/{retries} failed '
                  f'({type(error).__name__}), retrying in {backoff}s')
            time.sleep(backoff)

    raise last_error


def run_sparql_chunked(query_template, qitems, chunk_size=None, label=''):
    """Run a query once per chunk of QIDs, halving the chunk on timeout.

    query_template must contain a '{values}' placeholder that receives a
    space separated list of 'wd:Qnnn' tokens for a VALUES clause.

    Substitution is a plain replace, not str.format: SPARQL is full of
    literal braces and str.format would try to parse them as format fields.
    """
    chunk_size = chunk_size or config.SPARQL_CHUNK_SIZE
    qitems = list(qitems)
    bindings = []
    index = 0
    total = len(qitems)

    while index < total:
        chunk = qitems[index:index + chunk_size]
        values = ' '.join('wd:' + q for q in chunk)
        try:
            bindings.extend(
                run_sparql(query_template.replace('{values}', values)))
            index += chunk_size
            done = min(index, total)
            print(f'    {label} {done}/{total} ({100 * done // total}%)')
            if PROGRESS:
                PROGRESS(done, total, label)
        except Exception:                              # noqa: BLE001
            if chunk_size <= config.SPARQL_MIN_CHUNK:
                # Skip this stubborn chunk rather than abandoning the run.
                print(f'    {label} skipping {len(chunk)} items after repeated failure')
                index += chunk_size
                continue
            chunk_size = max(config.SPARQL_MIN_CHUNK, chunk_size // 2)
            print(f'    {label} backing off to chunk size {chunk_size}')

    return bindings


def qid_from_uri(uri):
    """'http://www.wikidata.org/entity/Q42' -> 'Q42'"""
    return uri.rsplit('/', 1)[-1]


def binding_value(binding, key, default=None):
    item = binding.get(key)
    return item['value'] if item else default


# ------------------------------------------------------------------ sqlite
def connect():
    conn = sqlite3.connect(config.DB_FILE, timeout=60)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    return conn


def create_run_log(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_log (
            cycle text, script text, function text,
            duration text, finished_at text,
            PRIMARY KEY (cycle, script, function))
    """)
    conn.commit()


def already_run(conn, script, function, force=False):
    if force:
        return False
    create_run_log(conn)
    row = conn.execute(
        'SELECT duration FROM run_log WHERE cycle=? AND script=? AND function=?',
        (cycle_year_month(), script, function)).fetchone()
    if row:
        print(f'  = {function} already completed this cycle (took {row[0]}), skipping')
        return True
    return False


def mark_run(conn, script, function, started):
    create_run_log(conn)
    duration = str(datetime.timedelta(seconds=int(time.time() - started)))
    conn.execute(
        'INSERT OR REPLACE INTO run_log VALUES (?,?,?,?,?)',
        (cycle_year_month(), script, function, duration,
         datetime.datetime.now().isoformat(timespec='seconds')))
    conn.commit()
    print(f'  + {function} done in {duration}')


class stage:
    """Context manager wrapping one resumable pipeline stage.

    Usage:
        with stage(conn, 'content_retrieval', 'retrieve_ccc') as st:
            if st.skip: return
            ...
    """

    def __init__(self, conn, script, function, force=False):
        self.conn, self.script, self.function, self.force = conn, script, function, force
        self.skip = False

    def __enter__(self):
        print(f'\n>> {self.script}.{self.function}')
        self.started = time.time()
        self.skip = already_run(self.conn, self.script, self.function, self.force)
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None and not self.skip:
            mark_run(self.conn, self.script, self.function, self.started)
        return False
