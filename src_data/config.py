# -*- coding: utf-8 -*-
"""Configuration shared by the data stages.

Paths, the endpoints every request goes to, and the tuning that keeps requests
gentle enough for Wikimedia's servers.
"""

import datetime
import os


# ---------------------------------------------------------------- cycle
def cycle_year_month():
    """The data cycle a run belongs to, e.g. '2026-09'.

    Stages are checkpointed once per calendar month, so a run in a new month is
    a new cycle and recomputes with fresh data.
    """
    return datetime.date.today().strftime('%Y-%m')


# ---------------------------------------------------------------- paths
PROJECT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(PROJECT_PATH, 'data')
DB_FILE = os.path.join(DATA_PATH, 'uganda_diversity.db')

os.makedirs(DATA_PATH, exist_ok=True)

# ---------------------------------------------------------------- endpoints
WDQS_ENDPOINT = 'https://query.wikidata.org/sparql'
CONTACT = 'denis@ripplenami.com'
USER_AGENT = f'UgandaContentGap/1.0 ({CONTACT}) python-requests'

# ---------------------------------------------------------------- territory
# Languages of Uganda that Wikidata items can carry as a sign of a Ugandan
# connection. Swahili is deliberately absent: it is a regional lingua franca,
# and using it as evidence would pull in tens of thousands of Kenyan and
# Tanzanian items, more than the whole genuine Uganda corpus.
UGANDAN_LANGUAGE_QIDS = [
    'Q33368',   # Luganda
    'Q35772',   # Runyankole
    'Q33705',   # Acholi
    'Q35818',   # Ateso
    'Q33587',   # Lusoga
    'Q36377',   # Lugbara
]

# Title keywords for the keyword search: articles whose title names the
# territory or its major places.
TITLE_KEYWORDS = [
    'Uganda', 'Ugandan', 'Kampala', 'Entebbe', 'Buganda', 'Busoga',
    'Bunyoro', 'Toro Kingdom', 'Ankole', 'Karamoja', 'Acholi',
]

# ---------------------------------------------------------------- tuning
SPARQL_CHUNK_SIZE = 700        # QIDs per chunked VALUES query
SPARQL_MIN_CHUNK = 80          # floor when backing off after a timeout
SPARQL_RETRIES = 4
SPARQL_PAUSE = 0.7             # seconds between WDQS calls, be a good citizen
