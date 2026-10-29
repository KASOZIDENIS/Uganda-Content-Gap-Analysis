# Uganda Content Gap Dashboards

Prepared for the Wikimedia Community User Group Uganda (WCUGU). What Wikimedia
holds about Uganda, how good it is, who reads it and who writes it, and what is
missing: English Wikipedia, Luganda Wikipedia, Wikimedia Commons, Wikidata,
Wikisource and the other Wikimedia projects.

## The dashboards

| Open | For |
|---|---|
| `Uganda Content Gap Dashboard (Excel).xlsx` | English Wikipedia. Choose a group and a sub-category on the **Dashboard** sheet and every tile and chart follows. |
| `Uganda Content Gap Dashboard (Google Sheets).xlsx` | The same, prepared for Google Sheets. |
| `Luganda Wikipedia Pageviews.xlsx` | Every Luganda Wikipedia article, with views by year. |
| `Uganda Wikimedia Projects Dashboard (Excel).xlsx` and `(Google Sheets).xlsx` | Commons, Wikidata, Wikisource and the other projects together. |
| `project_dashboards/` | One dashboard for each Wikimedia project (Commons, Wikidata, Wikisource, Wikiquote, Wiktionary, Wikibooks, Wikinews, Wikivoyage, Wikiversity, Wikispecies, Meta-Wiki, the Runyankore test on the Incubator, MediaWiki, Wikifunctions). |

## The lists behind them

| Folder | Contents |
|---|---|
| `category_files/` | A list of articles for each of the 18 main groups, and the reference lists (every article once, what was excluded and why). |
| `all_categories/` | A list for each of the 3,572 categories and sub-categories. |
| `project_categories/` | A list for every category on the other projects. |

The dashboards link to these lists, so keep the folders beside the workbooks.

## The data and the programs

| Folder | Contents |
|---|---|
| `data/` | The database (`uganda_diversity.db`) and the data files the dashboards are built from. |
| `src_data/` | The programs that collect the data from Wikimedia. |
| `src_viz/` | The programs that build the workbooks and lists from the data. |
| `docs/` | The documentation: [start here](docs/README.md). It covers where the data comes from, how every number is worked out, a guide to each dashboard, a data dictionary, how to refresh and the limits of the analysis. |

To update the data and rebuild everything: `pip install -r requirements.txt`,
then `python src_data/refresh.py` (see [docs/06](docs/06-pipeline-and-refresh.md)).

Colours are from the Wikimedia Community User Group Uganda logo (CC BY-NC-SA 3.0).
Wikipedia text and data are CC BY-SA; Wikidata is CC0.
