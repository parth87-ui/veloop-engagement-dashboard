"""Work Package B — User lifecycle reconstruction.

Meaningful activity (analyst definition, derived from the observed taxonomy):
  A *user-initiated, completed value action*:
    - feature events with stage 'complete' (ad_completed, captcha_completed, daily_reward_claimed,
      follow_task_completed, mining_activity, mission_completed, referral_created, referral_shared,
      spin_completed, streak_claimed, tap_completed), OR
    - a task in 05_Task_Activity with task_status = 'Completed'.
  Excluded: views/opens (exposure), starts (intent only), skips/failures/abandons, system-awarded
  progression outcomes (badge_earned, level_up), mining_stopped (neutral) and streak_broken (negative).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from analysis import config
from analysis.pipeline.context import Context
from analysis.utils.funnel import stage_table
from analysis.utils.io import save_table
from analysis.utils.metrics import dist_summary, pct

TIME_BUCKETS = [(-0.01, 1, "< 1 hour"), (1, 24, "1–24 hours"), (24, 72, "1–3 days"), (72, 168, "3–7 days"),
                (168, 336, "7–14 days"), (336, 720, "14–30 days"), (720, 1e9, "> 30 days")]

REGULAR_WEEKS = 3  # activity in >= 3 distinct weeks after first active day


def bucketize(hours: pd.Series) -> pd.Series:
    out = pd.Series("No activity", index=hours.index, dtype=object)
    for lo, hi, lab in TIME_BUCKETS:
        out[(hours > lo) & (hours <= hi)] = lab
    return out


def run(ctx: Context) -> None:
    u, e, t, s = ctx.users, ctx.events, ctx.tasks, ctx.sessions
    n = len(u)

    # union of meaningful-activity dates (events + completed tasks)
    md = pd.concat([
        e.loc[e.is_meaningful, ["user_id", "date"]],
        t.loc[t.is_completed, ["user_id"]].assign(date=t.loc[t.is_completed, "task_completed_at"].dt.normalize()),
    ]).drop_duplicates()
    ctx.extra["meaningful_days"] = md
    u["n_meaningful_days_all"] = u.user_id.map(md.groupby("user_id").size()).fillna(0).astype(int)

    active = u[u.is_active]
    # top-quartile breadth: feature breadth is strongly tied to volume in this dataset, so the
    # median would label half of all active users "multi-feature" and lose discriminating power
    multi_threshold = int(active.n_features_completed.quantile(0.75))
    ctx.R.setdefault("thresholds", {})
    ctx.R["thresholds"].update({
        "multi_feature_min_completed_features": multi_threshold,
        "regular_engagement_min_weeks": REGULAR_WEEKS,
    })
    # canonical journey flags – the ONLY definitions used by every funnel, KPI and dashboard view
    u["is_multi_feature"] = u.n_features_completed >= multi_threshold
    u["is_regular"] = u.n_active_weeks >= REGULAR_WEEKS
    u["started"] = u.user_id.isin(set(e.loc[e.stage == "start", "user_id"]) | set(t.user_id))
    u["completed_any"] = u.first_meaningful_dt.notna()
    u["returned"] = u.n_active_days >= 2          # "repeat user" everywhere in the project
    u["established"] = u.n_meaningful_days_all >= 3

    lc = stage_table(u, ctx.R["thresholds"],
                     ["Registered", "Logged in", "Used a feature", "Completed a meaningful activity",
                      "Returned (2nd active day)", "Multi-feature", "Regular (≥3 active weeks)"],
                     labels={"Registered": "Registration", "Logged in": "First login",
                             "Used a feature": "First feature interaction",
                             "Completed a meaningful activity": "First meaningful activity",
                             "Returned (2nd active day)": "Repeated activity (2nd active day)",
                             "Multi-feature": "Multi-feature usage", "Regular (≥3 active weeks)": "Regular engagement"})
    save_table(lc, "lifecycle_stages")

    # time-to-X distributions
    tt = {}
    for col, label in [("hours_to_first_session", "Registration → first session"),
                       ("hours_to_first_activity", "Registration → first feature event"),
                       ("hours_to_first_meaningful", "Registration → first meaningful activity")]:
        b = bucketize(u[col]).value_counts()
        order = [lab for _, _, lab in TIME_BUCKETS] + ["No activity"]
        tt[col] = {"label": label, "summary_hours": dist_summary(u[col]),
                   "buckets": [{"bucket": k, "users": int(b.get(k, 0)), "pct": pct(b.get(k, 0), n)} for k in order]}
    bucket_tbl = pd.DataFrame([{"metric": v["label"], **{x["bucket"]: x["users"] for x in v["buckets"]}} for v in tt.values()])
    save_table(bucket_tbl, "lifecycle_time_to_activity_buckets")

    # activity depth groups
    depth = {
        "no_activity": int((u.n_active_days == 0).sum()),
        "one_time": int((u.n_active_days == 1).sum()),
        "repeat": int((u.n_active_days >= 2).sum()),
        "one_session": int((u.n_sessions == 1).sum()),
        "multi_feature": int(u.is_multi_feature.sum()),
        "regular": int(u.is_regular.sum()),
        "never_beyond_first_meaningful_day": int(((u.n_meaningful_days_all <= 1) & u.is_active).sum()),
    }

    # derived milestones vs milestone sheet
    m = ctx.raw["milestones"]
    der = {
        "first_login": u.has_session.sum(),
        "first_feature_use": u.is_active.sum(),
        "first_task_start": (u.n_tasks > 0).sum(),
        "first_task_completion": (u.n_tasks_completed > 0).sum(),
        "first_reward_activity": e[e.reward_related_flag == "Yes"].user_id.nunique(),
        "third_active_day": (u.n_active_days >= 3).sum(),
        "seventh_active_day": (u.n_active_days >= 7).sum(),
        "first_streak": e[e.event_name == "streak_claimed"].user_id.nunique(),
        "first_mission": e[e.feature_name == "Missions"].user_id.nunique(),
        "first_spin": e[e.event_name == "spin_completed"].user_id.nunique(),
        "first_referral_activity": e[e.feature_name == "Referral"].user_id.nunique(),
        "level_up": e[e.event_name == "level_up"].user_id.nunique(),
    }
    sheet = m.milestone_type.value_counts()
    mil = pd.DataFrame([{"milestone": k, "users_derived_from_raw": int(v), "users_in_milestone_sheet": int(sheet.get(k, 0)),
                         "difference": int(sheet.get(k, 0) - v), "pct_of_registered_derived": pct(v, n)}
                        for k, v in der.items()])
    save_table(mil, "milestones_derived_vs_sheet")

    first_feat = u.first_feature.value_counts().rename_axis("feature").reset_index(name="users")
    first_feat["pct_of_active"] = (first_feat.users / u.is_active.sum() * 100).round(1)
    first_task = t.sort_values("task_viewed_at").groupby("user_id").task_category.first().value_counts()
    first_comp = u.first_meaningful_feature.value_counts()
    save_table(first_feat, "lifecycle_first_feature")

    ctx.R["lifecycle"] = {
        "meaningful_definition": {
            "included_events": config.MEANINGFUL_EVENTS,
            "included_tasks": "05_Task_Activity rows with task_status = 'Completed'",
            "excluded": {"exposure (views/opens)": config.EXPOSURE_EVENTS, "start (intent only)": config.START_EVENTS,
                         "negative outcomes": config.NEGATIVE_OUTCOME_EVENTS,
                         "system progression outcomes": config.PROGRESSION_EVENTS,
                         "neutral/negative state": ["mining_stopped", "streak_broken"]},
            "rationale": "A meaningful activity is the earliest point at which a simulated user completes an action that "
                         "the product is designed to reward. Views and starts show exposure or intent only; badges and "
                         "level-ups are consequences awarded by the system rather than user actions.",
            "limitations": "Event-level completions cannot be tied to a preceding start within the same session "
                           "(see DQ-035); 'meaningful' therefore means 'a completion was logged', not 'a full flow was "
                           "observed'. Value of each action (points earned) is not in the dataset.",
            "users_with_meaningful_event": int((u.n_meaningful > 0).sum()),
            "users_with_completed_task": int((u.n_tasks_completed > 0).sum()),
        },
        "stages": lc, "time_to": tt, "depth": depth, "milestones": mil, "first_feature": first_feat,
        "first_task_category": first_task.to_dict(), "first_meaningful_feature": first_comp.to_dict(),
        "median_days_reg_to_first_activity": float(u.hours_to_first_activity.median() / 24),
        "median_days_reg_to_first_meaningful": float(u.hours_to_first_meaningful.median() / 24),
        "median_hours_first_activity_to_meaningful": float((u.hours_to_first_meaningful - u.hours_to_first_activity).median()),
        "meaningful_within_15min_of_first_activity_pct": pct(((u.hours_to_first_meaningful - u.hours_to_first_activity) <= 0.25).sum(),
                                             u.is_active.sum()),
    }
