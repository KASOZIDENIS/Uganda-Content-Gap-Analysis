# 08 Code map

Which program makes which file. For maintainers. Programs are plain Python;
there is no build toolchain.

```
src_data/    collects data: network in, SQLite and CSV out
src_viz/     builds the files: database in, workbooks and lists out
data/        the database, the data files and the client's category list
docs/        this documentation
```

## 1. Collecting data (`src_data/`)

### 1.1 The English Wikipedia analysis

| Program | Does |
|---|---|
| `category_profiles.py` | The core: the category walk, discovery by search, reading each article, the relevance evidence, Wikidata facts, creation dates, views. Holds the groups, the Ugandan keywords and the walk's two-step allowance. |
| `refresh.py` | The incremental update: eleven stages, progress reporting, cancel and resume (see [06](06-pipeline-and-refresh.md)). |
| `revision_history.py` | Edits and editors per page per year, English, Luganda and other projects. Tables `rev_done`, `rev_edits`, `rev_users`. |
| `uganda_editors.py` | Editors located in Uganda per month from the Foundation's geoeditors releases. |
| `ugandan_wikipedians.py` | The accounts in *Category:Wikipedians in Uganda* and every edit of each. |
| `luganda_pages.py` | Every Luganda Wikipedia article with views, details, Wikidata link, edit history; writes `ug_luganda_pages.csv`. |

### 1.2 The Wikidata corpus, census units and places

| Program | Does |
|---|---|
| `content_retrieval.py` | Stage 1: the Uganda corpus from Wikidata by independent strategies (country, location, citizenship, birth or death place, title keywords); the number of strategies that agree is a confidence signal. |
| `corpus_export.py` | Stage 2: the corpus as `ug_ccc_full_corpus.csv`. |
| `ubos_units.py` | The census units (districts, counties, sub-counties, parishes) from the UBOS workbook, matched against the corpus; writes `ug_register_units.csv`. |
| `geo_places.py` | The cities, districts, sub-regions and refugee settlements of Uganda, each looked up on Wikipedia. |
| `commons_audit.py` | The first Commons audit (four levels) and the theme and campaign rules that `commons_full.py` reuses; writes `ug_commons_categories.csv`, `ug_commons_media.csv`, `ug_commons_summary.csv`. |
| `commons_geography.py` | Places against Commons: category, files, lead image. |
| `run_all.py`, `reset_stage.py` | The orchestrator for the stages above, and a tool to clear a stage's checkpoint. |
| `config.py`, `ug_utils.py`, `wikiapi.py`, `yn.py` | Paths, endpoints and tuning; Wikidata Query Service access, chunking, SQLite and checkpoints; one API call with back-off, the category-member walk and the quality class; the Y / N / N/A helper. |

### 1.3 The other Wikimedia projects

| Program | Does |
|---|---|
| `sister_projects.py` | Project statistics and the Wikidata WikiProject Uganda measures; writes `data/projects/projects.json`. |
| `commons_full.py` | The full Commons crawl, no depth limit; tables `commons_ug_cats`, `commons_ug_files`, `commons_ug_catfiles`; checks usage of each file. |
| `wikidata_items.py` | Every Wikidata item about Uganda, one row each (`wd_items`). |
| `projects_history.py` | Sitelinks of every Ugandan article, the Wikidata growth estimate, and the pages of the other projects with their creation dates. |
| `project_analytics.py` | Categories, Wikidata data, views and edit histories for those pages. |
| `incubator_nyn.py` | The Runyankore test pages on the Incubator only. |

## 2. Building the files (`src_viz/`)

### 2.1 English Wikipedia

| Program | Makes |
|---|---|
| `build_category_files.py` | `category_files/`: the lists, `_All_articles.csv`, the excluded list, the reconciliation. Holds the load of every article, the quality, action, effort and flag rules, and the shared workbook helper. |
| `build_all_categories.py` | `all_categories/`. |
| `build_analysis_data.py` | `data/analysis/`: women and men compared, regions, rural and urban, notable people with no article. |
| `build_dashboard_excel.py` | The Wikipedia dashboard, Excel and (`DASH_TARGET=sheets`) Google Sheets. |
| `build_luganda_excel.py` | `Luganda Wikipedia Pageviews.xlsx`. |
| `universe.py` | The relevance test and the category ancestors, shared so the files cannot disagree. |
| `structures.py` | The building-type classifier. |
| `history.py`, `luganda.py` | The year-by-year record and the editing community; the Luganda loader. Shared by the dashboards and the workbooks. |
| `sheet_tidy.py` | Ends every workbook where its data ends (hides unused rows and columns, keeps two spare). |
| `xl_basics.py` | Cell formats, tables and charts for the Luganda workbook. |

### 2.2 The other projects

| Program | Makes |
|---|---|
| `build_projects_dashboard.py` | The combined projects dashboard. |
| `build_project_dashboards.py` | The 15 per-project dashboards. |
| `build_project_categories.py` | `project_categories/`. |
| `projects_data.py` | The database accessors these use. |

## 3. How a figure travels

Take the number of stubs in "Health in Uganda":

1. `category_profiles.py` reads the article's wikitext and assessments and stores
   its class, size and stub tag in `cat_articles`.
2. `build_category_files.load()` joins it with the relevance test and sets the
   `stub` flag.
3. The flag is written as Y/N into `category_files/health_in_uganda.csv` and the
   dashboard's Data sheet.
4. On the Dashboard sheet the tile is `COUNTIFS(group, "Y")` over the Data sheet,
   so it follows whatever group is chosen; the Categories sheet computes the
   same share from the same rows.

Because every presentation reads the same loaded article table, the dashboard
and the lists cannot disagree.
