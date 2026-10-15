"""Single source of truth for user journey stages.

Every funnel/lifecycle table (lifecycle, activation funnel, engagement funnel, dashboard) is built
from the same stage definitions here, so a stage with the same name always has the same count.

Two counts are reported for every stage, never mixed:
  * users (cumulative) – users who met this stage AND every earlier stage in that funnel
  * users_standalone   – users who meet this stage's rule regardless of earlier stages
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.utils.metrics import pct


def canonical_stages(u: pd.DataFrame, th: dict) -> dict[str, tuple[str, np.ndarray, str, str]]:
    """name -> (definition, boolean mask, data source, limitation)."""
    n = len(u)
    return {
        "Registered": ("User record in 01_Users_1000", np.ones(n, bool), "01_Users_1000",
                       "Registration time only; no pre-registration exposure."),
        "Logged in": ("≥1 session (login proxied by session existence)", u.has_session.to_numpy(bool), "02_Sessions",
                      "No login event exists in the simulated taxonomy."),
        "Used a feature": ("≥1 feature event of any kind", u.is_active.to_numpy(bool), "03_Feature_Events",
                           "Includes passive views."),
        "Started an activity": ("≥1 start event (ad/captcha/spin/mission/tap/mining) or a task start",
                                u.started.to_numpy(bool), "03 + 05",
                                "Daily Reward, Streak, Follow & Referral have no start event."),
        "Completed a meaningful activity": ("≥1 meaningful completion (completion event or completed task)",
                                            u.completed_any.to_numpy(bool), "03 + 05",
                                            "Completion cannot be linked to a specific start (DQ-035)."),
        "Returned (2nd active day)": ("Active on at least 2 distinct calendar days", u.returned.to_numpy(bool),
                                      "03_Feature_Events", "Right-censored: recent users have had less time to return."),
        "Established (≥3 meaningful days)": ("Meaningful activity on at least 3 distinct days",
                                             u.established.to_numpy(bool), "03 + 05", "Analyst threshold."),
        "Multi-feature": (f"Meaningful completions in ≥{th['multi_feature_min_completed_features']} distinct features "
                          "(P75 of active users)", u.is_multi_feature.to_numpy(bool), "03_Feature_Events",
                          "Breadth rises with activity volume; not a strictly sequential step."),
        "Regular (≥3 active weeks)": (f"Active in ≥{th['regular_engagement_min_weeks']} distinct weeks after the first "
                                      "active day", u.is_regular.to_numpy(bool), "03_Feature_Events",
                                      "Users first active < 3 weeks before data end cannot qualify."),
    }


def stage_table(u: pd.DataFrame, th: dict, names: list[str], labels: dict[str, str] | None = None) -> pd.DataFrame:
    """Build a funnel from canonical stage names (optionally relabelled for the brief's wording)."""
    st = canonical_stages(u, th)
    n = len(u)
    rows, cum = [], np.ones(n, bool)
    for name in names:
        definition, mask, src, lim = st[name]
        cum = cum & mask
        rows.append({"stage": (labels or {}).get(name, name), "canonical_stage": name, "definition": definition,
                     "users": int(cum.sum()), "denominator": n, "pct_of_registered": pct(cum.sum(), n),
                     "users_standalone": int(mask.sum()), "standalone_pct_of_registered": pct(mask.sum(), n),
                     "data_source": src, "limitation": lim})
    df = pd.DataFrame(rows)
    df["pct_of_previous"] = (df.users / df.users.shift(1) * 100).round(1)
    df.loc[0, "pct_of_previous"] = 100.0
    df["users_cumulative"] = df.users  # alias kept for readability in tables
    return df
