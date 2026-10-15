"""Work Packages O & T — Behavioural drop-off matrix and the complete engagement funnel."""
from __future__ import annotations

import numpy as np
import pandas as pd

from analysis import config
from analysis.pipeline.context import Context
from analysis.utils.funnel import stage_table
from analysis.utils.io import save_table
from analysis.utils.metrics import pct


def run(ctx: Context) -> None:
    u, e, t, s, ud = ctx.users, ctx.events, ctx.tasks, ctx.sessions, ctx.user_day
    end_day = ctx.data_end.normalize()
    th = ctx.R["thresholds"]
    rows = []

    def add(stage, entering, continuing, observation, limitation, implication, unit="users"):
        entering, continuing = int(entering), int(continuing)
        rows.append({"stage": stage, "unit": unit, "entering": entering, "continuing": continuing,
                     "drop_off": entering - continuing, "drop_off_pct": pct(entering - continuing, entering),
                     "observation": observation, "limitation": limitation, "product_implication": implication})

    add("Registration → Login", len(u), u.has_session.sum(),
        f"{(~u.has_session).sum()} simulated users never opened a session; median time to first session for the rest "
        f"was {u.hours_to_first_session.median() / 24:.1f} days.",
        "No login/registration events; session existence is the login proxy.",
        "Investigate the post-registration handoff (verification, first-open prompt) and the multi-day delay to first session.")
    add("Login → Feature exploration (any feature event)", u.has_session.sum(), (u.has_session & u.is_active).sum(),
        f"Every user with a session also has feature events, but {(~s.is_valid).sum()} individual sessions contain no events.",
        "Zero-event sessions may be logging gaps rather than behaviour.",
        "Instrument session_started/feature_impression to separate empty visits from tracking loss.")
    eu = e.sort_values(["user_id", "event_datetime"])
    first_day = eu[eu.date == eu.user_id.map(u.set_index("user_id").first_active_date)]
    fd_feats = first_day.groupby("user_id").feature_name.nunique()
    add("First feature → second distinct feature (first active day)", u.is_active.sum(), (fd_feats >= 2).sum(),
        f"Median distinct features on the first active day: {fd_feats.median():.0f}.",
        "Breadth on day 1 depends on how many events a session contains.",
        "Cross-feature discovery on day 1 appears high; low-breadth day-1 users are the target for discovery tests.")
    # feature view -> start (only Missions and Spin the Wheel have both an exposure and a start event)
    pairs = {"Missions": ("mission_viewed", "mission_started"), "Spin the Wheel": ("spin_opened", "spin_started")}
    ent = cont = 0
    per_feature = []
    for f, (v_ev, s_ev) in pairs.items():
        viewers = set(e.loc[e.event_name == v_ev, "user_id"])
        starters = set(e.loc[e.event_name == s_ev, "user_id"])
        ent += len(viewers)
        cont += len(viewers & starters)
        per_feature.append({"feature": f, "viewers": len(viewers), "viewers_who_started": len(viewers & starters),
                            "starters_without_view": len(starters - viewers)})
    pf = pd.DataFrame(per_feature)
    add("Feature view → feature start (user×feature, Missions & Spin)", ent, cont,
        "Many viewers never record a start of the same feature; many starters never record a view "
        f"({int(pf.starters_without_view.sum())} user×feature pairs).",
        "Only 2 features log both a view and a start; views and starts are not linked within sessions (DQ-035).",
        "Treat as a hypothesis signal: test clearer calls-to-action on mission and spin surfaces.", unit="user×feature pairs")
    add("Task view → task start (records)", len(t), t.task_started_at.notna().sum(),
        "Every task record has a start timestamp – view→start drop-off is not observable.",
        "Task records appear to be created only when a task is started (no pure 'viewed' records).",
        "Add task_viewed events independent of starts to measure task-list friction.", unit="task records")
    resolved = t[t.is_resolved]
    add("Task start → task completion (resolved records)", len(resolved), resolved.is_completed.sum(),
        f"{(resolved.task_status == 'Abandoned').sum()} abandoned and {(resolved.task_status == 'Failed').sum()} failed; "
        f"{(t.task_status == 'Pending').sum()} pending records excluded.",
        "Pending tasks may later resolve; failure_reason is categorical only.",
        "Largest record-level friction point – investigate the dominant failure reasons by category.", unit="task records")
    mses = e[e.is_meaningful].groupby("user_id").session_id.nunique()
    add("First meaningful activity → second meaningful activity (separate session)", (mses >= 1).sum(), (mses >= 2).sum(),
        "Share of completers who complete again in another session.",
        "Event-based completions only (task completions excluded here to keep a single source).",
        "Post-completion prompts (next suggested activity) are a candidate investigation.")
    # active-day ladder on a fixed 30-day horizon (users with ≥30 observable days) to remove right-censoring
    elig = u[u.is_active & (u.observable_days_since_first_active >= 30)]
    ad30 = ud[ud.day_since_first_active.between(0, 29)].groupby("user_id").date.nunique().reindex(elig.user_id).fillna(0)
    add("First active day → second active day (first 30 days)", len(ad30), (ad30 >= 2).sum(),
        f"Within their first 30 days, {(ad30 == 1).sum()} of {len(ad30)} users with a full 30-day horizon were active "
        f"on only one day (all-time, unrestricted: {(u.n_active_days == 1).sum()} one-day users).",
        "Restricted to users first active ≥30 days before data end; strongly calendar-dependent (see cohorts).",
        "Second-day return is a primary user-level drop-off; post-first-day re-engagement is a key investigation area.")
    add("Second active day → third active day (first 30 days)", (ad30 >= 2).sum(), (ad30 >= 3).sum(),
        "Share of returning users who return a second time within 30 days.", "Same 30-day horizon population.",
        "Habit-formation mechanics (streaks, daily rewards) are candidates for investigation here.")
    add("Third active day → seventh active day (first 30 days)", (ad30 >= 3).sum(), (ad30 >= 7).sum(),
        "Progression to a 7th active day within the first 30 days.", "Same 30-day horizon population.",
        "Mid-term progression: missions/levels may matter more than onboarding here (hypothesis).")
    later = ud[ud.day_since_first_active.between(7, 30)].user_id.unique()
    add("First week → later activity (days 7–30)", len(elig), elig.user_id.isin(later).sum(),
        "Users with ≥30 observable days who were active again between day 7 and day 30.",
        "Restricted to users first active ≥30 days before data end.",
        "Week-2+ re-engagement is the target for notification-timing experiments.")
    dm = pd.DataFrame(rows)
    save_table(dm, "dropoff_matrix")
    save_table(pf, "dropoff_view_to_start_by_feature")

    # ---------------------------------------------------------------- engagement funnel (WP-T)
    # Same canonical stages and order as the lifecycle and activation funnel, so shared stages match exactly.
    # A "viewed a feature" stage is NOT used: Ads, CAPTCHA, Tap & Earn and Mining log no view events, so it
    # would drop users who clearly used the product and create a false dip.
    ef = stage_table(u, th, ["Registered", "Logged in", "Used a feature", "Started an activity",
                             "Completed a meaningful activity", "Returned (2nd active day)", "Multi-feature",
                             "Regular (≥3 active weeks)"])
    save_table(ef, "engagement_funnel")

    biggest = dm.loc[dm.unit == "users"].sort_values("drop_off_pct", ascending=False).iloc[0]
    ctx.R["dropoff"] = {"matrix": dm, "view_to_start_by_feature": pf, "engagement_funnel": ef,
                        "largest_user_dropoff_stage": biggest.stage, "largest_user_dropoff_pct": float(biggest.drop_off_pct),
                        "first_day_median_features": float(fd_feats.median())}
