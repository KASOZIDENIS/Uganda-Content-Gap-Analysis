# 07 Limitations and assumptions

What the numbers cannot tell you, and the choices that shape them. Read this
before quoting a figure. Section references are to
[03 Methodology](03-methodology.md).

## 1. The count of articles is a judgement, not a fact

* **The relevance test is a heuristic** (section 3). It is checked on every
  article and its reason is kept, but it can be wrong both ways. A few hundred
  articles filed directly in "... in Uganda" categories, such as expatriates and
  refugees, are probably about Uganda and are currently left out. Some borderline
  articles that mention Uganda in their opening may be included.
* **Species** filed under Ugandan fauna and flora count because they occur in
  Uganda, though many are found across the continent. They are 489 of the 8,881
  articles.
* **Anything relying on completeness should be read as a floor, not an exact
  count.** A classifier trained on assessed ground truth could catch culturally
  Ugandan topics that carry no explicit link to Uganda; this analysis uses
  explicit tests, which cannot.
* **A few widely read pages can dominate a total.** The most read article has
  more than 28 million views, and views are concentrated in a handful of
  articles, for example people with a Ugandan link who are famous worldwide.
  Read totals of views with that in mind, and use the per-article and
  per-year columns.
* **Counts depend on the category tree today.** Wikipedia's categories change
  daily. The count of 8,881 is a snapshot; so are the 3,572 categories.

## 2. Counting rules

* Group totals count an article in every group it is in, so groups add up to
  more than the total (section 4). Use *All categories* or the primary category
  for a count in which each article appears once.
* A count of the articles in Ugandan categories that does not test relevance
  counts memberships and everything that merely sits in a category, so it is
  always larger than the count of articles about Uganda (section 19).

## 3. Quality

* About 3% of articles carry a WikiProject class. For the rest the class is an
  **estimate from length** (under 2,000 bytes is called a stub), which says how
  much an article says, not how well. A long article full of unsourced claims is
  rated B; a short, excellent article is rated Stub. The *Class from* column
  keeps the two apart.
* The number of **references** is counted from the wikitext. Unusual citation
  styles may be missed.
* **Words to reach C** uses a working figure of six bytes per word and a C-class
  floor of 10,000 bytes; it is an order of magnitude for planning, not a target.

## 4. Readership

* **All-time views are views since July 2015.** The Pageviews API holds nothing
  earlier, so an article written in 2005 has no views for its first ten years.
  All-time views therefore cover a different span for an old article and a new
  one; to compare them, use the views for each calendar year, which every list
  gives.
* Before July 2015 the analysis can show only what the pages record (articles
  written, edits, editors), not how much they were read.
* Views count human page loads. They do not count reads through search-engine
  snippets, apps that cache pages, or mirrors, and they say nothing about **why**
  a page is read. The question of why an article is read most, or not at all,
  needs the reader research that page views cannot supply.
* An article with no recorded views may be unread, or new, or only recently
  linked from anywhere; check whether it is discoverable before rewriting it.
* Small numbers on a small wiki (Luganda, the Incubator) are noisy.

## 5. People

* **Gender** comes from Wikidata. Only female and male are compared; other or
  missing values are counted separately. Wikidata's gender data for Ugandan
  people is incomplete, so a share of women among people with a recorded gender
  is not the share among all people.
* **Living** is inferred: no death date and born in 1906 or later. A person with
  no birth date and no death date is *unknown*.
* The analysis does not record ethnicity, religion, disability or any other
  personal characteristic.

## 6. Representation and marginalised communities

The minutes ask to "identify missing perspectives from marginalised communities".
What can be measured from public Wikimedia data is limited:

* Women and men; living and deceased; the four regions; and rural and urban
  places. These are proxies.
* **Region** depends on an article being filed under a region category, so it
  places only part of the articles; an article about a place that is in no
  region category is not placed.
* **Rural and urban** is read from what the Wikidata item is (a village, a city),
  not from where the subject lives.
* Communities and perspectives that are not named in titles or categories (for
  example a particular community's history written under a general title) are not
  visible to this analysis. Closing that gap needs the inventories that are not
  published in machine-readable form: the Ministry of Gender's national heritage
  inventory, the Cross-Cultural Foundation of Uganda's (CCFU) case studies, the
  Uganda Community Museums Association's (UCOMA) community museums and the UBOS
  ethnicity tables. None is used here.

## 7. Editors

* **Editors located in Uganda** are **not** the same as editors of Ugandan
  content. Nothing public ties an editor's country to the articles they edit.
  An editor in Kampala may be writing about anything; an editor abroad may be
  writing about Uganda.
* The Foundation publishes the counts as **ranges** and, from mid-2023, with
  deliberate noise; the dashboards plot the middle of each range. Treat the
  trend as indicative, not as a measurement.
* **The Wikipedians in Uganda** are the editors who put themselves in
  *Category:Wikipedians in Uganda*. It is self-declared, so it is not every
  editor in Uganda, and some editors who are in Uganda have not joined the
  category. 332 pages were listed and 316 are accounts. The trend shows the
  growth of that community, not of all editing from Uganda.
* **Translation activity** (also in the minutes) is not measured directly. The
  analysis lists the articles that have an English version and no Luganda
  one, which is where translation would happen, but it cannot see translations
  already made through Wikipedia's content translation tool.
* Editors of the Ugandan articles are **registered accounts**; edits by people
  not logged in are counted as edits but not as editors.

## 8. Luganda Wikipedia

* The relationship to English is read through Wikidata. An article with no
  Wikidata item has no known English counterpart even if one exists.
* "About Uganda" for Luganda articles is true where the page is the Luganda side
  of an article in the English analysis; Luganda articles about Uganda with no
  English counterpart in the analysis are not marked.

## 9. Commons

* Counts are of files **filed directly** in a category; a file in two
  categories is counted once in totals and listed in both categories.
* **Themes** are guessed from category names, so a category named for a place
  or a person falls to *Other*. About a quarter of files had no theme at the time
  of the first audit.
* **Campaigns** are read from category names; files are often moved out of the
  campaign category to their subject afterwards, so campaign totals are a floor.
* Whether a file is **used** on a Wikimedia project is Wikimedia's global usage
  record at the time it was checked; 25 files were not checked (N/A). The
  figure that about 80% of files are used nowhere includes many files that are
  simply new or are in good categories but not yet on a page.
* The crawl follows categories whose own name is Ugandan and two steps beyond.
  A Ugandan file filed only under a category with no Ugandan name and more than
  two steps from one (for example a photograph filed only under a generic
  subject category) is not found.

## 10. Wikidata

* The items about Uganda are those whose country is Uganda, citizens of Uganda
  and items located within Uganda. Items related to Uganda in other ways (for
  example a work set in Uganda) are not in the list.
* **Created (estimated year)** is estimated from item numbers and is not each
  item's own history.
* A large share of the 76,917 items are bulk-imported records (schools, villages,
  parishes) with no article in any language; they are counted separately from the
  article-bearing items in the corpus.

## 11. Wikisource and the other projects

* They count **pages that mention** "Uganda", "Ugandan" or "Luganda". A work can
  mention Uganda without being about it, and a work about Uganda that never
  uses those words is missed. These are mention counts, not counts of works about
  Uganda.
* On projects with few pages the shares (stubs, little read) rest on small
  numbers.

## 12. The Incubator

The dashboard covers Runyankore Wikipedia (`nyn`) test pages only. Test wikis
are not Wikidata sitelinks, so content on other Incubator tests is not counted
(by design), and the Acholi test is not in the dashboard.

## 13. What is not here

* Content in languages other than English, Luganda and Swahili (apart from the
  Wikidata labels and the edition-composition tables) is not analysed.
* Offline sources (books, archives, oral histories) are outside the analysis.
  Wikimedia's coverage is measured against Wikimedia's own categories and
  Wikidata, not against an independent inventory of what should exist.
* Interactions between projects beyond the sitelinks (for example which Wikipedia
  articles cite Wikisource texts) are not measured.

## 14. Assumptions made on the client's behalf

* The client's own category list is the definition of "the Uganda tree",
  extended by Ugandan names and by search.
* **Sport in Uganda** is a main group in its own right.
* **Buildings and structures in Uganda** holds structures only; people and the
  other things filed there are excluded (section 10).
* There are **no task files**; every category has its own list instead.
* Colours are those of the WCUGU logo.
