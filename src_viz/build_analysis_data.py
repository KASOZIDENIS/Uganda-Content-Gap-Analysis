# -*- coding: utf-8 -*-
"""The tables the dashboard draws on that are not lists of
articles: women and men compared across categories, the regional balance,
rural against urban, and notable people with no English article.

They are working data, not deliverables, and are written to `data/analysis/`.

    python src_viz/build_analysis_data.py
"""

import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src_data'))

import build_category_files as bcf     # noqa: E402
import category_profiles as cp         # noqa: E402
import config                          # noqa: E402
import ug_utils                        # noqa: E402

OUT_DIR = os.path.join(config.DATA_PATH, 'analysis')
KEEP = {'BI1', 'GE8', 'BI2', 'UP3'}
DATA = config.DATA_PATH


def data(name, **kw):
    return pd.read_csv(os.path.join(DATA, name), **kw)


def fname(code, name):
    return f'{code}_{re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")}'


def write_custom(code, name, note, sheets, index, csv_sheet=None):
    if code not in KEEP:
        return
    main = sheets[csv_sheet] if csv_sheet else next(iter(sheets.values()))
    main.to_csv(os.path.join(OUT_DIR, fname(code, name) + '.csv'),
                index=False, encoding='utf-8-sig')
    print(f'  {code:<5} {name:<40} {len(main):6d} rows')


def regional_balance(arts, index):
    rx = re.compile(r'(Central|Eastern|Northern|Western) Region, Uganda')

    def region(title):
        cats = bcf.ANCESTORS.get(title, ((), {}))[1]
        found = sorted({m.group(1) for c in cats
                        for m in [rx.search(c)] if m})
        return '; '.join(found)

    df = arts.copy()
    df['region'] = df['title'].map(region)
    df['subcat'] = df['direct_cats'].str.split('; ').str[0]
    df['depth'] = 0
    df['also_in'] = ''
    placed = df[df['region'] != '']
    rows = []
    for name in ('Central', 'Eastern', 'Northern', 'Western'):
        sub = placed[placed['region'].str.contains(name)]
        rows.append({
            'Region': name, 'Articles': len(sub),
            'Share of regional articles': round(len(sub) / len(placed), 3)
            if len(placed) else 0,
            'Stubs': int(sub['stub'].sum()),
            'No lead image': int((sub['has_image'] == 0).sum()),
            'With Luganda': int(sub['has_luganda'].sum()),
            'Total views, all time': int(sub['views_all_time'].sum()),
            'Median size (bytes)': int(sub['bytes'].median())
            if len(sub) else 0,
            'Median views': int(sub['views_all_time'].median())
            if len(sub) else 0})
    table = pd.DataFrame(rows)
    write_custom('GE8', 'Regional balance',
                 'Articles under each region of Uganda, by the region '
                 'categories Wikipedia uses. An article that sits in two '
                 'regions counts in both. Kampala is in the Central Region.',
                 {'Regions': table,
                  'Articles': placed[['title', 'region', 'quality', 'bytes',
                                      'has_image', 'has_luganda',
                                      'views_all_time']].sort_values(
                      'views_all_time', ascending=False)}, index, 'Regions')


# -------------------------------------------------------------- the others
def people(arts, high, index):
    humans = arts[arts['is_human'] == 1].copy()
    humans['subcat'] = humans['direct_cats'].str.split('; ').str[0]
    humans['depth'] = 0
    humans['also_in'] = humans['in_categories'].map('; '.join)
    humans = humans.sort_values('views_all_time', ascending=False)

    # UP2: the gender split in detail
    def split(by):
        g = humans.groupby([by, 'gender'])
        t = g.size().unstack(fill_value=0)
        for c in ('female', 'male', 'other / unrecorded'):
            if c not in t:
                t[c] = 0
        t['total'] = t[['female', 'male', 'other / unrecorded']].sum(axis=1)
        known = t['female'] + t['male']
        t['women share of known'] = (t['female'] / known).where(
            known > 0).round(3)
        return t.reset_index()

    life = split('life_status')
    cls = split('quality')
    humans['decade'] = (humans['born'] // 10 * 10).astype('Int64').astype(str)
    dec = split('decade')
    cat = split('primary_category')
    write_custom('UP2', 'Gender split',
                 'Biographies by gender, then by living or deceased, class, '
                 'decade of birth and category. From Wikidata; a person '
                 'with no recorded binary gender is in the third column.',
                 {'By category': cat, 'Living or deceased': life,
                  'By class': cls, 'By decade of birth': dec}, index,
                 'By category')

    # UP3: missing notable people
    corpus = data('ug_ccc_full_corpus.csv')
    missing = corpus[(corpus['types'].fillna('').str.contains(r'\bQ5\b')) &
                     (corpus['en_title'].isna())].sort_values(
        'sitelink_count', ascending=False)[
        ['qitem', 'label', 'sitelink_count', 'gender', 'date_of_birth',
         'lg_title', 'sw_title', 'type_labels']]
    sheets = {'Wikidata people, no English article': missing}
    for nm, f in (('Women in office, undocumented',
                   'ug_women_offices_undocumented.csv'),
                  ('Men in office, undocumented',
                   'ug_men_offices_undocumented.csv')):
        try:
            sheets[nm] = data(f)
        except FileNotFoundError:
            pass
    write_custom('UP3', 'Missing notable people',
                 'People known to Wikidata through a Ugandan link who have no '
                 'English Wikipedia article, ranked by how many other '
                 'languages have written about them; and office holders from '
                 'the rosters with no article.', sheets, index)


ERAS = (
    ('Pre-colonial, before 1894', r'Kingdom of|Kabakas|pre-?colonial|'
     r'archaeolog|Bunyoro-Kitara|Mwanga|Mutesa|Kabalega|Bigo|Ntusi|'
     r'slave trade|Speke|Stanley|Emin Pasha'),
    ('Protectorate, 1894-1962', r'Protectorate|colonial|East African '
     r'campaign|Uganda Railway|Lugard|Buganda Agreement|Mau Mau'),
    ('Independence and Obote I, 1962-1971', r'Obote|1966|independence|'
     r'Mengo|Kabaka crisis|Uganda National Liberation'),
    ('Amin, 1971-1979', r'Amin|Entebbe|Operation Entebbe|Uganda.Tanzania '
     r'War|Asians'),
    ('Obote II and Bush War, 1979-1986', r'Bush War|Okello|National '
     r'Resistance Army|Luweero'),
    ('Museveni era, 1986 on', r'Museveni|Lord.s Resistance|Kony|Allied '
     r'Democratic Forces|National Resistance Movement|Kasese|Ebola|'
     r'(19[89]|20[0-2])\d'),
)


def bias(arts, index):
    humans = arts[arts['is_human'] == 1]
    known = humans[humans['gender'].isin(['female', 'male'])]

    def line(frame):
        f, m = frame[frame['gender'] == 'female'], frame[
            frame['gender'] == 'male']

        def share(sub, col):
            return round(float((sub[col] > 0).mean()), 3) if len(sub) else None

        return {
            'Women': len(f), 'Men': len(m),
            'Women share': round(len(f) / (len(f) + len(m)), 3)
            if len(f) + len(m) else None,
            'Women stubs': share(f, 'stub'), 'Men stubs': share(m, 'stub'),
            'Women with lead image': share(f, 'has_image'),
            'Men with lead image': share(m, 'has_image'),
            'Women with Luganda': share(f, 'has_luganda'),
            'Men with Luganda': share(m, 'has_luganda'),
            'Women cited': share(f, 'refs'), 'Men cited': share(m, 'refs'),
            'Women median size': int(f['bytes'].median()) if len(f) else None,
            'Men median size': int(m['bytes'].median()) if len(m) else None,
            'Women median views': int(f['views_all_time'].median())
            if len(f) else None,
            'Men median views': int(m['views_all_time'].median())
            if len(m) else None}

    # By every category an article sits in, as the category's own workbook
    # does. Counting under one main category made "Ugandan people" look like
    # 19 women and 138 men, because most people are filed first under
    # something smaller.
    by_cat = []
    tops = sorted({t for held in known['in_categories'] for t in held})
    for top in tops:
        sub = known[known['in_categories'].map(lambda held: top in held)]
        by_cat.append(dict({'Category': top}, **line(sub)))
    overall = pd.DataFrame([dict({'Category': 'All people'}, **line(known))])
    table = pd.concat([overall, pd.DataFrame(by_cat)], ignore_index=True)
    write_custom('BI1', 'Gender bias across categories',
                 'Women and men with an article, compared on every measure '
                 'this project holds: how many are stubs, have a lead image, '
                 'a Luganda article, a citation, how long the article is and '
                 'how much it is read. People with no recorded binary gender '
                 'are left out of the comparison. Shares are of each group.',
                 {'By category': table}, index, 'By category')

    # BI2, rural against urban
    corpus = data('ug_ccc_full_corpus.csv')
    labels = corpus['type_labels'].fillna('')
    urban = labels.str.contains(
        r'city of Uganda|municipality|town council|division of Uganda|'
        r'city division|^city$', case=False)
    rural = labels.str.contains(
        r'sub-county|parish|village|county of Uganda|stream|hill',
        case=False) & ~urban
    rows = []
    for name, mask in (('Urban: cities, municipalities, towns, divisions',
                        urban), ('Rural: sub-counties, parishes, villages, '
                                 'hills, streams', rural)):
        sub = corpus[mask]
        rows.append({'Setting': name, 'Wikidata items': len(sub),
                     'With English article': int(sub['en_title'].notna()
                                                 .sum()),
                     'With Luganda article': int(sub['lg_title'].notna()
                                                 .sum()),
                     'Share with English': round(float(
                         sub['en_title'].notna().mean()), 3) if len(sub)
                     else None})
    setting = pd.DataFrame(rows)
    units = data('ug_register_units.csv')
    units = units[units['source'] == 'UBOS']
    reg = units.groupby(['kind', 'verdict']).size().unstack(fill_value=0)
    reg['share with article'] = (reg.get('has_article', 0) /
                                 reg.sum(axis=1)).round(3)
    write_custom('BI2', 'Rural versus urban',
                 'How well rural and urban places are covered. Items are '
                 'Wikidata items tied to Uganda that have at least one '
                 'Wikipedia article in any language, so the share with an '
                 'English article is a share of those. The register sheet '
                 'checks every census unit instead.',
                 {'Urban and rural': setting,
                  'Census units': reg.reset_index()}, index, 'Urban and rural')


# -------------------------------------------------------------------- main
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = ug_utils.connect()
    members, arts, high = bcf.load(conn)
    conn.close()
    print(f'{len(arts)} articles about Uganda')

    index = []
    regional_balance(arts, index)
    people(arts, high, index)
    bias(arts, index)
    print(f'wrote the analysis tables to {OUT_DIR}')


if __name__ == '__main__':
    main()
