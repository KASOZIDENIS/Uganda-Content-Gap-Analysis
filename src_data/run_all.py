# -*- coding: utf-8 -*-
"""Run the data stages for the English Wikipedia dashboards, in order.

    python run_all.py            # resume: skip stages already done this cycle
    python run_all.py --force    # recompute everything

Stages are checkpointed per calendar month, so re-running mid-month picks up
where an interrupted run left off. A new month starts a fresh cycle, which is
how the analysis stays current.

This builds the Wikidata corpus, the census units and the category profiles;
`refresh.py` then brings the article histories, views, editors and the
Luganda Wikipedia up to date and rebuilds the files. The other Wikimedia
projects have their own scripts (see docs/06-pipeline-and-refresh.md).
"""

import sys
import time

import category_profiles
import commons_audit
import commons_geography
import content_retrieval
import corpus_export
import geo_places
import ug_utils
import uganda_editors
import ubos_units


def main():
    force = '--force' in sys.argv
    started = time.time()
    print('=' * 70)
    print(f'UGANDA CONTENT GAP - cycle {ug_utils.cycle_year_month()}')
    print('=' * 70)
    # The Wikidata corpus: every item about Uganda that has an article.
    content_retrieval.main(force)
    corpus_export.main(force)
    # Stages whose failure should not sink the cycle: third-party downloads and
    # long API crawls. Each checkpoints, so a re-run resumes.
    for stage in (ubos_units, geo_places, category_profiles,
                  uganda_editors, commons_audit, commons_geography):
        try:
            stage.main(force)
        except Exception as reason:                    # noqa: BLE001
            print(f'  {stage.__name__} skipped: '
                  f'{type(reason).__name__}: {reason}')
    print('\n' + '=' * 70)
    print(f'Done in {(time.time() - started) / 60:.1f} minutes.')
    print('=' * 70)


if __name__ == '__main__':
    main()
