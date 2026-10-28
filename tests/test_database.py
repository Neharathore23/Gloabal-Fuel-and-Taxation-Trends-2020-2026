"""Database initialisation, loading, constraints, views, named queries."""
import pytest

from src import analytics, database


def test_rows_inserted_equal_clean(pipeline):
    assert pipeline["load"]["inserted_records"] == len(pipeline["clean"])


def test_summary_entities(pipeline):
    assert database.summary()  # non-empty summary dict
    q = analytics.query
    assert q("SELECT COUNT(*) n FROM dim_country").n[0] == 84
    assert q("SELECT COUNT(DISTINCT region) n FROM dim_country").n[0] == 7
    assert q("SELECT COUNT(*) n FROM dim_fuel").n[0] == 3
    assert q("SELECT COUNT(*) n FROM fact_fuel_price").n[0] == len(pipeline["clean"])


def test_validation_has_no_violations(pipeline):
    v = database.validate()
    assert sum(v.values()) == 0, v


def test_unique_natural_key_enforced(pipeline):
    eng = database.get_engine()
    with pytest.raises(Exception):
        with eng.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO fact_fuel_price (record_id, country_id, date_id, fuel_id, price_usd_per_litre, "
                "price_before_tax_usd, tax_usd_per_litre, tax_rate_pct, tax_share_pct, subsidy_usd_per_litre, "
                "subsidy_ratio_pct, affordability_pct_daily_income, dq_flags, is_imputed) "
                "SELECT 999999, country_id, date_id, fuel_id, price_usd_per_litre, price_before_tax_usd, "
                "tax_usd_per_litre, tax_rate_pct, tax_share_pct, subsidy_usd_per_litre, subsidy_ratio_pct, "
                "affordability_pct_daily_income, dq_flags, is_imputed FROM fact_fuel_price LIMIT 1")


def test_foreign_key_enforced(pipeline):
    eng = database.get_engine()
    with pytest.raises(Exception):
        with eng.begin() as conn:
            conn.exec_driver_sql("UPDATE fact_fuel_price SET country_id = -5 WHERE record_id = "
                                 "(SELECT MIN(record_id) FROM fact_fuel_price)")


def test_all_named_queries_run(pipeline):
    qs = database.load_queries()
    assert len(qs) >= 13
    for name in qs:
        assert database.run_named(name) is not None, name


def test_unknown_named_query():
    with pytest.raises(KeyError):
        database.run_named("does_not_exist")


def test_views_return_rows(pipeline):
    for v in ("vw_fuel_price_detail", "vw_country_year_fuel", "vw_region_year_fuel", "vw_yoy_country_fuel",
              "vw_volatility_country_fuel", "vw_region_rank_country_year"):
        assert analytics.query(f"SELECT COUNT(*) n FROM {v}").n[0] > 0, v


def test_detail_view_matches_fact(pipeline):
    assert analytics.query("SELECT COUNT(*) n FROM vw_fuel_price_detail").n[0] == len(pipeline["clean"])


def test_region_average_sql_matches_pandas(pipeline):
    clean = pipeline["clean"]
    # the view is the mean of country-year means (each country weighted equally)
    exp = (clean.groupby(["region", "country_code", "year", "fuel_type"])["price_usd_per_litre"].mean()
           .groupby(["region", "year", "fuel_type"]).mean())
    got = analytics.query("SELECT region, year, fuel_type, avg_price FROM vw_region_year_fuel")
    got = got.set_index(["region", "year", "fuel_type"])["avg_price"]
    common = exp.index.intersection(got.index)
    assert len(common) > 100
    assert (exp.loc[common] - got.loc[common]).abs().max() < 1e-6


def test_yoy_view_calculation(pipeline):
    d = analytics.query("SELECT * FROM vw_yoy_country_fuel")
    d = d.dropna(subset=["yoy_change_pct"])
    assert len(d) > 100
    prev = d["avg_price"] - d["yoy_change_usd"]
    assert (((d["avg_price"] / prev - 1) * 100) - d["yoy_change_pct"]).abs().max() < 1e-6


def test_export_tables(tmp_path, pipeline):
    out = database.export_tables(out_dir=tmp_path)
    assert set(out) == {f"{t}.csv" for t in database.EXPORT_TABLES}
    assert all((tmp_path / name).exists() for name in out)