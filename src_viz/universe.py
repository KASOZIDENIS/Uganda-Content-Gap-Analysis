# -*- coding: utf-8 -*-
"""Which articles are about Uganda, and which categories each one hangs under.

Two things the per-category files and the task files both need, kept here so
they cannot disagree.

**Relevance.** The category tree files Barack Obama under Ugandan descent and
Tanzania under a holiday Uganda observes. So membership of a category is not
accepted as evidence. An article counts as about Uganda when at least one of
these holds, and the basis is kept and exported so any row can be checked:

    title       the title carries a Ugandan name
    wikidata    the item's country, citizenship, origin, location chain,
                or birth or death place reaches Uganda
    lead        the opening sentence names Uganda or a Ugandan place or
                people, or the lead does so three times; a single mention
                further down is how Kenya names its neighbour
    office      the article is filed as a holder of a Ugandan office
    biota       a species listed under a Ugandan fauna or flora category;
                Wikipedia files a species there because it occurs in Uganda,
                and the lead often does not say so

Everything else is written to `_Excluded_not_about_Uganda.csv`, so nothing is
dropped without being shown.

**Ancestors.** An article's own category is rarely the useful one: a footballer
sits in "Vipers SC players", and it is three steps up that the tree says
"Ugandan sportspeople". The task files are defined on those ancestors.
"""

import re

import pandas as pd

import category_profiles as cp

BIOTA = re.compile(
    r'^(Flora|Fauna|Mammals|Reptiles|Amphibians|Insects|Fish|Birds|'
    r'Lepidoptera|Arthropods|Biota|Molluscs|Fungi|Butterflies|Moths|Beetles|'
    r'Spiders|Snails|Plants|Orchids|Trees|Primates|Bats|Rodents|Frogs|Snakes|'
    r'Lizards|Odonata|Dragonflies|Hymenoptera|Diptera|Orthoptera|Coleoptera|'
    r'Crustaceans|Freshwater fish|Endemic (fauna|flora|birds|freshwater fish)'
    r') (of|in) (Uganda|the Albertine)|^Lists of biota of Uganda|'
    r'^Biota of Uganda|^Endemic .* of Uganda')

TITLE_WORDS = cp.LEAD_WORDS

# A holder of a Ugandan office, or a diplomat posted there, is about Uganda
# even when the lead is about the person: Elizabeth II was Queen of Uganda,
# and a Governor of Uganda may be described only by his career.
OFFICE = re.compile(
    r'^(Governors?|Presidents|Prime ministers|Vice[- ]presidents|Kabakas|'
    r'Chief justices|High commissioners|Ambassadors|Colonial '
    r'administrators|Administrators|Commissioners|Resident commissioners)'
    r'.*\b(of|to|in) (the )?(Protectorate of )?Uganda$')

# Wikidata's "country" is weak when the item lists many. The Equator, the Nile
# and the English language all name Uganda among a dozen or a hundred.
MAX_COUNTRIES = 3

# The lead has to say Uganda where an article says what it is about: in the
# opening, or repeatedly. A single mention further down is how Tanzania,
# Kenya and the Congo name their neighbour.
LEAD_REPEATS = cp.LEAD_REPEATS


def category_graph(conn):
    """(parents of each category, categories each article sits directly in)."""
    cat_parents, page_parents = {}, {}
    for parent, child, kind in conn.execute(
            'SELECT parent, child, kind FROM cat_edges'):
        if kind == 'subcat':
            cat_parents.setdefault(child, []).append(parent)
        else:
            page_parents.setdefault(child, []).append(parent)
    return cat_parents, page_parents


def ancestors(conn, titles):
    """{title: (direct category names, {ancestor category name: distance})}.

    Distance is how many steps up from the article's own category: 0 is a
    category the article is filed in, 1 its parent. The task rules use it
    because the further up you climb the less a category says about the
    article. A person from a district is three steps below "Districts of
    Uganda", and is not a district.
    """
    cat_parents, page_parents = category_graph(conn)
    memo = {}

    def up(cat, trail=()):
        if cat in memo:
            return memo[cat]
        if cat in trail:
            return {}
        found = {cat: 0}
        for parent in cat_parents.get(cat, ()):
            for k, d in up(parent, trail + (cat,)).items():
                if d + 1 < found.get(k, 99):
                    found[k] = d + 1
        memo[cat] = found
        return found

    def bare(c):
        return c.split(':', 1)[1] if ':' in c else c

    out = {}
    for title in titles:
        direct = page_parents.get(title, [])
        every = {}
        for cat in direct:
            for k, d in up(cat).items():
                if d < every.get(k, 99):
                    every[k] = d
        out[title] = (sorted(bare(c) for c in direct),
                      {bare(k): d for k, d in every.items()})
    return out


def judge(arts, anc):
    """Add `basis` to each article: why it counts as about Uganda, or ''.

    The lead is the weakest of the tests, so it is only trusted with company.
    Tanzania, Kenya and the Congo all name Uganda in the opening sentence as a
    neighbour. An article that sits directly in a Ugandan-named category has
    an editor's judgement behind it, and the lead need only agree; one that
    does not has to name Uganda in the opening and again after it.
    """
    def basis(row):
        reasons = []
        direct, every = anc.get(row['title'], ((), {}))
        if TITLE_WORDS.search(row['title']):
            reasons.append('title')
        evidence = row.get('wd_evidence')
        if isinstance(evidence, str) and evidence:
            tokens = [t.strip() for t in evidence.split(';')]
            n = row.get('wd_countries')
            if n == n and n is not None and n > MAX_COUNTRIES:
                tokens = [t for t in tokens if t != 'country']
            if tokens:
                reasons.append('wikidata: ' + '; '.join(tokens))
        first = row.get('lead_first') or 0
        hits = row.get('lead_hits') or 0
        ugandan_category = any(TITLE_WORDS.search(c) for c in direct)
        if ugandan_category and (first > 0 or hits >= LEAD_REPEATS):
            reasons.append('lead')
        elif first > 0 and hits >= 2:
            reasons.append('lead')
        if any(OFFICE.search(c) for c in direct):
            reasons.append('office')
        if not reasons and any(BIOTA.search(c) for c in every):
            reasons.append('biota')
        return ' + '.join(reasons)

    arts = arts.copy()
    arts['basis'] = arts.apply(basis, axis=1)
    return arts


def merge_relevance(conn, arts):
    rel = pd.read_sql('SELECT title, lead_hits, lead_first, wd_evidence, '
                      'wd_countries '
                      'FROM cat_relevance', conn)
    return arts.merge(rel, on='title', how='left')
