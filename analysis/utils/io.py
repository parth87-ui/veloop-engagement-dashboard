"""I/O helpers: loading the workbook, writing tables and JSON consistently."""
from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import config


def ensure_dirs() -> None:
    for p in (config.DATA_PROCESSED, config.DATA_ANALYTICAL, config.OUT_TABLES,
              config.OUT_CHARTS, config.OUT_REPORTS, config.OUT_DASH):
        p.mkdir(parents=True, exist_ok=True)


def load_workbook(path: Path = config.RAW_WORKBOOK) -> dict[str, pd.DataFrame]:
    if not path.exists():
        raise FileNotFoundError(
            f"Raw workbook not found at {path}. Place VELOOP_Simulated_User_Behavior_1000.xlsx "
            "in data/raw/ (it is git-ignored because it contains simulated personal fields).")
    sheets = pd.read_excel(path, sheet_name=None)
    return {key: sheets[name].copy() for key, name in config.SHEETS.items()}


def save_table(df: pd.DataFrame, name: str, folder: Path = config.OUT_TABLES, index: bool = False) -> Path:
    path = folder / f"{name}.csv"
    df.to_csv(path, index=index)
    return path


def _clean(obj):
    """Recursively convert numpy / pandas objects into JSON-safe python values."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_clean(v) for v in obj]
    if isinstance(obj, pd.DataFrame):
        return _clean(obj.to_dict(orient="records"))
    if isinstance(obj, pd.Series):
        return _clean(obj.to_dict())
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return None if math.isnan(v) or math.isinf(v) else round(v, 6)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()
    if obj is pd.NaT:
        return None
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return obj


def to_jsonable(obj):
    return _clean(obj)


def save_json(obj, name: str, folder: Path = config.OUT_DASH, compact: bool = True) -> Path:
    path = folder / f"{name}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(_clean(obj), fh, ensure_ascii=False,
                  separators=(",", ":") if compact else None, indent=None if compact else 2)
    return path
