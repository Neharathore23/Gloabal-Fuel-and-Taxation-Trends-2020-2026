# Demo script (about 7 minutes)

1. **0:00 Intro (30s)** - "Global Fuel Prices, Taxation and Subsidy Trends: Python, SQLite, Flask and Plotly, with Tableau specs. The data is synthetic and labelled so."
2. **0:30 Pipeline (60s)** - Run `python scripts/run_pipeline.py`; point at counts: 20,724 source rows -> 20,631 clean -> 20,631 in the database; 84 countries, 7 regions, 3 fuels. Mention the 27,468 target is not met (82 monthly periods) and why.
3. **1:30 Data quality page (45s)** - rejected rows, imputations, flags.
4. **2:15 Global dashboard (75s)** - KPI cards; apply Fuel = Diesel and Region = South Asia; show the cards and charts update; hover on map.
5. **3:30 Regional page (45s)** - ranking top 15 by price; regional trends.
6. **4:15 Tax & subsidy (60s)** - price vs tax scatter, subsidy vs price; say "association, not causation".
7. **5:15 Affordability (45s)** - income group chart: low-income pay a far larger share of daily income per litre.
8. **6:00 Trends (45s)** - forecast band widening, naive vs Holt backtest, volatility.
9. **6:45 Tableau page + wrap-up (45s)** - not embedded until a URL is set; show the CSV exports and specs; run `python scripts/run_tests.py` and `python scripts/perf_test.py`.
