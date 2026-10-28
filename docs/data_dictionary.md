# Data dictionary

**All data shipped with this project is SYNTHETIC** (seed 42). Grain: **one row per country x month x fuel type**. Prices are **nominal USD per litre** (LPG per litre-equivalent); no inflation adjustment, no currency conversion (prices are generated directly in USD; `currency_local` is metadata only).

## fact_fuel_price (grain: country x month x fuel)
| Column | Type | Description |
|---|---|---|
| record_id | INTEGER PK | Surrogate key |
| country_id | INTEGER FK | -> dim_country |
| date_id | INTEGER FK | -> dim_date (YYYYMM) |
| fuel_id | INTEGER FK | -> dim_fuel |
| price_usd_per_litre | NUMERIC > 0 | Retail price incl. tax |
| price_before_tax_usd | NUMERIC | price - tax |
| tax_usd_per_litre | NUMERIC >= 0 | Tax amount per litre |
| tax_rate_pct | NUMERIC 0-500 | tax / (price - tax) x 100 (rate on pre-tax price) |
| tax_share_pct | NUMERIC 0-<100 | tax / price x 100 |
| subsidy_usd_per_litre | NUMERIC >= 0 | Subsidy per litre (may exceed price in heavily subsidised synthetic countries) |
| subsidy_ratio_pct | NUMERIC >= 0 | subsidy / price x 100 |
| affordability_pct_daily_income | NUMERIC > 0 | price / (GDP pc / 365) x 100; **lower = more affordable** |
| dq_flags | TEXT | `;`-separated flags (imputed_*, price_outlier, tax_rate_mismatch) |
| is_imputed | 0/1 | 1 if any value was imputed |
UNIQUE(country_id, date_id, fuel_id).

## dim_country
`country_id` PK, `country_code` (ISO-3, unique), `country_name`, `region` (7 values), `income_group` (Low / Lower-middle / Upper-middle / High; illustrative thresholds on GDP per capita, not official World Bank cut-offs), `currency_local`.

## dim_date
`date_id` (YYYYMM) PK, `full_date` (first of month, unique), `year`, `quarter`, `month`, `month_name`.

## dim_fuel
`fuel_id` PK, `fuel_type` (Petrol, Diesel, LPG), `unit`.

## fact_economy (country x year)
`country_id`, `year`, `gdp_per_capita_usd` (annual median of the monthly values).

## etl_run
Audit rows for each load (timestamp, source/loaded counts, data origin).

## Views
`vw_fuel_price_detail` (flat, used by Flask), `vw_country_year_fuel`, `vw_region_year_fuel`, `vw_yoy_country_fuel`, `vw_volatility_country_fuel`, `vw_region_rank_country_year`.

## Ten core analytical variables
Country (`country`), Region (`region`), Date/year (`date`,`year`), Fuel type (`fuel_type`), Retail price (`price_usd_per_litre`), Tax amount (`tax_usd_per_litre`), Tax rate (`tax_rate_pct`), Subsidy (`subsidy_usd_per_litre`/`subsidy_ratio_pct`), Income (`gdp_per_capita_usd`/`income_group`), Affordability (`affordability_pct_daily_income`).

## Required input columns for real data
`country_code, country, region, income_group, date, fuel_type, currency_local, price_usd_per_litre, tax_usd_per_litre, tax_rate_pct, subsidy_usd_per_litre, gdp_per_capita_usd, data_source` (rename with `config.COLUMN_MAP`).

## Cleaning rules
See `src/preprocessing.RULES` (also shown on the Methodology page and the data quality report).
