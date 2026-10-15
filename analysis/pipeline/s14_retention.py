"""Work Packages R & S — Behavioural cohorts and return (retention) behaviour.

Primary cohort date  : FIRST ACTIVE DATE (first feature-event day) – measures return after first use.
Secondary cohort date: REGISTRATION DATE – shown separately and never mixed with the primary view.
Return windows / eligibility: see analysis/utils/returns.py.
Cohort comparisons use a fixed 30-day horizon (users with ≥30 observable days) so cohorts with
different tenure are compared fairly.
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

WEEKS = 12


def _rates(df: pd.DataFrame, prefix: str = "") -> dict:
    out = {}
    for lab in config.RETURN_WINDOWS:
        el = df[f"{prefix}{lab}_eligible"].astype(bool)
        out[f"{lab}_eligible"] = int(el.sum())
        out[f"{lab}_returned"] = int(df.loc[el, f"{prefix}{lab}_return"].sum())
        out[f"{lab}_rate_pct"] = pct(out[f"{lab}_returned"], el.sum())
    return out


def run(ctx: Context) -> None:
    u, ud = ctx.users, ctx.user_day
    end_day = ctx.data_end.normalize()
    act = u[u.is_active].copy()

    overall = _rates(act)
    reg_flags = compute_return_flags(u.assign(reg_anchor=u.reg_date), ud, ctx.data_end, anchor_col="reg_anchor")
    reg_flags.columns = ["reg_" + c for c in reg_flags.columns]
    ureg = u.set_index("user_id").join(reg_flags)
    overall_reg = _rates(ureg, "reg_")
    # exact-day ("classic") retention for comparison
    off = ud.assign(off=ud.day_since_first_active)
    classic = {}
    for n in (1, 7, 14, 30):
        el = act[act.first_active_date + pd.Timedelta(days=n) <= end_day]
        hit = off[(off.off == n) & off.user_id.isin(el.user_id)].user_id.nunique()
        classic[f"day_{n}"] = {"eligible": len(el), "returned": int(hit), "rate_pct": pct(hit, len(el))}

    # PRIMARY retention table: one anchor (first active date), one active definition, eligible-only denominators
    ret_rows, reg_rows = [], []
    for lab, (lo, hi) in config.RETURN_WINDOWS.items():
        days = f"{lo}–{hi}" if lo != hi else f"{lo}"
        ret_rows.append({"window": lab, "days_after_first_active_day": days,
                         "eligible_users": overall[f"{lab}_eligible"], "returned_users": overall[f"{lab}_returned"],
                         "return_rate_pct": overall[f"{lab}_rate_pct"]})
        reg_rows.append({"window": lab, "days_after_registration": days,
                         "eligible_users": overall_reg[f"{lab}_eligible"], "returned_users": overall_reg[f"{lab}_returned"],
                         "return_rate_pct": overall_reg[f"{lab}_rate_pct"]})
    ret_tbl = pd.DataFrame(ret_rows)
    save_table(ret_tbl, "return_rates_overall")
    # comparison only (appendix): same windows anchored on registration date – never mixed with the primary table
    reg_tbl = pd.DataFrame(reg_rows)
    save_table(reg_tbl, "return_rates_registration_anchor_comparison")

    # monthly cohorts (first-active month)
    act["cohort_month"] = act.first_active_date.dt.to_period("M").astype(str)
    mc = []
    for m, g in act.groupby("cohort_month"):
        mc.append({"cohort_month": m, "users": len(g), **_rates(g),
                   "mean_active_days": round(g.n_active_days.mean(), 2)})
    mc = pd.DataFrame(mc)
    save_table(mc, "cohort_monthly_returns")

    # weekly cohort × week-offset matrix
    act["cohort_week"] = act.first_active_date.dt.to_period("W-SUN").dt.start_time
    wk = ud.merge(act[["user_id", "cohort_week"]], on="user_id")
    wk["week_offset"] = wk.day_since_first_active // 7
    sizes = act.groupby("cohort_week").size()
    mat = wk[wk.week_offset <= WEEKS].groupby(["cohort_week", "week_offset"]).user_id.nunique().unstack(fill_value=0)
    pct_mat = mat.div(sizes, axis=0) * 100
    for c in pct_mat.columns:  # blank out unobservable cells
        unobs = (pct_mat.index + pd.Timedelta(days=7 * int(c) + 6)) > end_day
        pct_mat.loc[unobs, c] = np.nan
    pct_mat.insert(0, "cohort_size", sizes)
    pct_mat = pct_mat.round(1).reset_index()
    pct_mat["cohort_week"] = pct_mat.cohort_week.dt.strftime("%Y-%m-%d")
    save_table(pct_mat, "cohort_weekly_matrix")
    weighted_curve = []
    for c in range(0, WEEKS + 1):
        col = mat[c] if c in mat.columns else pd.Series(0, index=sizes.index)
        obs = ~((sizes.index + pd.Timedelta(days=7 * c + 6)) > end_day)
        weighted_curve.append({"week": c, "eligible_users": int(sizes[obs].sum()),
                               "active_pct": pct(col[obs].sum(), sizes[obs].sum())})
    weighted_curve = pd.DataFrame(weighted_curve)
    save_table(weighted_curve, "return_curve_weekly")
    day_curve = []
    for n in range(0, 61):
        el = act[act.first_active_date + pd.Timedelta(days=n) <= end_day]
        hit = off[(off.off == n) & off.user_id.isin(el.user_id)].user_id.nunique()
        day_curve.append({"day": n, "eligible": len(el), "active_pct": pct(hit, len(el), 2)})
    day_curve = pd.DataFrame(day_curve)

    # behavioural cohorts on a fixed 30-day horizon
    h30 = act[act.observable_days_since_first_active >= 30].copy()
    w30 = ud[ud.day_since_first_active.between(0, 29)]
    agg30 = w30.groupby("user_id").agg(active_days_30=("date", "nunique"), sessions_30=("sessions", "sum"),
                                       events_30=("events", "sum"), meaningful_30=("meaningful", "sum"))
    h30 = h30.join(agg30, on="user_id")
    ee = ctx.events.merge(h30[["user_id", "first_active_date"]], on="user_id")
    ee = ee[(ee.date - ee.first_active_date).dt.days.between(0, 29)]
    h30["features_30"] = h30.user_id.map(ee.groupby("user_id").feature_name.nunique()).fillna(0)
    tk = ctx.tasks.merge(h30[["user_id", "first_active_date"]], on="user_id")
    tk = tk[(tk.date - tk.first_active_date).dt.days.between(0, 29) & tk.is_resolved]
    tk = tk[["user_id", "is_completed"]]
    h30["fmf"] = h30.first_meaningful_feature.fillna("None (task only)")
    h30["activation_timing"] = pd.Categorical(h30.activation_speed, ["Within 24h", "Day 2–7", "After day 7", "Never"])
    dims = {"Registration month": "reg_month", "Acquisition source": "acquisition_source", "Device": "device",
            "First meaningful feature": "fmf", "Activation timing": "activation_timing"}
    cohort_rows = []
    tests = []
    for dim, col in dims.items():
        tc = tk.merge(h30[["user_id", col]], on="user_id").groupby(col, observed=True).is_completed.mean() * 100
        for val, g in h30.groupby(col, observed=True):
            cohort_rows.append({"dimension": dim, "cohort": str(val), "users": len(g),
                                "active_days_30d_mean": round(g.active_days_30.mean(), 2),
                                "sessions_30d_mean": round(g.sessions_30.mean(), 2),
                                "feature_diversity_30d_mean": round(g.features_30.mean(), 2),
                                "repeat_activity_pct": pct((g.active_days_30 >= 2).sum(), len(g)),
                                "task_completion_rate_pct": round(float(tc.get(val, np.nan)), 1),
                                "D7_return_pct": pct(g.D7_return.sum(), g.D7_eligible.sum()),
                                "D30_return_pct": pct(g.D30_return.sum(), g.D30_eligible.sum())})
        kw = stats.kruskal(*[g.active_days_30.values for _, g in h30.groupby(col, observed=True) if len(g) >= 5])
        ct = pd.crosstab(h30[col], h30.D30_return)
        chi_p = stats.chi2_contingency(ct)[1] if ct.shape[1] == 2 else np.nan
        tests.append({"dimension": dim, "kruskal_p_active_days_30d": float(f"{kw.pvalue:.4g}"),
                      "chi2_p_d30_return": float(f"{chi_p:.4g}")})
    cohorts = pd.DataFrame(cohort_rows)
    cohort_tests = pd.DataFrame(tests)
    save_table(cohorts, "behavioural_cohorts_30d")
    save_table(cohort_tests, "behavioural_cohort_tests")

    ctx.R["retention"] = {
        "definitions": {
            "cohort_date": "First active date = calendar date of the user's first feature event (03_Feature_Events).",
            "secondary_cohort_date": "Registration date (01_Users_1000.registration_datetime) – reported separately.",
            "active_definition": "≥1 feature event on that calendar day.",
            "windows": {k: f"days {lo}–{hi} after cohort day 0" for k, (lo, hi) in config.RETURN_WINDOWS.items()},
            "denominator": "Users whose entire window lies within the observation period (ends "
                           f"{end_day.date()}); later users are excluded, not counted as non-returners.",
            "d30_supported": f"Yes – {overall['D30_eligible']} users have a fully observable day 15–30 window.",
        },
        "overall": overall, "overall_registration_anchor": overall_reg, "classic_exact_day": classic,
        "table": ret_tbl, "registration_anchor_table": reg_tbl, "monthly": mc, "weekly_matrix": pct_mat, "weekly_curve": weighted_curve, "daily_curve": day_curve,
        "cohorts_30d": cohorts, "cohort_tests": cohort_tests, "h30_users": int(len(h30)),
    }
