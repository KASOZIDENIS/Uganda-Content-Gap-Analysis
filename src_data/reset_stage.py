# -*- coding: utf-8 -*-
"""Clear the checkpoint for one or more pipeline stages so they re-run.

    python reset_stage.py fetch_pageviews
    python reset_stage.py --all
    python reset_stage.py --list
"""

import sys

import ug_utils


def main():
    args = [a for a in sys.argv[1:]]
    conn = ug_utils.connect()
    ug_utils.create_run_log(conn)

    if not args or '--list' in args:
        rows = conn.execute("""
            SELECT cycle, script, function, duration FROM run_log
            ORDER BY cycle, script, function""").fetchall()
        if not rows:
            print('no stages recorded yet')
        for cycle, script, function, duration in rows:
            print(f'  {cycle}  {script}.{function}  ({duration})')
        return

    if '--all' in args:
        n = conn.execute('DELETE FROM run_log').rowcount
        conn.commit()
        print(f'cleared {n} checkpoints - the next run recomputes everything')
        return

    for function in args:
        n = conn.execute('DELETE FROM run_log WHERE function=?',
                         (function,)).rowcount
        conn.commit()
        print(f'cleared {n} checkpoint(s) for {function}')


if __name__ == '__main__':
    main()
