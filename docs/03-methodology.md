# 03 Methodology

How each number was worked out. This document replaces the "Method" tabs that
used to sit inside the dashboards. Section numbers are used in the other
documents.

Contents: 1 What counts as an article about Uganda · 2 Finding candidates ·
3 Testing relevance · 4 Groups and counting · 5 Quality, stubs and effort ·
6 Readership · 7 History from the first article · 8 People · 9 Regions and
rural places · 10 Buildings and structures · 11 Editors · 12 Luganda Wikipedia ·
13 Gaps · 14 Commons · 15 Wikidata · 16 Wikisource and the other projects ·
17 Where Uganda lives across projects · 18 The Runyankore test · 19 From the
category tree to the articles

---

## 1. What counts as an article about Uganda

Wikipedia files articles under Ugandan categories that are not about Uganda:
people of Ugandan descent, films shot there, neighbouring countries, global
topics such as the English language or the Equator. The category tree also
leads out of Uganda: geography leads to African districts, and from there to the
rest of the encyclopedia.

So **being in a Ugandan category is not accepted as proof.** Each article is
tested on its own, and the reason it passed is kept in the column *Why it is
about Uganda*. What fails is listed with its category in
`category_files/_Excluded_not_about_Uganda.csv`. Nothing is dropped without
being shown.

## 2. Finding candidate articles

There are three routes in. Every article found by any of them still has to pass
the test in section 3.

**2.1 The category walk.** The walk starts at `Category:Uganda` and at every
category on the client's own list (the 2,885 categories in
`data/inputs/uganda_category_list.csv`), plus any category found by searching for Ugandan names
(Uganda, Ugandan, Kampala, Buganda, Bunyoro, Ankole, Busoga, Tooro, Karamoja,
Acholi, Teso, Lango, Entebbe, Rwenzori, Baganda, Lugbara, Luganda, Kigezi,
Bugisu, Bukedi, West Nile).

* A category is **followed** if its own name is Ugandan (on the client's list,
  or it contains one of those names or another keyword such as Jinja, Gulu or
  Mbarara).
* Below a Ugandan-named category the walk may go **two further steps** through
  categories whose names are not Ugandan, because Wikipedia files "Hospitals in
  Kampala" under "Hospitals in Uganda" and the Ugandan name is lost one step
  down. Every Ugandan-named category it meets resets that allowance.
* There is **no depth limit in practice**: what stops the walk leaking into the
  rest of Wikipedia is the allowance, not the depth. (A safety ceiling of 10
  levels exists to guard against loops; the deepest Ugandan categories sit at
  that level.)
* Maintenance categories (Wikipedia, WikiProject, "Articles ...", "CS1" and
  similar) are skipped.

The walk assigns every article to a **main group**. There are 18:

* the 14 top-level categories of the client's list: Buildings and structures in
  Uganda, Culture, Economy, Education, Environment, Geography, Government,
  Health, History, Politics, Society, Ugandan people, Uganda stubs and
  Uganda-related lists;
* **Sport in Uganda**, added as a main group because it sits under Culture,
  Society and Ugandan people at once and so was in none of them as a whole;
* **Other Uganda categories**: Ugandan categories the client's list did not
  place under any main group;
* **Found by search** and **Uncategorised**, described next.

**2.2 Search.** A full-text search for each Ugandan name finds articles that no
category walk reaches. The group *Found by search* holds the ones that pass the
test and were not already in the tree. A further 17,499 search results mention
Uganda without being about it and are rejected (they are counted in
`_Reconciliation.csv`, not listed).

**2.3 The Wikidata corpus.** Separately from the categories, Wikidata is asked
for every item that has an English article and whose country, citizenship,
location (inside Uganda's administrative hierarchy) or birth or death place is
Uganda. Those that the category walk did not reach form the group
**Uncategorised**: articles that are about Uganda but sit in no Ugandan
category, which is what the project meeting asked to find.

## 3. Testing relevance

An article counts as about Uganda if **at least one** of these holds. All that
hold are recorded, joined with "+" in *Why it is about Uganda*.

| Test | Rule |
|---|---|
| **title** | The title contains a Ugandan name (Uganda, Ugandan, Kampala, Buganda, Bunyoro, Ankole, Busoga, Tooro, Karamoja, Acholi, Entebbe, Luganda, Lugbara, Kigezi, Bugisu, Bukedi, Jinja, Gulu, Mbarara, Lusoga, Runyankore, Ateso and similar). |
| **wikidata** | The article's Wikidata item reaches Uganda by country, citizenship, country of origin, jurisdiction, a "located in" chain, or a birth or death place in Uganda. The *country* claim is ignored when the item lists **more than three** countries, because the Nile, the Equator and the English language list Uganda among a dozen. |
| **lead** | The opening sentence names Uganda. Where the article sits directly in a Ugandan-named category (an editor's judgement is behind it) the lead need only agree: a Ugandan name in the first 250 characters, or three or more mentions in the lead. Where it does not, the lead has to say Uganda in the first 250 characters **and** at least once more. A single mention further down is how Kenya and Tanzania name their neighbour. |
| **office** | The article is filed as a holder of a Ugandan office (governors, presidents, prime ministers, kabakas, chief justices, high commissioners, ambassadors, administrators, commissioners of Uganda). Queen Elizabeth II was Queen of Uganda and a governor may be described only by his career. |
| **biota** | A species filed under a Ugandan fauna or flora category (birds, mammals, fish, plants, insects and so on). Wikipedia files a species there because it occurs in Uganda, and the lead often does not say so. Used only when no other test passes. |

Results: of 12,858 articles found anywhere in the walked tree, 4,319 fail and
8,526 pass; 355 more come from Wikidata and search; **8,881 articles are about
Uganda** (section 19). The basis of the 8,881: lead 8,069, wikidata 6,286, title
1,439, biota 489, office 166 (an article can have several).

The test is a heuristic. See [07](07-limitations-and-assumptions.md).

## 4. Groups and counting

* **Category lists** (`category_files/<group>.xlsx` and `.csv`) list an article in
  **every** group it is filed in, so each list is complete on its own. The
  column *Also in* names the other groups. The lists therefore add up to more
  than the number of distinct articles.
* **All categories** (`all_categories/`) has a list for every category and
  sub-category that holds an article about Uganda: 3,572 of them. A category's
  list holds the articles filed in it **or in any category beneath it**.
  Categories with no article left after the test are listed in the index too,
  marked as empty, so every category found is searchable.
* **The dashboard** follows the same rule. Choosing a group, then a
  sub-category, counts every article filed there or beneath. Choosing **All
  categories** counts each article once: 8,881.
* **Primary category.** Where an article has to appear once (`_All_articles.csv`,
  the Priorities list), it is assigned the smallest of its groups, ignoring
  "Uganda stubs" and "Uganda-related lists" unless they are its only groups.
  The smallest group is chosen so that small, specific groups (Uganda's
  buildings, say) are not swallowed by large general ones.
* **Duplication.** Counting by membership is deliberate: each list has to stand
  on its own. Nothing is removed from one list to avoid repeating it in another.
  The one-per-article counts (All categories, primary category) avoid
  double-counting where a total is needed.

## 5. Quality, stubs and effort

**Class.** Where an article carries a WikiProject assessment, that class is used
(FA, FL, A, GA, B, C, Start, Stub; the highest class if several projects
disagree). About 3% of articles carry one (278 of 8,881). Every other article
gets an **estimate from its length**: under 2,000 bytes Stub; under 10,000
Start; under 25,000 C; above that B. The column *Class from* says which: `assessed` or `size`. The two are never mixed up
in a chart.

**Size** is the byte length of the article's wikitext (its source), not the
length of the rendered page. **References** are counted in the wikitext:
`<ref>` tags plus citation and sfn templates.

**Stub** (Y/N) is Y when the class is Stub or the article carries a stub
template. **Maintenance tags** records the tags seen: *citation needed*,
*unreferenced*, *update*, *more citations needed*, *stub template*.

**Lead image** is Y when the article has a page image.

**Action** says what an article needs:

| Action | When |
|---|---|
| OK | A list, or an article that is C-class or better, has references and has a Luganda article. |
| Translate to Luganda | Good enough (not a stub or start, has references) but no Luganda article. |
| Expand | A stub or start, or with no references, but a Luganda article exists. |
| Expand, then translate | A stub or start, or with no references, and no Luganda article. |

**Bytes to reach C** is how far an article that needs expanding is below
10,000 bytes (the floor of a C-class article). **Words to reach C** divides that
by 6, the working figure of bytes per word. **Expansion effort** bands the gap:
Small up to 3,000 bytes, Medium up to 7,000, Large above.

**High views, low quality** (Y/N) is Y when the article is in the **top quarter
of all-time views of the whole corpus** (at least the 75th percentile) and its
class is Stub or Start. The threshold is set across the whole corpus, not per
category, so an article is flagged the same way in every list it appears in.
The 75th-percentile value appears on the `Priorities` sheet.

## 6. Readership

* **What a view is.** Human views of the page, all platforms, with known bots
  and spiders excluded: the Pageviews API's `all-access`, `user` agent type.
* **Where from.** The Pageviews REST API, **one request per article**, returning
  a figure per month from July 2015 (the first month it holds) to the last
  complete month. The monthly figures are added into calendar years.
* **Total views, all time** is the sum of every month the API holds. An article
  written before July 2015 is therefore counted from July 2015, and one written
  later is counted from the month it was written. *Views 2015 (Jul-Dec)* is the
  half year; each later year is a full year (the current year runs to the last
  complete month).
* **Views, last 12 months** is kept in the lists and the Data sheet for
  reference. The dashboards show all-time views.
* **Before July 2015** the API holds no views at all. For those years the
  analysis shows what pages themselves record: articles written, edits and
  editors per year (section 7).
* **Luganda views** are measured the same way for the Luganda article that
  matches an English one (columns *Luganda views, all time* and per year).
* An article that has no recorded traffic is shown with 0; the API reports
  nothing rather than a zero for an unread page.

## 7. History from the first article

The first Ugandan article was written in **2001**. The Pageviews API starts in
2015 and the Foundation's editor-location data in 2018, but every page keeps its
full edit history from its first edit. The analysis reads that history for each
article in the analysis and for its Luganda counterpart and records, per year:

* **articles written**: the year of each article's first edit;
* **edits**: edits to the article in that year, including edits by people not
  logged in;
* **editors**: distinct **registered accounts** that edited in that year, counted
  once a year across the wiki; edits by IP address are not counted as editors.

The first read takes about an hour; later updates read only the edits made
since. The year-by-year tables in the dashboard and the Luganda
workbook (*Articles in existence*, *Written*, *Edits*, *Editors*) are built
from this.

## 8. People

* A page is **a person** (Person = Y) when its Wikidata item is an instance of
  *human* (Q5). Where the item could not be read the answer is N/A.
* **Gender** is Wikidata's *sex or gender* claim (female, male). Anything else,
  or no claim, is *other / unrecorded*; the analysis compares female and male
  only and counts the rest separately. For a page that is not a person, Gender
  is N/A.
* **Born** and **Died** are years from Wikidata's dates of birth and death.
* **Living / deceased.** *Living* means no death date **and** born in 1906 or
  later (so that people with no recorded death but born over a century ago are
  not counted as living); *deceased* means a death date; *unknown* is a person
  with neither fact. Non-persons are N/A.
* "Women among people" is shown only where at least 20 people have a recorded
  binary gender (10 for the other-project lists), so small groups do not give
  misleading percentages.

## 9. Regions and rural places

Both measures are on the `Representation` sheet and are working tables in
`data/analysis/`.

* **Regional balance.** An article belongs to a region when it, or a category
  above it, is filed under *Central, Eastern, Northern* or *Western Region,
  Uganda*. An article in two regions counts in both. Kampala is in the Central
  Region. Articles with no region are not placed.
* **Rural against urban.** Wikidata items about Uganda are classed by what they
  are: **urban** (cities, municipalities, town councils, divisions) and
  **rural** (sub-counties, counties, parishes, villages, hills, streams). The
  sheet shows how many of each have an English and a Luganda article. Beside it,
  the 2024 census units (UBOS) show how many districts, counties, sub-counties
  and parishes have an article.

## 10. Buildings and structures

The group gathers Wikipedia's buildings and structures categories together with
its transport categories and the lists of buildings, transport and the tallest
buildings in Africa. Roots outside the group's own category are opened only
through categories whose names are Ugandan, so the continental list brings in
its Ugandan entries and not the continent. From *Uganda-related lists* only
lists about structures and transport are taken (title filter).

People named in these categories are **left out of the group** (a person
appears only under the groups that really cover them), and so are films,
attacks, parks and dioceses filed there. Each remaining article is given a
**Building type** from its title and the categories it sits in directly (roads
and bridges, railways, airports, ports and ferries, religious buildings,
hospitals, education buildings, sports venues, heritage, government, hotels and
offices, energy and water, and lists). The first matching type wins, from the
most specific to the most general.

## 11. Editors

Three different measures answer three different questions.

**11.1 Editors located in Uganda** (`Editors` sheet).
The Wikimedia Foundation publishes editors per country, wiki and month, from
January 2018, in activity bands (1 to 4 edits, 5 to 99, 100 or more). They are
published as **ranges** (for example 41 to 50) to protect privacy, so the charts
plot the middle of each range, averaged across the year's months. From mid-2023
the Foundation adds deliberate noise of a few editors either way; Luganda counts
below ten are published as 1 to 10. This counts editors **located in Uganda
whatever they edited**. Nothing public ties an editor's country to the articles
they touched, so "editors of Ugandan content" is not recoverable and is not
claimed.

**11.2 The editing community** (`Editor community` sheet).
English Wikipedia's *Category:Wikipedians in Uganda* lists editors who declare
themselves to be in Uganda: 332 pages listed, **316 accounts** found. For each,
the account's registration date, edit count, rights and the date of **every
edit** are read, so the community can be followed from each person's first
account, years before the Foundation's data begins. It is self-declared, so it
is not every editor in Uganda. For each editor the sheet gives status by the date
of the last edit: **Active** (within the last year), **Quiet** (one to three
years), **Inactive** (over three years), **No edits**. Cohort rows show, for the
accounts created in each year, how many are still active. Each editor is listed
in the sheet, with a link to their user page.

**11.3 Editors of the Ugandan articles** (section 7), counted from each page's
history, in English and Luganda.

## 12. Luganda Wikipedia

Luganda Wikipedia is small enough to take whole. Every content page in the main
namespace of `lg.wikipedia.org` is listed through the MediaWiki *allpages* API
(redirects excluded), not sampled and not reached through a category: **7,183
articles**. The wiki's front page is left out because it is not an article and
would dominate every total. For each article:

* views, all time and per year, as in section 6 (one request per article);
* written, edits and editors, from its edit history (section 7);
* its **Wikidata item**, from the page itself, and its **English article**, from
  that item's sitelinks. An article with an item but no English sitelink is
  content Luganda has and English does not, the reverse of the gap this project
  usually measures;
* **About Uganda** (Y/N) is Y where the page is the Luganda side of an article
  in the English analysis (4,069 articles).

## 13. Gaps

Three lists answer "what is missing".

* **Uncategorised articles** (group *Uncategorised*, 104 articles): about
  Uganda, in no Ugandan category (section 2.3).
* **Uganda items with articles in other languages but not in English**
  (`_Uganda_articles_not_in_English.csv`): Wikidata items in the Uganda corpus
  that have a Luganda, Swahili or other article and no English one, ranked by
  how many languages have written about them.
* **Notable people with no English article**: Wikidata items that are human,
  with a Ugandan link and no English article, ranked by number of languages
  (`data/analysis`, shown on the `Gaps` sheet).

## 14. Wikimedia Commons

* **Everything under Category:Uganda, with no depth limit.** The first audit
  stopped four levels down because a walk with no stop leaks into the rest of
  Commons: Commons files Uganda's lakes, rivers and mountains under categories
  it shares with Kenya, Tanzania, Congo and Rwanda. The full crawl stops the
  leak the same way as the Wikipedia walk: a category is followed when its own
  name is Ugandan, or when it is within two steps of one that is. Result:
  **6,384 categories**.
* For every category the files **directly in it** are recorded; for every file
  when it was uploaded, by whom, its size, MIME type and media type. Result:
  **62,878 files**, uploaded between 2004 and 2026. A file in two categories is
  counted once in totals and appears in both category lists.
* **Media type** is the type Commons itself reports: BITMAP is a raster picture
  (JPEG, PNG, GIF, TIFF, WebP), DRAWING is a vector drawing (SVG), VIDEO is WebM,
  OGV or MPG (Commons does not take MOV), AUDIO is OGG, WAV, FLAC or Opus, and
  OFFICE is PDF or DjVu. **Extension** is read from the file name. **Uploaded** is
  the date of the file's latest version.
* **Used on a Wikimedia project** (Y/N/N/A) is whether any wiki uses the file
  (Wikimedia's global usage). About 80% of the files (50,051) are used nowhere;
  25 were not checked and show N/A. *Wikis using it* is the number of wikis.
* **Themes** are matched from the category's title, the only text a crawl has,
  so a category named for a place or a person cannot be classified and falls to
  *Other*. **Campaigns** (Wiki Loves Earth, Monuments, Folklore, Africa and
  others) are read from the category name. Campaign uploads are often
  recategorised to their subject afterwards, so campaign totals are a floor.
* **Where Commons is thin** (on the Commons sheet) counts: categories with no
  files and no sub-categories, categories with one to four files, files used on no
  project, files not yet checked, uploaders who added a single file, and the
  share of files from the ten busiest uploaders.
* **Places and Commons.** The districts, cities, sub-regions and refugee
  settlements of Uganda (the district list comes from the UBOS census) are looked
  up on Wikipedia and on Commons: does the place have an article, does that
  article use a lead image, does Commons have a category for it and how many files
  does it hold. The `Needs work` sheet of the projects dashboard reports districts
  with no files and with fewer than five files; `data/ug_commons_geography.csv`
  has every place.

## 15. Wikidata

The Wikidata dashboard follows what the
[Wikidata WikiProject Uganda](https://www.wikidata.org/wiki/Wikidata:WikiProject_Uganda)
tracks.

* **The items.** Every Wikidata item about Uganda is read as a row (**76,917**
  items). An item is included through one or more of three routes, recorded in
  *Included because*: its **country** is Uganda; it is a **citizen** of Uganda
  (people); it is **located in** Uganda (a chain of "located in the
  administrative territory" claims reaching Uganda). The list is read in ranges
  of item numbers small enough for the Wikidata Query Service and its detail
  (labels, claims, sitelinks) through the Wikidata API.
* **Measures** come from queries over those items and from the WikiProject's own
  lists: items by what they are and where they are; people by gender and
  occupation; **label coverage** in English, Luganda, Swahili, French and German;
  the lists of hospitals, universities, schools, museums, hotels, parks and
  monuments; Luganda **lexemes** (the words) by lexical category; and the tasks
  the WikiProject sets (items with no Luganda label, no classification, no
  image).
* **Growth.** Wikidata numbers its items in the order they are made, so an
  item's number says roughly when it was created. The creation dates of a few
  hundred items spread across the number range fix the curve, and Uganda's items
  are then counted by number. *Created (estimated year)* is therefore an
  **estimate from the numbering, not each item's own history.**

## 16. Wikisource and the other projects

For Wikisource, Wikiquote, Wiktionary (English and Swahili), Wikibooks,
Wikinews, Wikivoyage, Wikiversity, Wikispecies, Meta-Wiki, MediaWiki and
Wikifunctions:

* The project's own **search** for "Uganda", "Ugandan" and "Luganda" lists the
  pages. This counts **pages that mention Uganda, not works about Uganda**.
  Only content namespaces are searched (Wikisource also searches Author, Index
  and Page).
* The site's own statistics give the project's content pages, edits, registered
  and active editors, so the share of the project that mentions Uganda can be
  shown.
* For each page the same analytics as English Wikipedia are gathered: size,
  words, **views in every year from July 2015**, **categories**, **when it was
  written** (first edit), **edits and editors per year** from its history, the
  Wikidata item, the number of Wikipedia languages with the subject, whether a
  Luganda or Swahili article exists, and for a person their gender.
* Size classes on these dashboards are: Stub under 1,000 bytes, Short 1,000 to
  4,999, Medium 5,000 to 19,999, Long 20,000 and over. Pages read fewer than 100
  times since July 2015 count as little read.
* Editions that do not exist (for example some Swahili projects) are left out.

## 17. Where Uganda lives across the projects

For each of the 8,881 Ugandan Wikipedia articles, its Wikidata item says
which other projects hold the same subject (Commons, Wikiquote, Wikisource,
Wikivoyage, Wikispecies, Wikinews, Wikibooks, Wikiversity, Wiktionary) and in
how many Wikipedia languages it has an article. The sheet *Where Uganda lives*
shows each project's share of Ugandan articles, by main group, and lists the
most-read articles that have no Commons page or exist only in English.

## 18. The Runyankore test

The Incubator holds tests of new language editions as pages whose titles begin
with the edition's code. The Incubator dashboard is about **Runyankore Wikipedia
(`nyn`) only**: every page under `Wp/nyn/` (2,193 pages), read in full, and no
other test on the Incubator. For each page the same analytics are gathered as
for the other projects.

## 19. From the category tree to the articles

`category_files/_Reconciliation.csv` shows how the articles in the category tree
become the articles about Uganda. Figures at the time of writing:

| Measure | Value | Note |
|---|---:|---|
| Distinct articles anywhere in the walked tree | 12,858 | Every article in a category the walk reached |
| of which fail the test for being about Uganda | 4,319 | Listed in `_Excluded_not_about_Uganda.csv` |
| of which are about Uganda | 8,526 | |
| Added by the Wikidata corpus and by search | 355 | Passed the same tests |
| **Articles about Uganda, in total** | **8,881** | The `_All_articles.csv` file |
| Search results rejected for not being about Uganda | 17,499 | Pages that mention Uganda without being about it |

A count of the articles in Ugandan categories that does not test relevance
counts memberships (an article in three categories counts three times) and
includes everything that merely sits there, so it will always be larger than
8,881, which counts each article once and only if it is about Uganda.

---

## 20. The Y, N and N/A convention

Every yes/no column in every file uses **Y**, **N** or **N/A**. *N/A* means the
question does not apply (the gender of a page that is not a person, the living
status of a non-person) or the answer is not known (a Commons file whose usage was
not checked). Inside the analysis the same flags are held as 1 and 0; the
files show Y and N, and the dashboards' formulas count "Y" and "N".
