# 04 Dashboards and files guide

What every deliverable shows, sheet by sheet. For how a figure was worked out,
follow the section reference to [03 Methodology](03-methodology.md); for the
meaning of a column see [05 Data dictionary](05-data-dictionary.md).

All dashboards use the Wikimedia Community User Group Uganda colours. Sheets
that carry charts are laid out like a page; sheets that carry data look like an
ordinary spreadsheet, with gridlines, filters and frozen headers, and end where
their data ends.

---

## 1. Uganda Content Gap Dashboard (Excel and Google Sheets)

English Wikipedia's articles about Uganda. Files:
`Uganda Content Gap Dashboard (Excel).xlsx` and
`Uganda Content Gap Dashboard (Google Sheets).xlsx`.

**Using it.** On the **Dashboard** sheet choose a group (cell D6) and,
optionally, a sub-category beside it. Every tile, chart and table on the sheet
then recomputes for that choice: no macros are used, only formulas over the
**Data** sheet. A group or sub-category counts every article filed in it or
beneath it (section 4). Choosing *All categories* counts each article once.

**Google Sheets copy.** The same workbook prepared for Google Sheets: data bars
become colour scales, links to local folders become plain names, and the
sub-category dropdown lists every category rather than only the chosen group's.
Upload it to Drive and use *File, Make a copy* to make a selection of your own.

| Sheet | What it shows | Method |
|---|---|---|
| **Dashboard** | Eight tiles for the selection: articles, total views (all time), stub share, share with a Luganda article, share with no lead image, people, women among people, "read a lot, written little". Then charts: how good the articles are (class), how much they are read each year, when they were written, who the people are (gender by living or deceased), the ten most read articles, and what the articles need (the *Action* column). | 3: 5, 6, 7, 8 |
| **Categories** | The 18 main groups side by side: articles, share of articles and of views, stub share, share in Luganda, share with no lead image, people, women among people, read a lot / written little, words to reach C. Each group name links to its list in `category_files/`. | 4, 5, 8 |
| **All categories** | Every category and sub-category with an article about Uganda (3,572), with its articles, group and a link to its own list in `all_categories/`. Searchable and filterable. | 4 |
| **Representation** | Women and men with an article, compared on stubs, lead image, Luganda article, citations, length and readership, by category; women among biographies by category; living and deceased by gender; regional balance across the four regions; rural and urban places and the census units (UBOS) with an article. | 8, 9 |
| **Readership** | Views against the content that exists, year by year from 2015, with articles in existence; "readers go where the quality is" (share of views by class); the twenty-five most read articles. Year-by-year columns reach back to 2001 for articles written, edits and editors. | 6, 7 |
| **Editors** | Editors located in Uganda, by month and wiki, from January 2018 (Foundation data): editors making five or more edits a month, and casual and new contributors (1 to 4 edits) since mid-2023, for English Wikipedia, Luganda Wikipedia, Commons and Wikidata. | 11.1 |
| **Editor community** | The editors listed in *Category:Wikipedians in Uganda*, from the day each created an account: tiles (editors in the list, active in the last year, new accounts this year, median account age, edits so far), growth year by year, "who stayed" (accounts by year created and how many are still active), and a list of **every editor** from account creation to today with status. | 11.2 |
| **Priorities** | The articles in the top quarter of readership that are still stub or start-class (1,268 in all, the 400 most read listed): class, total views, references, Luganda article, words to reach C and action. Filter by category from the header row. | 5 |
| **Gaps** | What is missing: articles about Uganda that sit in no category (104), Uganda items with articles in other languages and none in English, and notable people with no English article. | 13 |
| **Luganda** | Luganda Wikipedia on its own: at a glance, year by year from its first article, how much each article has been read in all, and the twenty-five most read. The full list is in the Luganda workbook. | 12 |
| **Data** | One row per article with every column the dashboard computes from: class, stub, total views, Luganda article, lead image, person, gender, living or deceased, year created, views for each year (English and Luganda), action, high views low quality, bytes to reach C, references, Wikipedia categories, why it is about Uganda, and the category paths the selection formulas search. Filter or sort any column. | 3, 5 |
| **Calc, Lists** (hidden) | The formulas behind the Dashboard's charts, and the dropdown lists. | |

## 2. Luganda Wikipedia Pageviews (workbook)

`Luganda Wikipedia Pageviews.xlsx`: every article on Luganda Wikipedia
(section 12).

| Sheet | What it shows |
|---|---|
| **Executive summary** | Tiles (articles, views in all, the share with a Wikidata item and with an English article, articles read fewer than 1,000 times, articles never read, articles about Uganda, median article size) and charts of how readership is spread and how the wiki has grown. |
| **Year by year** | From the first Luganda article: articles written and in existence, views, edits and editors for each year. Views exist from 2015; earlier years show what the pages record. |
| **All articles** | Every article: views in all and for each year, when written, edits, size, Wikidata item, English article, whether it is about Uganda. |
| **Most read** | The thousand most read. |
| **Never read** | Articles with no recorded views. |
| **No English article** | Content Luganda has that English does not. |
| **No Wikidata item** | Articles with no Wikidata item, so no link to other languages. |
| **About Uganda** | The Luganda side of the articles in the English analysis (4,069). |

## 3. Uganda Wikimedia Projects Dashboard (Excel and Google Sheets)

`Uganda Wikimedia Projects Dashboard (Excel).xlsx` and `(Google Sheets).xlsx`.
One workbook for the projects other than Wikipedia (sections 14 to 17).

| Sheet | What it shows |
|---|---|
| **Overview** | At a glance across the Wikimedia projects; every project and edition checked (content pages, pages mentioning Uganda, editors); links to each project's own dashboard. |
| **Commons** | Wikimedia Commons: everything about Uganda to any depth. At a glance; how the collection has grown year by year (files and uploaders); what kind of files (photographs, drawings, video, audio, documents), by theme, by extension; Wiki Loves and other campaigns by year uploaded; the twenty-five largest categories; and **where Commons is thin** (empty and thin categories, unused files, one-file uploaders, how concentrated the uploading is). |
| **Wikidata** | At a glance; label coverage in English, Luganda, Swahili, French and German; items by what they are; places by type; people (gender, occupations); the lists the WikiProject keeps; Luganda lexemes; the tasks the WikiProject sets; important items; estimated growth of items about Uganda by year. |
| **Wikisource** | Texts, author pages and texts that mention Uganda or Luganda, by edition, most relevant first. |
| **Other projects** | What each of the other projects holds on Uganda, with pages that mention Uganda by project and growth by year. |
| **Where Uganda lives** | The share of Ugandan Wikipedia articles each project also covers, by main group; most-read articles with no Commons page; most-read articles that exist only in English. |
| **Luganda** | Luganda across the projects: editions that exist, Luganda on English Wiktionary, how much of Wikidata about Uganda can be read in Luganda, pages mentioning Luganda by project. |
| **Needs work** | What is missing and where to start. |
| **Projects data** | Every project edition checked and every count taken. |
| **Coverage data** | One row per Ugandan Wikipedia article and which other projects hold the same subject. |

## 4. A dashboard for each project (`project_dashboards/`)

Fifteen workbooks, each in two files (`... (Excel).xlsx`, `... (Google Sheets).xlsx`):

* Commons, Wikidata (built for files and items), and
* Wikisource, Wikiquote, Wiktionary (English), Wiktionary (Swahili), Wikibooks,
  Wikinews, Wikivoyage, Wikiversity, Wikispecies, Meta-Wiki, MediaWiki,
  Wikifunctions, and Runyankore Wikipedia on the Incubator.

The page projects carry the same sheets, reflecting the English Wikipedia
analysis:

| Sheet | What it shows |
|---|---|
| **Dashboard** | At a glance; how big the pages are; how much each page has been read in all; the ten most read pages. |
| **Growth** | Year by year: pages written, pages in existence, views, edits and editors, from the first page. |
| **Data** | **Everything the analysis is made from**: one row per page with every column (see [05](05-data-dictionary.md) section 4). Filter or sort any column. |
| **Most read** | The hundred most read pages. |
| **Needs work** | The gaps, with the pages to start from; the most read stubs and short pages. |
| **People** | (Wikiquote, Wikisource and Wikispecies, where pages are people.) Women and men, gender from Wikidata. |

The **Commons** workbook has the Commons sheet plus *Categories data* and *Files
data* (every category and every file). The **Wikidata** workbook has the Wikidata
and Luganda sheets plus *Items* (all 76,917 items, with all their columns) and
*Measures* (every figure the Wikidata sheet reports, as rows).

## 5. Category lists

| Folder | Contents |
|---|---|
| `category_files/` | One list per main group (`<group>.xlsx` and `.csv`), the building group's list including *Building type*; and the four reference files: `_All_articles.csv`, `_Excluded_not_about_Uganda.csv`, `_Reconciliation.csv`, `_Uganda_articles_not_in_English.csv`, plus `_Index.xlsx`. |
| `all_categories/` | One list per category (CSV, plus an Excel workbook from 100 articles), and `_Category_index.csv` with every category, its group and its count. |
| `project_categories/<project>/` | One list per category on that project (CSV, plus an Excel workbook from 100 rows) and `_Category_index`. Commons lists the **files** in each category, the page projects the **pages**. A page in two categories is in both lists. |

**The lists contain lists only.** Each holds the articles and every column
needed to work on them, with no analysis; the analysis is in the dashboards.
