"""Optional: download Plotly.js, Bootstrap and the world map topology into static/vendor/ so the dashboard works offline.

Usage:  python scripts/vendor_assets.py
The Flask app automatically prefers files in static/vendor/ over the CDN. Needs internet access once.
"""
import sys
import urllib.request
from pathlib import Path

VENDOR = Path(__file__).resolve().parents[1] / "static" / "vendor"
FILES = {
    "plotly.min.js": "https://cdn.plot.ly/plotly-2.35.2.min.js",
    "bootstrap.min.css": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
    "bootstrap.bundle.min.js": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
    "topojson/world_110m.json": "https://cdn.plot.ly/world_110m.json",
}


def main() -> int:
    failed = 0
    for rel, url in FILES.items():
        dest = VENDOR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                data = r.read()
            if not data:
                raise OSError("empty response")
            dest.write_bytes(data)
            print(f"ok   {rel} ({len(data) / 1024:.0f} KB)")
        except Exception as e:  # network errors, proxies, 404
            failed += 1
            print(f"FAIL {rel}: {e}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
