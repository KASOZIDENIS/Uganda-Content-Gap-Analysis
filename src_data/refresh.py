# -*- coding: utf-8 -*-
"""Bring everything up to date, and say where the run has reached.

The same pipeline as category_profiles.py, made incremental so that an update
costs minutes rather than hours:

    tree      ask MediaWiki the size of every category already read (about a
              minute) and re-read only those that changed
    discover  search for articles and categories named for Uganda
    read      class, size, references and lead image of articles not seen before
    test      is each new article about Uganda? Opening sentence, Wikidata,
              and the country count; the ones that fail are dropped
    wikidata  gender, life dates, Luganda links and Commons, for everyone
    history   the year each new article was first written
    revisions the edit history of every article, English and Luganda
    views     total, yearly and last-twelve-month views; for every article when
              a new month is out, otherwise only for the new ones
    editors   the latest months of editors in Uganda, and the Wikipedians in Uganda
    luganda   every Luganda article: new pages, views and edit history
    files     the category lists, the all-category lists, the analysis tables
              and the Excel and Google Sheets dashboards

It can be cancelled between steps, and a run that is interrupted resumes next
time because every stage works from what is still missing.

    python src_data/refresh.py              # update everything
    python src_data/refresh.py --remeasure  # also re-measure every article's views
"""

import datetime
import json
import os
import subprocess
import sys
import threading
import time

import config
import category_profiles as cp
import ug_utils

ROOT = config.PROJECT_PATH
sys.path.insert(0, os.path.join(ROOT, 'src_viz'))

# id, label, what it does, weight in the overall percentage
STAGES = [
    ('tree', 'Check the category tree',
     'Asks Wikipedia how big each category is and re-reads only those that '
     'have changed.', 8),
    ('discover', 'Look for new articles',
     'Searches Wikipedia for articles and categories named for Uganda, its '
     'places and its topics.', 6),
    ('read', 'Read the new articles',
     'Quality class, size, references and lead image of each article not '
     'seen before.', 10),
    ('test', 'Remove what is not about Uganda',
     'Tests each new article\'s opening sentence and Wikidata record, and '
     'drops the ones that fail.', 12),
    ('wikidata', 'Check Wikidata',
     'Gender, life dates, Luganda links and Commons categories, refreshed '
     'for every article.', 8),
    ('history', 'Date the new articles',
     'Finds the year each new article was first written.', 5),
    ('revisions', 'Trace the edits',
     'Reads the edit history of each article, in English and Luganda, so '
     'the years before page views and editor data begin are filled in.', 12),
    ('views', 'Count the views',
     'Total, yearly and last-twelve-month views: for the new articles, and '
     'for all of them when a new month is out.', 25),
    ('editors', 'Update the editors',
     'Adds the latest months of editors located in Uganda from the '
     'Wikimedia Foundation releases, and the edits of the Wikipedians in '
     'Uganda.', 4),
    ('luganda', 'Update Luganda Wikipedia',
     'Every Luganda article: new pages, all-time views and edit history, '
     'on their own.', 12),
    ('files', 'Rebuild the files',
     'Category lists, every-category lists, analysis tables, the dashboard '
     'workbooks and the Luganda workbook.', 22),
]


class Cancelled(Exception):
    pass


# ------------------------------------------------------------------- state
_lock = threading.RLock()
_cancel = threading.Event()
_thread = None
_state = {}


def _fresh():
    return {
        'state': 'idle', 'started': None, 'finished': None, 'updated': None,
        'options': {}, 'percent': 0, 'stage': -1, 'activity': '',
        'stages': [{'id': i, 'label': l, 'desc': d, 'weight': w,
                    'state': 'waiting', 'done': 0, 'total': 0, 'note': ''}
                   for i, l, d, w in STAGES],
        'funnel': {'tree': 0, 'categoriesChecked': 0, 'categoriesChanged': 0,
                   'found': 0, 'read': 0, 'kept': 0, 'rejected': 0,
                   'viewsDone': 0, 'viewsTotal': 0},
        'log': [], 'result': None, 'error': None}


def _save():
    """Kept as a hook; progress is shown on the console."""


def _percent():
    total = sum(s['weight'] for s in _state['stages'])
    got = 0.0
    for s in _state['stages']:
        if s['state'] in ('done', 'skipped'):
            got += s['weight']
        elif s['state'] == 'running' and s['total']:
            got += s['weight'] * min(1.0, s['done'] / s['total'])
    return round(100.0 * got / total, 1)


def status():
    """A copy of the state, safe to send to the page."""
    with _lock:
        if not _state:
            _state.update(_fresh())
        snap = json.loads(json.dumps(_state))
    snap['log'] = snap['log'][-60:]
    snap['now'] = time.time()
    return snap


def log(line):
    line = str(line).rstrip()
    if not line:
        return
    with _lock:
        stamp = datetime.datetime.now().strftime('%H:%M:%S')
        _state['log'].append(f'{stamp}  {line}')
        del _state['log'][:-200]
        _state['updated'] = time.time()
    print(line, flush=True)


def _stage(i, **fields):
    with _lock:
        s = _state['stages'][i]
        s.update(fields)
        _state['stage'] = i
        _state['percent'] = _percent()
        _state['updated'] = time.time()
        if fields.get('state') in ('done', 'skipped', 'error'):
            _save()


def _funnel(**fields):
    with _lock:
        _state['funnel'].update(fields)


class Reporter:
    """What the pipeline calls as it goes. Raises Cancelled when asked to."""

    def __init__(self):
        self.stage = 0
        self.lo, self.hi = 0.0, 1.0
        self.last = 0.0

    def begin(self, i, note=''):
        self.stage, self.lo, self.hi = i, 0.0, 1.0
        _stage(i, state='running', done=0, total=0, note=note)
        log(STAGES[i][1])

    def finish(self, i, note='', skipped=False):
        s = _state['stages'][i]
        _stage(i, state='skipped' if skipped else 'done',
               done=s['total'] or 1, total=s['total'] or 1, note=note)
        if note:
            log(f'  {note}')

    def span(self, lo, hi):
        """The part of the current stage the next calls fill, 0 to 1."""
        self.lo, self.hi = lo, hi

    def __call__(self, done, total, note=''):
        if _cancel.is_set():
            raise Cancelled()
        now = time.time()
        if now - self.last < 0.25 and done < total:
            return
        self.last = now
        frac = (done / total) if total else 0.0
        scaled = self.lo + (self.hi - self.lo) * frac
        _stage(self.stage, done=int(scaled * 1000), total=1000,
               note=note[:90])
        _state['activity'] = f'{STAGES[self.stage][1]}: {note}'[:140]


def _check():
    if _cancel.is_set():
        raise Cancelled()


# -------------------------------------------------------------- the stages
def _run_script(rep, i, label, script, env=None, fatal=True):
    """One build script as a child process, its output into the log."""
    _check()
    log(f'  {label}')
    full_env = dict(os.environ, PYTHONIOENCODING='utf-8')
    full_env.update(env or {})
    proc = subprocess.Popen(
        [sys.executable, '-W', 'ignore', os.path.join(ROOT, 'src_viz', script)],
        cwd=ROOT, env=full_env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding='utf-8',
        errors='replace')
    tail = []
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            tail.append(line)
            del tail[:-30]
        if _cancel.is_set():
            proc.terminate()
            raise Cancelled()
    code = proc.wait()
    if code != 0:
        log(f'  {label} failed (exit {code}): ' + ' | '.join(tail[-4:]))
        if fatal:
            raise RuntimeError(f'{label} failed: ' + (tail[-1] if tail
                                                      else 'no output'))
    return code


def _titles(conn):
    return {r[0] for r in conn.execute('SELECT DISTINCT title FROM cat_members')}


def run(options=None):
    options = options or {}
    conn = ug_utils.connect()
    rep = Reporter()
    cp.REPORT = rep
    ug_utils.PROGRESS = rep
    names_tops = cp.load_tree()
    tops, names = names_tops
    try:
        known = _titles(conn) if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='cat_members'").fetchone() \
            else set()

        # 1 ---- the tree
        rep.begin(0)
        rep.span(0.0, 0.25)
        changed, checked = cp.refresh_tree(conn)
        _funnel(categoriesChecked=checked, categoriesChanged=changed)
        log(f'  {changed} of {checked} categories changed since the last '
            f'read')
        rep.span(0.25, 1.0)
        cp.crawl(conn, names, tops, True)
        now_titles = _titles(conn)
        _funnel(tree=len(now_titles))
        rep.finish(0, f'{changed} categories re-read; {len(now_titles):,} '
                      f'articles in the tree')

        # 2 ---- new articles by search
        rep.begin(1)
        rep.span(0.0, 0.5)
        cp.discover(conn, names, True)
        rep.span(0.5, 1.0)
        cp.discover_topics(conn, True)
        cp.add_search_hits(conn, True)
        cp.add_uncategorised(conn, True)
        found = _titles(conn) - known
        _funnel(found=len(found))
        rep.finish(1, f'{len(found):,} articles not seen before')

        # 3 ---- read them
        rep.begin(2)
        cp.describe(conn, True)
        new_read = len([t for t in found if conn.execute(
            'SELECT described FROM cat_articles WHERE title = ?',
            (t,)).fetchone() == (1,)]) if found else 0
        _funnel(read=new_read)
        rep.finish(2, f'{new_read:,} new articles read')

        # 4 ---- is it about Uganda?
        rep.begin(3)
        rep.span(0.0, 0.5)
        cp.relevance_leads(conn, True)
        rep.span(0.5, 1.0)
        cp.relevance_evidence(conn, True)
        wanted = {r[0] for r in conn.execute('SELECT title FROM cat_wanted')}
        kept_new = len(found & wanted)
        _funnel(kept=kept_new, rejected=len(found) - kept_new)
        rep.finish(3, f'{kept_new:,} of {len(found):,} new articles pass the '
                      f'test; {len(found) - kept_new:,} are dropped')

        # 5 ---- Wikidata
        rep.begin(4)
        rep.span(0.0, 0.8)
        conn.execute("""UPDATE cat_articles SET instance_of = NULL,
            commons_files = NULL WHERE title IN (SELECT title FROM
            cat_wanted)""")
        conn.commit()
        cp.wikidata_facts(conn, True)
        rep.span(0.8, 1.0)
        cp.commons_files(conn, True)
        rep.finish(4, 'Wikidata facts and Commons counts refreshed')

        # 6 ---- creation years
        rep.begin(5)
        cp.history(conn, True)
        rep.finish(5, 'new articles dated')

        # 7 ---- edit histories
        rep.begin(6)
        import revision_history as rh
        import build_category_files as bcf
        universe_titles = list(bcf.load(conn)[1]['title'])
        rh.run(conn, universe_titles, True)
        rep.finish(6, 'edit histories up to date')

        # 7 ---- views
        rep.begin(7)
        stale = cp.readership_is_stale(conn)
        everything = bool(options.get('remeasure')) or stale
        if everything:
            log('  re-measuring every article' + (
                ' (a new month of data is out)' if stale else ''))
            cp.mark_views_stale(conn)
        todo = conn.execute(
            'SELECT COUNT(*) FROM cat_articles WHERE described = 1 AND '
            'views_en IS NULL AND title IN (SELECT title FROM cat_wanted)'
        ).fetchone()[0]
        _funnel(viewsTotal=todo)
        if not todo:
            rep.finish(7, 'views are already up to date', skipped=True)
        else:
            cp.readership(conn, True)
            rep.finish(7, f'{todo:,} articles measured'
                       + (' (every article)' if everything else ''))

        # 8 ---- editors
        rep.begin(8)
        import uganda_editors as ue
        ue.fetch(conn, True)
        ue.fetch_recent(conn, True)
        import ugandan_wikipedians as uw
        uw.run(conn, True)
        rep.finish(8, 'editor counts and Wikipedians in Uganda updated')
        conn.close()
        conn = None

        # 9 ---- Luganda Wikipedia on its own
        rep.begin(9)
        import luganda_pages as lp
        lconn = ug_utils.connect()
        lp.list_pages(lconn, True)
        lp.fetch_details(lconn, True)
        lp.fetch_wikidata(lconn, True)
        lp.fetch_views(lconn, True)
        lpages = [t for (t,) in lconn.execute('SELECT title FROM luganda_pages')]
        import revision_history as rh2
        rh2.run(lconn, [], True, lpages)
        lp.export(lconn, True)
        lconn.close()
        rep.finish(9, f'{len(lpages):,} Luganda articles measured')

        # 9 ---- the files
        rep.begin(10)
        steps = [('Category lists', 'build_category_files.py', None, True),
                 ('Every-category lists', 'build_all_categories.py', None,
                  True),
                 ('Analysis tables', 'build_analysis_data.py', None, True),
                 ('Excel dashboard', 'build_dashboard_excel.py', None, False),
                 ('Google Sheets dashboard', 'build_dashboard_excel.py',
                  {'DASH_TARGET': 'sheets'}, False),
                 ('Luganda workbook', 'build_luganda_excel.py', None, False)]
        for k, (label, script, env, fatal) in enumerate(steps):
            _stage(10, done=k, total=len(steps), note=label)
            _run_script(rep, 10, label, script, env, fatal)
        rep.finish(10, 'all files rebuilt')

        with _lock:
            _state['state'] = 'done'
            _state['finished'] = time.time()
            _state['percent'] = 100.0
        log('Finished.')
    except Cancelled:
        with _lock:
            _state['state'] = 'cancelled'
            _state['finished'] = time.time()
            for s in _state['stages']:
                if s['state'] == 'running':
                    s['state'] = 'waiting'
        log('Cancelled. Work already saved is kept and the next update '
            'carries on from it.')
    except Exception as error:                          # noqa: BLE001
        with _lock:
            _state['state'] = 'error'
            _state['error'] = f'{type(error).__name__}: {error}'
            _state['finished'] = time.time()
            for s in _state['stages']:
                if s['state'] == 'running':
                    s['state'] = 'error'
        log(f'Stopped by an error: {error}')
    finally:
        cp.REPORT = None
        ug_utils.PROGRESS = None
        if conn is not None:
            conn.close()
        _save()


# ------------------------------------------------------------- the controls
def start(options=None):
    """Begin a run unless one is going; returns the state either way."""
    global _thread
    options = options or {}
    with _lock:
        if _thread is not None and _thread.is_alive():
            return status()
        _cancel.clear()
        _state.clear()
        _state.update(_fresh())
        _state['state'] = 'running'
        _state['started'] = time.time()
        _state['options'] = options
        target = run
        _thread = threading.Thread(target=target, args=(options,),
                                   name='refresh', daemon=True)
        _thread.start()
    return status()


def cancel():
    _cancel.set()
    log('Cancelling after the step in hand ...')
    return status()


def is_running():
    return _thread is not None and _thread.is_alive()


if __name__ == '__main__':
    opts = {'remeasure': '--remeasure' in sys.argv}
    start(opts)
    try:
        while is_running():
            time.sleep(1)
            snap = status()
            sys.stdout.write(f"\r{snap['percent']:5.1f}%  "
                             f"{snap['activity'][:90]:<90}")
            sys.stdout.flush()
    except KeyboardInterrupt:
        cancel()
        _thread.join()
    print('\n' + status()['state'])
