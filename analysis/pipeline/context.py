"""Shared pipeline state passed between steps."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Context:
    raw: dict[str, pd.DataFrame]
    # cleaned analytical layer (populated by s02_cleaning)
    users: pd.DataFrame | None = None
    sessions: pd.DataFrame | None = None
    events: pd.DataFrame | None = None
    tasks: pd.DataFrame | None = None
    user_day: pd.DataFrame | None = None
    # user-level feature matrix etc.
    extra: dict[str, pd.DataFrame] = field(default_factory=dict)
    # JSON-serialisable results keyed by analysis area
    R: dict = field(default_factory=dict)
    # observation window
    data_start: pd.Timestamp | None = None
    data_end: pd.Timestamp | None = None
