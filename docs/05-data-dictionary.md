# 05 Data dictionary

The meaning of every column in the lists and Data sheets. Section numbers in
brackets point to [03 Methodology](03-methodology.md).

**Y / N / N/A.** Every yes/no column holds Y, N or N/A (section 20 of 03). Counts
are numbers. Years are four-digit numbers. A year column named for the current
year runs to the last complete month (for example *Views 2026 (Jan-Sep)*).

---

## 1. English Wikipedia article lists

Used by every file in `category_files/` and `all_categories/`. The dashboard's
Data sheet holds the same columns under slightly different headings (section 2).

| Column | Meaning |
|---|---|
| **Article** | The article's title; links to English Wikipedia. |
| **Wikidata** | Its Wikidata item (for example Q1036); links to Wikidata. |
| **Why it is about Uganda** | The tests it passed, joined with "+": title, wikidata (with what linked it), lead, office, biota [3]. |
| **Subcategory** | The first-level category beneath the group that the article hangs under. |
| **Depth** | How many levels below the group's own category the article was found (0 is filed directly in it). |
| **Class** | FA, FL, A, GA, B, C, Start, Stub or Unknown [5]. |
| **Class from** | `assessed` (a WikiProject class) or `size` (estimated from length) [5]. |
| **Size (bytes)** | Byte length of the article's wikitext. |
| **References** | Number of references and citation templates in the wikitext. |
| **Stub** | Y when the class is Stub or the article carries a stub template [5]. |
| **Maintenance tags** | Tags found: citation needed, unreferenced, update, more citations, stub template. |
| **Lead image** | Y when the article has a page image. |
| **Luganda article** | Y when the Wikidata item has a Luganda Wikipedia article. |
| **Luganda title** | That article's title. |
| **Commons category** | The Commons category named on the Wikidata item. |
| **Commons files** | Files in that category. |
| **Created** | Year of the article's first edit. |
| **Total views, all time** | Every month the Pageviews API holds, from July 2015 [6]. |
| **Views, last 12 months** | The twelve months to the last complete month. |
| **Luganda views, all time / last 12 months** | The same for the Luganda article. |
| **Views 2015 (Jul-Dec) ... Views 2026** | Views in each calendar year. |
| **Person** | Y if a human (Wikidata Q5); N/A if unknown [8]. |
| **Gender** | female, male or other / unrecorded; N/A for non-persons [8]. |
| **Living / deceased** | living, deceased or unknown; N/A for non-persons [8]. |
| **Born, Died** | Years from Wikidata. |
| **High views, low quality** | Y when in the top quarter of views and Stub or Start [5]. |
| **Action** | OK, Translate to Luganda, Expand, or Expand, then translate [5]. |
| **Expansion effort** | Small, Medium or Large; empty where no expansion is needed [5]. |
| **Bytes to reach C** | Bytes below 10,000 for an article that needs expanding [5]. |
| **Building type** | Only in the buildings list: road or bridge, railway, airport, religious building and so on [10]. |
| **Also in** | The other groups the article is in. |
| **Wikipedia categories** | The categories the article is directly filed in. |

`_All_articles.csv` starts with two more columns: **Primary category** (the one
group it is counted under, section 4) and **In categories** (every group it is in)
and leaves out *Subcategory*, *Depth* and *Also in*.

### Reference files in `category_files/`

| File | Columns |
|---|---|
| `_Excluded_not_about_Uganda.csv` | Article, Wikidata, Filed under (the group it was found in), Wikipedia categories, Uganda words in lead (how many Ugandan words the opening has), Wikidata evidence (any link to Uganda found). |
| `_Uganda_articles_not_in_English.csv` | qitem (Wikidata item), label, sitelink_count (how many languages have an article), lg_title, sw_title (Luganda and Swahili titles), type_labels (what it is), gender, date_of_birth, admin_label (where it is). |
| `_Reconciliation.csv` | Measure, Value, Note: see 03 section 19. |
| `_Index.xlsx` | One row per main group with its counts. |

### `all_categories/_Category_index.csv`

| Column | Meaning |
|---|---|
| **Category** | The category's name. |
| **Group** | The main group(s) it hangs under. |
| **Parent** | Its parent category. |
| **Articles** | Articles about Uganda in it or beneath it. |
| **Filed directly** | Articles filed directly in it. |
| **Share of views** | Its share of all views of articles about Uganda. |
| **Stubs, In Luganda, No lead image** | Shares of its articles. |
| **People, Women among people** | Count of people; share of women among those with a recorded binary gender (shown from 20 people). |
| **Read a lot, written little** | Count of Y in *High views, low quality*. |
| **Words to reach C** | Total words needed to bring its short articles to C class. |
| **Top level** | Y if it is one of the main groups. |
| **File** | Its list. |

---

## 2. The dashboard's Data sheet

One row per article. Columns A to AS; the ones that differ from section 1:

| Column | Meaning |
|---|---|
| **Category** | The article's primary category. |
| **Class group** | The class grouped as the dashboard charts it: Stub, Start, C, or B or better (B, GA, A, FA, FL). |
| **Created** | Year created. |
| **Views 2015 ... / Luganda views 2015 ...** | Views per year, English then Luganda. |
| **High views low quality** | Y/N. |
| **Key, Counts toward the total** | Helper columns the dropdown formulas use; ignore them. |
| **Categories (every level)** | The category paths (`|Group|Category|...|`) the selection formulas search to decide whether an article belongs to the chosen group or sub-category. |

---

## 3. Luganda workbook and `data/ug_luganda_pages.csv`

| Column | Meaning |
|---|---|
| **Luganda article** (`lg_title`) | Title on lg.wikipedia.org. |
| **English label** | Label of its Wikidata item in English. |
| **Total views, all time** | July 2015 on [6]. |
| **Created** | Year of the first edit. |
| **Edits** | Edits all time. |
| **Views 2015 ... 2026** | Views per year. |
| **Bytes** | Wikitext size. |
| **Wikidata** | Its item. |
| **English article** | The English article that the item links to, if any. |
| **About Uganda** | Y if it is the Luganda side of an article in the English analysis [12]. |

The CSV also holds `views_12mo`, `views_prior_12mo`, `instance_of`, the three
links, and `main_page` (Y for the wiki's front page, which every workbook leaves
out).

---

## 4. Per-project Data sheets (`project_dashboards/`) and `project_categories/`

One row per page (not for Commons and Wikidata, see sections 5 and 6).

| Column | Meaning |
|---|---|
| **Page** | Title on that project; links to it. |
| **Wikidata item** | The page's item, if it has one. |
| **Created, Created (year)** | Date and year of the first edit. |
| **Last edited** | Date of the last edit. |
| **Size (bytes), Words** | Wikitext size and word count. |
| **Total views, all time** | July 2015 on. Empty where the API holds nothing. |
| **Views 2015 ... 2026** | Views per year. |
| **Edits, all time; Edits 2002 ...** | Edits per year, from the page's history. |
| **Categories, Number of categories** | The page's categories (separated by "; ") and how many. |
| **Wikipedia languages with the subject** | Wikipedias in which its Wikidata item has an article. |
| **In Luganda Wikipedia, In Swahili Wikipedia** | Y/N. |
| **A person** | Y when its item is human. |
| **Gender** | female, male or other; N/A where not a person. |

`project_categories/<project>/_Category_index` has: Category, Pages, Total views
(all time), Share of the project's views, Median size (bytes), Stubs (under
1,000 bytes), With a Luganda article, People, Women among people, First page
written, List.

## 5. Commons

**Categories data / `project_categories/Wikimedia_Commons/_Category_index`**

| Column | Meaning |
|---|---|
| **Category** | Name, linking to Commons. |
| **Level below Category:Uganda** | Steps from `Category:Uganda` (0 is Uganda itself). |
| **Parent category** | The category it was found under. |
| **Files directly in it** | Files filed in it, not in sub-categories. |
| **Sub-categories** | How many sub-categories it has. |
| **Theme** | Matched from the category name; *Other* when none matches. |
| **Campaign** | The campaign named in the category (Wiki Loves ...). |
| **Its own name is Ugandan** | Y when the name is Ugandan; N for a category reached only through the two-step allowance. |

The Commons category index adds: Share of all files, Share used on no project,
Uploaders, First upload, Latest upload.

**Files data / each Commons list**

| Column | Meaning |
|---|---|
| **File** | File name, linking to Commons. |
| **Found in category** | The first category the crawl found it in. |
| **Uploaded, Year** | Upload date and year. |
| **Uploader** | The account that uploaded it. |
| **Size (bytes)** | File size. |
| **MIME type, Media type, Extension** | For example `image/png`, BITMAP, `.png`. SVG files are DRAWING; PNG and JPEG are BITMAP. |
| **Used on a Wikimedia project** | Y/N/N/A [14]. |
| **Wikis using it** | Number of wikis that use it. |

## 6. Wikidata

**Items** (76,917 rows)

| Column | Meaning |
|---|---|
| **Item** | Q number, linking to Wikidata. |
| **Label, English / Luganda / Swahili / French / German** | The item's label in each language; empty where it has none. |
| **Instance of, Instance of (codes)** | What the item is, with the Q numbers. |
| **Located in, Located in (code)** | Its administrative location. |
| **Latitude, Longitude** | Coordinates, where it has them. |
| **Image** | Image file named on the item. |
| **Commons category** | Its Commons category. |
| **English / Luganda / Swahili Wikipedia article** | Its article titles, where they exist. |
| **Gender, Born, Died** | For people. |
| **Created (estimated year)** | Estimated from the item number [15]. |
| **Has a Luganda label** | Y/N. |
| **Included because** | The route(s) into the list: country, citizen, located in. |

**Measures**: every figure on the Wikidata sheet as rows of *Measure, Name,
Value*.

## 7. Projects dashboard data sheets

**Projects data.** Project, Edition, Site, Content pages, All pages, Files, Edits,
Registered users, Active editors, Pages mentioning Uganda, Pages mentioning
Ugandan, Pages mentioning Luganda, Share mentioning Uganda.

**Coverage data.** Article, Wikidata item, Main group, Total views (all time),
Class, Wikipedia languages with the subject, and one Y/N column each for Luganda
Wikipedia, Swahili Wikipedia, Commons, Wikiquote, Wikisource, Wikivoyage,
Wikispecies, Wikinews, Wikibooks, Wikiversity and Wiktionary.

---

## 8. Editors

**Editor community sheet.**

| Column | Meaning |
|---|---|
| **Editor** | The user name; links to the user page. |
| **Account created** | Registration date (or the first edit if none is recorded). |
| **First edit, Last edit** | Dates of the first and latest edit seen. |
| **Edits** | The account's edit count. |
| **Years with edits** | Calendar years in which it edited. |
| **Status** | Active (last edit within a year), Quiet (one to three years), Inactive (over three), No edits. |
| **Rights** | User rights held (for example autopatrolled, rollbacker, administrator). |
| **Account age (years)** | Years from account creation to today. |

Growth rows: year, new accounts, accounts to date, edited that year, edited five
or more times, edits. Cohort rows: year, accounts created, still active, no longer
active.

**Editors located in Uganda** (`data/ug_editors_monthly.csv`,
`ug_editors_recent.csv`): month, wiki, activity band, the lower and upper bound
of the published range and a midpoint used only for charting.

---

## 9. The data in `data/`

Written by the data stages (see [06](06-pipeline-and-refresh.md)). The dashboards
are built from the database (`uganda_diversity.db`) and from the files below.

| File | What it holds |
|---|---|
| `ug_ccc_full_corpus.csv` | The Wikidata corpus: every item that has a Wikipedia article about Uganda, with the strategies that found it, labels, types, gender, dates, and titles in English, Luganda and Swahili. `is_core` (Y/N) marks the items found by the four core Wikidata tests (country, citizenship, location, birth or death place); the rest are keyword hits. Used for the *Uncategorised* group, the items with articles in other languages but not English, notable people with no English article, and rural against urban. |
| `ug_luganda_pages.csv` | Every Luganda article (section 3). |
| `ug_register_units.csv` | The UBOS census units (districts, counties, sub-counties, parishes) and whether each has an article. |
| `ug_commons_categories.csv`, `ug_commons_media.csv`, `ug_commons_summary.csv` | The first Commons audit: categories, file types, headline figures. |
| `ug_commons_geography.csv`, `ug_commons_geography_summary.csv` | Places of Uganda against Commons: category, files, lead image. |
| `ug_editors_monthly.csv`, `ug_editors_recent.csv` | Editors located in Uganda, by month, wiki and activity band, with the bounds of each published range. |
| `data/inputs/uganda_category_list.csv` | The client's list of Ugandan categories (columns *Category* and *Depth*). |
| `data/projects/projects.json` | The other projects' counts and the Wikidata WikiProject measures. |
| `data/analysis/*.csv` | Working tables behind the dashboard: women and men compared by category, regional balance, rural against urban, notable people with no English article. |
| `data/cache/` | The UBOS census workbook, downloaded once. |
