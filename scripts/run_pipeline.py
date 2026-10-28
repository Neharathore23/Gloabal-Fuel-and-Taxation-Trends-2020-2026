"""One-command pipeline: generate/ingest -> validate/preprocess -> database -> exports.

Usage:  python scripts/run_pipeline.py [--regenerate]
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from src import analytics, data_generator, database, ingestion, preprocessing  # noqa: E402


def run(regenerate: bool = False) -> dict:
    timings = {}
    t0 = time.perf_counter()
    if regenerate or not config.RAW_FILE.exists():
        print(f"[1/5] Generating SYNTHETIC raw data at {config.RAW_FILE}")
        data_generator.generate_raw()
    else:
        print(f"[1/5] Using existing raw file {config.RAW_FILE}")
    timings["generate_s"] = round(time.perf_counter() - t0, 3)

    t0 = time.perf_counter()
    raw = ingestion.load_raw()
    timings["ingest_s"] = round(time.perf_counter() - t0, 3)

    t0 = time.perf_counter()
    clean, rejected, report = preprocessing.preprocess(raw)
    timings["preprocess_s"] = round(time.perf_counter() - t0, 3)
    print(f"[2/5] Preprocessed {len(raw):,} source rows -> {len(clean):,} clean, {len(rejected):,} removed")

    t0 = time.perf_counter()
    origin = "SYNTHETIC" if report["is_synthetic"] else "external"
    load = database.build_database(clean, meta={"data_origin": origin, "source_records": len(raw)})
    analytics.clear_cache()
    timings["db_total_s"] = round(time.perf_counter() - t0, 3)
    timings["db_load_s"] = load["load_seconds"]
    report["counts"]["inserted_records"] = load["inserted_records"]
    report["database"] = {"summary": database.summary(), "validation_violations": database.validate()}
    print(f"[3/5] Database {config.DATABASE_URL.split('///')[-1]}: {load['inserted_records']:,} fact rows inserted "
          f"(load {load['load_seconds']}s); SQL validation: {report['database']['validation_violations']}")

    report["timings"] = timings
    preprocessing.write_outputs(clean, rejected, report)
    print(f"[4/5] Wrote cleaned CSV, rejected-rows log, quality report, flat Tableau CSV")
    exported = database.export_tables()
    print(f"[5/5] Exported star-schema CSVs for Tableau: {', '.join(exported)}")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--regenerate", action="store_true", help="regenerate the synthetic raw file")
    r = run(ap.parse_args().regenerate)
    print(json.dumps({"counts": r["counts"], "entities": r["entities"], "timings": r["timings"]}, indent=2))
