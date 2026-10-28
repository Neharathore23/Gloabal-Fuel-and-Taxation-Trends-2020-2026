# SQL guide

Files in `database/`: `schema.sql` (tables, PK/FK, CHECK, UNIQUE, indexes), `views.sql` (6 analytical views), `queries.sql` (13 named queries; each begins with `-- name:` and optional `-- params:` defaults).

Run: `python -m src.database query <name> [key=value ...]`, e.g. `python -m src.database query country_comparison year=2024 fuel=Diesel`. Summary: `python -m src.database summary`.

| Query | Purpose |
|---|---|
| country_comparison | Country price, tax burden, subsidy, affordability for a year+fuel |
| regional_averages | Region averages for a fuel by year |
| tax_burden_top | Countries with the highest tax share of price |
| subsidy_effect | Subsidised vs unsubsidised groups: price, affordability |
| yoy_changes | Largest year-over-year price changes |
| volatility_ranking | Most volatile country-fuel pairs (CV) |
| regional_rank | Price rank of countries inside a region |
| median_price_by_region | Median/max price per region (window-based, portable) |
| validation_duplicates / _nulls / _ranges / _orphans | Integrity checks - all must return 0 |
| db_row_counts | Row counts per table |

Notes: all parameters are bound (`:name`), never concatenated. SQLite is the default; the SQL avoids vendor-specific functions except `sqrt`, registered for SQLite in `database.get_engine`. PostgreSQL has not been tested here.
Transactions: `database.build_database` drops/creates schema and loads all tables in one transaction (rollback on error).
