"""One-command setup: virtual environment + dependencies + data pipeline.

Usage:  python scripts/setup.py [--no-venv] [--regenerate] [--skip-pipeline]
Creates .venv, installs requirements.txt, runs scripts/run_pipeline.py inside it, and prints next steps.
"""
import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-venv", action="store_true", help="use the current Python instead of creating .venv")
    ap.add_argument("--regenerate", action="store_true", help="regenerate the synthetic raw data")
    ap.add_argument("--skip-pipeline", action="store_true")
    a = ap.parse_args()
    if sys.version_info < (3, 10):
        sys.exit("Python 3.10+ is required (3.11 recommended).")

    py = sys.executable
    if not a.no_venv:
        env = ROOT / ".venv"
        if not env.exists():
            print(f"Creating virtual environment at {env}")
            venv.create(env, with_pip=True)
        py = str(env / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    run([py, "-m", "pip", "install", "--upgrade", "pip"])
    run([py, "-m", "pip", "install", "-r", "requirements.txt"])
    if not a.skip_pipeline:
        run([py, "scripts/run_pipeline.py"] + (["--regenerate"] if a.regenerate else []))
    activate = r".venv\Scripts\Activate.ps1" if os.name == "nt" else "source .venv/bin/activate"
    print(f"\nSetup complete. Next:\n  {activate}\n  python scripts/run_tests.py\n  python app.py   # http://127.0.0.1:5000")


if __name__ == "__main__":
    main()
