# -*- coding: utf-8 -*-
"""Every category and sub-category, as its own file.

The category files cover the fourteen top-level categories. Wikipedia's tree
under them holds thousands more, and a reader who wants "Ugandan cricketers" or
"Hospitals in Kampala" should not have to filter a larger file to get it. So
every category that holds at least one article about Uganda gets its own CSV,
and the larger ones (100 articles or more) a full workbook as well.

A category's articles are those filed in it directly or in any category beneath
it, the same rule the top-level files use. `Depth` in each file says how many
steps below the category an article is filed: 0 is directly in it.

Writes to `all_categories/`:
    <category>.csv        every category with an article about Uganda
    <category>.xlsx       the ones with 100 articles or more
    _Category_index.csv   one row per category: group, parent, size, quality,
                          readership, people, where its file is
    _Category_index.xlsx  the same, filterable, with links

    python src_viz/build_all_categories.py
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
import universe                        # noqa: E402

OUT_DIR = os.path.join(config.PROJECT_PATH, 'all_categories')
XLSX_MIN = 100
FILES = '--index-only' not in sys.argv    # rebuild just the index
SKIP = ('Uganda',)          # the root holds everything; that is "All categories"


def file_stem(name, taken):
    stem = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:80] or 'category'
    unique, k = stem, 2
    while unique in taken:
        unique, k = f'{stem}_{k}', k + 1
    taken.add(unique)
    return unique


def membership(arts, members, anc):
    """(category, title, distance) for every article and every category above
    it, with the top-level categories taken from the walk so that they agree
    with the top-level files."""
    rows = [(cat, t, d) for t in arts['title']
            for cat, d in anc[t][1].items()]
    held = members[members['title'].isin(set(arts['title']))
                   & members['top'].isin(set(cp.load_tree()[0]))]
    rows += [(top, t, int(dep)) for top, t, dep in zip(
        held['top'], held['title'], held['depth'])]
    long = pd.DataFrame(rows, columns=['category', 'title', 'dist'])
    return long.groupby(['category', 'title'], as_index=False)['dist'].min()


def groups_of(conn, names):
    """{category: [top-level groups it can be reached from]}."""
    edges = {}
    for parent, child, kind in conn.execute(
            'SELECT parent, child, kind FROM cat_edges'):
        edges.setdefault(parent, []).append((child, kind))
    out = {}
    for top in cp.load_tree()[0]:
        reach = cp.reachable(edges, ['Category:' + top], names)
        for extra in cp.GROUP_ROOTS.get(top, {}):
            for cat, v in cp.reachable(edges, [extra], names, 0).items():
                reach.setdefault(cat, v)
        for cat in reach:
            out.setdefault(cat.split(':', 1)[1], []).append(top)
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = ug_utils.connect()
    members, arts, high = bcf.load(conn)
    names = cp.load_tree()[1]
    grp = groups_of(conn, names)
    cat_parents, _ = universe.category_graph(conn)
    conn.close()
    anc = bcf.ANCESTORS
    tops = set(cp.load_tree()[0])

    long = membership(arts, members, anc)
    long = long[~long['category'].isin(SKIP)]
    merged = long.merge(arts, on='title', how='left')
    for col in ('is_human', 'stub', 'has_image', 'has_luganda',
                'high_views_low_quality', 'expansion_gap_bytes'):
        merged[col] = merged[col].fillna(0)
    total_views = arts['views_all_time'].sum()

    taken = {'_category_index'}
    index = []
    written_x = 0
    for k, (cat, g) in enumerate(merged.groupby('category'), 1):
        n = len(g)
        people = g[g['is_human'] == 1]
        known = int(people['gender'].isin(['female', 'male']).sum())
        women = int((people['gender'] == 'female').sum())
        parents = sorted(p.split(':', 1)[1] for p in
                         cat_parents.get('Category:' + cat, []))
        is_top = cat in tops
        if is_top:
            link = f'category_files/{cp.slug(cat)}.xlsx'
            stem = None
        else:
            stem = file_stem(cat, taken)
            link = f'all_categories/{stem}.csv'
            if FILES:
                df = g.sort_values('views_all_time', ascending=False).copy()
                df['subcat'] = df['direct_cats'].fillna('').str.split(
                    '; ').str[0]
                df['depth'] = df['dist']
                df['also_in'] = ''
                bcf.csv_frame(df).to_csv(
                    os.path.join(OUT_DIR, stem + '.csv'), index=False,
                    encoding='utf-8-sig')
            if n >= XLSX_MIN:
                link = f'all_categories/{stem}.xlsx'
                if FILES:
                    bcf.write_workbook(cat, df, high,
                                       os.path.join(OUT_DIR, stem + '.xlsx'))
                written_x += 1
        index.append({
            'Category': cat,
            # Reached from the root but from none of the fourteen: it still
            # needs a home, or it would be in no dropdown.
            'Group': '; '.join(grp.get(cat, [])) or cp.OTHER,
            'Parent': '; '.join(parents[:3]),
            'Articles': n,
            'Filed directly': int((g['dist'] == 0).sum()),
            'Share of views': g['views_all_time'].sum() / total_views,
            'Stubs': g['stub'].mean(),
            'In Luganda': g['has_luganda'].mean(),
            'No lead image': (g['has_image'] == 0).mean(),
            'People': len(people),
            'Women among people': (women / known) if known >= 20 else None,
            'Read a lot, written little': int(g['high_views_low_quality']
                                              .sum()),
            'Words to reach C': round(
                g['expansion_gap_bytes'].sum() / bcf.BYTES_PER_WORD, -2),
            'Top level': 'Y' if is_top else 'N',
            'File': link})
        if k % 500 == 0:
            print(f'  {k} categories written ({written_x} workbooks)')

    # Every category the walk reached is listed, including those with no
    # article about Uganda left in or beneath them, so the whole tree under
    # Category:Uganda can be searched and none is missing from the lists.
    listed = {row['Category'] for row in index}
    for cat in sorted(grp):
        if cat in listed or cat in SKIP:
            continue
        parents = sorted(p.split(':', 1)[1] for p in
                         cat_parents.get('Category:' + cat, []))
        index.append({
            'Category': cat, 'Group': '; '.join(grp[cat]),
            'Parent': '; '.join(parents[:3]), 'Articles': 0,
            'Filed directly': 0, 'Share of views': None, 'Stubs': None,
            'In Luganda': None, 'No lead image': None, 'People': 0,
            'Women among people': None, 'Read a lot, written little': 0,
            'Words to reach C': 0, 'Top level': 'Y' if cat in tops else 'N',
            'File': ''})

    idx = pd.DataFrame(index).sort_values(
        ['Group', 'Articles'], ascending=[True, False]).reset_index(drop=True)
    idx.to_csv(os.path.join(OUT_DIR, '_Category_index.csv'), index=False,
               encoding='utf-8-sig')
    book = bcf.Book(os.path.join(OUT_DIR, '_Category_index.xlsx'))
    ws = book.wb.add_worksheet('Categories')
    ws.write(0, 0, f'{len(idx):,} categories and sub-categories under '
             'Category:Uganda. A category counts the articles filed in '
             'it and in everything beneath it.', book.f['note'])
    book.table(ws, 1, idx.fillna(''), list(idx.columns), None,
               {0: 44, 1: 30, 2: 30})
    book.close()
    print(f'\nwrote {len(idx)} categories to {OUT_DIR} '
          f'({written_x} with a workbook)')


if __name__ == '__main__':
    main()
