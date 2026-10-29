# -*- coding: utf-8 -*-
"""Stage 3: the Wikidata corpus, as one flat file.

The corpus is every Wikidata item about Uganda that has a Wikipedia article in
any language (stage 1, content_retrieval.py). It is written as
`data/ug_ccc_full_corpus.csv`.

The dashboards use it for four things: the articles about Uganda that sit in no
Ugandan category (the *Uncategorised* group), Ugandan items with articles in
other languages and none in English, notable people with no English article,
and rural against urban places.

    python src_data/corpus_export.py
"""

import os

import pandas as pd

import config
import ug_utils
import yn

SCRIPT = 'corpus_export'

MALE, FEMALE = 'Q6581097', 'Q6581072'

# Strategies that assert a *structural* link between the item and Uganda: its
# country, a location inside Uganda, Ugandan citizenship, or birth or death
# there. The remaining strategies (title keywords, ethnic group, language,
# part of) are useful for recall but weak on their own: cross-border
# ethnicities pull in Kenyans and an "... in Uganda" redirect pulls in global
# topics. Anything that has to be about Uganda is gated on a core strategy.
CORE_STRATEGIES = ('country_wd', 'citizenship_wd', 'location_wd',
                   'birth_death_wd')


def _export(df, name):
    path = os.path.join(config.DATA_PATH, name + '.csv')
    yn.export_frame(df, ('is_core',)).to_csv(path, index=False, encoding='utf-8')
    print(f'    -> {name}.csv ({len(df)} rows)')


def _labels(conn):
    return dict(conn.execute('SELECT qitem, label FROM entity_labels'))


def export_full_corpus(conn, force=False):
    """One flat CSV of the whole corpus, for anyone who wants to re-slice it."""
    with ug_utils.stage(conn, SCRIPT, 'export_full_corpus', force) as st:
        if st.skip:
            return

        labels = _labels(conn)
        df = pd.read_sql("""
            SELECT c.qitem, c.label, c.sitelink_count, c.num_strategies,
                   c.strategies, c.types, c.gender_qid, c.admin_qid,
                   c.latitude, c.longitude, c.date_of_birth, c.inception,
                   en.title AS en_title, lg.title AS lg_title,
                   sw.title AS sw_title
            FROM ccc_items c
            LEFT JOIN sitelinks en ON en.qitem=c.qitem AND en.languagecode='en'
            LEFT JOIN sitelinks lg ON lg.qitem=c.qitem AND lg.languagecode='lg'
            LEFT JOIN sitelinks sw ON sw.qitem=c.qitem AND sw.languagecode='sw'
        """, conn)
        df['is_core'] = df.strategies.fillna('').apply(
            lambda s: int(any(name in s for name in CORE_STRATEGIES)))
        df['gender'] = df.gender_qid.map(
            {MALE: 'male', FEMALE: 'female'}).fillna('')
        df['admin_label'] = df.admin_qid.map(lambda q: labels.get(q, '') if q else '')
        df['type_labels'] = df.types.fillna('').apply(
            lambda s: ', '.join(labels.get(q, q) for q in s.split('|')[:4] if q))
        _export(df, 'ug_ccc_full_corpus')


def main(force=False):
    conn = ug_utils.connect()
    export_full_corpus(conn, force)
    conn.close()


if __name__ == '__main__':
    import sys
    main(force='--force' in sys.argv)
