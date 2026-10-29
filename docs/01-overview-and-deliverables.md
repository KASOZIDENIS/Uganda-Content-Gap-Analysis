# 01 Overview and deliverables

## 1. Purpose

WCUGU asked for a content gap analysis of what Wikimedia holds about Uganda,
presented as interactive dashboards in Excel and Google Sheets. In short:

* an analysis of English Wikipedia's articles about Uganda: quality, size,
  stubs, lead images, readership, when each was written, who is written about
  (women and men, living and deceased), Luganda coverage, and the articles that
  sit in no category;
* the same for Luganda Wikipedia;
* editors in Uganda, and how the community has grown over time;
* Wikimedia Commons, Wikidata, Wikisource and every other Wikimedia project:
  everything about Uganda, how it has grown and what is missing;
* a list for every category, and the data behind every dashboard.

Everything is built from public Wikimedia endpoints only: no database replicas,
dumps or Wikimedia Cloud account are needed.

## 2. What is in the folder

```
Uganda Content Gap Dashboard (Excel).xlsx                  English Wikipedia
Uganda Content Gap Dashboard (Google Sheets).xlsx          the same, for Google Sheets
Luganda Wikipedia Pageviews.xlsx                           Luganda Wikipedia
Uganda Wikimedia Projects Dashboard (Excel).xlsx           Commons, Wikidata, Wikisource, the rest
Uganda Wikimedia Projects Dashboard (Google Sheets).xlsx   the same, for Google Sheets
project_dashboards/        one dashboard per Wikimedia project (15, each in Excel and Sheets form)
category_files/            a list for each of the 18 main groups, and the reference lists
all_categories/            a list for each of the 3,572 categories and sub-categories
project_categories/        a list for every category on the other projects
docs/                      this documentation
data/                      the data the dashboards are built from
src_data/, src_viz/        the programs that collect the data and build the files
```

### 2.1 English Wikipedia

| Deliverable | File | What it is |
|---|---|---|
| Dashboard, Excel | `Uganda Content Gap Dashboard (Excel).xlsx` | The interactive workbook. Pick a main group and a sub-category on the Dashboard sheet and every tile and chart follows. |
| Dashboard, Google Sheets | `Uganda Content Gap Dashboard (Google Sheets).xlsx` | The same workbook prepared for upload to Google Sheets. |
| Category lists | `category_files/` | One list (Excel and CSV) for each of the 18 main groups, plus `_All_articles.csv` (every article once), `_Excluded_not_about_Uganda.csv`, `_Reconciliation.csv`, `_Uganda_articles_not_in_English.csv` and `_Index.xlsx`. |
| Every category | `all_categories/` | A list for each of the 3,572 categories and sub-categories, with `_Category_index.csv`. The dashboard's second dropdown reads this index. |
| Luganda workbook | `Luganda Wikipedia Pageviews.xlsx` | Every Luganda Wikipedia article with its views for every year, when it was written, its edits and where it sits against English. |

### 2.2 The other Wikimedia projects

| Deliverable | File | What it is |
|---|---|---|
| Combined dashboard | `Uganda Wikimedia Projects Dashboard (Excel).xlsx` and `(Google Sheets).xlsx` | One workbook for Commons, Wikidata, Wikisource and the other projects, with how Ugandan articles spread across them. |
| A dashboard for each project | `project_dashboards/` | 15 independent dashboards, each in Excel and Google Sheets form: Commons, Wikidata, Wikisource, Wikiquote, Wiktionary (English and Swahili), Wikibooks, Wikinews, Wikivoyage, Wikiversity, Wikispecies, Meta-Wiki, the Incubator (Runyankore test only), MediaWiki and Wikifunctions. |
| Category lists | `project_categories/` | A list for every category on each of those projects (21,134 lists), with a category index for each project. |

### 2.3 The data and the programs

| Item | Where | What it is |
|---|---|---|
| The database | `data/uganda_diversity.db` | Everything collected from Wikimedia: categories, articles, edit histories, views, Luganda articles, Commons, Wikidata, the other projects. SQLite; opens in any SQLite viewer. |
| Exports | `data/*.csv` | The Wikidata corpus, the Luganda articles, the Commons category and file summaries, the editors located in Uganda, the census units. |
| Working tables | `data/analysis/` | Tables behind the dashboard (women and men compared, regions, rural and urban, notable people with no article). |
| Inputs | `data/inputs/` | The client's list of Ugandan categories that starts the category walk. |
| Other project figures | `data/projects/projects.json` | Project statistics and the Wikidata WikiProject measures. |
| Programs | `src_data/`, `src_viz/` | See [08](08-code-map.md). |

## 3. How the client's requests were answered

The first column quotes or summarises an item from the project meeting minutes.

| Request | Where it is answered |
|---|---|
| People: deceased and living; female and male | `Representation` sheet; columns *Person*, *Gender*, *Living / deceased*, *Born*, *Died* in every list. |
| Article classes (quality ratings) | `Dashboard` sheet "How good are the articles?"; column *Class* with *Class from* in every list. |
| Thematic balance, men against women | `Representation` sheet: women and men compared on stubs, lead image, Luganda article, citations, length and readership, by category. |
| Missing perspectives, rural communities | `Representation` sheet: regional balance (four regions) and rural against urban places. Marginalised communities are only partly captured: see [07](07-limitations-and-assumptions.md). |
| Commons: count Uganda-related files across subcategories; underrepresented multimedia | Commons dashboard: files by theme, by type (photographs, drawings, video, audio, documents), by extension, by year, with the thinnest categories listed. |
| Flag articles with high readership but low quality | Column *High views, low quality*; `Priorities` sheet. |
| Quality: length, references, class; articles needing expansion or translation | Columns *Size (bytes)*, *References*, *Class*, *Action*; `Priorities` and `Gaps` sheets. |
| Stubs by subcategory; number of stubs; expansion effort | `Categories` sheet (stub share per group); columns *Stub*, *Expansion effort* and *Bytes to reach C*. |
| Campaigns (Wiki Loves Earth, Monuments, Folklore) and Commons | Commons dashboard: campaign uploads by year. |
| Ranking of most-read articles, English and Luganda | `Dashboard` (ten most read), `Readership` (twenty-five most read), `Luganda` sheet and the Luganda workbook (`Most read`). |
| Active editors, new contributors | `Editors` sheet (Foundation data, 2018 on) and `Editor community` sheet (from each editor's first account). |
| Match user interest with gaps | `Priorities` sheet: widely read articles that are still stubs or start-class. |
| Consumption per year and views per year; views against the content we have | `Readership` sheet: views by year against articles in existence. |
| Articles created per year | `Dashboard` ("When were the articles written?") and `Readership`, from 2001. |
| What is read most, and what is not read | `Dashboard`, `Readership`, and the Luganda workbook's `Never read` sheet. *Why* an article is read is not something page views can answer. |
| Uncategorised articles | The group **Uncategorised**, and the `Gaps` sheet. |
| Avoid duplication | Each article is counted once under one main group in the dashboard totals; see [03](03-methodology.md) section 4. |
| Number of editors over time, from Uganda, with a trend | `Editors` and `Editor community` sheets. |
| An interactive dashboard | The Excel and Google Sheets dashboards. |

## 4. How the files relate

```
 Wikimedia APIs ──► programs in src_data ──► SQLite database + CSV exports
                                                    │
                  ┌────────────────┬────────────────┼──────────────────┐
                  ▼                ▼                ▼                  ▼
          category lists    Excel / Sheets     Luganda workbook   other-project
          all categories     dashboard                            dashboards and
                                                                  category lists
```

All the English Wikipedia files are built from the same article list, so they
cannot disagree with one another: if the dashboard says 8,881 articles, so does
`_All_articles.csv`.
