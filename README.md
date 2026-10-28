# Global Fuel Prices, Taxation and Subsidy Trends (2020-2026)

Local, reproducible analytics platform: Python/Pandas pipeline -> SQLite star schema -> SQL views -> Flask + Plotly dashboard, plus Tableau-ready exports and specifications.

> **The shipped data is SYNTHETIC** (simulated, seed 42) and is labelled as such in the app. Nothing in it is a real observation. See `docs/user_guide.md` to plug in real data.

## Architecture
CSV/Excel/DB -> ingestion + validation -> Pandas preprocessing -> SQLite -> SQL views/queries -> Flask JSON API + Plotly (16 charts) -> users; CSV exports -> Tableau (manual). Diagrams: `docs/project_report.md`.

## Prerequisites
Python 3.10+ (3.11 recommended), pip. Windows 10/11 or macOS/Linux, 8 GB RAM. Internet is needed only for `pip install` and for Plotly/Bootstrap CDNs (or run `python scripts/vendor_assets.py` for offline assets).

## Quick start
**Windows PowerShell**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/run_pipeline.py --regenerate
python scripts/run_tests.py
python app.py
```
**macOS / Linux**
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_pipeline.py --regenerate
python scripts/run_tests.py
python app.py
```
Or one command: `python scripts/setup.py` (creates `.venv`, installs, runs the pipeline). Open http://127.0.0.1:5000.

## Configuration
`config.py` + optional `.env` (copy `.env.example`): `RAW_DATA_FILE`, `DATABASE_URL`, `RANDOM_SEED`, `TABLEAU_EMBED_URL`, `TABLEAU_ALLOWED_HOSTS`, `FLASK_HOST/PORT/DEBUG`. No credentials are shown in the UI. Use a PostgreSQL URL (`pip install psycopg2-binary`) as an optional alternative (untested).

## Commands
| Task | Command |
|---|---|
| Full pipeline (generate/ingest -> clean -> DB -> exports) | `python scripts/run_pipeline.py [--regenerate]` |
| DB summary | `python -m src.database summary` |
| Named SQL query | `python -m src.database query country_comparison year=2024 fuel=Diesel` |
| Tests | `python scripts/run_tests.py` |
| Performance measurement | `python scripts/perf_test.py --json perf.json` |
| Offline assets (optional) | `python scripts/vendor_assets.py` |
| Run app | `python app.py` |

## Tableau
No workbook is included. Use `data/exports/*.csv` and follow `tableau/connection_guide.md`, `calculated_fields.md`, `dashboard_specification.md`, `story_specification.md`. To embed a published dashboard set `TABLEAU_EMBED_URL` (https, allowed host); the `/tableau` page says so plainly if nothing is embedded.

## Project layout
`app.py` Flask app; `config.py`; `src/` (data_generator, ingestion, validation, preprocessing, database, analytics, forecasting, charts, mdlite); `database/` (schema, views, queries); `templates/`, `static/`; `tableau/` specs; `docs/`; `tests/`; `scripts/`; `data/{raw,processed,exports}`.

## Troubleshooting
* *503 "Database not initialised"* - run `python scripts/run_pipeline.py`.
* *Charts blank* - Plotly CDN blocked; run `python scripts/vendor_assets.py` or check network.
* *PowerShell blocks activation* - `Set-ExecutionPolicy -Scope Process RemoteSigned`.
* *Port in use* - set `FLASK_PORT`.
* *Tableau embed shows nothing* - URL must be https on an allowed host and the dashboard must be published/public.

## Known limitations
Synthetic data; target of 27,468 records not met (actual 20,631 cleaned; see report); nominal USD only; tests were verified in a sandbox with a SQLAlchemy stand-in and a minimal pytest-compatible runner - run them on your machine; Plotly rendering, Tableau workbook and PostgreSQL untested. Details: `docs/project_report.md`.
