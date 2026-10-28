"""Shared fixtures: one SYNTHETIC dataset + one temporary SQLite database for the whole test session."""
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src import analytics, data_generator, database, ingestion, preprocessing  # noqa: E402


@pytest.fixture(scope="session")
def raw():
    return data_generator.build_clean(), data_generator.inject_defects(data_generator.build_clean())


@pytest.fixture(scope="session")
def pipeline(raw):
    """(truth, raw_with_defects, defect_info, clean, rejected, report) + temp DB active in config."""
    truth, (dirty_df, info) = raw
    work = Path(tempfile.mkdtemp(prefix="fuel_test_"))
    dirty_df.to_csv(work / "raw.csv", index=False)
    dirty = ingestion.load_raw(work / "raw.csv")  # same path as the real pipeline (text dtype + source_row)
    clean, rejected, report = preprocessing.preprocess(dirty)
    tmp = work / "test.db"
    old = config.DATABASE_URL
    config.DATABASE_URL = f"sqlite:///{tmp.as_posix()}"
    analytics.clear_cache()
    load = database.build_database(clean, meta={"data_origin": "SYNTHETIC", "source_records": len(dirty)})
    yield {"truth": truth, "dirty": dirty, "info": info, "clean": clean, "rejected": rejected,
           "report": report, "load": load}
    config.DATABASE_URL = old
    analytics.clear_cache()


@pytest.fixture(scope="session")
def client(pipeline):
    import app as app_module
    application = app_module.create_app()
    application.config["TESTING"] = True
    return application.test_client()
