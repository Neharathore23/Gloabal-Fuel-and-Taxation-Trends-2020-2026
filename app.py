"""Flask web application: dashboards, JSON APIs, methodology, data quality, Tableau integration and docs.

Run:  python app.py        (or: flask --app app run)
All SQL goes through src.analytics (parameterised, whitelisted); no credentials or paths are sent to the browser.
"""
import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, abort, g, jsonify, render_template, request, send_from_directory

import config
from src import analytics as A
from src import charts, database, mdlite

log = logging.getLogger("fuel-analytics")

NAV = [("index", "Home", "/"), ("dashboard", "Dashboard", "/dashboard"), ("regional", "Regional", "/regional"),
       ("taxation", "Tax & subsidy", "/taxation"), ("affordability", "Affordability", "/affordability"),
       ("trends", "Trends & forecast", "/trends")]
MORE = [("methodology", "Methodology", "/methodology"), ("data_quality", "Data quality", "/data-quality"),
        ("tableau", "Tableau", "/tableau"), ("docs", "Documentation", "/docs")]
CDN = {"plotly": "https://cdn.plot.ly/plotly-2.35.2.min.js",
       "bootstrap_css": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
       "bootstrap_js": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"}
VENDOR_FILES = {"plotly": "plotly.min.js", "bootstrap_css": "bootstrap.min.css", "bootstrap_js": "bootstrap.bundle.min.js"}
PERSONAS = [
    {"key": "policy", "name": "Energy policy consultant",
     "need": "Compare tax policy, subsidies and affordability across countries and regions.",
     "links": [("Tax & subsidy analysis", "/taxation"), ("Affordability by income", "/affordability")]},
    {"key": "supply", "name": "Global supply-chain manager",
     "need": "Track regional price gaps, volatility and the outlook for fuel procurement.",
     "links": [("Regional comparison", "/regional?fuel=Diesel"), ("Volatility & forecast", "/trends?fuel=Diesel")]},
    {"key": "research", "name": "Energy-economics researcher",
     "need": "Explore how income, prices, taxes and subsidies relate across countries.",
     "links": [("Income vs affordability", "/affordability"), ("Correlation matrix", "/affordability#correlation")]},
]
DOC_DIRS = {"docs": config.ROOT / "docs", "tableau": config.ROOT / "tableau", "root": config.ROOT}
DOC_ROOT_FILES = {"README"}
_NAME = re.compile(r"^[A-Za-z0-9_\-]{1,60}$")


# ---------------------------------------------------------------- helpers
def db_ready() -> bool:
    url = config.DATABASE_URL
    if url.startswith("sqlite:///") and not Path(url.replace("sqlite:///", "", 1)).exists():
        return False
    try:
        return len(A.options()["countries"]) > 0
    except Exception:  # missing tables, corrupt file, unreachable server
        return False


def valid_embed_url(url: str) -> str | None:
    """Return a safe https Tableau URL, or None when unset/invalid (never embed an unvalidated URL)."""
    if not url:
        return None
    p = urlparse(url)
    host = (p.hostname or "").lower()
    allowed = any(host == h or host.endswith("." + h) for h in config.TABLEAU_ALLOWED_HOSTS)
    if p.scheme != "https" or not allowed:
        return None
    return url if "?" in url else url + "?:showVizHome=no&:embed=true"


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def doc_index() -> list[dict]:
    items = []
    for folder, d in DOC_DIRS.items():
        for p in sorted(d.glob("*.md")) if d.exists() else []:
            if folder == "root" and p.stem not in DOC_ROOT_FILES:
                continue
            first = p.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
            title = first[0].lstrip("# ").strip() if first and first[0].startswith("#") else p.stem
            items.append({"folder": folder, "name": p.stem, "title": title[:90], "path": f"{folder}/{p.name}"})
    return items


def api_error(status: int, message: str):
    resp = jsonify({"error": message, "status": status})
    resp.status_code = status
    return resp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.config["TEMPLATES_AUTO_RELOAD"] = config.FLASK_DEBUG
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # ------------------------------------------------------------ request plumbing
    @app.before_request
    def _start():
        g.t0 = time.perf_counter()
        ep = request.endpoint or ""
        if ep in ("static", "healthz"):
            return None
        if not db_ready():
            if request.path.startswith("/api/"):
                return api_error(503, "Database not initialised. Run: python scripts/run_pipeline.py")
            return render_template("error.html", code=503, title="Database not initialised",
                                   message="Run the data pipeline first: python scripts/run_pipeline.py"), 503
        return None

    @app.after_request
    def _headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if hasattr(g, "t0"):
            resp.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - g.t0) * 1000:.1f}"
        return resp

    @app.errorhandler(A.FilterError)
    def _bad_filter(e):
        if request.path.startswith("/api/"):
            return api_error(400, str(e))
        return render_template("error.html", code=400, title="Invalid filter", message=str(e)), 400

    @app.errorhandler(404)
    def _404(_e):
        if request.path.startswith("/api/"):
            return api_error(404, "Not found")
        return render_template("error.html", code=404, title="Page not found",
                               message="That page or file does not exist."), 404

    @app.errorhandler(Exception)
    def _500(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            if request.path.startswith("/api/"):
                return api_error(e.code or 500, e.description or "Error")
            return render_template("error.html", code=e.code, title=e.name, message=e.description), e.code
        log.exception("Unhandled error on %s", request.path)  # details stay in the server log
        if request.path.startswith("/api/"):
            return api_error(500, "Internal error while computing this view. See the server log.")
        return render_template("error.html", code=500, title="Something went wrong",
                               message="The server could not complete this request. See the server log."), 500

    @app.context_processor
    def _ctx():
        vendor = Path(app.static_folder) / "vendor"
        assets = {k: (f"/static/vendor/{VENDOR_FILES[k]}" if (vendor / VENDOR_FILES[k]).exists() else CDN[k])
                  for k in CDN}
        topo = "/static/vendor/topojson/" if (vendor / "topojson" / "world_110m.json").exists() else ""
        try:
            synthetic = charts.is_synthetic()
        except Exception:
            synthetic = False
        return {"nav": NAV, "more_nav": MORE, "assets": assets, "topojson_url": topo, "synthetic": synthetic,
                "chart_reg": charts.REGISTRY, "page": (request.endpoint or "")}

    # ------------------------------------------------------------ pages
    def filter_page(template: str, **extra):
        return render_template(template, show_filters=True, opts=A.options(), **extra)

    @app.get("/")
    def index():
        s = database.summary()
        return render_template("index.html", summary=s, personas=PERSONAS, n_charts=len(charts.REGISTRY))

    @app.get("/dashboard")
    def dashboard():
        return filter_page("dashboard.html")

    @app.get("/regional")
    def regional():
        return filter_page("regional.html")

    @app.get("/taxation")
    def taxation():
        return filter_page("taxation.html")

    @app.get("/affordability")
    def affordability():
        return filter_page("affordability.html")

    @app.get("/trends")
    def trends():
        return filter_page("trends.html")

    @app.get("/methodology")
    def methodology():
        return render_template("methodology.html", prov=_read_json(config.PROVENANCE_FILE), cfg=config)

    @app.get("/data-quality")
    def data_quality():
        rep = _read_json(config.QUALITY_JSON)
        return render_template("data_quality.html", rep=rep, summary=database.summary(),
                               validation=database.validate(), target=config.TARGET_RECORDS)

    @app.get("/tableau")
    def tableau():
        files = sorted(p.name for p in config.EXPORT_DIR.glob("*.csv")) if config.EXPORT_DIR.exists() else []
        sizes = {n: round((config.EXPORT_DIR / n).stat().st_size / 1024) for n in files}
        embed = valid_embed_url(config.TABLEAU_EMBED_URL)
        return render_template("tableau.html", embed_url=embed, configured=bool(config.TABLEAU_EMBED_URL),
                               invalid=bool(config.TABLEAU_EMBED_URL) and embed is None, files=files, sizes=sizes,
                               allowed=config.TABLEAU_ALLOWED_HOSTS)

    @app.get("/docs")
    def docs():
        return render_template("docs.html", docs=doc_index(), charts=charts.REGISTRY.values())

    @app.get("/docs/<folder>/<name>")
    def doc_view(folder, name):
        d = DOC_DIRS.get(folder)
        if d is None or not _NAME.match(name) or (folder == "root" and name not in DOC_ROOT_FILES):
            abort(404)
        path = d / f"{name}.md"
        if not path.is_file():
            abort(404)
        return render_template("doc_view.html", html=mdlite.render(path.read_text(encoding="utf-8")), name=name,
                               folder=folder)

    @app.get("/download/<name>")
    def download(name):
        allowed = {p.name for p in config.EXPORT_DIR.glob("*.csv")} if config.EXPORT_DIR.exists() else set()
        if name not in allowed:
            abort(404)
        return send_from_directory(config.EXPORT_DIR, name, as_attachment=True)

    # ------------------------------------------------------------ JSON API
    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", "database": db_ready()})

    @app.get("/api/options")
    def api_options():
        return jsonify(A.options())

    @app.get("/api/charts")
    def api_charts():
        return jsonify([{"name": s.name, "title": s.title, "page": s.page} for s in charts.REGISTRY.values()])

    @app.get("/api/kpis")
    def api_kpis():
        f = A.parse_filters(request.args)
        return jsonify(charts.jsonable({**A.kpis(f), "synthetic": charts.is_synthetic(),
                                        "selection": charts.describe(f)}))

    @app.get("/api/chart/<name>")
    def api_chart(name):
        if name not in charts.REGISTRY:
            return api_error(404, f"Unknown chart '{name}'")
        f = A.parse_filters(request.args)
        return jsonify(charts.build(name, f, charts.parse_opts(request.args)))

    @app.get("/api/data/<name>")
    def api_data(name):
        if name not in charts.TABLES:
            return api_error(404, f"Unknown dataset '{name}'")
        return jsonify(charts.table(name, A.parse_filters(request.args), request.args))

    @app.get("/api/quality")
    def api_quality():
        rep = _read_json(config.QUALITY_JSON)
        if rep is None:
            return api_error(404, "No data quality report yet. Run: python scripts/run_pipeline.py")
        return jsonify(rep)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG)
