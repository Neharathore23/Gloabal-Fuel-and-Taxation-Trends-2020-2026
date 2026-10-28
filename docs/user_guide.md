# User guide

## Pages
* **Home** - overview, personas, dataset facts.
* **Global dashboard** - KPI cards (avg price, tax burden, subsidy ratio, countries), choropleth, trend lines, fuel comparison.
* **Regional & country** - regional bars, regional trends, country ranking (top N), stats table.
* **Tax & subsidy** - tax-rate box plot, region tax/subsidy, price vs tax, subsidy vs price.
* **Affordability** - income group vs affordability, GDP vs affordability, correlation matrix.
* **Trends & forecast** - forecast with 95% band and naive baseline, volatility, YoY.
* **Methodology / Data quality / Tableau / Docs** - assumptions, cleaning rules, counts, embed page, documentation.

## Filters
Date range (YYYY-MM), country, region, fuel type, income group. Click **Apply**; charts and KPI cards refresh. Filters live in the URL, so a link shares the exact view. If nothing matches you see an empty state; invalid input shows an error message (HTTP 400 from the API).

## Personas
* **Energy policy consultant** - Tax & subsidy + Affordability pages.
* **Supply chain manager** - Regional page, Trends (volatility, forecast).
* **Energy economics researcher** - Affordability (correlation matrix) + downloadable CSVs on the Tableau page.

## Reading the numbers
Prices are nominal USD/L. Tax burden = sum(tax)/sum(price). Subsidy ratio can exceed 100%. Affordability: lower is better. Correlation is association, not causation. 2026 is Jan-Oct (marked `*`). Data is synthetic.

## Replace synthetic data with real data
1. Put your CSV/XLSX in `data/raw/` (keep the original untouched).
2. Ensure the required columns (see `data_dictionary.md`), or map names in `config.COLUMN_MAP`; one row per country x month x fuel; prices in one currency (USD) or convert first.
3. `RAW_DATA_FILE=data/raw/yourfile.csv` in `.env`.
4. `python scripts/run_pipeline.py` (no `--regenerate`). The "synthetic" banners switch off automatically when no `data_source` value contains the word SYNTHETIC; review `data/processed/data_quality_report.md`.
5. Sources worth considering (check licences): national ministries/regulators, IEA, World Bank (GDP per capita, pump prices indicator), GIZ international fuel prices, IMF fuel subsidy estimates, GlobalPetrolPrices (licensed). Document currency and inflation treatment yourself.
