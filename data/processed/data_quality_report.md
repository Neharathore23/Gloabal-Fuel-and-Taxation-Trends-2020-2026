# Data Quality Report

Generated: 2026-10-28T18:59:21+00:00  
Data origin: **SYNTHETIC (simulated)**  
Grain: one row per country x month x fuel type  
Price basis: nominal USD per litre (no inflation adjustment, no FX conversion in this pipeline)

## Record counts

| Metric | Value |
|---|---|
| source records | 20,724 |
| exact duplicates removed | 60 |
| key conflicts removed | 0 |
| hard rejects | 27 |
| unimputable rejected | 0 |
| extreme price rejected | 6 |
| total removed | 93 |
| cleaned records | 20,631 |
| target records | 27,468 |
| target met | False |
| inserted records | 20,631 |

## Coverage

| Entity | Value |
|---|---|
| countries | 84 |
| regions | 7 |
| fuel types | 3 |
| income groups | 4 |
| months | 82 |
| min date | 2020-01-01 |
| max date | 2026-10-01 |

## Removed rows by reason

| Item | Count |
|---|---|
| exact_duplicate | 60 |
| missing_price | 15 |
| nonpositive_price | 6 |
| invalid_tax_rate | 6 |
| extreme_price | 6 |

## Imputations / derivations

| Item | Count |
|---|---|
| imputed_tax | 30 |
| imputed_tax_rate | 0 |
| imputed_subsidy | 40 |
| imputed_gdp | 20 |
| derived_income_group | 0 |

## Flags kept on rows

| Item | Count |
|---|---|
| price_outlier | 169 |
| imputed_subsidy | 40 |
| imputed_tax | 30 |
| imputed_gdp | 20 |

## Missing cells before cleaning

| Item | Count |
|---|---|
| country_code | 0 |
| country | 0 |
| region | 0 |
| income_group | 0 |
| date | 0 |
| fuel_type | 0 |
| currency_local | 0 |
| price_usd_per_litre | 15 |
| tax_usd_per_litre | 30 |
| tax_rate_pct | 0 |
| subsidy_usd_per_litre | 40 |
| gdp_per_capita_usd | 20 |
| data_source | 0 |

## Database

| Table | Rows |
|---|---|
| dim_country | 84 |
| dim_date | 82 |
| dim_fuel | 3 |
| fact_economy | 588 |
| fact_fuel_price | 20,631 |

SQL validation violations (all should be 0): validation_duplicates=0, validation_nulls=0, validation_ranges=0, validation_orphans=0

## Measured timings (seconds)

- generate_s: 1.753
- ingest_s: 0.343
- preprocess_s: 4.481
- db_total_s: 3.443
- db_load_s: 1.808

## Cleaning rules applied

1. Text fields are trimmed; country_code upper-cased; country/region/income labels are mapped to one canonical value per code.
2. Fuel labels are mapped to Petrol/Diesel/LPG (aliases: gasoline, gasoil, autogas...); unmapped labels are rejected.
3. Dates are parsed (mixed formats) and snapped to the first day of the month.
4. Exact duplicate rows (after standardisation) are removed and logged; conflicting duplicates of the same country/month/fuel keep the first row and log the rest.
5. Rejected: missing key fields, missing/non-positive price, tax rate <0 or >500, negative tax or subsidy, tax and rate both missing, non-positive GDP.
6. Missing tax amount = price x rate / (100 + rate); missing tax rate = tax / (price - tax) x 100 (flag imputed_tax / imputed_tax_rate).
7. Missing subsidy = median of the same country+fuel+year, else the country+fuel median (flag imputed_subsidy); unresolved rows are rejected.
8. Missing GDP per capita = median of the same country+year, else the country median (flag imputed_gdp); unresolved rows are rejected.
9. Missing income group is derived from GDP per capita using config.INCOME_BINS (flag derived_income_group).
10. Extreme prices (> 5x or < 1/5 of the country+fuel median) are rejected as probable unit errors.
11. Prices deviating >35% from a centred 13-month rolling median are flagged price_outlier but kept.
12. tax_rate_pct differing by >1 percentage point from tax/(price-tax) is flagged tax_rate_mismatch but kept.
13. Affordability = price per litre as % of daily GDP per capita (price / (GDP pc / 365) x 100); lower = more affordable.
14. Prices are nominal USD per litre; no inflation adjustment and no FX conversion is applied by this pipeline.
