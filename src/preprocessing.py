"""Standardise, de-duplicate, validate, impute (documented rules) and derive analytical fields."""
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import config
from src import validation as V

FUEL_ALIASES = {"petrol": "Petrol", "gasoline": "Petrol", "diesel": "Diesel", "gasoil": "Diesel",
                "lpg": "LPG", "autogas": "LPG", "liquefied petroleum gas": "LPG"}
INCOME_ALIASES = {"low": "Low", "low income": "Low", "lower-middle": "Lower-middle", "lower middle": "Lower-middle",
                  "upper-middle": "Upper-middle", "upper middle": "Upper-middle", "high": "High",
                  "high income": "High"}
REGION_ALIASES = {"mena": "Middle East & North Africa", "eca": "Europe & Central Asia",
                  "eap": "East Asia & Pacific", "lac": "Latin America & Caribbean", "sas": "South Asia",
                  "ssa": "Sub-Saharan Africa", "na": "North America"}

CLEAN_COLUMNS = ["record_id", "country_code", "country", "region", "income_group", "date", "year", "month",
                 "quarter", "fuel_type", "currency_local", "price_usd_per_litre", "price_before_tax_usd",
                 "tax_usd_per_litre", "tax_rate_pct", "tax_share_pct", "subsidy_usd_per_litre",
                 "subsidy_ratio_pct", "gdp_per_capita_usd", "affordability_pct_daily_income", "price_basis",
                 "data_source", "dq_flags", "is_imputed"]

RULES = [
    "Text fields are trimmed; country_code upper-cased; country/region/income labels are mapped to one canonical value per code.",
    "Fuel labels are mapped to Petrol/Diesel/LPG (aliases: gasoline, gasoil, autogas...); unmapped labels are rejected.",
    "Dates are parsed (mixed formats) and snapped to the first day of the month.",
    "Exact duplicate rows (after standardisation) are removed and logged; conflicting duplicates of the same country/month/fuel keep the first row and log the rest.",
    "Rejected: missing key fields, missing/non-positive price, tax rate <0 or >500, negative tax or subsidy, tax and rate both missing, non-positive GDP.",
    "Missing tax amount = price x rate / (100 + rate); missing tax rate = tax / (price - tax) x 100 (flag imputed_tax / imputed_tax_rate).",
    "Missing subsidy = median of the same country+fuel+year, else the country+fuel median (flag imputed_subsidy); unresolved rows are rejected.",
    "Missing GDP per capita = median of the same country+year, else the country median (flag imputed_gdp); unresolved rows are rejected.",
    "Missing income group is derived from GDP per capita using config.INCOME_BINS (flag derived_income_group).",
    "Extreme prices (> 5x or < 1/5 of the country+fuel median) are rejected as probable unit errors.",
    "Prices deviating >35% from a centred 13-month rolling median are flagged price_outlier but kept.",
    "tax_rate_pct differing by >1 percentage point from tax/(price-tax) is flagged tax_rate_mismatch but kept.",
    "Affordability = price per litre as % of daily GDP per capita (price / (GDP pc / 365) x 100); lower = more affordable.",
    "Prices are nominal USD per litre; no inflation adjustment and no FX conversion is applied by this pipeline.",
]


def _norm(s: pd.Series) -> pd.Series:
    return (s.astype("string").str.lower().str.replace("&", "and", regex=False)
            .str.replace(r"\s+", " ", regex=True).str.strip())


def _flag(d: pd.DataFrame, mask, name: str) -> None:
    mask = np.asarray(mask, dtype=bool)
    if mask.any():
        cur = d.loc[mask, "dq_flags"]
        d.loc[mask, "dq_flags"] = np.where(cur == "", name, cur + ";" + name)


def _mode_by_code(d: pd.DataFrame, col: str) -> pd.Series:
    modes = d.dropna(subset=[col]).groupby("country_code")[col].agg(lambda s: s.mode().iat[0])
    return d["country_code"].map(modes)


def standardize(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    for c in ["country_code", "country", "region", "income_group", "fuel_type", "currency_local", "data_source"]:
        d[c] = d[c].astype("string").str.strip().replace("", pd.NA)
    d["country_code"] = d["country_code"].str.upper()
    d["currency_local"] = d["currency_local"].str.upper()
    d["fuel_type"] = _norm(d["fuel_type"]).map(FUEL_ALIASES)
    canon = {_norm(pd.Series([v])).iat[0]: v for v in config.REGIONS.values()}
    canon.update({k: v for k, v in REGION_ALIASES.items()})
    d["region"] = _norm(d["region"]).map(canon)
    d["region"] = d["region"].fillna(_mode_by_code(d, "region"))
    d["income_group"] = _norm(d["income_group"]).map(INCOME_ALIASES)
    d["country"] = d["country"].str.replace(r"\s+", " ", regex=True)
    d["country"] = _mode_by_code(d, "country").fillna(d["country"])
    d["date"] = d["date"].dt.to_period("M").dt.to_timestamp()
    return d


def preprocess(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return (clean, rejected_log, report). `raw` must come from ingestion.load_raw."""
    V.check_columns(raw)
    n_source = len(raw)
    d, unparseable = V.coerce_types(raw)
    missing_before = {c: int(d[c].isna().sum()) for c in V.REQUIRED_COLUMNS}
    d = standardize(d)
    removed = []  # list of (source_row Series, reason str / Series)

    def drop(mask, reason):
        mask = np.asarray(mask, dtype=bool)
        r = reason[mask] if isinstance(reason, pd.Series) else reason
        removed.append(pd.DataFrame({"source_row": d.loc[mask, "source_row"].to_numpy(),
                                     "reason": r.to_numpy() if isinstance(r, pd.Series) else r}))
        return d.loc[~mask].copy()

    subset = [c for c in V.REQUIRED_COLUMNS]
    dup_exact = d.duplicated(subset=subset, keep="first")
    n_exact = int(dup_exact.sum())
    d = drop(dup_exact, "exact_duplicate")

    dup_key = d.duplicated(subset=["country_code", "date", "fuel_type"], keep="first")
    n_key = int(dup_key.sum())
    d = drop(dup_key & d["country_code"].notna() & d["date"].notna() & d["fuel_type"].notna(), "duplicate_key_conflict")

    reasons = V.hard_reject_reasons(d)
    hard = reasons != ""
    n_hard = int(hard.sum())
    d = drop(hard, reasons)

    d = d.reset_index(drop=True)
    d["dq_flags"] = ""
    d["year"] = d["date"].dt.year
    imputed = {}

    m = d["tax_usd_per_litre"].isna()
    d.loc[m, "tax_usd_per_litre"] = (d["price_usd_per_litre"] * d["tax_rate_pct"] / (100 + d["tax_rate_pct"]))[m]
    imputed["imputed_tax"] = int(m.sum())
    _flag(d, m, "imputed_tax")
    m = d["tax_rate_pct"].isna()
    d.loc[m, "tax_rate_pct"] = (d["tax_usd_per_litre"] / (d["price_usd_per_litre"] - d["tax_usd_per_litre"]) * 100)[m]
    imputed["imputed_tax_rate"] = int(m.sum())
    _flag(d, m, "imputed_tax_rate")

    for col, name in (("subsidy_usd_per_litre", "imputed_subsidy"), ("gdp_per_capita_usd", "imputed_gdp")):
        keys = ["country_code", "fuel_type", "year"] if col.startswith("subsidy") else ["country_code", "year"]
        fb = ["country_code", "fuel_type"] if col.startswith("subsidy") else ["country_code"]
        m = d[col].isna()
        d[col] = d[col].fillna(d.groupby(keys)[col].transform("median")).fillna(d.groupby(fb)[col].transform("median"))
        imputed[name] = int((m & d[col].notna()).sum())
        _flag(d, m & d[col].notna(), name)
    m = d["subsidy_usd_per_litre"].isna() | d["gdp_per_capita_usd"].isna() | d["tax_rate_pct"].isna() \
        | ~np.isfinite(d["tax_rate_pct"].fillna(0))
    n_unimputable = int(m.sum())
    d = drop(m, "unimputable_value")
    d = d.reset_index(drop=True)

    m = d["income_group"].isna()
    d.loc[m, "income_group"] = config.income_group(d.loc[m, "gdp_per_capita_usd"])
    imputed["derived_income_group"] = int(m.sum())
    _flag(d, m, "derived_income_group")
    d["income_group"] = d["income_group"].fillna(_mode_by_code(d, "income_group"))

    ratio = d["price_usd_per_litre"] / d.groupby(["country_code", "fuel_type"])["price_usd_per_litre"].transform("median")
    extreme = (ratio > config.EXTREME_RATIO) | (ratio < 1 / config.EXTREME_RATIO)
    n_extreme = int(extreme.sum())
    d = drop(extreme, "extreme_price").sort_values(["country_code", "fuel_type", "date"]).reset_index(drop=True)

    roll = d.groupby(["country_code", "fuel_type"])["price_usd_per_litre"].transform(
        lambda s: s.rolling(13, center=True, min_periods=3).median())
    _flag(d, ((d["price_usd_per_litre"] / roll) - 1).abs() > config.OUTLIER_TOLERANCE, "price_outlier")
    implied = d["tax_usd_per_litre"] / (d["price_usd_per_litre"] - d["tax_usd_per_litre"]) * 100
    _flag(d, (implied - d["tax_rate_pct"]).abs() > 1, "tax_rate_mismatch")

    d["month"] = d["date"].dt.month
    d["quarter"] = d["date"].dt.quarter
    d["price_before_tax_usd"] = d["price_usd_per_litre"] - d["tax_usd_per_litre"]
    d["tax_share_pct"] = d["tax_usd_per_litre"] / d["price_usd_per_litre"] * 100
    d["subsidy_ratio_pct"] = d["subsidy_usd_per_litre"] / d["price_usd_per_litre"] * 100
    d["affordability_pct_daily_income"] = d["price_usd_per_litre"] / (d["gdp_per_capita_usd"] / 365) * 100
    d["price_basis"] = "nominal USD per litre"
    d["is_imputed"] = d["dq_flags"].str.contains("imputed|derived", regex=True)
    d = d.sort_values(["country_code", "date", "fuel_type"]).reset_index(drop=True)
    d.insert(0, "record_id", np.arange(1, len(d) + 1))
    round_cols = {"price_before_tax_usd": 4, "tax_share_pct": 3, "subsidy_ratio_pct": 3, "tax_usd_per_litre": 4,
                  "tax_rate_pct": 2, "subsidy_usd_per_litre": 4, "affordability_pct_daily_income": 4,
                  "gdp_per_capita_usd": 0}
    d = d.round(round_cols)[CLEAN_COLUMNS]

    problems = V.final_checks(d)
    if problems:
        raise ValueError(f"Cleaned data failed validation: {problems}")

    rej = pd.concat(removed, ignore_index=True) if removed else pd.DataFrame(columns=["source_row", "reason"])
    rejected = rej.merge(raw, on="source_row", how="left").sort_values("source_row").reset_index(drop=True)
    by_reason = rejected["reason"].value_counts().to_dict()
    flags = pd.Series(";".join(d["dq_flags"]).split(";")).replace("", pd.NA).dropna().value_counts().to_dict()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "is_synthetic": bool(raw["data_source"].fillna("").str.contains("SYNTHETIC").any()),
        "data_sources": sorted(raw["data_source"].dropna().unique().tolist()),
        "grain": "one row per country x month x fuel type",
        "price_basis": "nominal USD per litre (no inflation adjustment, no FX conversion in this pipeline)",
        "counts": {"source_records": n_source, "exact_duplicates_removed": n_exact,
                   "key_conflicts_removed": n_key, "hard_rejects": n_hard,
                   "unimputable_rejected": n_unimputable, "extreme_price_rejected": n_extreme,
                   "total_removed": int(len(rejected)), "cleaned_records": int(len(d)),
                   "target_records": config.TARGET_RECORDS, "target_met": bool(len(d) == config.TARGET_RECORDS)},
        "rejected_by_reason": by_reason,
        "unparseable_cells": unparseable,
        "missing_before_cleaning": missing_before,
        "imputed": imputed,
        "flags_kept": flags,
        "entities": {"countries": int(d["country_code"].nunique()), "regions": int(d["region"].nunique()),
                     "fuel_types": int(d["fuel_type"].nunique()), "income_groups": int(d["income_group"].nunique()),
                     "months": int(d["date"].nunique()), "min_date": str(d["date"].min().date()),
                     "max_date": str(d["date"].max().date())},
        "rules": RULES,
    }
    return d, rejected, report


def write_outputs(clean: pd.DataFrame, rejected: pd.DataFrame, report: dict) -> None:
    for p in (config.PROCESSED_DIR, config.EXPORT_DIR):
        p.mkdir(parents=True, exist_ok=True)
    out = clean.copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out.to_csv(config.PROCESSED_FILE, index=False)
    rejected.to_csv(config.REJECTED_FILE, index=False)
    out.to_csv(config.TABLEAU_FLAT_FILE, index=False)
    config.QUALITY_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    config.QUALITY_MD.write_text(quality_markdown(report), encoding="utf-8")


def quality_markdown(r: dict) -> str:
    c, e = r["counts"], r["entities"]
    lines = ["# Data Quality Report", "",
             f"Generated: {r['generated_at']}  ",
             f"Data origin: **{'SYNTHETIC (simulated)' if r['is_synthetic'] else 'external / real source'}**  ",
             f"Grain: {r['grain']}  ", f"Price basis: {r['price_basis']}", "", "## Record counts", "",
             "| Metric | Value |", "|---|---|"]
    lines += [f"| {k.replace('_', ' ')} | {v:,} |" if isinstance(v, int) and not isinstance(v, bool) else f"| {k.replace('_', ' ')} | {v} |"
              for k, v in c.items()]
    lines += ["", "## Coverage", "", "| Entity | Value |", "|---|---|"] + [f"| {k.replace('_', ' ')} | {v} |" for k, v in e.items()]
    for title, key in (("Removed rows by reason", "rejected_by_reason"), ("Imputations / derivations", "imputed"),
                       ("Flags kept on rows", "flags_kept"), ("Missing cells before cleaning", "missing_before_cleaning")):
        lines += ["", f"## {title}", "", "| Item | Count |", "|---|---|"] + [f"| {k} | {v} |" for k, v in r[key].items()]
    db = r.get("database")
    if db:
        s = db["summary"]
        lines += ["", "## Database", "", "| Table | Rows |", "|---|---|"] + [f"| {k} | {v:,} |" for k, v in s["row_counts"].items()]
        lines += ["", "SQL validation violations (all should be 0): " + ", ".join(f"{k}={v}" for k, v in db["validation_violations"].items())]
    if r.get("timings"):
        lines += ["", "## Measured timings (seconds)", ""] + [f"- {k}: {v}" for k, v in r["timings"].items()]
    lines += ["", "## Cleaning rules applied", ""] + [f"{i}. {x}" for i, x in enumerate(r["rules"], 1)]
    return "\n".join(lines) + "\n"
