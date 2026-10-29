# -*- coding: utf-8 -*-
"""What kind of building or structure an article is about.

Wikipedia files these by type (airports, churches, hospitals, bridges), so the
type is read from the article's own title and the categories it sits directly
in. The first matching type wins, so the list runs from the most specific to
the most general. It is used for the
"Building type" column of the buildings file.
"""

import re

TYPES = [
    ('Lists', None),
    ('Airports and aviation',
     r'airport|airstrip|aerodrome|airline|aviation|airfield|air base'),
    ('Railways', r'railway|railroad|\brail\b|locomotive|rail transport'),
    ('Roads and bridges',
     r'\broads?\b|highway|expressway|bridge|bypass|flyover|motorway|'
     r'interchange|road transport'),
    ('Ports, ferries and water transport',
     r'\bports?\b|ferry|ferries|harbo|jetty|shipping|waterway|water transport|'
     r'inland water'),
    ('Religious buildings',
     r'church|cathedral|mosque|temple|shrine|basilica|chapel|monaster|'
     r'synagogue|religious buildings|places of worship|cathedrals'),
    ('Hospitals and health facilities',
     r'hospital|clinic|health cent|medical cent'),
    ('Education buildings',
     r'universit|school|college|campus|academy|institute of'),
    ('Sports venues',
     r'stadium|arena|golf|racecourse|cricket ground|football ground|'
     r'sports venue|sports complex|sports facilit'),
    ('Heritage, monuments and museums',
     r'heritage|monument|memorial|museum|tomb|palace|historic|\bfort\b|'
     r'castle|archaeolog|royal|shrines'),
    ('Government, security and justice',
     r'parliament|court|ministry|government building|prison|police|barracks|'
     r'military|embassy|state house|army|jail|headquarters|offices'),
    ('Hotels, offices and shopping',
     r'hotel|lodge|resort|\bmalls?\b|\bmarkets?\b|shopping|skyscraper|tower|'
     r'tallest|apartment|\bbank|commercial|restaurant|casino|theatre|cinema'),
    ('Energy, water and industry',
     r'\bdams?\b|power station|power plant|hydro|solar|pipeline|refinery|'
     r'water suppl|electric|substation|factory|\bmill\b|brewery|telecom'),
    ('Public transport and transport lists',
     r'\bbus\b|buses|taxi|boda|matatu|public transport|transport'),
]
OTHER = 'Other buildings and structures'
ORDER = [t for t, _ in TYPES] + [OTHER]
_COMPILED = [(t, re.compile(p, re.I) if p else None) for t, p in TYPES]
_GENERIC = re.compile(r'buildings and structures( in| under| by)?|'
                      r'building and structure stubs', re.I)


def classify(title, direct_cats):
    """The type of one article, from its title and direct categories."""
    if re.match(r'(List|Lists|Timeline) of ', title or ''):
        return 'Lists'
    text = _GENERIC.sub(' ', f'{title}; {direct_cats or ""}')
    for name, pattern in _COMPILED:
        if pattern is not None and pattern.search(text):
            return name
    return OTHER


# What the buildings group's own categories also hold: films shot at a place,
# battles and attacks, wildlife areas, dioceses, regions, books, people. These
# are about something else, so they stay under their own subject and not here.
_NOT_STRUCTURES = re.compile(
    r'\bfilms?\b|Attacks on|massacre|\bbattles?\b|murders?|crimes? in|clash|'
    r'shooting|stabbing|bombing|disaster|\bexecuted|national parks?|wildlife|'
    r'game reserves?|sanctuar|\bforests?\b|wetland|Ramsar|biosphere|'
    r'\bparks in\b|Dioces|Archdioces|Ecclesiastical|\bbishops?\b|'
    r'People from|\bwomen\b|\bbirths\b|Living people|novels|\bbooks\b|'
    r'Man-Eaters|registration plates|Cities in Uganda|Towns in Uganda|Airlines of|'
    r'Organisations based in|Companies of|companies based|Government-owned|'
    r'Church of Uganda|Anglican|Operation |\bwars?\b|conflict|elections?|terroris|hijack|\braid\b|'
    r'rebel|insurg|Regions of Uganda|Districts of Uganda|martyr', re.I)
_NOT_IN_TITLE = re.compile(
    r'\(film\)|\bdioces|archdioces|massacre|\bbattle of\b|\braid\b|'
    r'\bshooting\b|\bstabbing\b|\bclashes\b|National Park|Game Reserve|'
    r'Wildlife|Sanctuary|Forest|Wetland|Martyrs|Operation ', re.I)
_STRUCTURE_CATEGORY = re.compile(
    r'tombs?|museums?|hospitals|schools in|universities|airports|'
    r'airstrips|bridges|stadiums|churches|mosques|cathedrals|hotels|'
    r'skyscrapers|dams|\broads\b|railway stations|railway lines|'
    r'office buildings|palaces|prisons|libraries|power stations|'
    r'water supply|landmarks|shopping|markets|monuments|memorials', re.I)


def is_structure(title, direct_cats):
    """False for an article the buildings group holds only by association."""
    cats = direct_cats or ''
    if _STRUCTURE_CATEGORY.search(cats):
        return True
    return not (_NOT_STRUCTURES.search(cats) or _NOT_IN_TITLE.search(title or ''))
