"""Measure real response times of the dashboard API using Flask's in-process test client.

Usage:  python scripts/perf_test.py [--repeat 5] [--json out.json]
Reports cold (first call, cache empty) and warm (cached) latency per endpoint; also times the pipeline stages.
No network or running server is needed. Numbers depend on your machine - nothing here is pre-recorded.
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from src import analytics, charts  # noqa: E402

FILTER_SETS = {"all": "", "diesel_asia": "fuel=Diesel&region=South Asia", "2023-24": "date_from=2023-01&date_to=2024-12"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--json")
    a = ap.parse_args()
    from app import create_app

    client = create_app().test_client()
    if client.get("/healthz").get_json()["database"] is not True:
        sys.exit("Database not ready. Run: python scripts/run_pipeline.py")
    rows = []
    targets = [("page", p) for p in ("/", "/dashboard", "/regional", "/taxation", "/affordability", "/trends")]
    targets += [("api", "/api/kpis")] + [("api", f"/api/chart/{n}") for n in charts.REGISTRY]
    for fname, q in FILTER_SETS.items():
        for kind, path in targets:
            if kind == "page" and fname != "all":
                continue
            url = path + (("?" + q) if q and kind == "api" else "")
            analytics.clear_cache()
            t = time.perf_counter()
            r = client.get(url)
            cold = (time.perf_counter() - t) * 1000
            warm = []
            for _ in range(a.repeat):
                t = time.perf_counter()
                client.get(url)
                warm.append((time.perf_counter() - t) * 1000)
            rows.append({"filters": fname, "kind": kind, "path": path, "status": r.status_code,
                         "cold_ms": round(cold, 1), "warm_median_ms": round(statistics.median(warm), 1)})
    bad = [r for r in rows if r["status"] != 200]
    api = [r for r in rows if r["kind"] == "api"]
    summary = {"db": config.DATABASE_URL.split("///")[-1].split("/")[-1], "requests_tested": len(rows),
               "non_200": len(bad), "api_cold_ms_median": round(statistics.median(r["cold_ms"] for r in api), 1),
               "api_cold_ms_max": max(r["cold_ms"] for r in api),
               "api_warm_ms_median": round(statistics.median(r["warm_median_ms"] for r in api), 1),
               "slowest": sorted(rows, key=lambda r: -r["cold_ms"])[:3]}
    print(json.dumps(summary, indent=2))
    if a.json:
        Path(a.json).write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
