# -*- coding: utf-8 -*-
"""Turn the MEGA EDITATHON workbooks into the task lists the editathon page reads.

    python scripts/build_tasks.py

Reads  MEGA EDITATHON/*.xlsx
Writes editathon/tasks/index.json and editathon/tasks/<list>.<n>.json

Each row is [title or item id, label, extra 1, extra 2, extra 3]; the page knows
what the extras mean from the list's "cols" in index.json.
"""
import json
import os
import re
import sys

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'MEGA EDITATHON')
OUT = os.path.join(ROOT, 'editathon', 'tasks')
CHUNK = 5000
QID = re.compile(r'(Q\d+)')

# id, file, sheet (None = first), wiki, kind, title column, extra columns (header names), what the page calls them
LISTS = [
    ('en-image-exists', 'Wikipedia Articles Without a Lead Image.xlsx', ' Image exists', 'enwiki', 'image-exists',
     'Article', ['Image on Commons', 'Subject'], ['Image to add', 'Subject']),
    ('en-pick-category', 'Wikipedia Articles Without a Lead Image.xlsx', ' Pick Image from category', 'enwiki', 'pick-category',
     'Article', ['Commons category', 'Subject'], ['Commons category', 'Subject']),
    ('en-capture', 'Wikipedia article images that need capturing.xlsx', None, 'enwiki', 'capture',
     'Article', ['Subject'], ['Subject']),
    ('lg-image-exists', 'Luganda Wikipedia Articles Without an Image.xlsx', None, 'lgwiki', 'image-exists',
     'Luganda article', ['Image', 'English Wikipedia article', 'Wikidata'], ['Image to add', 'English article', 'Wikidata item']),
    ('lg-capture', 'Luganda article images that need Capturing.xlsx', None, 'lgwiki', 'capture',
     'Luganda article', ['English Wikipedia article', 'Wikidata'], ['English article', 'Wikidata item']),
    ('nyn-image-exists', 'Runyankore Incubator Articles Without an Image.xlsx', None, 'incubatorwiki', 'image-exists',
     'Runyankore page', ['Image', 'English Wikipedia article'], ['Image to add', 'English article']),
    ('nyn-capture', 'Runyankore article images that need Capturing.xlsx', None, 'incubatorwiki', 'capture',
     'Runyankore page', ['English Wikipedia article'], ['English article']),
    ('wd-image-exists', 'Wikidata - Image Gaps.xlsx', None, 'wikidatawiki', 'wd-image-exists',
     'Item', ['English label', 'Commons category'], ['English label', 'Commons category']),
    ('wd-capture', 'Wikidata item images that need capturing.xlsx', None, 'wikidatawiki', 'wd-capture',
     'Item', ['English label', 'Type', 'Place'], ['English label', 'Type', 'Place']),
    ('wd-no-luganda', 'Wiki data items with  No luganda label.xlsx', None, 'wikidatawiki', 'wd-label',
     'Item', ['English label', 'Swahili label', 'Type'], ['English label', 'Swahili label', 'Type']),
]
NAMES = {
    'en-image-exists': 'English Wikipedia: add the image that exists',
    'en-pick-category': 'English Wikipedia: pick an image from Commons',
    'en-capture': 'English Wikipedia: photographs needed',
    'lg-image-exists': 'Luganda Wikipedia: add the image that exists',
    'lg-capture': 'Luganda Wikipedia: photographs needed',
    'nyn-image-exists': 'Runyankore (Incubator): add the image that exists',
    'nyn-capture': 'Runyankore (Incubator): photographs needed',
    'wd-image-exists': 'Wikidata: connect the Commons image (P18)',
    'wd-capture': 'Wikidata: items with no image anywhere',
    'wd-no-luganda': 'Wikidata: add the Luganda label',
}


def cell_text(v):
    if v is None:
        return ''
    s = str(v).strip()
    m = re.match(r'=HYPERLINK\("[^"]*","([^"]*)"\)$', s)
    return m.group(1) if m else s


def main():
    index = []
    for lid, fname, sheet, wiki, kind, tcol, extras, labels in LISTS:
        path = os.path.join(SRC, fname)
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb[sheet] if sheet else wb[wb.sheetnames[0]]
        rows = ws.iter_rows(values_only=True)
        head = None
        for r in rows:
            if r and r[0] == '#':
                head = [cell_text(x) for x in r]
                break
        if head is None:
            sys.exit('no header row in ' + fname)
        pos = {h: i for i, h in enumerate(head) if h}
        ti = pos[tcol]
        ei = [pos[e] for e in extras]
        out, seen = [], set()
        for r in rows:
            if not r or r[ti] is None:
                continue
            t = cell_text(r[ti])
            if not t or t in seen:
                continue
            seen.add(t)
            out.append([t] + [cell_text(r[i]) for i in ei])
        # Wikidata lists are keyed by item number
        chunks = [out[i:i + CHUNK] for i in range(0, len(out), CHUNK)]
        os.makedirs(OUT, exist_ok=True)
        for n, ch in enumerate(chunks):
            with open(os.path.join(OUT, f'{lid}.{n}.json'), 'w', encoding='utf-8') as fh:
                json.dump(ch, fh, ensure_ascii=False, separators=(',', ':'))
        index.append({'id': lid, 'name': NAMES[lid], 'wiki': wiki, 'kind': kind, 'count': len(out), 'chunks': len(chunks),
                      'cols': labels})
        print(lid, len(out), 'rows', len(chunks), 'files')
    with open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8') as fh:
        json.dump({'lists': index}, fh, ensure_ascii=False, separators=(',', ':'))


if __name__ == '__main__':
    main()
