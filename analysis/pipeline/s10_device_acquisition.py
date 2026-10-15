"""Work Packages L & M — Device and acquisition-source behaviour.

Differences are reported as "observed behavioural differences" with a significance test and
effect size. Explanations are listed as hypotheses only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from analysis import config
from analysis.pipeline.context import Context
from analysis.utils.io import save_table
from analysis.utils.metrics import pct
from analysis.utils.returns import compute_return_flags


def _kw(groups) -> tuple[float, float]:
    groups = [g.dropna() for g in groups if len(g.dropna()) > 0]
    h, p = stats.kruskal(*groups)
    n, k = sum(len(g) for g in groups), len(groups)
    eps2 = (h - k + 1) / (n - k) if n > k else np.nan
    return float(p), float(max(eps2, 0))


def _chi(df: pd.DataFrame, col: str, flag: str) -> tuple[float, float]:
    d = df[[col, flag]].dropna()
    ct = pd.crosstab(d[col], d[flag])
    if ct.shape[1] < 2:
        return float("nan"), float("nan")
    chi2, p, *_ = stats.chi2_contingency(ct)
    v = np.sqrt(chi2 / (ct.values.sum() * (min(ct.shape) - 1)))
    return float(p), float(v)


def compare_groups(ctx: Context, col: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    u, s, e, t = ctx.users, ctx.sessions, ctx.events, ctx.tasks
    act = u[u.is_active]
    if col == "device":
        sg = s.copy()  # session device == primary device for every user (validated: 0 mismatches)
    else:
        sg = s.merge(u[["user_id", col]], on="user_id")
    eg = e.merge(u[["user_id", col]], on="user_id", suffixes=("_e", "")) if col != "device" else e
    tg = t.merge(u[["user_id", col]], on="user_id", suffixes=("_t", "")) if col != "device" else t

    tbl = u.groupby(col).agg(users=("user_id", "size"), active_users=("is_active", "sum"),
                             activation_eligible=("activation_eligible", "sum"), activated=("is_activated", "sum"),
                             d7_eligible=("D7_eligible", "sum"), d7_returned=("D7_return", "sum"),
                             d30_eligible=("D30_eligible", "sum"), d30_returned=("D30_return", "sum"),
                             mean_engagement_score=("engagement_score", "mean"))
    tbl["pct_of_users"] = tbl.users / len(u) * 100
    tbl["active_rate_pct"] = tbl.active_users / tbl.users * 100
    tbl["activation_rate_pct"] = tbl.activated / tbl.activation_eligible * 100
    tbl["d7_return_pct"] = tbl.d7_returned / tbl.d7_eligible * 100
    tbl["d30_return_pct"] = tbl.d30_returned / tbl.d30_eligible * 100
    ag = act.groupby(col)
    tbl["median_days_to_first_activity"] = ag.hours_to_first_activity.median() / 24
    tbl["sessions_per_active_user"] = ag.n_sessions.mean()
    tbl["mean_active_days"] = ag.n_active_days.mean()
    tbl["median_active_days"] = ag.n_active_days.median()
    tbl["repeat_user_rate_pct"] = ag.n_active_days.apply(lambda x: (x >= 2).mean() * 100)
    tbl["high_frequency_share_pct"] = ag.segment.apply(lambda x: (x == "High-Frequency Users").mean() * 100)
    tbl["one_time_share_pct"] = ag.segment.apply(lambda x: (x == "One-Time Users").mean() * 100)
    tbl["mean_feature_diversity"] = ag.n_features.mean()
    tbl["mean_features_completed"] = ag.n_features_completed.mean()
    tbl["events_per_active_user"] = ag.n_events.mean()
    sv = sg[sg.is_valid]
    tbl["median_session_duration_s"] = sg.groupby(col).session_duration_seconds.median()
    tbl["mean_session_duration_s"] = sg.groupby(col).session_duration_seconds.mean()
    tbl["events_per_valid_session"] = sv.groupby(col).raw_event_count.mean()
    tr = tg[tg.is_resolved]
    tbl["task_completion_rate_pct"] = tr.groupby(col).is_completed.mean() * 100
    tbl["task_abandonment_rate_pct"] = tr.groupby(col).task_status.apply(lambda x: (x == "Abandoned").mean() * 100)
    ads = eg[eg.event_name.isin(["ad_completed", "ad_skipped"])]
    tbl["ad_skip_rate_pct"] = ads.groupby(col).event_name.apply(lambda x: (x == "ad_skipped").mean() * 100)
    mis = eg[eg.event_name.isin(["mission_completed", "mission_abandoned"])]
    tbl["mission_abandon_rate_pct"] = mis.groupby(col).event_name.apply(lambda x: (x == "mission_abandoned").mean() * 100)
    tbl = tbl.round(2).sort_values("users", ascending=False).reset_index()

    groups = sorted(u[col].dropna().unique())
    tests = []
    for metric, series_fn in [
        ("active days (active users)", lambda g: act.loc[act[col] == g, "n_active_days"]),
        ("sessions (active users)", lambda g: act.loc[act[col] == g, "n_sessions"]),
        ("feature diversity (active users)", lambda g: act.loc[act[col] == g, "n_features"]),
        ("engagement score (active users)", lambda g: act.loc[act[col] == g, "engagement_score"]),
        ("session duration (sessions)", lambda g: sg.loc[sg[col] == g, "session_duration_seconds"]),
        ("events per valid session", lambda g: sv.loc[sv[col] == g, "raw_event_count"]),
        ("hours to first activity", lambda g: act.loc[act[col] == g, "hours_to_first_activity"]),
    ]:
        p, eff = _kw([series_fn(g) for g in groups])
        tests.append({"metric": metric, "test": "Kruskal-Wallis", "p_value": p, "effect_size": round(eff, 4),
                      "effect_measure": "epsilon²"})
    for metric, df, flag in [("activation", u, "is_activated_f"), ("D7 return", u, "D7_return"),
                             ("task completion (resolved tasks)", tr, "is_completed")]:
        d = df.copy()
        if flag == "is_activated_f":
            d = d[d.activation_eligible]
            d["is_activated_f"] = d.is_activated.astype(int)
        p, v = _chi(d, col, flag)
        tests.append({"metric": metric, "test": "Chi-square", "p_value": p, "effect_size": round(v, 4),
                      "effect_measure": "Cramér's V"})
    tests = pd.DataFrame(tests)
    # conventional 'small effect' floors: epsilon² ≥ 0.01, Cramér's V ≥ 0.10
    non_trivial = np.where(tests.effect_measure == "epsilon²", tests.effect_size >= 0.01, tests.effect_size >= 0.10)
    tests["interpretation"] = np.select(
        [(tests.p_value < 0.05) & non_trivial, tests.p_value < 0.05],
        ["Observed behavioural difference (statistically detectable, at least small effect)",
         "Statistically detectable but negligible effect size"],
        "No statistically detectable difference at α=0.05")
    tests["p_value"] = tests.p_value.map(lambda x: float(f"{x:.4g}"))

    uc = ctx.extra["uf_complete"].reindex(u.user_id).fillna(0)
    adopt = (uc > 0).groupby(u.set_index("user_id")[col]).mean().mul(100).round(1)
    return tbl, tests, adopt.reset_index()


def run(ctx: Context) -> None:
    u = ctx.users
    rf = compute_return_flags(u, ctx.user_day, ctx.data_end)
    for c in rf.columns:
        u[c] = u.user_id.map(rf[c])
    ctx.users = u

    out = {}
    for col, name in [("device", "device"), ("acquisition_source", "acquisition")]:
        tbl, tests, adopt = compare_groups(ctx, col)
        save_table(tbl, f"{name}_behaviour_comparison")
        save_table(tests, f"{name}_significance_tests")
        save_table(adopt, f"{name}_feature_completion_adoption_pct")
        out[name] = {"table": tbl, "tests": tests, "feature_adoption_pct": adopt}

    # device × source mix (to check whether device differences are confounded by source)
    mix = pd.crosstab(u.acquisition_source, u.device, normalize="index").round(4) * 100
    save_table(mix.reset_index(), "acquisition_device_mix_pct")
    out["device_source_mix"] = mix.reset_index()
    p_mix = stats.chi2_contingency(pd.crosstab(u.acquisition_source, u.device))[1]
    out["device_source_independence_p"] = float(p_mix)
    out["platform_note"] = ("platform = 'Web' for 100% of users, sessions and events; device (Android / iOS / Windows / "
                            "macOS) is the only usable platform dimension. Device is constant per user in this dataset.")
    out["referral_detail"] = ctx.raw["users"].referral_source_detail.value_counts().to_dict()
    ctx.R["segments_device_acq"] = out
