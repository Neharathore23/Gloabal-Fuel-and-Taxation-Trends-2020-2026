"""Database layer: engine, schema creation, transactional load, named queries, summary, exports.

CLI:  python -m src.database build | summary | query <name> [key=value ...]
"""
import calendar
import math
import re
import sys
import time
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, event, text

import config

_ENGINES: dict = {}
FACT_COLUMNS = ["record_id", "country_id", "date_id", "fuel_id", "price_usd_per_litre", "price_before_tax_usd",
                "tax_usd_per_litre", "tax_rate_pct", "tax_share_pct", "subsidy_usd_per_litre",
                "subsidy_ratio_pct", "affordability_pct_daily_income", "dq_flags", "is_imputed"]
EXPORT_TABLES = ["dim_country", "dim_date", "dim_fuel", "fact_economy", "fact_fuel_price", "vw_fuel_price_detail"]


def get_engine(url: str | None = None):
    url = url or config.DATABASE_URL
    if url not in _ENGINES:
        if url.startswith("sqlite:///"):
            from pathlib import Path
            Path(url.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)
        eng = create_engine(url)
        if eng.dialect.name == "sqlite":
            @event.listens_for(eng, "connect")
            def _setup(dbapi_conn, _record):
                dbapi_conn.execute("PRAGMA foreign_keys=ON")
                dbapi_conn.create_function("sqrt", 1, lambda x: None if x is None else math.sqrt(x))
        _ENGINES[url] = eng
    return _ENGINES[url]


def _strip_comments(sql: str) -> str:
    return re.sub(r"^\s*--.*$", "", sql, flags=re.M)


def _run_script(conn, path) -> None:
    for stmt in (s.strip() for s in _strip_comments(path.read_text(encoding="utf-8")).split(";")):
        if stmt:
            conn.exec_driver_sql(stmt)


def init_schema(engine=None) -> None:
    """(Re)create all tables and views in one transaction."""
    engine = engine or get_engine()
    with engine.begin() as conn:
        _run_script(conn, config.SQL_DIR / "schema.sql")
        _run_script(conn, config.SQL_DIR / "views.sql")


def _mode(s: pd.Series):
    return s.mode().iat[0]


def build_tables(clean: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Split the flat clean table into star-schema tables with explicit surrogate keys."""
    c = clean.groupby("country_code").agg(country_name=("country", _mode), region=("region", _mode),
                                          income_group=("income_group", _mode),
                                          currency_local=("currency_local", _mode)).reset_index()
    c.insert(0, "country_id", range(1, len(c) + 1))
    dates = pd.DataFrame({"full_date": sorted(clean["date"].unique())})
    dates["year"], dates["month"] = dates["full_date"].dt.year, dates["full_date"].dt.month
    dates["quarter"] = dates["full_date"].dt.quarter
    dates["date_id"] = dates["year"] * 100 + dates["month"]
    dates["month_name"] = dates["month"].map(lambda m: calendar.month_name[m])
    dates["full_date"] = dates["full_date"].dt.strftime("%Y-%m-%d")
    dates = dates[["date_id", "full_date", "year", "quarter", "month", "month_name"]]
    fuels = pd.DataFrame({"fuel_type": config.FUEL_TYPES})
    extra = sorted(set(clean["fuel_type"]) - set(config.FUEL_TYPES))
    fuels = pd.concat([fuels, pd.DataFrame({"fuel_type": extra})], ignore_index=True)
    fuels.insert(0, "fuel_id", range(1, len(fuels) + 1))
    fuels["unit"] = "USD per litre (nominal)"
    econ = (clean.groupby(["country_code", "year"])["gdp_per_capita_usd"].median().reset_index()
            .merge(c[["country_id", "country_code"]], on="country_code")[["country_id", "year", "gdp_per_capita_usd"]])
    f = (clean.merge(c[["country_id", "country_code"]], on="country_code")
         .merge(fuels[["fuel_id", "fuel_type"]], on="fuel_type"))
    f["date_id"] = f["date"].dt.year * 100 + f["date"].dt.month
    f["dq_flags"] = f["dq_flags"].fillna("")
    f["is_imputed"] = f["is_imputed"].astype(int)
    return {"dim_country": c, "dim_date": dates, "dim_fuel": fuels, "fact_economy": econ,
            "fact_fuel_price": f[FACT_COLUMNS].sort_values("record_id")}


def load_clean(engine, clean: pd.DataFrame, meta: dict | None = None) -> dict:
    """Insert all tables in ONE transaction (all-or-nothing) and verify row counts."""
    tables = build_tables(clean)
    meta = meta or {}
    t0 = time.perf_counter()
    with engine.begin() as conn:
        for name in ("dim_country", "dim_date", "dim_fuel", "fact_economy", "fact_fuel_price"):
            tables[name].to_sql(name, conn, if_exists="append", index=False, chunksize=2000)
        inserted = conn.execute(text("SELECT COUNT(*) FROM fact_fuel_price")).scalar_one()
        if inserted != len(clean):
            raise RuntimeError(f"Row count mismatch: expected {len(clean)}, inserted {inserted}")
        conn.execute(text("INSERT INTO etl_run (loaded_at, data_origin, source_records, cleaned_records, inserted_records) "
                          "VALUES (:t, :o, :s, :c, :i)"),
                     {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "o": meta.get("data_origin"),
                      "s": meta.get("source_records"), "c": int(len(clean)), "i": int(inserted)})
    return {"inserted_records": int(inserted), "load_seconds": round(time.perf_counter() - t0, 3)}


def build_database(clean: pd.DataFrame, engine=None, meta: dict | None = None) -> dict:
    """Recreate schema + views and load `clean`; returns load stats."""
    engine = engine or get_engine()
    init_schema(engine)
    return load_clean(engine, clean, meta)


def load_queries() -> dict:
    """Parse database/queries.sql into {name: (sql, default_params)}."""
    out, cur = {}, None
    for line in (config.SQL_DIR / "queries.sql").read_text(encoding="utf-8").splitlines():
        if m := re.match(r"--\s*name:\s*(\w+)", line):
            cur = m.group(1)
            out[cur] = {"lines": [], "params": {}}
        elif cur and (m := re.match(r"--\s*params:\s*(.*)", line)):
            for kv in m.group(1).split():
                k, v = kv.split("=", 1)
                out[cur]["params"][k] = int(v) if v.lstrip("-").isdigit() else v.replace("_", " ") if k == "region" else v
        elif cur and not line.strip().startswith("--"):
            out[cur]["lines"].append(line)
    return {k: ("\n".join(v["lines"]).strip().rstrip(";"), v["params"]) for k, v in out.items()}


def run_named(name: str, engine=None, **params) -> pd.DataFrame:
    queries = load_queries()
    if name not in queries:
        raise KeyError(f"Unknown query '{name}'. Available: {sorted(queries)}")
    sql, defaults = queries[name]
    engine = engine or get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params={**defaults, **params})


def validate(engine=None) -> dict:
    """Run the SQL validation queries; every value should be 0."""
    return {n: int(run_named(n, engine).iloc[0, 0]) for n in load_queries() if n.startswith("validation_")}


def summary(engine=None) -> dict:
    """Row counts, entity counts, date range and missing values."""
    engine = engine or get_engine()
    with engine.connect() as conn:
        one = lambda q: conn.execute(text(q)).scalar_one()  # noqa: E731
        cols = [c for c in FACT_COLUMNS if c not in ("record_id", "dq_flags")]
        miss = conn.execute(text("SELECT " + ", ".join(f"SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END)" for c in cols)
                                 + " FROM fact_fuel_price")).one()
        run = conn.execute(text("SELECT loaded_at, data_origin, source_records, cleaned_records, inserted_records "
                                "FROM etl_run ORDER BY run_id DESC LIMIT 1")).mappings().first()
        return {
            "row_counts": dict(run_named("db_row_counts", engine).values.tolist()),
            "countries": one("SELECT COUNT(*) FROM dim_country"),
            "regions": one("SELECT COUNT(DISTINCT region) FROM dim_country"),
            "fuel_types": one("SELECT COUNT(*) FROM dim_fuel"),
            "income_groups": one("SELECT COUNT(DISTINCT income_group) FROM dim_country"),
            "date_min": str(one("SELECT MIN(full_date) FROM dim_date")),
            "date_max": str(one("SELECT MAX(full_date) FROM dim_date")),
            "missing_values": {c: int(v or 0) for c, v in zip(cols, miss)},
            "last_load": dict(run) if run else None,
        }


def export_tables(engine=None, out_dir=None) -> list[str]:
    """Write the star schema (and the flat view) as Tableau-ready CSV files."""
    engine, out_dir = engine or get_engine(), out_dir or config.EXPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    with engine.connect() as conn:
        for t in EXPORT_TABLES:
            df = pd.read_sql(text(f"SELECT * FROM {t}"), conn)
            df.to_csv(out_dir / f"{t}.csv", index=False)
            written.append(f"{t}.csv")
    return written


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    if cmd == "build":
        df = pd.read_csv(config.PROCESSED_FILE, parse_dates=["date"], keep_default_na=False, na_values=[""])
        print(build_database(df))
    elif cmd == "summary":
        import json
        print(json.dumps(summary(), indent=2))
    elif cmd == "query":
        kv = dict(a.split("=", 1) for a in sys.argv[3:])
        print(run_named(sys.argv[2], **kv).to_string(index=False))
    else:
        sys.exit(__doc__)
