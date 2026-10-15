"""Work Package H — Analyst-Created Simulated Engagement Score (NOT an official VELOOP metric).

Score (0–100) = 100 × Σ weight_k × component_k, every component scaled to [0, 1].
Count components are winsorised at P99, log1p-transformed and min-max scaled (counts are
right-skewed; log damps the influence of extreme users). Ratio components are naturally bounded.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from analysis.pipeline.context import Context
from analysis.utils.io import save_table
from analysis.utils.metrics import dist_summary, minmax_log, pct

N_COMPLETABLE_FEATURES = 11   # features with at least one 'complete' stage event
MIN_CONSISTENCY_WEEKS = 4      # consistency horizon floor to avoid rewarding very recent users

COMPONENTS = [
    # key, label, weight, transformation, reason
    ("c_frequency", "Activity Frequency (active days)", 0.25, "log1p + min-max (P99 cap)",
     "Return on separate days is the most direct signal of repeated engagement in the brief."),
    ("c_sessions", "Session Frequency (sessions)", 0.10, "log1p + min-max (P99 cap)",
     "Adds visit intensity, but is ~0.95 rank-correlated with active days, so weighted low to avoid double counting."),
    ("c_consistency", "Active-Day Consistency (active weeks / observable weeks, floor 4)", 0.15, "ratio, capped at 1",
     "Rewards spread-out activity over bursts; partially corrects for tenure differences."),
    ("c_diversity", "Feature Diversity (distinct features with a completion / 11)", 0.15, "ratio",
     "Breadth of value actions; capped by the 11 completable simulated features."),
    ("c_completion", "Meaningful Completion (meaningful events + completed tasks)", 0.25, "log1p + min-max (P99 cap)",
     "Completed value actions are what the product rewards; views alone are excluded."),
    ("c_progression", "Milestone Progression (level_up + badge_earned events)", 0.10, "log1p + min-max (P99 cap)",
     "Progression is a consequence of activity, so weighted low to limit redundancy."),
]


def compute_components(u: pd.DataFrame) -> pd.DataFrame:
    c = pd.DataFrame(index=u.index)
    c["c_frequency"] = minmax_log(u.n_active_days)
    c["c_sessions"] = minmax_log(u.n_sessions)
    horizon = np.maximum(u.observable_weeks.fillna(0), MIN_CONSISTENCY_WEEKS)
    c["c_consistency"] = (u.n_active_weeks / horizon).clip(upper=1).fillna(0)
    c["c_diversity"] = (u.n_features_completed / N_COMPLETABLE_FEATURES).clip(upper=1)
    c["c_completion"] = minmax_log(u.n_meaningful + u.n_tasks_completed)
    c["c_progression"] = minmax_log(u.n_level_up + u.n_badge_earned)
    return c


def score(c: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    tot = sum(weights.values())
    return 100 * sum(c[k] * w for k, w in weights.items()) / tot


def run(ctx: Context) -> None:
    u = ctx.users
    comp = compute_components(u)
    base_w = {k: w for k, _, w, _, _ in COMPONENTS}
    u["engagement_score"] = score(comp, base_w).round(2)
    for k in base_w:
        u[k] = comp[k].round(4)

    act = u.is_active
    base = u.loc[act, "engagement_score"]
    top_n = max(1, int(round(act.sum() * 0.1)))
    base_top = set(base.nlargest(top_n).index)
    base_bot = set(base.nsmallest(top_n).index)

    def compare(name, s_alt, desc):
        s_alt = s_alt[act]
        rho = stats.spearmanr(base, s_alt).statistic
        return {"scenario": name, "description": desc, "spearman_vs_base": round(float(rho), 4),
                "top_decile_overlap_pct": pct(len(base_top & set(s_alt.nlargest(top_n).index)), top_n),
                "bottom_decile_overlap_pct": pct(len(base_bot & set(s_alt.nsmallest(top_n).index)), top_n)}

    sens = [compare("Equal weights", score(comp, {k: 1 for k in base_w}), "All six components weighted 1/6")]
    for k, label, *_ in COMPONENTS:
        sens.append(compare(f"Drop {label.split(' (')[0]}", score(comp, {kk: w for kk, w in base_w.items() if kk != k}),
                            "Component removed, remaining weights renormalised"))
    # PCA-derived weights (first principal component of standardised components, active users)
    X = comp[act].values
    Xs = (X - X.mean(0)) / X.std(0)
    eigval, eigvec = np.linalg.eigh(np.cov(Xs.T))
    pc1 = np.abs(eigvec[:, -1])
    pca_w = dict(zip(base_w, pc1 / pc1.sum()))
    sens.append(compare("PCA (PC1 loadings) weights", score(comp, pca_w),
                        "Weights = |PC1 loadings| – " + ", ".join(f"{k[2:]} {v:.2f}" for k, v in pca_w.items())))
    pr = comp.rank(pct=True)
    sens.append(compare("Percentile-rank transform", score(pr, base_w), "Components replaced by percentile ranks"))
    sens = pd.DataFrame(sens)
    save_table(sens, "engagement_score_sensitivity")

    # predictive check: score built on first 14 days vs activity on days 15–60 (users with ≥60 observable days)
    ud, e = ctx.user_day, ctx.events
    mature = u[act & (u.observable_days_since_first_active >= 60)].set_index("user_id")
    early_ud = ud[ud.day_since_first_active.between(0, 13)]
    late_ud = ud[ud.day_since_first_active.between(14, 59)]
    early = pd.DataFrame(index=mature.index)
    early["n_active_days"] = early_ud.groupby("user_id").date.nunique()
    early["n_sessions"] = early_ud.groupby("user_id").sessions.sum()
    early["n_meaningful"] = early_ud.groupby("user_id").meaningful.sum()
    early = early.fillna(0)
    ee = e[e.user_id.isin(mature.index)].copy()
    ee["dsf"] = (ee.date - ee.user_id.map(mature.first_active_date)).dt.days
    ee = ee[ee.dsf.between(0, 13)]
    early["n_features_completed"] = ee[ee.is_meaningful].groupby("user_id").feature_name.nunique()
    early["n_progress"] = ee[ee.event_name.isin(["level_up", "badge_earned"])].groupby("user_id").size()
    early["n_active_weeks"] = ee.assign(w=ee.dsf // 7).groupby("user_id").w.nunique()
    early = early.fillna(0)
    ec = pd.DataFrame(index=early.index)
    ec["c_frequency"] = minmax_log(early.n_active_days)
    ec["c_sessions"] = minmax_log(early.n_sessions)
    ec["c_consistency"] = early.n_active_weeks / 2
    ec["c_diversity"] = early.n_features_completed / N_COMPLETABLE_FEATURES
    ec["c_completion"] = minmax_log(early.n_meaningful)
    ec["c_progression"] = minmax_log(early.n_progress)
    early_score = score(ec, base_w)
    later_days = late_ud.groupby("user_id").date.nunique().reindex(early.index).fillna(0)
    pv = stats.spearmanr(early_score, later_days)
    q = pd.qcut(early_score.rank(method="first"), 4, labels=["Q1 (lowest)", "Q2", "Q3", "Q4 (highest)"])
    pred_tbl = pd.DataFrame({"early_score_quartile": q, "later_active_days": later_days,
                             "returned_after_day_14": later_days > 0}).groupby("early_score_quartile", observed=True).agg(
        users=("later_active_days", "size"), mean_later_active_days=("later_active_days", "mean"),
        returned_after_day_14_pct=("returned_after_day_14", lambda x: round(x.mean() * 100, 1))).reset_index()
    save_table(pred_tbl, "engagement_score_predictive_check")

    corr = comp[act].corr(method="spearman").round(3)
    seg_score = u.groupby("segment").engagement_score.agg(["count", "mean", "median", "min", "max"]).round(2) \
        .reindex(ctx.R["segmentation"]["order"]).reset_index()
    extremes_cols = ["user_id", "segment", "engagement_score", "n_active_days", "n_sessions", "n_events",
                     "n_features_completed", "n_meaningful", "n_tasks_completed", "n_level_up", "tenure_days"]
    top = u[act].nlargest(10, "engagement_score")[extremes_cols]
    bottom = u[act].nsmallest(10, "engagement_score")[extremes_cols]
    save_table(pd.concat([top.assign(group="Top 10"), bottom.assign(group="Bottom 10")]), "engagement_score_extremes")
    bands = pd.cut(u.engagement_score, bins=[-0.01, 20, 40, 60, 80, 100], labels=["0–20", "20–40", "40–60", "60–80", "80–100"])
    band_tbl = bands.value_counts().sort_index().rename_axis("band").reset_index(name="users")
    hist = np.histogram(u.loc[act, "engagement_score"], bins=list(range(0, 105, 5)))[0].tolist()

    comp_tbl = pd.DataFrame([{"component": label, "key": k, "weight": w, "transformation": tr, "reason": r,
                              "mean_active": round(comp.loc[act, k].mean(), 3)} for k, label, w, tr, r in COMPONENTS])
    save_table(comp_tbl, "engagement_score_components")
    save_table(u[["user_id", "segment", "engagement_score"] + list(base_w)], "engagement_scores_by_user", )

    ctx.R["engagement_score"] = {
        "label": "Analyst-Created Simulated Engagement Score",
        "disclaimer": "Created for this internship analysis only. It is not an official VELOOP metric and is not used by VELOOP.",
        "components": comp_tbl, "sensitivity": sens, "component_correlation": corr.reset_index().rename(columns={"index": "component"}),
        "summary_active": dist_summary(base), "summary_all": dist_summary(u.engagement_score),
        "by_segment": seg_score, "bands_all_users": band_tbl, "hist_active_5pt": hist,
        "top10": top, "bottom10": bottom, "pca_weights": {k: round(v, 3) for k, v in pca_w.items()},
        "predictive_check": {"users": int(len(early)), "spearman": round(float(pv.statistic), 3), "p_value": float(pv.pvalue),
                             "quartiles": pred_tbl,
                             "method": "Score recomputed using only each user's first 14 days after first activity "
                                       "(users with ≥60 observable days); compared with active days on days 15–59."},
        "limitations": [
            "Weights are analyst judgement; sensitivity tests show how much rankings depend on them.",
            "Components are correlated (frequency, sessions and completions move together), so the score is close to "
            "a single 'activity volume' dimension.",
            "Tenure bias: users registered recently have had less time to accumulate activity; the consistency "
            "floor only partially corrects this.",
            "No reward value, XP balance or level is available, so 'progression' uses counts of progression events.",
            "The score describes simulated behaviour; it has no validated link to any business outcome.",
        ],
    }
