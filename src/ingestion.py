"""Load raw data (CSV, Excel or an external SQL database) without altering the source file."""
from pathlib import Path

import numpy as np
import pandas as pd

import config


def _finish(df: pd.DataFrame, column_map: dict | None) -> pd.DataFrame:
    df = df.rename(columns={**config.COLUMN_MAP, **(column_map or {})})
    df.columns = [str(c).strip() for c in df.columns]
    df.insert(0, "source_row", np.arange(2, len(df) + 2))  # line number in the source file (header = 1)
    return df


def load_raw(path=None, column_map: dict | None = None) -> pd.DataFrame:
    """Read a CSV/XLSX file as text so that validation, not the parser, decides what is invalid."""
    path = Path(path or config.RAW_FILE)
    if not path.exists():
        raise FileNotFoundError(f"Raw data file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    elif suffix in (".xlsx", ".xlsm", ".xls"):
        df = pd.read_excel(path, dtype=str)
    else:
        raise ValueError(f"Unsupported file type '{suffix}'. Use .csv or .xlsx.")
    return _finish(df, column_map)


def load_from_database(url: str, query: str, column_map: dict | None = None) -> pd.DataFrame:
    """Optional: pull raw records from an external database (any SQLAlchemy URL)."""
    from sqlalchemy import create_engine, text

    with create_engine(url).connect() as conn:
        df = pd.read_sql(text(query), conn).astype("string")
    return _finish(df, column_map)
