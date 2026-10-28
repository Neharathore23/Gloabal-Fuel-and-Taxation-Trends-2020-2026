"""Schema and value validation helpers (pure functions; no I/O)."""
import numpy as np
import pandas as pd

import config

REQUIRED_COLUMNS = ["country_code", "country", "region", "income_group", "date", "fuel_type", "currency_local",
                    "price_usd_per_litre", "tax_usd_per_litre", "tax_rate_pct", "subsidy_usd_per_litre",
                    "gdp_per_capita_usd", "data_source"]
NUMERIC = ["price_usd_per_litre", "tax_usd_per_litre", "tax_rate_pct", "subsidy_usd_per_litre",
           "gdp_per_capita_usd"]


def check_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Use config.COLUMN_MAP to rename source columns.")


def coerce_types(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Convert numerics and dates; report how many non-empty cells could not be parsed."""
    d = df.copy()
    unparseable = {}
    for col in NUMERIC:
        before = d[col].notna() & (d[col].astype("string").str.strip() != "")
        d[col] = pd.to_numeric(d[col], errors="coerce")
        unparseable[col] = int((before & d[col].isna()).sum())
    before = d["date"].notna()
    d["date"] = pd.to_datetime(d["date"], errors="coerce", format="mixed")
    unparseable["date"] = int((before & d["date"].isna()).sum())
    return d, unparseable


HARD_REJECT_RULES = [
    "missing_country_code", "invalid_date", "unknown_fuel_type", "missing_region", "missing_price",
    "nonpositive_price", "invalid_tax_rate", "negative_tax", "negative_subsidy", "missing_tax_and_rate",
    "invalid_gdp",
]


def hard_reject_reasons(d: pd.DataFrame) -> pd.Series:
    """First-matching reject reason per row ('' = row passes)."""
    p, t, r, s, g = (d[c] for c in NUMERIC)
    conds = [
        d["country_code"].fillna("").eq(""),
        d["date"].isna(),
        d["fuel_type"].isna(),
        d["region"].isna(),
        p.isna(),
        p <= 0,
        (r < 0) | (r > config.TAX_RATE_MAX),
        t < 0,
        s < 0,
        t.isna() & r.isna(),
        g <= 0,
    ]
    return pd.Series(np.select([np.asarray(c, dtype=bool) for c in conds], HARD_REJECT_RULES, default=""),
                     index=d.index)


def final_checks(d: pd.DataFrame) -> list[str]:
    """Assertions on the cleaned table; returns a list of problems (empty = valid)."""
    problems = []
    core = ["country_code", "region", "date", "fuel_type", "price_usd_per_litre", "tax_usd_per_litre",
            "tax_rate_pct", "subsidy_usd_per_litre", "gdp_per_capita_usd", "income_group",
            "affordability_pct_daily_income"]
    for c in core:
        if d[c].isna().any():
            problems.append(f"nulls in {c}")
    if (d["price_usd_per_litre"] <= 0).any():
        problems.append("non-positive price")
    if ((d["tax_rate_pct"] < 0) | (d["tax_rate_pct"] > config.TAX_RATE_MAX)).any():
        problems.append("tax rate out of range")
    if d.duplicated(["country_code", "date", "fuel_type"]).any():
        problems.append("duplicate natural keys")
    return problems
