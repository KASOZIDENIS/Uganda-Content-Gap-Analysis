# 06 Pipeline and how to refresh

How the data is collected, how to bring everything up to date, and how each
deliverable is rebuilt. All commands are run from the project folder in a
terminal.

## 1. Requirements

* Python 3.10 or newer (built and tested on 3.14) and an internet connection.
* `pip install -r requirements.txt` installs `pandas`, `requests` and
  `xlsxwriter` (`numpy` comes with pandas).
* Excel or Google Sheets to read the workbooks.
* About 1 GB of disk space (the data folder is about 150 MB, the lists another
  450 MB).

## 2. Updating

Two commands bring the English Wikipedia and Luganda Wikipedia dashboards up to
date; the other Wikimedia projects have scripts of their own (section 4).

```bash
python src_data/refresh.py              # update, then rebuild the dashboards and lists
python src_data/refresh.py --remeasure  # the same, re-measuring every article's views
```

Updates are incremental. Category sizes are compared and only changed
categories are re-read, only new articles are tested and measured, and every
article's views are re-measured only when a new month of data is out (or with
`--remeasure`). Most updates take minutes; the month's first update, which
re-measures every article, takes hours. The run prints where it has reached;
press Ctrl+C to cancel. An interrupted run resumes next time, because every
stage works from what is still missing.

### The stages

| # | Stage | What it does |
|---|---|---|
| 1 | Check the category tree | Asks Wikipedia the size of every category already read (about a minute) and re-reads only those that changed. |
| 2 | Look for new articles | Searches for articles and categories named for Uganda, its places and its topics; adds the Wikidata corpus's uncategorised articles. |
| 3 | Read the new articles | Class, size, references and lead image of each article not seen before. |
| 4 | Remove what is not about Uganda | Tests each new article's opening sentence and Wikidata record; drops the ones that fail ([03](03-methodology.md) section 3). |
| 5 | Check Wikidata | Gender, life dates, Luganda links and Commons categories, refreshed for every article. |
| 6 | Date the new articles | The year each new article was first written. |
| 7 | Trace the edits | The edit history of each article, English and Luganda, so the years before page views and editor data begin are filled in. The first read takes about an hour; later runs read only pages edited since. |
| 8 | Count the views | Total, yearly and last-twelve-month views, for the new articles; for **all** of them when a new month of data is out. The longest stage. |
| 9 | Update the editors | The latest months of editors located in Uganda (Foundation releases) and the edits of the Wikipedians in Uganda. |
| 10 | Update Luganda Wikipedia | Every Luganda article: new pages, all-time views, edit history. |
| 11 | Rebuild the files | Category lists, every-category lists, analysis tables, the Excel and Google Sheets dashboards and the Luganda workbook. |

The update does **not** rebuild the other-project dashboards and category lists;
run section 4 and 5 for those.

### A file open in Excel

A workbook open in Excel cannot be overwritten. The builders then write beside
it with `_NEW` in the name (`..._NEW.xlsx`, `_NEW2`, and so on) and say so in the
log. Close the workbook and run the build again, or rename the new file.

## 3. Running from the beginning

The first time, or to rebuild from nothing. Every stage resumes where it
stopped, and re-running mid-month skips what is done.

```bash
pip install -r requirements.txt

# English Wikipedia (hours; resumable)
python src_data/run_all.py       # the Wikidata corpus, the census units, the places of
                                 # Uganda, the category profiles, editors, the Commons audit
python src_data/refresh.py       # edit histories, views, Luganda Wikipedia, then the files
```

`--force` on `run_all.py` recomputes every stage. To redo one stage:

```bash
python src_data/reset_stage.py --list       # what has run this cycle
python src_data/reset_stage.py <stage>      # clear that stage's checkpoint
```

Checkpoints are kept per **calendar month** in the `run_log` table, so a new
month starts a fresh cycle and the analysis stays current.

## 4. The other Wikimedia projects

Several hours, mostly the Wikidata Query Service. Each script resumes where it
stopped.

```bash
python src_data/sister_projects.py          # project counts and the WikiProject Uganda measures
python src_data/commons_full.py             # every Ugandan Commons category and file, no depth limit
python src_data/projects_history.py         # sitelinks, Wikidata growth, the other projects' pages
python src_data/wikidata_items.py           # every Wikidata item about Uganda, one row each
python src_data/project_analytics.py        # their views, categories, gender and edit histories
python src_data/incubator_nyn.py            # the Runyankore test pages only
```

## 5. Rebuilding the files

The builders read only the database and the data files, never the network, so
each takes seconds to a few minutes.

```bash
# English Wikipedia
python src_viz/build_category_files.py                  # category_files/
python src_viz/build_all_categories.py                  # all_categories/
python src_viz/build_analysis_data.py                   # data/analysis/
python src_viz/build_dashboard_excel.py                 # Dashboard (Excel)
DASH_TARGET=sheets python src_viz/build_dashboard_excel.py   # Dashboard (Google Sheets)
python src_viz/build_luganda_excel.py                   # Luganda workbook

# The other projects
python src_viz/build_projects_dashboard.py              # combined dashboard (Excel)
DASH_TARGET=sheets python src_viz/build_projects_dashboard.py
python src_viz/build_project_dashboards.py              # one per project (Excel)
DASH_TARGET=sheets python src_viz/build_project_dashboards.py
python src_viz/build_project_categories.py              # project_categories/
```

On Windows PowerShell set the variable first: `$env:DASH_TARGET='sheets'`.

Environment variables (all optional): `DASH_TARGET=sheets` (build the Google
Sheets version), `DRIVE_FOLDER` (a Drive folder address; links to category lists
then point there), `DASH_OUT` and `PROJ_OUT` (write somewhere other than the
project folder), `DASH_DEFAULT` and `DASH_SUB` (the group and sub-category the
dashboard opens on), `UG_DB` (use another database).

## 6. What the database holds

`data/uganda_diversity.db` (SQLite), 42 tables, by purpose:

| Purpose | Tables |
|---|---|
| English Wikipedia category walk | `cat_edges` (parent, child, kind), `cat_fetched`, `cat_info`, `cat_roots`, `cat_members` (article, group, sub-category, depth) |
| Articles | `cat_articles` (everything measured about one article), `cat_relevance` (lead and Wikidata evidence), `cat_wanted` (articles that pass), `search_hits` |
| Wikidata corpus | `ccc_items`, `sitelinks`, `strategy_hits`, `entity_labels`, `wikidata_only`, `wikidata_only_totals` |
| Edit histories | `rev_done` (first and last edit per page), `rev_edits` (edits per page per year), `rev_users` (distinct editors per wiki per year, IP addresses flagged) |
| Editors | `ug_editors`, `ug_editors_recent` (Foundation data), `wp_users`, `wp_user_years` (Wikipedians in Uganda) |
| Luganda Wikipedia | `luganda_pages` |
| Commons | `commons_ug_cats`, `commons_ug_files`, `commons_ug_catfiles` (the full crawl); `commons_categories`, `commons_files`, `commons_mediatype_check` (the first audit); `commons_geo` (places against Commons) |
| Wikidata | `wd_items`, `wd_items_done`, `wd_qdates`, `wd_ug_buckets` |
| Other projects | `proj_pages`, `proj_pageinfo`, `proj_views`, `art_sitelinks` |
| Places and census units | `geo_places`, `register_entries` |
| Bookkeeping | `run_log` (stage checkpoints), `refresh_meta` (when views were last measured) |

The database can be opened with any SQLite viewer (for example DB Browser for
SQLite).

## 7. Checks that were run

* **Dashboard formulas against the data.** The Excel dashboard was recalculated
  in LibreOffice and its tiles, top-five table, action counts and yearly counts
  compared with the same figures computed independently from the data with
  pandas. They matched exactly for All categories (for example 8,881 articles,
  428,853,094 views, 3,777 people, 1,268 high-views-low-quality articles) and for
  group and sub-category selections.
* **Workbooks.** All 35 workbooks were opened and their sheet lists checked. Data
  sheets show gridlines and borders and end where the data ends; chart pages are
  laid out like a page.
* **Y/N/N/A.** The flag columns of the rebuilt lists and CSV exports were checked
  to hold only Y, N or N/A.
* **A clean rebuild.** After the folder was reduced to what the dashboards need,
  every workbook and list was rebuilt from the database and compared with the
  version before.

## 8. Troubleshooting

| Symptom | Cause and remedy |
|---|---|
| `..._NEW.xlsx` appears | The workbook was open in Excel. Close it and rebuild. |
| A stage reports 429 or timeouts | Wikimedia is throttling. The stage retries and backs off; leave it, or re-run later: it resumes. |
| The Wikidata Query Service times out | Normal for heavy queries; the pipeline splits them. Re-run to resume. |
| Numbers look a month old | Views are measured to the last complete month. Run `refresh.py`; with `--remeasure` if a new month has begun. |
| "database is locked" | Two programs wrote at once. Run one stage at a time. |
