# Uganda Content Gap Analysis: Documentation

Prepared for the Wikimedia Community User Group Uganda (WCUGU).

This documentation explains how the Uganda content gap analysis was made: where the
data came from, how each number was worked out, what every deliverable
contains and how to bring it up to date. The dashboards themselves no longer
carry a "Method" tab. Everything those tabs said, and a good deal more, is
here.

## Where to start

| If you want to... | Read |
|---|---|
| Know what was delivered and which file to open | [01 Overview and deliverables](01-overview-and-deliverables.md) |
| Know where the data comes from and how fresh it is | [02 Data sources](02-data-sources.md) |
| Know how an article is judged to be "about Uganda", how views, quality, people and editors are counted | [03 Methodology](03-methodology.md) |
| Know what every dashboard, sheet and tab shows | [04 Dashboards and files guide](04-dashboards-guide.md) |
| Look up the meaning of a column | [05 Data dictionary](05-data-dictionary.md) |
| Update the data, or rebuild a file | [06 Pipeline and how to refresh](06-pipeline-and-refresh.md) |
| Know what the numbers cannot tell you | [07 Limitations and assumptions](07-limitations-and-assumptions.md) |
| Find which program makes which file | [08 Code map](08-code-map.md) |

## The analysis in one page

**The question.** What does English Wikipedia hold about Uganda, how good is
it, who reads it, who writes it, and what is missing? Then the same questions
for Luganda Wikipedia and for Wikimedia Commons, Wikidata, Wikisource and the
other Wikimedia projects.

**The answer is built in five steps.**

1. **Find every candidate article.** A walk through English Wikipedia's
   category tree, starting from the client's own list of Ugandan categories
   and following any category whose name is Ugandan. Searches and Wikidata add
   articles the categories miss.
2. **Test each article.** Being filed under a Ugandan category does not make
   an article about Uganda (Barack Obama sits under "Ugandan descent"). Each
   article is tested on its title, its Wikidata record and its opening
   sentence. What fails is listed with the reason, not silently dropped.
3. **Measure each article that passes.** Quality class, size, references,
   lead image, the year it was written, its views in every year since July
   2015, its edit history, its Wikidata facts (gender, life dates, Luganda
   link, Commons category).
4. **Group and count.** Articles are grouped by the main Ugandan category they
   sit under, and every one of the 3,572 categories and sub-categories has a
   list of its own.
5. **Present.** One interactive Excel dashboard (and a Google Sheets copy), the
   Luganda workbook, a dashboard for the other Wikimedia projects and one for
   each project, plus all the lists behind them.

**Headline figures at the time of writing** (data through September 2026):

| Measure | Figure |
|---|---|
| English Wikipedia articles about Uganda | 8,881 |
| Categories and sub-categories with a list of their own | 3,572 |
| Total views of those articles since July 2015 | 428,853,094 |
| Candidate articles tested and rejected as not about Uganda | 4,319 from the category walk, 17,499 search results |
| Luganda Wikipedia articles | 7,183 (6,189,472 views) |
| Wikimedia Commons: Ugandan categories and files | 6,384 categories, 62,878 files |
| Wikidata items about Uganda | 76,917 |
| Pages that mention Uganda on the other projects | 18,048 |
| Wikipedians in Uganda tracked through their own edits | 316 accounts |

These figures change every day. They are what the files held when this
documentation was written; the files themselves always show the current
figures.

## A note on Y, N and N/A

Wherever a column answers a yes/no question, every file uses the same three
values: **Y** for yes, **N** for no and **N/A** where the question does not
apply or the answer is not known (for example, the gender of something that is
not a person). Counts and percentages are numbers as usual.

## Conventions used in these documents

* "Article" means a page in the main namespace of a Wikipedia that is not a
  redirect.
* "Views" are human page views from the Wikimedia Pageviews API, with known
  bots and spiders excluded. "Views, all time" means every month the API holds,
  which starts in July 2015.
* File names are in `code style` and are relative to the project folder.
