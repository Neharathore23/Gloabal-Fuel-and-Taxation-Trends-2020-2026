"""Filter-aware analytics layer used by the Flask app.

* All filters are validated against the database dimensions and passed as bound parameters.
* Group-by columns and metrics come from fixed whitelists (no user text is ever interpolated into SQL).
* Results are cached per (database version, SQL, parameters); the cache invalidates when the SQLite file changes.
"""
import os
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
from sqlalchemy import text

from src import database

VIEW = "vw_fuel_price_detail"
DIMENSIONS = {"country_code", "country", "region", "income_group", "year", "quarter", "date", "fuel_type"}
_P, _T, _S = "price_usd_per_litre", "tax_usd_per_litre", "subsidy_usd_per_litre"
_VAR = f"(AVG({_P}*{_P}) - AVG({_P})*AVG({_P})) * COUNT(*) / (COUNT(*) - 1.0)"
METRICS = {
    "n_records": "COUNT(*)",
    "n_countries": "COUNT(DISTINCT country_code)",
    "avg_price": f"AVG({_P})",
    "min_price": f"MIN({_P})",
    "max_price": f"MAX({_P})",
    "avg_tax_usd": f"AVG({_T})",
    "avg_tax_rate_pct": "AVG(tax_rate_pct)",
    "effective_tax_burden_pct": f"SUM({_T}) * 100.0 / SUM({_P})",
    "avg_subsidy_usd": f"AVG({_S})",
    "subsidy_to_price_pct": f"SUM({_S}) * 100.0 / SUM({_P})",
    "avg_affordability_pct": "AVG(affordability_pct_daily_income)",
    "avg_gdp_per_capita": "AVG(gdp_per_capita_usd)",
    "std_price": f"CASE WHEN COUNT(*) > 1 THEN sqrt(CASE WHEN {_VAR} > 0 THEN {_VAR} ELSE 0 END) END",
}
DETAIL_COLUMNS = ["country_code", "country", "region", "income_group", "date", "year", "fuel_type", _P, _T,
                  "tax_rate_pct", "tax_share_pct", _S, "subsidy_ratio_pct", "gdp_per_capita_usd",
                  "affordability_pct_daily_income"]


class FilterError(ValueError):
    """Raised for invalid filter input (the API maps this to HTTP 400)."""


@dataclass(frozen=True)
class Filters:
    date_from: str | None = None  # 'YYYY-MM-01'
    date_to: str | None = None
    countries: tuple = ()
    regions: tuple = ()
    fuels: tuple = ()
    income_groups: tuple = ()


# ---------------------------------------------------------------- engine / cache plumbing
def _version(url: str):
    eng = database.get_engine(url)
    if eng.dialect.name == "sqlite" and eng.url.database:
        try:
            return os.stat(eng.url.database).st_mtime_ns
        except OSError:
            return None
    with eng.connect() as conn:
        return conn.execute(text("SELECT MAX(run_id) FROM etl_run")).scalar()


@lru_cache(maxsize=512)
def _cached(url: str, version, sql: str, params: tuple) -> pd.DataFrame:
    with database.get_engine(url).connect() as conn:
        return pd.read_sql(text(sql), conn, params=dict(params))


def query(sql: str, params: dict | None = None, url: str | None = None) -> pd.DataFrame:
    from config import DATABASE_URL
    url = url or DATABASE_URL
    return _cached(url, _version(url), sql, tuple(sorted((params or {}).items()))).copy()


def clear_cache() -> None:
    _cached.cache_clear()


# ---------------------------------------------------------------- options + filter parsing
def options(url: str | None = None) -> dict:
    d = query("SELECT country_code, country_name AS country, region, income_group FROM dim_country "
              "ORDER BY country_name", url=url)
    dates = query("SELECT MIN(full_date) AS lo, MAX(full_date) AS hi FROM dim_date", url=url).iloc[0]
    fuels = query("SELECT fuel_type FROM dim_fuel ORDER BY fuel_id", url=url)["fuel_type"].tolist()
    inc = [g for g in ("Low", "Lower-middle", "Upper-middle", "High") if g in set(d["income_group"])]
    return {"countries": d.to_dict("records"), "regions": sorted(d["region"].unique()), "fuels": fuels,
            "income_groups": inc, "date_min": str(dates["lo"])[:7], "date_max": str(dates["hi"])[:7]}


def _csv(args, key: str) -> list[str]:
    raw = args.get(key) or ""
    return [v.strip() for v in raw.split(",") if v.strip()]


def parse_filters(args, url: str | None = None) -> Filters:
    """Build validated Filters from a mapping such as request.args (comma-separated multi-values)."""
    opt = options(url)
    out = {}
    for key, field, allowed in (("country", "countries", {c["country_code"] for c in opt["countries"]}),
                                ("region", "regions", set(opt["regions"])),
                                ("fuel", "fuels", set(opt["fuels"])),
                                ("income", "income_groups", set(opt["income_groups"]))):
        vals = _csv(args, key)
        bad = [v for v in vals if v not in allowed]
        if bad:
            raise FilterError(f"Invalid {key} value(s): {', '.join(bad)}")
        out[field] = tuple(sorted(set(vals)))
    for key, field in (("date_from", "date_from"), ("date_to", "date_to")):
        v = (args.get(key) or "").strip()
        if v:
            try:
                out[field] = pd.Timestamp(v[:7] + "-01").strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                raise FilterError(f"Invalid {key} '{v}' (use YYYY-MM)") from None
    if out.get("date_from") and out.get("date_to") and out["date_from"] > out["date_to"]:
        raise FilterError("date_from must not be after date_to")
    return Filters(**out)


def where_clause(f: Filters) -> tuple[str, dict]:
    parts, params = [], {}
    if f.date_from:
        parts.append("date >= :date_from")
        params["date_from"] = f.date_from
    if f.date_to:
        parts.append("date <= :date_to")
        params["date_to"] = f.date_to
    for col, vals, tag in (("country_code", f.countries, "c"), ("region", f.regions, "r"),
                           ("fuel_type", f.fuels, "f"), ("income_group", f.income_groups, "i")):
        if vals:
            keys = [f"{tag}{i}" for i in range(len(vals))]
            parts.append(f"{col} IN ({', '.join(':' + k for k in keys)})")
            params.update(dict(zip(keys, vals)))
    return (" WHERE " + " AND ".join(parts)) if parts else "", params


# ---------------------------------------------------------------- generic aggregation
def aggregate(f: Filters, by: list[str], metrics: list[str], order_by: str | None = None,
              descending: bool = True, limit: int | None = None, url: str | None = None) -> pd.DataFrame:
    if not set(by) <= DIMENSIONS:
        raise ValueError(f"Unsupported group-by: {set(by) - DIMENSIONS}")
    if not set(metrics) <= set(METRICS):
        raise ValueError(f"Unsupported metrics: {set(metrics) - set(METRICS)}")
    where, params = where_clause(f)
    select = ", ".join(by + [f"{METRICS[m]} AS {m}" for m in metrics])
    sql = f"SELECT {select} FROM {VIEW}{where}"
    if by:
        sql += " GROUP BY " + ", ".join(by)
    if order_by:
        if order_by not in set(by) | set(metrics):
            raise ValueError("order_by must be a selected column")
        sql += f" ORDER BY {order_by} {'DESC' if descending else 'ASC'}"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return query(sql, params, url)


def detail(f: Filters, url: str | None = None) -> pd.DataFrame:
    where, params = where_clause(f)
    df = query(f"SELECT {', '.join(DETAIL_COLUMNS)} FROM {VIEW}{where} ORDER BY country_code, fuel_type, date",
               params, url)
    df["date"] = pd.to_datetime(df["date"])
    return df


# ---------------------------------------------------------------- dashboard datasets
KPI_METRICS = ["avg_price", "effective_tax_burden_pct", "subsidy_to_price_pct", "n_countries", "n_records",
               "avg_affordability_pct"]


def kpis(f: Filters, url: str | None = None) -> dict:
    row = aggregate(f, [], KPI_METRICS, url=url).iloc[0]
    if int(row["n_records"]) == 0:
        return {"empty": True, **{m: None for m in KPI_METRICS}, "n_records": 0, "n_countries": 0}
    out = {m: (None if pd.isna(row[m]) else float(row[m])) for m in KPI_METRICS}
    out["n_records"], out["n_countries"] = int(row["n_records"]), int(row["n_countries"])
    return {"empty": False, **out}


def country_averages(f: Filters, url: str | None = None) -> pd.DataFrame:
    return aggregate(f, ["country_code", "country", "region", "income_group"],
                     ["avg_price", "avg_tax_rate_pct", "effective_tax_burden_pct", "avg_subsidy_usd",
                      "subsidy_to_price_pct", "avg_affordability_pct", "avg_gdp_per_capita", "n_records"],
                     order_by="avg_price", url=url)


def region_averages(f: Filters, url: str | None = None) -> pd.DataFrame:
    return aggregate(f, ["region", "fuel_type"], ["avg_price", "effective_tax_burden_pct", "subsidy_to_price_pct",
                                                  "avg_affordability_pct", "n_countries"], url=url)


def monthly_trend(f: Filters, by: str = "fuel_type", url: str | None = None) -> pd.DataFrame:
    return aggregate(f, ["date", by], ["avg_price", "avg_tax_usd", "avg_subsidy_usd"], url=url).sort_values("date")


def fuel_by_year(f: Filters, url: str | None = None) -> pd.DataFrame:
    return aggregate(f, ["year", "fuel_type"], ["avg_price", "effective_tax_burden_pct", "n_records"], url=url)


def income_affordability(f: Filters, url: str | None = None) -> pd.DataFrame:
    df = aggregate(f, ["income_group", "fuel_type"], ["avg_affordability_pct", "avg_price", "avg_gdp_per_capita",
                                                       "n_countries"], url=url)
    order = {g: i for i, g in enumerate(["Low", "Lower-middle", "Upper-middle", "High"])}
    return df.sort_values("income_group", key=lambda s: s.map(order))


def price_statistics(f: Filters, by: str = "region", url: str | None = None) -> pd.DataFrame:
    """Mean, median, max and std of monthly retail prices by group (pandas: SQL has no portable median)."""
    if by not in DIMENSIONS:
        raise ValueError("unsupported grouping")
    df = detail(f, url)
    if df.empty:
        return pd.DataFrame(columns=[by, "mean", "median", "max", "std", "n"])
    return (df.groupby(by)["price_usd_per_litre"].agg(mean="mean", median="median", max="max", std="std", n="count")
            .reset_index())


def volatility(f: Filters, url: str | None = None) -> pd.DataFrame:
    """Per country+fuel: coefficient of variation of price level, and std dev of month-over-month % change."""
    df = detail(f, url)
    if df.empty:
        return pd.DataFrame(columns=["country_code", "country", "region", "fuel_type", "cv_pct", "mom_vol_pct"])
    df = df.sort_values(["country_code", "fuel_type", "date"])
    df["mom_pct"] = df.groupby(["country_code", "fuel_type"])["price_usd_per_litre"].pct_change() * 100
    g = df.groupby(["country_code", "country", "region", "fuel_type"])
    out = g.agg(avg_price=("price_usd_per_litre", "mean"), std_price=("price_usd_per_litre", "std"),
                mom_vol_pct=("mom_pct", "std"), n_months=("date", "nunique")).reset_index()
    out["cv_pct"] = out["std_price"] / out["avg_price"] * 100
    return out[out["n_months"] > 2]


def yoy(f: Filters, by: str = "fuel_type", url: str | None = None) -> pd.DataFrame:
    """Year-over-year change of the average price; the last year may be partial (see n_months)."""
    if by not in DIMENSIONS - {"year", "date", "quarter"}:
        raise ValueError("unsupported grouping")
    df = aggregate(f, ["year", by], ["avg_price"], url=url).sort_values([by, "year"])
    df["yoy_change_usd"] = df.groupby(by)["avg_price"].diff()
    df["yoy_change_pct"] = df.groupby(by)["avg_price"].pct_change() * 100
    return df


CORR_VARS = {"avg_price": "Retail price", "avg_tax_rate_pct": "Tax rate", "effective_tax_burden_pct": "Tax burden",
             "subsidy_to_price_pct": "Subsidy / price", "avg_gdp_per_capita": "GDP per capita",
             "avg_affordability_pct": "Affordability (% daily income)"}


def correlations(f: Filters, url: str | None = None) -> dict:
    """Pearson correlation across countries (country-level means). Association only - not causal."""
    df = country_averages(f, url)
    if len(df) < 3:
        return {"labels": [], "matrix": [], "n_countries": int(len(df))}
    m = df[list(CORR_VARS)].corr()
    return {"labels": list(CORR_VARS.values()), "matrix": m.round(3).fillna(0).values.tolist(),
            "n_countries": int(len(df))}


def monthly_series(f: Filters, url: str | None = None) -> pd.Series:
    """Average monthly price for the selection, as a month-start indexed series (input for forecasting)."""
    df = aggregate(f, ["date"], ["avg_price"], url=url).sort_values("date")
    s = pd.Series(df["avg_price"].to_numpy(), index=pd.to_datetime(df["date"]), name="avg_price")
    return s.asfreq("MS").interpolate() if len(s) else s
