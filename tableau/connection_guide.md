# Tableau connection guide

**Status:** no Tableau workbook (.twb/.twbx) is shipped. Workbooks must be authored and validated in Tableau Desktop or Tableau Public (free). Everything below is a specification and has **not** been tested inside Tableau from this project's build environment. The data files and their column names were verified against the generated CSVs.

## 1. Create the data (one command)
```
python scripts/run_pipeline.py        # Windows PowerShell / macOS / Linux
```
Outputs in `data/exports/`: `fuel_prices_tableau.csv` (flat) and the star schema `dim_country.csv`, `dim_date.csv`, `dim_fuel.csv`, `fact_economy.csv`, `fact_fuel_price.csv`, plus `vw_fuel_price_detail.csv`.

> The data is **synthetic** (seed 42) unless you replaced it (see `docs/user_guide.md`). Add a visible "Synthetic data" caption to every dashboard.

## 2. Option A - flat CSV (recommended for Tableau Public)
1. Tableau > Connect > Text file > `data/exports/fuel_prices_tableau.csv`.
2. Set types: `date` = Date, `year/month/quarter` = Number (whole), measures = Number (decimal), `country_code` = Geographic role > Country/Region (ISO 3166-1 alpha-3 is recognised; if some codes are unmatched use `country` with the Country/Region role instead).
3. Set `price_basis`, `data_source`, `dq_flags` to Dimension. Set `is_imputed` to Dimension (Boolean or Number 0/1).
4. Extract (Data > Extract) - ~20.6k rows, instant.

## 3. Option B - star schema CSVs (relationships)
Add all five tables to the canvas as **Relationships** (not joins), Tableau 2020.2+:

| From (many) | To (one) | Key |
|---|---|---|
| fact_fuel_price | dim_country | `country_id` = `country_id` |
| fact_fuel_price | dim_date | `date_id` = `date_id` (YYYYMM integer) |
| fact_fuel_price | dim_fuel | `fuel_id` = `fuel_id` |
| fact_economy | dim_country | `country_id` = `country_id` |

Grain of `fact_fuel_price`: **country x month x fuel type** (natural key `country_id, date_id, fuel_id`). `fact_economy` is country x year and is only for GDP-per-capita lookups; do not join it to the price fact on year unless you also keep the country key (it would fan out measures at the wrong grain - use the GDP column already on the flat file for affordability).

## 4. Option C - SQLite directly
Tableau has no native SQLite connector. Use the CSV extracts, or install a SQLite ODBC driver and use "Other Databases (ODBC)" with `data/fuel_analytics.db`. Not recommended for Tableau Public (no ODBC).

## 5. PostgreSQL (optional)
Load the same tables into PostgreSQL (`DATABASE_URL=postgresql+psycopg2://...` then `python scripts/run_pipeline.py`; `pip install psycopg2-binary`) and use Tableau's native PostgreSQL connector. SQL files use portable syntax; PostgreSQL support has **not** been tested here.

## 6. Publish to Tableau Public (optional)
1. Save to Tableau Public (File > Save to Tableau Public As...). Data is extracted and becomes public - fine for synthetic data, do not do this with licensed data.
2. Open the published viz > Share > copy the **Link** (looks like `https://public.tableau.com/views/<Workbook>/<Sheet>`).
3. Put it in `.env`: `TABLEAU_EMBED_URL=https://public.tableau.com/views/<Workbook>/<Sheet>` and restart Flask.
4. The `/tableau` page embeds it only if the URL is https and its host is in `TABLEAU_ALLOWED_HOSTS` (default `public.tableau.com,online.tableau.com`). Otherwise it states plainly that nothing is embedded. For Tableau Server/Cloud add your host to `TABLEAU_ALLOWED_HOSTS` and make sure the site permits embedding (X-Frame/CSP settings are controlled by Tableau admins).

## 7. Manual steps that need Tableau
Building every worksheet/dashboard/story, creating parameters, publishing, and verifying the embed. Everything else is automated.

## 8. Performance tips
Use an extract; hide unused fields; use `year`/`date` filters as context filters; keep the date filter on a continuous month; avoid `COUNTD(country)` on very large detail views; prefer the flat file for Tableau Public.
