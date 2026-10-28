"""Flask routes, JSON API, filter behaviour, charts, invalid/empty input handling."""
import json

import pytest

import app as app_module
import config
from src import charts, mdlite

PAGES = ["/", "/dashboard", "/regional", "/taxation", "/affordability", "/trends", "/methodology",
         "/data-quality", "/tableau", "/docs"]


def test_pages_ok(client):
    for p in PAGES:
        r = client.get(p)
        assert r.status_code == 200, p
        assert b"<html" in r.data.lower()


def test_healthz_and_headers(client):
    r = client.get("/healthz")
    assert r.get_json() == {"status": "ok", "database": True}
    r = client.get("/dashboard")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and "app;dur=" in r.headers["Server-Timing"]


def test_unknown_page_404(client):
    assert client.get("/nope").status_code == 404


def test_synthetic_label_visible(client):
    assert b"synthetic" in client.get("/dashboard").data.lower()


def test_at_least_ten_charts():
    assert len(charts.REGISTRY) >= 10
    assert len({s.name for s in charts.REGISTRY.values()}) == len(charts.REGISTRY)


def test_every_chart_returns_valid_json(client):
    for name in charts.REGISTRY:
        r = client.get(f"/api/chart/{name}")
        assert r.status_code == 200, name
        j = json.loads(r.data)  # strict JSON (no NaN)
        assert j["empty"] is False and j["figure"]["data"], name
        assert j["synthetic"] is True


def test_every_chart_survives_filters(client):
    combos = ["fuel=Diesel", "region=South Asia", "country=IND,DEU,BRA", "income=Low,High",
              "date_from=2023-01&date_to=2024-06", "fuel=LPG&region=Sub-Saharan Africa&income=Low"]
    for name in charts.REGISTRY:
        for q in combos:
            r = client.get(f"/api/chart/{name}?{q}")
            assert r.status_code == 200, (name, q)
            json.loads(r.data)


def test_chart_empty_state(client):
    q = "country=IND&region=Europe %26 Central Asia"
    r = client.get(f"/api/chart/region_bar?{q}")
    assert r.status_code == 200 and r.get_json()["empty"] is True and r.get_json()["message"]


def test_kpis_endpoint_and_filters_change_values(client):
    all_ = client.get("/api/kpis").get_json()
    dsl = client.get("/api/kpis?fuel=Diesel&region=South Asia").get_json()
    assert all_["n_countries"] == 84 and all_["empty"] is False
    assert dsl["n_records"] < all_["n_records"] and dsl["avg_price"] != all_["avg_price"]
    assert set(all_) >= {"avg_price", "effective_tax_burden_pct", "subsidy_to_price_pct", "n_countries"}


def test_kpis_empty(client):
    j = client.get("/api/kpis?country=IND&region=North America").get_json()
    assert j["empty"] is True and j["n_countries"] == 0


def test_filters_change_chart_data(client):
    a = client.get("/api/chart/country_ranking").get_json()["figure"]["data"]
    b = client.get("/api/chart/country_ranking?region=South Asia").get_json()["figure"]["data"]
    assert json.dumps(a) != json.dumps(b)


def test_invalid_inputs_return_400(client):
    for q in ("country=ZZZ", "fuel=Coal", "region=Mars", "income=Rich", "date_from=oops",
              "date_from=2025-01&date_to=2021-01", "country=IND';DROP TABLE dim_country;--"):
        for path in ("/api/kpis", "/api/chart/region_bar", "/api/data/country_table"):
            r = client.get(f"{path}?{q}")
            assert r.status_code == 400, (path, q)
            assert "error" in r.get_json()


def test_invalid_chart_options(client):
    for q in ("n=1", "n=abc", "n=999", "horizon=0", "horizon=100", "by=password"):
        assert client.get(f"/api/chart/country_ranking?{q}").status_code == 400, q


def test_unknown_chart_and_dataset_404(client):
    assert client.get("/api/chart/bogus").status_code == 404
    assert client.get("/api/data/bogus").status_code == 404


def test_data_endpoints(client):
    t = client.get("/api/data/country_table").get_json()
    assert len(t["rows"]) == 84 and t["columns"]
    s = client.get("/api/data/price_stats?by=fuel_type").get_json()
    assert {r["fuel_type"] for r in s["rows"]} == {"Petrol", "Diesel", "LPG"}
    assert client.get("/api/data/price_stats?by=evil").status_code == 400


def test_options_and_charts_endpoints(client):
    assert len(client.get("/api/options").get_json()["countries"]) == 84
    assert len(client.get("/api/charts").get_json()) == len(charts.REGISTRY)


def test_quality_endpoint(client):
    r = client.get("/api/quality")
    assert r.status_code in (200, 404)  # depends on whether the pipeline wrote the JSON report


def test_forecast_horizon_option(client):
    j = client.get("/api/chart/forecast?horizon=6&fuel=Petrol").get_json()
    assert j["empty"] is False


def test_forecast_with_too_little_data_is_handled(client):
    r = client.get("/api/chart/forecast?country=IND&fuel=Petrol&date_from=2025-01")
    assert r.status_code == 200 and r.get_json()["empty"] is True


def test_download_whitelist(client):
    assert client.get("/download/../config.py").status_code == 404
    assert client.get("/download/passwd").status_code == 404


def test_doc_view_path_traversal_blocked(client):
    for u in ("/docs/root/config", "/docs/docs/..%2Fconfig", "/docs/etc/passwd", "/docs/docs/nonexistent"):
        assert client.get(u).status_code == 404, u


def test_embed_url_validation():
    v = app_module.valid_embed_url
    assert v("") is None
    assert v("http://public.tableau.com/views/x/y") is None          # not https
    assert v("https://evil.example.com/views/x/y") is None            # host not allowed
    assert v("https://public.tableau.com.evil.com/x") is None         # suffix trick
    assert v("javascript:alert(1)") is None
    assert v("https://public.tableau.com/views/Book/Dash").startswith("https://public.tableau.com/views/Book/Dash?")


def test_tableau_page_reports_not_configured(client):
    old = config.TABLEAU_EMBED_URL
    config.TABLEAU_EMBED_URL = ""
    try:
        html = client.get("/tableau").data.decode().lower()
        assert "<iframe" not in html
    finally:
        config.TABLEAU_EMBED_URL = old


def test_tableau_page_rejects_bad_url(client):
    old = config.TABLEAU_EMBED_URL
    config.TABLEAU_EMBED_URL = "https://evil.example.com/x"
    try:
        assert "<iframe" not in client.get("/tableau").data.decode().lower()
    finally:
        config.TABLEAU_EMBED_URL = old


def test_mdlite_escapes_html():
    out = mdlite.render("# T\n\n<script>alert(1)</script>\n\n- a\n- b")
    assert "<script>" not in out and "<li>" in out


def test_missing_database_gives_503():
    old = config.DATABASE_URL
    config.DATABASE_URL = "sqlite:///" + (config.ROOT / "data" / "does_not_exist.db").as_posix()
    try:
        c = app_module.create_app().test_client()
        assert c.get("/api/kpis").status_code == 503
        assert c.get("/dashboard").status_code == 503
        assert c.get("/healthz").get_json()["database"] is False
    finally:
        config.DATABASE_URL = old
