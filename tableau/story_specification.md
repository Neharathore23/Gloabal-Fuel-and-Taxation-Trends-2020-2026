# Tableau story specification (6 scenes; 5 required)

Story title: **Global Fuel Prices, Taxation and Subsidies, 2020-2026 (synthetic demonstration data)**. Size: Automatic. Caption text should be written from what the data shows when you build it; the figures below were **measured on the synthetic dataset** (20,631 cleaned records, 84 countries) and must be re-checked against your own data - they are not real-world facts.

| # | Scene | Question | Visualization | Filters | Key interpretation (synthetic data) | Audience |
|---|---|---|---|---|---|---|
| 1 | Global price landscape | How much does a litre cost around the world? | D1: W1 map + KPIs + W3 | All fuels, full period | Average price USD 0.77/L; highest Switzerland (1.73), lowest Iran (0.13). Prices peak in 2022 (petrol avg 1.17) and ease to ~0.85 by 2025. | A, B, C |
| 2 | Regional and country differences | Which regions/countries are cheapest and most expensive? | D2: W2 + W5 | Fuel = Petrol; region action | Europe & Central Asia highest (avg 1.06); MENA lowest (0.37). | B |
| 3 | Taxation and subsidy policies | How do taxes and subsidies differ, and how do they relate to price? | D3: W6 + W7 + W8 | Region, income | Tax burden ~25% overall; Europe 41%, MENA 3.5%. Subsidy-to-price ~7.7% overall, MENA 49%. Country-level correlation of tax burden with price is +0.90 (association, not causation). | A |
| 4 | Income and affordability | Who bears the largest fuel cost relative to income? | D4: W9 + W12 | Fuel = Petrol | Low-income countries pay ~45% of daily income per petrol litre vs ~1.1% in high-income countries. Price level alone is almost uncorrelated with affordability (r = -0.01). | A, C |
| 5 | Trends, forecast, implications | Where are prices heading and how volatile are they? | D5: W3 + W11 + W10 | Region of interest | Volatility (CV) ranges ~6% to ~22% by country-fuel. Forecast bands widen with horizon; synthetic backtest favoured damped Holt over naive. Procurement: budget a band, not a point. Policy: subsidies are concentrated where prices are lowest. | A, B |
| 6 | (Optional) Method and caveats | Can I trust this? | Text + data-quality table | - | Synthetic data, nominal USD, 2026 partial year, 169 price outliers flagged, 90 imputed values documented. | All |

## Build steps
1. Finish D1-D5. 2. Story > New Story; size Automatic. 3. Drag each dashboard in as a scene; rename scene captions with the question above. 4. Add a text caption per scene (1-2 sentences, from the "Key interpretation" column after you re-verify numbers). 5. Use the same global filters in each scene (filters on the dashboard are saved per scene state). 6. Present mode: test navigation.
