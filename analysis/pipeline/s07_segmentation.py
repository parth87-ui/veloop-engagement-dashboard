"""Work Package G — Behavioural engagement segmentation (mutually exclusive, rule-based).

Assignment is hierarchical (first matching rule wins), so every user has exactly one segment:
  0. No Recorded Activity  – 0 active days
  1. One-Time Users        – exactly 1 active day
  2. High-Frequency Users  – active days ≥ P75 of active users
  3. Multi-Feature Users   – 2..(P75−1) active days AND meaningful completions in ≥ P75 distinct features
  4. Returning Users       – median..(P75−1) active days
  5. Occasional Users      – 2..(median−1) active days
Thresholds are quantiles of the observed active-user distribution (computed, not assumed).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from analysis.pipeline.context import Context
from analysis.utils.io import save_table
from analysis.utils.metrics import pct

SEGMENT_ORDER = ["No Recorded Activity", "One-Time Users", "Occasional Users", "Returning Users",
                 "Multi-Feature Users", "High-Frequency Users"]


def assign_segments(active_days: pd.Series, features_completed: pd.Series, med: int, p75: int, breadth: int) -> pd.Series:
    conds = [active_days == 0, active_days == 1, active_days >= p75,
             (active_days >= 2) & (features_completed >= breadth), active_days >= med]
    labels = ["No Recorded Activity", "One-Time Users", "High-Frequency Users", "Multi-Feature Users", "Returning Users"]
    return pd.Series(np.select(conds, labels, "Occasional Users"), index=active_days.index)


def run(ctx: Context) -> None:
    u = ctx.users
    a = u[u.is_active]
    med = int(a.n_active_days.median())
    p75 = int(a.n_active_days.quantile(0.75))
    breadth = int(ctx.R["thresholds"]["multi_feature_min_completed_features"])
    ctx.R["thresholds"].update({"active_days_median": med, "active_days_p75": p75})
    u["segment"] = assign_segments(u.n_active_days, u.n_features_completed, med, p75, breadth)

    rules = {
        "No Recorded Activity": "0 active days (registered, no feature events)",
        "One-Time Users": "Exactly 1 active day",
        "Occasional Users": f"2–{med - 1} active days and breadth below {breadth} completed features",
        "Returning Users": f"{med}–{p75 - 1} active days and breadth below {breadth} completed features",
        "Multi-Feature Users": f"2–{p75 - 1} active days and meaningful completions in ≥{breadth} distinct features",
        "High-Frequency Users": f"≥{p75} active days (top quartile of active users)",
    }
    rationale = {
        "No Recorded Activity": "Separates registration-only accounts so they do not dilute behavioural averages.",
        "One-Time Users": "A single active day is the clearest 'did not return' signal (brief, segment A).",
        "Occasional Users": f"Below the median active-user frequency ({med} days).",
        "Returning Users": f"At or above the median but below the top quartile ({p75} days).",
        "Multi-Feature Users": f"Top-quartile breadth (P75 = {breadth} features) without top-quartile frequency – "
                               "broad explorers who are not yet frequent.",
        "High-Frequency Users": f"Top quartile of active days (P75 = {p75}).",
    }
    prof = u.groupby("segment").agg(
        users=("user_id", "size"), mean_active_days=("n_active_days", "mean"), median_active_days=("n_active_days", "median"),
        mean_sessions=("n_sessions", "mean"), mean_events=("n_events", "mean"), mean_features=("n_features", "mean"),
        mean_features_completed=("n_features_completed", "mean"), mean_meaningful=("n_meaningful", "mean"),
        mean_tasks_completed=("n_tasks_completed", "mean"), task_resolved=("n_tasks_resolved", "sum"),
        task_completed=("n_tasks_completed", "sum"), mean_active_weeks=("n_active_weeks", "mean"),
        median_session_s=("median_session_seconds", "median"),
        median_tenure_days=("tenure_days", "median")).reindex(SEGMENT_ORDER).reset_index()
    prof["pct_users"] = (prof.users / len(u) * 100).round(1)
    prof["task_completion_rate_pct"] = (prof.task_completed / prof.task_resolved * 100).round(1)
    prof["rule"] = prof.segment.map(rules)
    prof["rationale"] = prof.segment.map(rationale)
    prof = prof.drop(columns=["task_resolved", "task_completed"]).round(2)
    save_table(prof, "engagement_segments")

    # why breadth is not an independent tier: correlation with frequency
    rho, p = stats.spearmanr(a.n_active_days, a.n_features_completed)
    xt = pd.crosstab(np.select([u.n_active_days == 0, u.n_active_days == 1, u.n_active_days < med, u.n_active_days < p75],
                               ["0 days", "1 day", f"2–{med - 1} days", f"{med}–{p75 - 1} days"], f"≥{p75} days"),
                     np.where(u.n_features_completed >= breadth, f"≥{breadth} features", f"<{breadth} features"))
    save_table(xt.reset_index().rename(columns={"row_0": "active_days_band"}), "segment_frequency_breadth_matrix")

    seg_source = pd.crosstab(u.acquisition_source, u.segment, normalize="index").reindex(columns=SEGMENT_ORDER) * 100
    seg_device = pd.crosstab(u.device, u.segment, normalize="index").reindex(columns=SEGMENT_ORDER) * 100
    ctx.R["segmentation"] = {
        "order": SEGMENT_ORDER, "rules": rules, "profile": prof,
        "thresholds": {"active_days_median": med, "active_days_p75": p75, "breadth_p75": breadth},
        "frequency_breadth_spearman": round(float(rho), 3), "frequency_breadth_p": float(p),
        "frequency_breadth_matrix": xt.reset_index().rename(columns={"row_0": "active_days_band"}),
        "by_source_pct": seg_source.round(1).reset_index(), "by_device_pct": seg_device.round(1).reset_index(),
        "counts": u.segment.value_counts().reindex(SEGMENT_ORDER).fillna(0).astype(int).to_dict(),
    }
