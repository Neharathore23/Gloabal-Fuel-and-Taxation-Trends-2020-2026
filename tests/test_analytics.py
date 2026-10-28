"""Filters, aggregation correctness, statistics, forecasting."""
import numpy as np
import pandas as pd
import pytest

from src import analytics as A
from src import forecasting


def F(**kw):
    return A.parse_filters(kw)


def test_parse_filters_valid(pipeline):
    f = F(country="IND,DEU", fuel="Petrol", date_from="2022-01", date_to="2023-12")
    assert f.countries == ("DEU", "IND") and f.fuels == ("Petrol",)
    assert f.date_from == "2022-01-01" and f.date_to == "2023-12-01"




def test_parse_filters_invalid(pipeline):
    for args in ({"country": "ZZZ"}, {"region": "Atlantis"}, {"fuel": "Coal"}, {"income": "Rich"},
                 {"date_from": "garbage"}, {"date_from": "2024-05", "date_to": "2022-01"},
                 {"country": "IND'; DROP TABLE fact_fuel_price;--"}):
        with pytest.raises(A.FilterError):
            A.parse_filters(args)


def test_sql_injection_does_not_alter_db(pipeline):
    with pytest.raises(A.FilterError):
        A.parse_filters({"fuel": "Petrol'; DROP TABLE dim_fuel;--"})
    assert A.query("SELECT COUNT(*) n FROM dim_fuel").n[0] == 3


def test_options(pipeline):
    o = A.options()
    assert len(o["countries"]) == 84 and len(o["regions"]) == 7 and len(o["fuels"]) == 3
    assert o["date_min"] == "2020-01" and o["date_max"] == "2026-10"


def test_unsupported_group_by_rejected(pipeline):
    with pytest.raises(ValueError):
        A.aggregate(F(), ["country; DROP TABLE x"], ["avg_price"])
    with pytest.raises(ValueError):
        A.aggregate(F(), ["region"], ["not_a_metric"])


def test_kpis_match_pandas(pipeline):
    clean = pipeline["clean"]
    k = A.kpis(F())
    assert k["empty"] is False
    assert k["n_records"] == len(clean) and k["n_countries"] == 84
    assert abs(k["avg_price"] - clean["price_usd_per_litre"].mean()) < 1e-9
    assert abs(k["effective_tax_burden_pct"] - clean["tax_usd_per_litre"].sum() / clean["price_usd_per_litre"].sum() * 100) < 1e-6
    assert abs(k["subsidy_to_price_pct"] - clean["subsidy_usd_per_litre"].sum() / clean["price_usd_per_litre"].sum() * 100) < 1e-6


def test_filter_reduces_and_matches(pipeline):
    clean = pipeline["clean"]
    sub = clean[(clean["fuel_type"] == "Diesel") & (clean["region"] == "South Asia")]
    k = A.kpis(F(fuel="Diesel", region="South Asia"))
    assert k["n_records"] == len(sub)
    assert abs(k["avg_price"] - sub["price_usd_per_litre"].mean()) < 1e-9
    assert k["n_records"] < A.kpis(F())["n_records"]


def test_date_filter(pipeline):
    clean = pipeline["clean"]
    sub = clean[(clean["date"] >= "2024-01-01") & (clean["date"] <= "2024-12-01")]
    assert A.kpis(F(date_from="2024-01", date_to="2024-12"))["n_records"] == len(sub)


def test_empty_selection(pipeline):
    k = A.kpis(F(country="IND", region="Europe & Central Asia"))
    assert k["empty"] is True and k["n_records"] == 0 and k["avg_price"] is None
    assert A.country_averages(F(country="IND", region="Europe & Central Asia")).empty


def test_country_averages_one_row_per_country(pipeline):
    df = A.country_averages(F())
    assert len(df) == 84 and df["country_code"].is_unique
    assert df["avg_price"].is_monotonic_decreasing


def test_price_statistics(pipeline):
    s = A.price_statistics(F(), "fuel_type").set_index("fuel_type")
    c = pipeline["clean"].groupby("fuel_type")["price_usd_per_litre"]
    assert (s["median"] - c.median()).abs().max() < 1e-9
    assert (s["max"] - c.max()).abs().max() < 1e-9
    assert (s["median"] <= s["max"]).all()


def test_volatility_definition(pipeline):
    v = A.volatility(F(country="IND", fuel="Petrol"))
    row = v.iloc[0]
    s = pipeline["clean"].query("country_code=='IND' and fuel_type=='Petrol'")["price_usd_per_litre"]
    assert abs(row["cv_pct"] - s.std() / s.mean() * 100) < 1e-6


def test_yoy_calculation(pipeline):
    y = A.yoy(F(fuel="Petrol"), "fuel_type")
    y = y.sort_values("year")
    expected = y["avg_price"].pct_change() * 100
    assert np.allclose(y["yoy_change_pct"].dropna(), expected.dropna())
    assert pd.isna(y["yoy_change_pct"].iloc[0])


def test_correlations_matrix(pipeline):
    c = A.correlations(F())
    m = np.array(c["matrix"])
    assert m.shape == (6, 6) and np.allclose(np.diag(m), 1) and np.allclose(m, m.T)
    assert (np.abs(m) <= 1.0001).all()
    assert A.correlations(F(country="IND"))["matrix"] == []


def test_affordability_ordering(pipeline):
    d = A.income_affordability(F(fuel="Petrol")).set_index("income_group")["avg_affordability_pct"]
    assert d["Low"] > d["High"]  # low-income countries spend a larger share of daily income per litre


def test_forecast_output(pipeline):
    s = A.monthly_series(F(fuel="Petrol"))
    r = forecasting.forecast_series(s, horizon=12)
    fc = r["forecast"]
    assert len(fc) == 12 and (fc["lower"] <= fc["forecast"]).all() and (fc["forecast"] <= fc["upper"]).all()
    assert fc["date"].iloc[0] == s.index[-1] + pd.offsets.MonthBegin(1)
    assert set(r["metrics"]) >= {"holt", "naive"} and r["metrics"]["holt"]["mape_pct"] >= 0
    wide = (fc["upper"] - fc["lower"]).to_numpy()
    assert wide[-1] > wide[0]  # uncertainty widens with horizon


def test_forecast_rejects_short_series_and_bad_horizon():
    with pytest.raises(ValueError):
        forecasting.forecast_series(pd.Series(range(10), index=pd.date_range("2020-01-01", periods=10, freq="MS"), dtype=float))
    s = pd.Series(np.linspace(1, 2, 40), index=pd.date_range("2020-01-01", periods=40, freq="MS"))
    with pytest.raises(ValueError):
        forecasting.forecast_series(s, horizon=99)


def test_forecast_recovers_linear_trend():
    s = pd.Series(np.linspace(1, 2, 48), index=pd.date_range("2020-01-01", periods=48, freq="MS"))
    r = forecasting.forecast_series(s, horizon=3)
    assert r["metrics"]["holt"]["mape_pct"] < r["metrics"]["naive"]["mape_pct"]
