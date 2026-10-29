# 02 Data sources

Everything comes from public Wikimedia endpoints and public releases. No
private data, no login and no paid service is used. Requests identify
themselves with a contact address in the user agent, as Wikimedia's policy asks
(`CONTACT` in `src_data/config.py`).

## 1. The sources

| Source | Address | What it provides | Used for |
|---|---|---|---|
| English Wikipedia API (MediaWiki Action API) | `en.wikipedia.org/w/api.php` | Category members and sizes, article text and size, references, page assessments (quality class), lead image, Wikidata item of a page, search results, edit histories, user accounts and contributions | The category walk, the relevance test, quality, size, references, creation dates, edit histories, the Wikipedians in Uganda |
| Wikimedia Pageviews API (REST) | `wikimedia.org/api/rest_v1/metrics/pageviews/per-article/` | Monthly human views of a page, from July 2015 | Every views figure, English, Luganda and the other projects |
| Wikidata API and Query Service | `wikidata.org/w/api.php`, `query.wikidata.org/sparql` | Items, labels, claims (gender, dates of birth and death, country, location, citizenship), sitelinks, counts for the WikiProject Uganda queries | The relevance test, people facts, the Wikidata dashboard, Luganda and Commons links |
| Luganda Wikipedia API | `lg.wikipedia.org/w/api.php` | Every content page, its size, its Wikidata item, its edit history | The Luganda workbook and sheets |
| Wikimedia Commons API | `commons.wikimedia.org/w/api.php` | Category tree, files in each category, upload date and uploader, size, type, which wikis use a file | The Commons dashboard |
| The other projects' APIs | for example `en.wikisource.org`, `species.wikimedia.org`, `meta.wikimedia.org`, `incubator.wikimedia.org` | Search for "Uganda", "Ugandan" and "Luganda", site statistics, page lists, page creation dates, categories | The combined and per-project dashboards |
| Wikimedia Foundation geoeditors releases | `dumps.wikimedia.org/other/geoeditors/` | Editors per country, wiki and month, in activity bands and published ranges, from January 2018 | The `Editors` sheet |
| Wikidata WikiProject Uganda | `wikidata.org/wiki/Wikidata:WikiProject_Uganda` | The list of things the WikiProject tracks | What the Wikidata dashboard measures |
| The client's category list | `data/inputs/uganda_category_list.csv` | WCUGU's own list of 2,885 Ugandan categories, with the level of each | The 14 top-level categories are the main groups, and the names start the category walk |
| UBOS 2024 census | `ubos.org`, the sub-county profiles workbook (kept in `data/cache/`) | The administrative hierarchy: 147 districts, 312 counties, 2,207 sub-counties, 10,854 parishes | The rural and urban comparison; the district list that Commons is checked against |

## 2. How fresh the data is

* **Pageviews.** The API holds nothing newer than the last complete month. A
  run measures to the last complete month before it started. At the time of
  writing the views run to **30 September 2026**. The window is worked out when
  the run starts (`pv_window()` in `src_data/category_profiles.py`), so a run in
  November measures October as well.
* **Editors.** The Foundation publishes monthly. The `Editors` sheet runs from
  **January 2018 to September 2026**.
* **Everything else** reflects the day the stage last ran. Each file records
  when it was built.

## 3. Request etiquette and failure handling

Wikimedia throttles heavy use, so every stage is deliberately gentle and
resumable.

* Five requests in parallel at most; a pause between batches
  (`SPARQL_PAUSE` in `config.py`, `PAUSE` in `wikiapi.py`).
* When the server answers "too many requests" (HTTP 429) or a timeout, the
  request backs off and retries, up to 30 times for the Wikipedia API.
* The Wikidata Query Service times out on heavy queries. Large lists are
  therefore read in small pieces: the Wikidata items about Uganda are fetched
  through the Wikidata API by item number rather than by one large query.
* Each stage records what it finished in the database (`run_log` table, once a
  calendar month), so an interrupted run resumes where it stopped instead of
  starting again.

## 4. What is stored

* `data/uganda_diversity.db`, a SQLite database with 42 tables; they are listed
  in [06](06-pipeline-and-refresh.md).
* `data/*.csv`, exports of some of those tables.
* `data/projects/projects.json`, the figures for the other projects' counts.
* `data/cache/`, the UBOS workbook, downloaded once and kept.

Nothing is sent anywhere: the programs only read from Wikimedia and write to
this folder.

## 5. Licences

* Wikipedia text and data: CC BY-SA. Wikidata: CC0. Commons files carry their
  own licences; this project reads only their descriptions, not the files.
* Colours come from the Wikimedia Community User Group Uganda logo, licensed
  CC BY-NC-SA 3.0.
* The analysis code is free to reuse.
