"""Central configuration: paths, database, app settings, shared reference constants.

Everything can be overridden with environment variables or a .env file (see .env.example).
"""
import os
from pathlib import Path

import pandas as pd

try:  # optional dependency
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EXPORT_DIR = DATA_DIR / "exports"
SQL_DIR = ROOT / "database"

# ---- Data sources -------------------------------------------------------------------
# Point RAW_DATA_FILE at a real CSV/XLSX to bypass the synthetic generator.
RAW_FILE = Path(os.getenv("RAW_DATA_FILE", RAW_DIR / "fuel_prices_raw_synthetic.csv"))
PROVENANCE_FILE = RAW_DIR / "DATA_PROVENANCE.json"
PROCESSED_FILE = PROCESSED_DIR / "fuel_prices_clean.csv"
REJECTED_FILE = PROCESSED_DIR / "rejected_rows.csv"
QUALITY_JSON = PROCESSED_DIR / "data_quality_report.json"
QUALITY_MD = PROCESSED_DIR / "data_quality_report.md"
TABLEAU_FLAT_FILE = EXPORT_DIR / "fuel_prices_tableau.csv"

# Rename columns of a real dataset to the expected names: {"Their Name": "our_name"}.
COLUMN_MAP: dict = {}

# ---- Database -----------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'fuel_analytics.db').as_posix()}")

# ---- Generator / scope --------------------------------------------------------------
SEED = int(os.getenv("RANDOM_SEED", "42"))
START_DATE = "2020-01-01"
END_DATE = "2026-10-01"  # last month generated (monthly grain)
TARGET_RECORDS = 27_468  # figure requested in the project brief

# ---- Flask / dashboard --------------------------------------------------------------
TABLEAU_EMBED_URL = os.getenv("TABLEAU_EMBED_URL", "").strip()  # empty = not configured
# Hosts allowed in TABLEAU_EMBED_URL (exact or *.suffix match); add your Tableau Server/Cloud host if you use one.
TABLEAU_ALLOWED_HOSTS = tuple(h.strip().lower() for h in os.getenv(
    "TABLEAU_ALLOWED_HOSTS", "public.tableau.com,online.tableau.com").split(",") if h.strip())
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

# ---- Shared reference constants -----------------------------------------------------
REGIONS = {
    "EAP": "East Asia & Pacific",
    "ECA": "Europe & Central Asia",
    "LAC": "Latin America & Caribbean",
    "MENA": "Middle East & North Africa",
    "NAM": "North America",
    "SAS": "South Asia",
    "SSA": "Sub-Saharan Africa",
}
FUEL_TYPES = ["Petrol", "Diesel", "LPG"]
INCOME_ORDER = ["Low", "Lower-middle", "Upper-middle", "High"]
# Illustrative thresholds on GDP per capita (USD); NOT the official World Bank annual cut-offs.
INCOME_BINS = [0, 1_100, 4_500, 14_000, float("inf")]
TAX_RATE_MAX = 500.0  # % of pre-tax price; above this a rate is treated as invalid
EXTREME_RATIO = 5.0  # price > 5x (or < 1/5) of the country-fuel median is rejected as probable unit error
OUTLIER_TOLERANCE = 0.35  # |price / rolling-median - 1| above this is flagged (kept)


def income_group(gdp_per_capita: pd.Series) -> pd.Series:
    """Map GDP per capita (USD) to an income group label."""
    return pd.cut(gdp_per_capita, bins=INCOME_BINS, labels=INCOME_ORDER, right=False).astype("string")
