"""Advanced analyses not covered elsewhere + the advanced-analysis register.

  * Correlation analysis (Spearman) of user-level behaviour metrics
  * Calendar-confounding check: is the activation-speed → return association explained by WHEN users joined?
  * Multivariable association model: logistic regression of fourth-week (D30) return on first-week
    behaviour with calendar, source and device controls; 5-fold cross-validated ROC-AUC.
All results are associations within simulated data – never causal estimates.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from analysis import config
from analysis.pipeline.context import Context
from analysis.utils.io import save_table
from analysis.utils.metrics import pct

CORR_COLS = {"n_active_days": "Active days", "n_sessions": "Sessions", "n_events": "Events",
             "n_features": "Feature diversity", "n_features_completed": "Features completed",
             "n_meaningful": "Meaningful events", "n_tasks_completed": "Tasks completed",
             "median_session_seconds": "Median session (s)", "hours_to_first_activity": "Hours to first activity",
             "n_level_up": "Level-ups", "n_streak_claimed": "Streak claims", "tenure_days": "Tenure (days)",
             "engagement_score": "Engagement score"}


def run(ctx: Context) -> None:
    u, ud, e, t = ctx.users, ctx.user_day, ctx.events, ctx.tasks
    act = u[u.is_active].copy()

    # ---------------------------------------------------------------- correlation
    corr = act[list(CORR_COLS)].rename(columns=CORR_COLS).corr(method="spearman").round(3)
    save_table(corr.reset_index(names="metric"), "correlation_matrix_spearman")
    pairs = corr.where(np.triu(np.ones(corr.shape, bool), 1)).stack().sort_values(key=abs, ascending=False)
    top_pairs = pairs.head(10).reset_index()
    top_pairs.columns = ["metric_a", "metric_b", "spearman_rho"]

    # ---------------------------------------------------------------- calendar confounding
    h = act[act.D30_eligible.astype(bool)].copy()
    h["fast"] = h.activation_speed.isin(["Within 24h", "Day 2–7"])
    raw_diff = h.loc[h.fast, "D30_return"].mean() - h.loc[~h.fast, "D30_return"].mean()
    diffs, wts, strata = [], [], []
    for m, g in h.groupby("reg_month"):
        if g.fast.sum() >= 5 and (~g.fast).sum() >= 5:
            d = g.loc[g.fast, "D30_return"].mean() - g.loc[~g.fast, "D30_return"].mean()
            diffs.append(d)
            wts.append(len(g))
            strata.append({"reg_month": m, "users": len(g), "fast_activators": int(g.fast.sum()),
                           "d30_fast_pct": round(g.loc[g.fast, "D30_return"].mean() * 100, 1),
                           "d30_slow_pct": round(g.loc[~g.fast, "D30_return"].mean() * 100, 1),
                           "difference_pp": round(d * 100, 1)})
    strat = pd.DataFrame(strata)
    adj_diff = float(np.average(diffs, weights=wts)) if diffs else float("nan")
    save_table(strat, "calendar_confounding_activation_speed")
    first_active_doy = act.first_active_date.dt.dayofyear
    rho_cal = stats.spearmanr(first_active_doy, act.hours_to_first_activity)
    calendar = {"raw_difference_pp": round(raw_diff * 100, 1), "month_adjusted_difference_pp": round(adj_diff * 100, 1),
                "strata": strat, "users": len(h),
                "first_active_date_vs_hours_to_first_activity_rho": round(float(rho_cal.statistic), 3),
                "reading": "Fast activation remains associated with higher fourth-week return within registration months"
                           if adj_diff > 0.03 else "Association largely disappears after controlling for registration month"}

    # ---------------------------------------------------------------- logistic model of D30 return
    m = act[act.D30_eligible.astype(bool)].copy()
    w1 = ud[ud.day_since_first_active.between(0, 6)]
    f7 = w1.groupby("user_id").agg(w1_active_days=("date", "nunique"), w1_sessions=("sessions", "sum"),
                                   w1_events=("events", "sum"), w1_meaningful=("meaningful", "sum"))
    m = m.join(f7, on="user_id")
    ee = e.merge(m[["user_id", "first_active_date"]], on="user_id")
    ee = ee[(ee.date - ee.first_active_date).dt.days.between(0, 6)]
    m["w1_features_completed"] = m.user_id.map(ee[ee.is_meaningful].groupby("user_id").feature_name.nunique()).fillna(0)
    m["w1_streak_or_daily"] = m.user_id.map(ee[ee.event_name.isin(["streak_claimed", "daily_reward_claimed"])]
                                            .groupby("user_id").size()).fillna(0)
    tk = t.merge(m[["user_id", "first_active_date"]], on="user_id")
    tk = tk[(tk.date - tk.first_active_date).dt.days.between(0, 6) & tk.is_resolved]
    # users with no resolved first-week task get the population first-week rate (neutral imputation)
    m["w1_task_completion_rate"] = m.user_id.map(tk.groupby("user_id").is_completed.mean()).fillna(tk.is_completed.mean())
    m["log_hours_to_first_activity"] = np.log1p(m.hours_to_first_activity)
    m["calendar_day_first_active"] = m.first_active_date.dt.dayofyear
    num = ["w1_active_days", "w1_sessions", "w1_events", "w1_meaningful", "w1_features_completed", "w1_streak_or_daily",
           "w1_task_completion_rate", "log_hours_to_first_activity", "calendar_day_first_active"]
    X = pd.concat([m[num].fillna(0),
                   pd.get_dummies(m.device, prefix="device", drop_first=True, dtype=float),
                   pd.get_dummies(m.acquisition_source, prefix="source", drop_first=True, dtype=float)], axis=1)
    y = m.D30_return.astype(int)
    pipe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
    cv = StratifiedKFold(5, shuffle=True, random_state=config.RANDOM_SEED)
    auc = cross_val_score(pipe, X, y, cv=cv, scoring="roc_auc")
    auc_cal = cross_val_score(pipe, X[["calendar_day_first_active"]], y, cv=cv, scoring="roc_auc")
    auc_beh = cross_val_score(pipe, X[[c for c in num if c != "calendar_day_first_active"]], y, cv=cv, scoring="roc_auc")
    pipe.fit(X, y)
    coefs = pd.DataFrame({"feature": X.columns, "standardised_coefficient": pipe[-1].coef_[0].round(3)})
    coefs["odds_ratio_per_sd"] = np.exp(coefs.standardised_coefficient).round(3)
    coefs = coefs.reindex(coefs.standardised_coefficient.abs().sort_values(ascending=False).index)
    save_table(coefs, "d30_return_logistic_coefficients")
    model = {"users": len(m), "base_rate_pct": pct(y.sum(), len(y)), "cv_auc_mean": round(float(auc.mean()), 3),
             "cv_auc_std": round(float(auc.std()), 3), "cv_auc_calendar_only": round(float(auc_cal.mean()), 3),
             "cv_auc_behaviour_only": round(float(auc_beh.mean()), 3), "coefficients": coefs,
             "note": "Standardised logistic-regression coefficients (L2, C=1). Associations only; features are "
                     "correlated, so individual coefficients should not be read as independent effects."}

    # ---------------------------------------------------------------- register of advanced analyses
    R = ctx.R
    reg = [
        ("Cohort analysis", "First-active monthly & weekly cohorts, fixed 30-day horizon comparisons, Kruskal/χ² tests",
         "Which cohorts return more?",
         f"Registration-month cohorts differ strongly (χ² p={R['retention']['cohort_tests'].set_index('dimension').loc['Registration month', 'chi2_p_d30_return']:.2g}); "
         "source and device cohorts do not.", "behavioural_cohorts_30d.csv"),
        ("Behavioural segmentation", "Quantile-derived, hierarchical mutually exclusive segments",
         "Which behavioural groups exist?", f"Six segments; High-Frequency = {R['segmentation']['counts']['High-Frequency Users']} users.",
         "engagement_segments.csv"),
        ("Sequence analysis", "Timestamp-ordered feature paths, first-order transition matrix, lift vs independence",
         "Do journeys follow structured paths?",
         f"Transition lifts {R['journey']['transition_lift_range'][0]:.2f}–{R['journey']['transition_lift_range'][1]:.2f}; "
         "stage transitions show no view→start→complete structure.", "journey_transition_probabilities.csv"),
        ("Feature affinity analysis", "Session co-occurrence support and lift for all 105 feature pairs",
         "Which features are used together?", f"Lift range {R['features']['lift_range'][0]:.2f}–{R['features']['lift_range'][1]:.2f} (weak affinities).",
         "feature_affinity_pairs.csv"),
        ("Activation analysis", "Window sensitivity (1–30 days) with censoring-aware denominators and capture curve",
         "What is a defensible activation definition?", f"{R['activation']['window_days']}-day window selected; rate {R['activation']['rate_pct']}%.",
         "activation_windows.csv"),
        ("Retention analysis", "Window-based (D1/D7/D14/D30) and exact-day return, two anchors, weekly return curve",
         "How often do users return?", f"D7 {R['retention']['overall']['D7_rate_pct']}%, D30 {R['retention']['overall']['D30_rate_pct']}% (first-active anchor).",
         "return_rates_overall.csv"),
        ("Anomaly detection", "Tukey far-out fences, logical impossibility checks, duplicate-sequence detection",
         "What unusual behaviour should be investigated?", f"{len(R['anomalies']['register'])} anomaly records across {len(R['anomalies']['summary'])} types.",
         "anomaly_register.csv"),
        ("Distribution analysis", "Quartile-based duration bands, frequency distributions, Spearman duration↔depth",
         "What do sessions look like?", f"Duration↔events ρ = {R['sessions']['metrics']['duration_events_spearman']} (longer ≠ deeper).",
         "session_duration_bands.csv"),
        ("Time-series analysis", "Daily series, robust-z spike/drop detection on residual vs rolling median, trend-adjusted weekday index",
         "When are users active? Are there spikes?", f"{len(R['time']['flags'])} flagged days; weekday/weekend p={R['time']['weekend']['mannwhitney_p_dau_index']:.2f}.",
         "daily_activity_timeseries.csv"),
        ("Correlation analysis", "Spearman matrix of 13 user-level metrics", "Which behaviours move together?",
         f"Strongest pair: {top_pairs.iloc[0].metric_a} ↔ {top_pairs.iloc[0].metric_b} (ρ={top_pairs.iloc[0].spearman_rho}).",
         "correlation_matrix_spearman.csv"),
        ("Confounding check (stratification)", "Activation speed vs D30 return within registration-month strata",
         "Is the activation-speed association explained by join date?",
         f"Raw difference {calendar['raw_difference_pp']}pp vs month-adjusted {calendar['month_adjusted_difference_pp']}pp.",
         "calendar_confounding_activation_speed.csv"),
        ("Multivariable association model", "Logistic regression, 5-fold CV ROC-AUC, calendar/source/device controls",
         "Which first-week behaviours are associated with fourth-week return?",
         f"CV AUC {model['cv_auc_mean']} (calendar only {model['cv_auc_calendar_only']}, behaviour only {model['cv_auc_behaviour_only']}).",
         "d30_return_logistic_coefficients.csv"),
        ("Funnel analysis", "Activation funnel, 8-stage engagement funnel, drop-off matrix", "Where do users stop?",
         f"Largest user-level drop-off: {R['dropoff']['largest_user_dropoff_stage']} ({R['dropoff']['largest_user_dropoff_pct']}%).",
         "dropoff_matrix.csv"),
        ("Device & acquisition segmentation", "Group comparisons with Kruskal-Wallis / χ² and effect sizes",
         "Do devices / sources behave differently?", "No metric shows a non-trivial effect size.",
         "device_significance_tests.csv / acquisition_significance_tests.csv"),
        ("Engagement score validation", "Sensitivity (9 scenarios), PCA weights, early-score predictive check",
         "Is the score robust and meaningful?",
         f"Min Spearman vs base {R['engagement_score']['sensitivity'].spearman_vs_base.min():.3f}; early-score↔later activity ρ={R['engagement_score']['predictive_check']['spearman']}.",
         "engagement_score_sensitivity.csv"),
    ]
    reg = pd.DataFrame(reg, columns=["analysis", "method", "question", "key_result", "output_file"])
    save_table(reg, "advanced_analysis_register")
    ctx.R["advanced"] = {"correlation": corr.reset_index(names="metric"), "top_correlations": top_pairs,
                         "calendar_confounding": calendar, "d30_model": model, "register": reg}
