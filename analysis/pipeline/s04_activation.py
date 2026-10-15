"""Work Package C — Activation analysis.

Activation (operational definition selected here):
  A simulated user is *activated* if their first meaningful activity (see s03) occurs within
  N days of registration_datetime. Denominator = users whose full N-day window is observable
  (registration_datetime <= data_end − N days) so recent registrants are not counted as failures.

The window N is chosen from the capture curve: the share of eventual activators (users with
≥ 60 days of tenure, so 'eventual' is observable) who activated within N days.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from analysis import config
from analysis.pipeline.context import Context
from analysis.utils.funnel import stage_table
from analysis.utils.io import save_table
from analysis.utils.metrics import pct

CAPTURE_TENURE_DAYS = 60


def run(ctx: Context) -> None:
    u, e, t = ctx.users, ctx.events, ctx.tasks
    end = ctx.data_end
    hrs = u.hours_to_first_meaningful
    rows = []
    mature = u[u.registration_datetime <= end - pd.Timedelta(days=CAPTURE_TENURE_DAYS)]
    eventual = mature.hours_to_first_meaningful.notna() & (mature.hours_to_first_meaningful <= CAPTURE_TENURE_DAYS * 24)
    for w in config.ACTIVATION_WINDOWS:
        elig = u.registration_datetime <= end - pd.Timedelta(days=w)
        act = elig & (hrs <= w * 24)
        cap = (mature.hours_to_first_meaningful <= w * 24).sum()
        rows.append({"window_days": w, "eligible_users": int(elig.sum()), "activated_users": int(act.sum()),
                     "activation_rate_pct": pct(act.sum(), elig.sum()),
                     "capture_of_60d_activators_pct": pct(cap, eventual.sum())})
    win = pd.DataFrame(rows)
    win["marginal_gain_pp"] = win.capture_of_60d_activators_pct.diff().round(1)
    win["gain_per_extra_day_pp"] = (win.marginal_gain_pp / win.window_days.diff()).round(2)
    # selection rule: smallest window that captures the majority (≥50%) of 60-day activators
    W = int(win.loc[win.capture_of_60d_activators_pct >= 50, "window_days"].min())
    win["selected"] = win.window_days == W
    save_table(win, "activation_windows")
    ctx.R.setdefault("thresholds", {})["activation_window_days"] = W
    elig = u.registration_datetime <= end - pd.Timedelta(days=W)
    u["activation_eligible"] = elig
    u["is_activated"] = elig & (hrs <= W * 24)
    u["activation_speed"] = np.select(
        [hrs <= 24, hrs <= 7 * 24, hrs.notna()], ["Within 24h", "Day 2–7", "After day 7"], "Never")
    ws = win.set_index("window_days")

    # Activation funnel (ever, within observation window) – canonical stages shared with every other funnel
    fn = stage_table(u, ctx.R["thresholds"],
                     ["Registered", "Logged in", "Used a feature", "Started an activity", "Completed a meaningful activity",
                      "Returned (2nd active day)", "Established (≥3 meaningful days)"])
    save_table(fn, "activation_funnel")

    # activation by registration month
    bym = u[elig].groupby("reg_month").agg(eligible=("user_id", "size"), activated=("is_activated", "sum")).reset_index()
    bym["activation_rate_pct"] = (bym.activated / bym.eligible * 100).round(1)
    save_table(bym, "activation_by_reg_month")

    ctx.R["activation"] = {
        "definition": f"First meaningful activity within {W} days of registration; denominator = users registered at "
                      f"least {W} days before data end ({end.date()}).",
        "window_rationale": (
            f"Selection rule: the smallest tested window that captures the majority (≥50%) of users who activate within "
            f"60 days. Capture by window: 1d {ws.loc[1, 'capture_of_60d_activators_pct']}%, 3d "
            f"{ws.loc[3, 'capture_of_60d_activators_pct']}%, 7d {ws.loc[7, 'capture_of_60d_activators_pct']}%, 14d "
            f"{ws.loc[14, 'capture_of_60d_activators_pct']}%, 30d {ws.loc[30, 'capture_of_60d_activators_pct']}%. "
            f"Short windows misclassify most eventual activators because the simulated cohort takes a median of "
            f"{u.hours_to_first_session.median() / 24:.1f} days to open a first session. The gain per extra day falls from "
            f"{ws.loc[14, 'gain_per_extra_day_pp']}pp (days 8–14) to {ws.loc[30, 'gain_per_extra_day_pp']}pp (days 15–30), "
            f"so {W} days is the elbow; longer windows also shrink the eligible population "
            f"({int(ws.loc[W, 'eligible_users'])} users eligible at {W}d vs {int(ws.loc[30, 'eligible_users'])} at 30d). "
            f"The 7-day rate ({ws.loc[7, 'activation_rate_pct']}%) is reported alongside as an 'early activation' view."),
        "window_days": W, "rate_7d_pct": float(ws.loc[7, "activation_rate_pct"]),
        "windows": win, "funnel": fn, "by_reg_month": bym,
        "rate_pct": float(ws.loc[W, "activation_rate_pct"]),
        "eligible": int(ws.loc[W, "eligible_users"]), "activated": int(ws.loc[W, "activated_users"]),
        "speed_distribution": u.activation_speed.value_counts().to_dict(),
    }
