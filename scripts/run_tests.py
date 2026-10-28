"""Run the automated test suite with pytest and print a one-line summary.  Usage: python scripts/run_tests.py [pytest args]"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    try:
        import pytest  # noqa: F401
    except ImportError:
        sys.exit("pytest is not installed. Run: pip install -r requirements.txt")
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", "-q", *sys.argv[1:]], cwd=ROOT))
