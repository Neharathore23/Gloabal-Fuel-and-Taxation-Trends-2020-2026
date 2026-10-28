# Tableau calculated fields

Use the flat file `fuel_prices_tableau.csv`. Field names are the CSV column names. 18 calculated fields (CF1-CF18). Prices are **nominal USD per litre** (LPG per litre-equivalent).

| # | Name | Formula | Purpose |
|---|---|---|---|
| CF1 | Avg Retail Price | `AVG([price_usd_per_litre])` | Headline price KPI |
| CF2 | Median Retail Price | `{ FIXED [country_code],[fuel_type] : MEDIAN([price_usd_per_litre]) }` | Robust central price |
| CF3 | Max Retail Price | `MAX([price_usd_per_litre])` | Peak price |
| CF4 | Effective Tax Burden % | `SUM([tax_usd_per_litre]) / SUM([price_usd_per_litre])` (format as %) | Tax as share of price, volume-neutral (matches the Flask KPI) |
| CF5 | Avg Tax Rate % | `AVG([tax_rate_pct]) / 100` (format %) | Rate on pre-tax price (can exceed 100%) |
| CF6 | Subsidy-to-Price Ratio | `SUM([subsidy_usd_per_litre]) / SUM([price_usd_per_litre])` (format %) | Subsidy intensity; may exceed 100% (e.g. synthetic Venezuela/Iran) |
| CF7 | Affordability (% daily income) | `SUM([price_usd_per_litre]) / SUM([gdp_per_capita_usd]/365)` (format %) | Cost of one litre as % of average daily GDP per capita; **lower = more affordable** |
| CF8 | Price Previous Year | `LOOKUP([Avg Retail Price], -1)` with table calc "compute using" Year, restarting every Country+Fuel | Prior-year price |
| CF9 | YoY Change (USD) | `[Avg Retail Price] - LOOKUP([Avg Retail Price], -1)` | Absolute change |
| CF10 | YoY Change % | `([Avg Retail Price] - LOOKUP([Avg Retail Price], -1)) / ABS(LOOKUP([Avg Retail Price], -1))` | Relative change. 2026 is partial (Jan-Oct): label it |
| CF11 | Price Volatility (CV) | `STDEV([price_usd_per_litre]) / AVG([price_usd_per_litre])` computed per Country+Fuel | Coefficient of variation of price level |
| CF12 | Regional Price Rank | `RANK(AVG([price_usd_per_litre]))` computing within Region (Country as addressing) | Rank of countries inside a region |
| CF13 | Price vs Global Avg | `AVG([price_usd_per_litre]) / { FIXED [fuel_type] : AVG([price_usd_per_litre]) } - 1` | Premium/discount against the fuel-type global mean |
| CF14 | Tax Excl. Price | `[price_before_tax_usd]` (alias) or `SUM([price_usd_per_litre]) - SUM([tax_usd_per_litre])` | Pre-tax price comparison |
| CF15 | Income Group (sorted) | `CASE [income_group] WHEN 'Low' THEN 1 WHEN 'Lower-middle' THEN 2 WHEN 'Upper-middle' THEN 3 WHEN 'High' THEN 4 END` | Sort key for income groups |
| CF16 | Selected Metric | `CASE [Metric Parameter] WHEN 'Price' THEN [Avg Retail Price] WHEN 'Tax burden' THEN [Effective Tax Burden %] WHEN 'Subsidy ratio' THEN [Subsidy-to-Price Ratio] WHEN 'Affordability' THEN [Affordability (% daily income)] END` | Drives the map/ranking metric switch |
| CF17 | Data Quality Flag | `IF [is_imputed] = 1 OR NOT ISNULL([dq_flags]) AND [dq_flags] <> '' THEN 'Flagged' ELSE 'Clean' END` | Transparency on imputed/flagged rows |
| CF18 | Price Index (start = 100) | `AVG([price_usd_per_litre]) / LOOKUP(AVG([price_usd_per_litre]), FIRST()) * 100` | Compare trends of different fuels/regions from a common base |

## Parameters
| Name | Type | Values |
|---|---|---|
| Metric Parameter | String list | Price, Tax burden, Subsidy ratio, Affordability |
| Top N | Integer range | 5-30, step 5, default 15 |
| Forecast months | Integer range | 1-36 (used with Tableau's built-in Forecast; it is exponential smoothing, not the Holt model used in Flask) |

## Correlation
Right-click a scatter > Trend Line > Show (Pearson R shown in the description), or use `CORR([avg tax], [avg price])` in a table aggregated at **country** level (use a LOD: `{ FIXED [country_code] : AVG([price_usd_per_litre]) }`). Correlation is not causation.

## Notes
* Ratios of sums (CF4, CF6, CF7) intentionally match `src/analytics.py` so Tableau and Flask KPIs agree.
* Filtering a view changes the ratio's denominator automatically; FIXED LODs ignore dimension filters unless the filter is added to context.
