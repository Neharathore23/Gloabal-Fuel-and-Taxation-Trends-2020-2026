# Tableau dashboard specification

Data: `fuel_prices_tableau.csv` (see `connection_guide.md`). Size: Automatic (min 1000 x 700); also create a Phone layout for D1 and D4. Theme: dark navy header (#0B2540), teal (#1B998B) and amber (#F4A261) accents, colour-blind-safe palettes (Tableau "Color Blind" or Viridis for sequential). Footer caption on all dashboards: **"Synthetic demonstration data - not real observations"**.

## Global filters (apply to all worksheets: Apply to Worksheets > All Using This Data Source)
| # | Filter | Field | Control |
|---|---|---|---|
| 1 | Date | `date` | Range slider (continuous month) |
| 2 | Country | `country` | Multi-value dropdown |
| 3 | Region | `region` | Multi-value dropdown |
| 4 | Fuel type | `fuel_type` | Single-value list (default All) |
| 5 | Income group | `income_group` | Multi-value list sorted by CF15 |

Parameters: Metric Parameter, Top N, Forecast months.

## Worksheets (10 required + 3 extras)
| # | Worksheet | Build |
|---|---|---|
| W1 | Global price map | Filled map; Detail=`country`; Color=CF16 (Selected Metric), sequential Viridis; Tooltip: price, tax burden, subsidy, affordability |
| W2 | Regional average price | Bars: Rows=`region` (sorted desc), Columns=CF1; Color=`fuel_type` (side by side) |
| W3 | Price trends 2020-2026 | Lines: Columns=`date` (month, continuous), Rows=CF1, Color=`fuel_type`; add Region as a filter/trellis |
| W4 | Fuel comparison | Grouped bars by `year` x `fuel_type` on CF1; tooltip incl. CF10 |
| W5 | Country ranking | Horizontal bars of `country`, CF16, Top N parameter filter (Top by CF16) |
| W6 | Tax rate comparison | Box plot: `region` x `tax_rate_pct` (Detail=`country`) |
| W7 | Price vs tax scatter | Columns=CF4, Rows=CF1, Detail=`country`, Color=`region`, Size=`gdp_per_capita_usd`, trend line |
| W8 | Subsidy vs price | Columns=CF6, Rows=CF1, Detail=`country`, Color=`income_group`; reference line at 100% (subsidy > price) |
| W9 | Income vs affordability | Bars: `income_group` (CF15 order) x CF7, Color=`fuel_type`; add scatter alt: `gdp_per_capita_usd` (log) vs CF7 |
| W10 | Volatility + forecast | Dual: bars of CF11 by `country` (Top N) and line of CF1 by month with Analytics > Forecast (Forecast months, show prediction interval) |
| W11 | YoY change | Bars `year` x CF10 by `fuel_type` (2026 labelled "Jan-Oct") |
| W12 | Correlation heat table | Text table of `CORR` at country level (optional) |
| W13 | KPI strip | Four BANs: CF1, CF4, CF6, COUNTD(`country_code`) |

## Dashboards
**D1 Global Overview** (Persona: all) - top: KPI strip W13 (4 tiles, fixed height 90). Left 60%: W1. Right 40%: W4 over W3. Filter bar on top (all five filters + Metric Parameter).
**D2 Regional & Country** (B Supply Chain) - W2 + W5 + W3 (trellis by region) + W10 left half.
**D3 Tax & Subsidy** (A Policy) - W6, W7, W8, subsidy/tax summary text table.
**D4 Affordability & Economics** (C Researcher) - W9 (both views), W12, tooltip notes about association vs causation.
**D5 Trends & Forecast** (B, A) - W3, W11, W10 forecast, caption "Tableau forecast = exponential smoothing; Flask uses damped Holt".

Use a Vertical/Horizontal container structure (tiled, not floating) so layouts resize. Add alt-text titles and keep fonts consistent (Tableau Book, 10-12 pt body, 16-18 pt titles).

## Actions
1. **Filter action** (Select): W1 map -> all worksheets in D1/D2, source field `country`.
2. **Filter action**: W2 region bar -> W3, W5, W10 on `region`.
3. **Highlight action**: W7 scatter -> W8 on `country`.
4. **Filter action**: W9 income bars -> W7, W8 on `income_group`.
5. **URL action** (optional): `country` -> Flask `/regional?country=<ISO3>` (set `country_code` as the field; works only when Flask is reachable).
6. **Go to sheet** buttons for D1-D5 navigation.

## Accessibility and quality
Colour-blind-safe palette; no colour-only encoding (labels/tooltips); sort axes meaningfully; label units (USD/L, %); caption incl. "nominal USD, not inflation-adjusted"; show flagged data share (CF17) in the D1 tooltip.

## Verification checklist (manual, in Tableau)
- [ ] Row count of the extract = number of rows in `fuel_prices_tableau.csv`
- [ ] CF4/CF6/CF7 match the Flask KPI cards for the same filters
- [ ] All 5 filters affect all worksheets
- [ ] Map shows 84 countries (unmatched codes = 0)
