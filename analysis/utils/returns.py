"""Return (retention) flags anchored on each user's FIRST ACTIVE DATE (first feature-event day).

Definitions (calendar days, day 0 = first active date):
  D1  – active on day 1
  D7  – active on any day 1..7
  D14 – active on any day 8..14   (second-week return)
  D30 – active on any day 24..30  (fourth-week return; same 7-day width as D7/D14)
A user is *eligible* for a window only if the whole window lies inside the observation period
(first_active_date + last_offset <= data end date); otherwise the flag is NaN (right-censored).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from analysis import config


def compute_return_flags(users: pd.DataFrame, user_day: pd.DataFrame, data_end: pd.Timestamp,
                         anchor_col: str = "first_active_date") -> pd.DataFrame:
    end_day = data_end.normalize()
    anchor = users.set_index("user_id")[anchor_col]
    ud = user_day[["user_id", "date"]].copy()
    ud["offset"] = (ud.date - ud.user_id.map(anchor)).dt.days
    out = pd.DataFrame(index=anchor.index)
    for label, (lo, hi) in config.RETURN_WINDOWS.items():
        eligible = anchor.notna() & (anchor + pd.Timedelta(days=hi) <= end_day)
        hit = ud[(ud.offset >= lo) & (ud.offset <= hi)].user_id.unique()
        flag = pd.Series(anchor.index.isin(hit), index=anchor.index).astype(float)
        out[f"{label}_eligible"] = eligible
        out[f"{label}_return"] = flag.where(eligible, np.nan)
    return out
