# RESUME GUIDE (for continuing in a new Claude session)

Original requirements: `docs/MASTER_PROMPT.md` (read it first). This file records what is done and what is next.

## How to resume
1. Unzip, `cd global-fuel-analytics`, `pip install -r requirements.txt`.
2. Verify: `python scripts/run_pipeline.py --regenerate`.
3. Tell Claude: "Continue this project from RESUME.md. Build the next pending stage, run it, fix errors, then zip it."

## Stage checklist
- [x] **Stage 1** - config, synthetic generator, ingestion, validation, preprocessing, pipeline script, quality report, Tableau flat CSV.
- [x] **Stage 2** - `database/schema.sql` (star schema), `views.sql` (6 views), `queries.sql` (13 named queries); `src/database.py` (transactional load, summary, validate, run_named, export_tables); `src/analytics.py` (validated Filters, whitelisted SQL aggregation + cache, KPIs, stats, volatility, yoy, correlations); `src/forecasting.py` (naive vs damped Holt, 95% band, backtest); pipeline now loads DB + exports star-schema CSVs.
- [x] **Stage 3** - `app.py` (factory + routes + JSON API), `src/charts.py` (16 Plotly figure builders + 2 tables, plain JSON specs, shared theme), `src/mdlite.py` (safe markdown for /docs), 13 templates, `static/css/app.css`, `static/js/app.js`, `scripts/vendor_assets.py` (optional offline Plotly/Bootstrap).
- [x] **Stage 4 (DONE)** - pytest suite (`tests/`), `tableau/*.md` (calculated_fields, dashboard_specification, story_specification with 5 scenes, connection_guide), `docs/*.md` (project_report, data_dictionary, sql_guide, tableau_guide, user_guide, presentation_script, Mermaid ER/architecture), `README.md`, `scripts/setup.py`, `scripts/run_tests.py`, `scripts/perf_test.py`, final verification with REAL measurements.

## Key decisions (keep consistent)
- **Data is SYNTHETIC** (seed 42). Never describe it as real. Real data: set `RAW_DATA_FILE` / `config.COLUMN_MAP`.
- **Grain**: one row per country x month x fuel type. Monthly 2020-01..2026-10 = 82 months x 84 countries x 3 fuels = **20,664** defect-free rows. The brief's 27,468 target is **not met** (27,468 = 84 x 3 x 109 periods; 82 monthly periods do not give 109). Report the actual count; do not claim 27,468.
- **Units**: nominal USD per litre (LPG per litre-equivalent). No inflation adjustment, no FX conversion.
- **Raw file** has deliberately injected defects (listed in `data/raw/DATA_PROVENANCE.json`); the pipeline removes/imputes them with documented rules (`src/preprocessing.RULES`).
- **Clean table** columns: see `preprocessing.CLEAN_COLUMNS`. Natural key = (country_code, date, fuel_type). `record_id` is the surrogate key.
- Derived: `tax_share_pct = tax/price*100`; `tax_rate_pct = tax/(price-tax)*100` (rate on pre-tax net price); `subsidy_ratio_pct = subsidy/price*100`; `affordability_pct_daily_income = price/(GDP pc/365)*100` (lower = more affordable).
- Tableau workbook cannot be authored here: provide specs/guides only, plus a configurable `TABLEAU_EMBED_URL`; never fake a working embed.

## Actual results so far (Stage 1, measured)
- Source rows 20,724 -> cleaned 20,631 (60 exact duplicates, 27 hard rejects, 6 extreme prices removed; all logged in `data/processed/rejected_rows.csv`).
- 84 countries, 7 regions, 3 fuel types, 4 income groups.
- Imputed: 30 tax, 40 subsidy, 20 GDP. Flagged (kept): 169 price_outlier.
- Timings: generate 0.14s, ingest 0.03s, preprocess 0.29s.

## Stage 2 notes (for Stage 3 - Flask)
- DB: `data/fuel_analytics.db` (SQLite). Rebuild: `python scripts/run_pipeline.py`. Tables: dim_country, dim_date, dim_fuel, fact_economy (country x year), fact_fuel_price, etl_run. Views: vw_fuel_price_detail (flat; used by analytics), vw_country_year_fuel, vw_region_year_fuel, vw_yoy_country_fuel, vw_volatility_country_fuel, vw_region_rank_country_year.
- Use `src.analytics` only (never hand-write SQL in Flask): `parse_filters(request.args)` (raises `FilterError` -> return HTTP 400; query keys: `country`, `region`, `fuel`, `income` comma-separated, `date_from`, `date_to` as YYYY-MM), `options()`, `kpis(f)`, `country_averages(f)` (choropleth/ranking/tax/scatter/subsidy), `region_averages(f)`, `monthly_trend(f, by)`, `fuel_by_year(f)`, `income_affordability(f)`, `price_statistics(f, by)`, `volatility(f)`, `yoy(f, by)`, `correlations(f)`, `monthly_series(f)` + `forecasting.forecast_series(series)`.
- `kpis` returns `{"empty": True,...}` when a filter matches nothing -> UI must show an empty state.
- 2026 is a partial year (Jan-Oct): label YoY for 2026 accordingly.
- Forecast needs >= 24 monthly points (raises ValueError -> HTTP 400/empty state).
- Correlation matrix is across country-level means; always caption "association, not causation".

## Measured results (Stage 2)
- 20,631 fact rows inserted (= cleaned rows); DB load 0.17s; SQL validation violations (duplicates, nulls, ranges, orphans) all 0.
- All 13 named queries execute. Holdout backtest (South Asia petrol, 6 months): Holt MAPE 0.65% vs naive 1.49% (synthetic data).


## Stage 3 notes (for Stage 4 - tests, docs, Tableau)
- **Run**: `python app.py` -> http://127.0.0.1:5000 . Pages: `/`, `/dashboard`, `/regional`, `/taxation`, `/affordability`, `/trends`, `/methodology`, `/data-quality`, `/tableau`, `/docs`, `/docs/<docs|tableau|root>/<name>`, `/download/<csv>`.
- **API** (GET): `/api/options`, `/api/kpis`, `/api/chart/<name>` (opts `by`=fuel_type|region|income_group, `n` 3-30, `horizon` 1-36), `/api/data/<price_stats|country_table>`, `/api/charts`, `/api/quality`, `/healthz`. Filters = `date_from`, `date_to` (YYYY-MM), comma-separated `country` (ISO-3), `region`, `fuel`, `income`. Bad input -> 400 `{"error"}`; unknown chart/dataset -> 404; DB missing -> 503. `Server-Timing` header carries server ms (use it in the perf script).
- **Charts (16)**: choropleth, trend_lines, fuel_comparison (dashboard); region_bar, trend_region, country_ranking (regional); tax_rate_box, region_tax_subsidy, price_vs_tax, subsidy_vs_price (taxation); income_affordability, affordability_gdp, correlation (affordability); forecast, volatility, yoy_change (trends). `charts.REGISTRY` is the source of truth. `charts.build(name, filters, opts)` returns `{empty, message, figure, note, synthetic}`. Tables: `charts.table(name, f, args)`.
- Figures are plain JSON, so **no plotly Python package is needed** (removed from requirements). Plotly.js 2.35.2 + Bootstrap 5.3.3 load from CDN; `python scripts/vendor_assets.py` downloads them to `static/vendor/` (auto-preferred; also makes the map offline). That script is UNTESTED (no network in the build sandbox).
- Tableau embed: `config.TABLEAU_EMBED_URL` accepted only if https and host in `config.TABLEAU_ALLOWED_HOSTS`; otherwise the page says nothing is embedded.
- Tests should monkeypatch `config.DATABASE_URL` to a temp sqlite file and call `database.build_database(clean)`; `analytics`/`charts`/`app` read it at call time. Call `analytics.clear_cache()` between DBs.
- 2026 and filtered first/last years are labelled with `*` (partial) in year charts.

## Measured in Stage 3 (build sandbox where real SQLAlchemy could NOT be installed: PyPI/GitHub/npm blocked)
- Verified with a TEST-ONLY SQLAlchemy stand-in: `dev/sqlalchemy_test_shim/sqlalchemy.py`. If your sandbox also lacks SQLAlchemy, copy it to `<somedir>/sqlalchemy/__init__.py` and `export PYTHONPATH=<somedir>`. Never ship or use it for real work (final zip removes `dev/`). On a normal machine `pip install -r requirements.txt` installs the real package.
- All 12 pages return 200; 16 charts x 8 filter combinations = 0 failures, strict-JSON valid; invalid inputs -> 400/404 as designed. Chart API 5-200 ms (volatility slowest, ~195 ms cold).
- Headless Chromium with a Plotly stub: filters update URL/nav/KPIs/charts/tables; empty, error and invalid-date states OK; no JS errors; no horizontal overflow at 375 px.
- NOT verified here: actual Plotly.js rendering (library unavailable offline), Bootstrap styling, a run against real SQLAlchemy. Say so honestly in the docs/final report.


## Stage 4 notes (DONE)
- Added `tests/` (conftest + 3 files, 70 tests), `tableau/*.md` (4 files), `docs/*.md` (6 files + MASTER_PROMPT), `README.md`, `scripts/setup.py`, `run_tests.py`, `perf_test.py`.
- Tests were run in a sandbox WITHOUT real pytest/SQLAlchemy using `dev/sqlalchemy_test_shim` and a minimal runner; first thing to do on a normal machine: `pip install -r requirements.txt && python scripts/run_tests.py` and fix anything that real pytest/SQLAlchemy expose.
- Remaining manual work: build the Tableau workbook from `tableau/`, view charts in a browser, optional PostgreSQL test.
