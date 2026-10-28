"""Dataset generation, validation, preprocessing, ingestion."""
import pandas as pd
import pytest

import config
from src import data_generator, ingestion, preprocessing, validation


def test_generator_scope(raw):
    truth, _ = raw
    assert truth["country_code"].nunique() == 84
    assert truth["region"].nunique() == 7
    assert set(truth["fuel_type"]) == set(config.FUEL_TYPES)
    assert len(truth) == 84 * 3 * 82  # country x fuel x month grain
    assert pd.to_datetime(truth["date"]).min() == pd.Timestamp("2020-01-01")
    assert pd.to_datetime(truth["date"]).max() == pd.Timestamp("2026-10-01")


def test_generator_reproducible():
    a, b = data_generator.build_clean(seed=7), data_generator.build_clean(seed=7)
    pd.testing.assert_frame_equal(a, b)
    c = data_generator.build_clean(seed=8)
    assert not a["price_usd_per_litre"].equals(c["price_usd_per_litre"])


def test_generator_is_consistent(raw):
    t, _ = raw
    assert (t["price_usd_per_litre"] > 0).all()
    assert (t["tax_usd_per_litre"] >= 0).all() and (t["subsidy_usd_per_litre"] >= 0).all()
    assert (t["tax_usd_per_litre"] < t["price_usd_per_litre"]).all()


def test_defects_are_injected(raw):
    _, (dirty, info) = raw
    assert len(dirty) > 84 * 3 * 82 - 1
    assert info  # documented defect counts


def test_check_columns_rejects_missing():
    with pytest.raises(ValueError):
        validation.check_columns(pd.DataFrame({"country_code": ["A"]}))


def test_coerce_types_counts_unparseable():
    df = pd.DataFrame({c: ["1"] for c in validation.NUMERIC})
    df["price_usd_per_litre"] = ["abc"]
    df["date"] = ["not a date"]
    out, bad = validation.coerce_types(df)
    assert bad["price_usd_per_litre"] == 1 and bad["date"] == 1
    assert out["price_usd_per_litre"].isna().all()


def test_hard_reject_rules():
    base = dict(country_code="AAA", date=pd.Timestamp("2020-01-01"), fuel_type="Petrol", region="R",
                price_usd_per_litre=1.0, tax_usd_per_litre=0.3, tax_rate_pct=40.0,
                subsidy_usd_per_litre=0.0, gdp_per_capita_usd=5000.0)
    rows = [dict(base), {**base, "price_usd_per_litre": -1.0}, {**base, "tax_rate_pct": 900.0},
            {**base, "tax_usd_per_litre": -0.1}, {**base, "gdp_per_capita_usd": 0.0}]
    r = validation.hard_reject_reasons(pd.DataFrame(rows)).tolist()
    assert r[0] == ""
    assert r[1] == "nonpositive_price" and r[2] == "invalid_tax_rate"
    assert r[3] == "negative_tax" and r[4] == "invalid_gdp"


def test_preprocess_accounting(pipeline):
    rep, clean = pipeline["report"], pipeline["clean"]
    c = rep["counts"]
    assert c["source_records"] == len(pipeline["dirty"])
    assert c["cleaned_records"] == len(clean)
    assert c["source_records"] - c["total_removed"] == c["cleaned_records"]
    assert len(pipeline["rejected"]) >= c["total_removed"] - c["exact_duplicates_removed"] - 1


def test_clean_output_quality(pipeline):
    clean = pipeline["clean"]
    assert not clean.duplicated(["country_code", "date", "fuel_type"]).any()
    assert (clean["price_usd_per_litre"] > 0).all()
    assert clean[["tax_usd_per_litre", "tax_rate_pct", "subsidy_usd_per_litre", "gdp_per_capita_usd"]].notna().all().all()
    assert list(clean.columns) == preprocessing.CLEAN_COLUMNS
    assert validation.final_checks(clean) == []


def test_derived_columns_formula(pipeline):
    c = pipeline["clean"]
    # derived columns are stored rounded (2-4 dp), so compare with a rounding-sized tolerance
    assert ((c["tax_usd_per_litre"] / c["price_usd_per_litre"] * 100) - c["tax_share_pct"]).abs().max() < 0.02
    exp = c["price_usd_per_litre"] / (c["gdp_per_capita_usd"] / 365) * 100
    assert (exp - c["affordability_pct_daily_income"]).abs().max() < 0.01
    assert ((c["subsidy_usd_per_litre"] / c["price_usd_per_litre"] * 100) - c["subsidy_ratio_pct"]).abs().max() < 0.01


def test_imputation_is_flagged(pipeline):
    c = pipeline["clean"]
    assert (c.loc[c["is_imputed"].astype(bool), "dq_flags"] != "").all()


def test_ingestion_csv_roundtrip(tmp_path, pipeline):
    p = tmp_path / "x.csv"
    pipeline["dirty"].drop(columns="source_row").head(50).to_csv(p, index=False)
    assert len(ingestion.load_raw(p)) == 50


def test_ingestion_excel_roundtrip(tmp_path, pipeline):
    p = tmp_path / "x.xlsx"
    pipeline["dirty"].drop(columns="source_row").head(20).to_excel(p, index=False)
    assert len(ingestion.load_raw(p)) == 20


def test_ingestion_missing_file(tmp_path):
    with pytest.raises(Exception):
        ingestion.load_raw(tmp_path / "nope.csv")
