"""Build the clean analytical layer (PII-free) used by every downstream analysis.

Decisions (all documented in docs/methodology.md):
  * 03_Feature_Events is the primary behavioural source; 10_Event_Data_Quality_Audit is a QA copy.
  * Exact-content duplicate events (17) are excluded from the clean layer; raw is untouched.
  * Event order = event_datetime, ties broken by event_id (sequence_number is unreliable).
  * Active day = calendar day with >= 1 feature event (identical to 04_Daily_Activity's coverage).
  * Valid session = session with >= 1 raw feature event.
  * Session counts/events per session are recomputed from raw events (session-sheet counters are invalid).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from analysis import config
from analysis.pipeline.context import Context
from analysis.utils.io import save_table


def daypart(hour: pd.Series) -> pd.Series:
    h = hour.where(hour >= 5, hour + 24)
    out = pd.Series(index=hour.index, dtype=object)
    for lo, hi, label in config.DAYPART_BINS:
        out[(h >= lo) & (h < hi)] = label
    return out


def run(ctx: Context) -> None:
    raw = ctx.raw
    end = ctx.data_end
    end_day = end.normalize()

    # ------------------------------------------------------------------ events
    e = raw["events"].copy()
    dup_ids = set(ctx.extra["flag_dup_content_event_ids"].event_id)
    e = e[~e.event_id.isin(dup_ids)].copy()
    e["stage"] = e.event_name.map(config.EVENT_STAGE)
    assert e.stage.notna().all(), "Unmapped event_name in taxonomy"
    e["feature_area"] = e.feature_name.map(config.FEATURE_AREA)
    e["is_meaningful"] = e.stage.eq("complete")
    e["date"] = e.event_datetime.dt.normalize()
    e["hour"] = e.event_datetime.dt.hour
    e["dow"] = e.event_datetime.dt.day_name()
    e["is_weekend"] = e.event_datetime.dt.dayofweek >= 5
    e["daypart"] = daypart(e.hour)
    e = e.sort_values(["user_id", "event_datetime", "event_id"]).reset_index(drop=True)
    e["order_in_session"] = e.groupby("session_id").cumcount() + 1
    e = e.drop(columns=["platform"])  # single-valued

    # ------------------------------------------------------------------ sessions
    s = raw["sessions"].copy().drop(columns=["platform", "session_status"])
    g = e.groupby("session_id")
    s["raw_event_count"] = s.session_id.map(g.size()).fillna(0).astype(int)
    s["raw_feature_count"] = s.session_id.map(g.feature_name.nunique()).fillna(0).astype(int)
    s["raw_meaningful_count"] = s.session_id.map(g.is_meaningful.sum()).fillna(0).astype(int)
    s["first_raw_feature"] = s.session_id.map(g.feature_name.first())
    s["last_raw_feature"] = s.session_id.map(g.feature_name.last())
    s["last_raw_event"] = s.session_id.map(g.event_name.last())
    s["is_valid"] = s.raw_event_count > 0
    s["is_overlapping"] = s.session_id.isin(set(ctx.extra["flag_overlap_session_ids"].session_id))
    fence = float(ctx.extra["session_long_fence"].fence.iloc[0])
    s["is_long_session"] = s.session_duration_seconds > fence
    s["date"] = s.session_start.dt.normalize()
    s["hour"] = s.session_start.dt.hour
    s["dow"] = s.session_start.dt.day_name()
    s["is_weekend"] = s.session_start.dt.dayofweek >= 5
    s["daypart"] = daypart(s.hour)
    s = s.sort_values(["user_id", "session_start"]).reset_index(drop=True)
    s["user_session_index"] = s.groupby("user_id").cumcount() + 1
    dur_min = s.session_duration_seconds / 60
    s["event_density_per_min"] = np.where(s.is_valid, s.raw_event_count / dur_min, np.nan)

    # ------------------------------------------------------------------ tasks
    t = raw["tasks"].copy()
    t["view_to_start_s"] = (t.task_started_at - t.task_viewed_at).dt.total_seconds()
    t["start_to_complete_s"] = (t.task_completed_at - t.task_started_at).dt.total_seconds()
    t["is_completed"] = t.task_status.eq("Completed")
    t["is_resolved"] = t.task_status.isin(["Completed", "Failed", "Abandoned"])
    t["hour"] = t.task_started_at.dt.hour
    t["daypart"] = daypart(t.hour)
    t["date"] = t.task_viewed_at.dt.normalize()

    # ------------------------------------------------------------------ users (PII removed)
    u = raw["users"].drop(columns=config.PII_COLUMNS + ["platform"]).copy()
    u = u.rename(columns={"primary_device": "device"})
    u["reg_date"] = u.registration_datetime.dt.normalize()
    u["reg_month"] = u.registration_datetime.dt.to_period("M").astype(str)
    u = u.set_index("user_id")

    sg = s.groupby("user_id")
    u["n_sessions"] = sg.size()
    u["n_valid_sessions"] = sg.is_valid.sum()
    u["first_session_dt"] = sg.session_start.min()
    u["last_session_dt"] = sg.session_start.max()
    u["total_session_seconds"] = sg.session_duration_seconds.sum()
    u["median_session_seconds"] = sg.session_duration_seconds.median()

    eg = e.groupby("user_id")
    u["n_events"] = eg.size()
    u["n_active_days"] = eg.date.nunique()
    u["first_event_dt"] = eg.event_datetime.min()
    u["last_event_dt"] = eg.event_datetime.max()
    u["n_features"] = eg.feature_name.nunique()
    u["n_areas"] = eg.feature_area.nunique()
    u["first_feature"] = eg.feature_name.first()
    em = e[e.is_meaningful]
    mg = em.groupby("user_id")
    u["n_meaningful"] = mg.size()
    u["n_features_completed"] = mg.feature_name.nunique()
    u["first_meaningful_event_dt"] = mg.event_datetime.min()
    u["first_meaningful_feature"] = mg.feature_name.first()
    u["n_meaningful_days"] = mg.date.nunique()
    for ev in ["level_up", "badge_earned", "streak_claimed", "streak_broken", "daily_reward_claimed",
               "spin_completed", "mission_completed", "mission_abandoned", "ad_completed", "ad_skipped",
               "captcha_completed", "captcha_failed"]:
        u[f"n_{ev}"] = e[e.event_name == ev].groupby("user_id").size()
    u["n_referral_actions"] = e[e.event_name.isin(["referral_created", "referral_shared"])].groupby("user_id").size()
    u["n_starts"] = e[e.stage == "start"].groupby("user_id").size()
    u["n_exposures"] = e[e.stage == "exposure"].groupby("user_id").size()

    tg = t.groupby("user_id")
    u["n_tasks"] = tg.size()
    u["n_tasks_completed"] = tg.is_completed.sum()
    u["n_tasks_resolved"] = tg.is_resolved.sum()
    u["n_tasks_abandoned"] = t[t.task_status == "Abandoned"].groupby("user_id").size()
    u["n_tasks_failed"] = t[t.task_status == "Failed"].groupby("user_id").size()
    u["first_task_dt"] = tg.task_viewed_at.min()
    u["first_task_complete_dt"] = t[t.is_completed].groupby("user_id").task_completed_at.min()

    count_cols = [c for c in u.columns if c.startswith("n_")] + ["total_session_seconds"]
    u[count_cols] = u[count_cols].fillna(0).astype(int)

    u["first_activity_dt"] = u[["first_session_dt", "first_event_dt"]].min(axis=1)
    u["last_activity_dt"] = u[["last_session_dt", "last_event_dt"]].max(axis=1)
    u["first_meaningful_dt"] = u[["first_meaningful_event_dt", "first_task_complete_dt"]].min(axis=1)
    u["hours_to_first_activity"] = (u.first_event_dt - u.registration_datetime).dt.total_seconds() / 3600
    u["hours_to_first_session"] = (u.first_session_dt - u.registration_datetime).dt.total_seconds() / 3600
    u["hours_to_first_meaningful"] = (u.first_meaningful_dt - u.registration_datetime).dt.total_seconds() / 3600
    u["first_active_date"] = u.first_event_dt.dt.normalize()
    u["last_active_date"] = u.last_event_dt.dt.normalize()
    u["active_span_days"] = (u.last_active_date - u.first_active_date).dt.days
    u["tenure_days"] = (end_day - u.reg_date).dt.days
    u["observable_days_since_first_active"] = (end_day - u.first_active_date).dt.days
    e_week = e.assign(week=(e.date - e.user_id.map(u.first_active_date)).dt.days // 7)
    u["n_active_weeks"] = e_week.groupby("user_id").week.nunique()
    u["n_active_weeks"] = u.n_active_weeks.fillna(0).astype(int)
    u["observable_weeks"] = np.floor(u.observable_days_since_first_active / 7) + 1
    u["is_active"] = u.n_events > 0
    u["has_session"] = u.n_sessions > 0
    u = u.reset_index()

    # ------------------------------------------------------------------ user-day
    ud = e.groupby(["user_id", "date"]).agg(events=("event_id", "size"), features=("feature_name", "nunique"),
                                            meaningful=("is_meaningful", "sum")).reset_index()
    sd = s.groupby(["user_id", "date"]).agg(sessions=("session_id", "size"), valid_sessions=("is_valid", "sum"),
                                            session_seconds=("session_duration_seconds", "sum")).reset_index()
    ud = ud.merge(sd, on=["user_id", "date"], how="left").fillna({"sessions": 0, "valid_sessions": 0, "session_seconds": 0})
    ud = ud.merge(u[["user_id", "reg_date", "first_active_date", "acquisition_source", "device"]], on="user_id")
    ud["day_since_first_active"] = (ud.date - ud.first_active_date).dt.days
    ud["day_since_reg"] = (ud.date - ud.reg_date).dt.days
    ud["is_first_active_day"] = ud.day_since_first_active == 0

    # ------------------------------------------------------------------ user x feature
    uf_events = e.pivot_table(index="user_id", columns="feature_name", values="event_id", aggfunc="count", fill_value=0)
    uf_sessions = e.groupby(["user_id", "feature_name"]).session_id.nunique().unstack(fill_value=0)
    uf_days = e.groupby(["user_id", "feature_name"]).date.nunique().unstack(fill_value=0)
    uf_complete = em.pivot_table(index="user_id", columns="feature_name", values="event_id", aggfunc="count", fill_value=0)
    uf_complete_days = em.groupby(["user_id", "feature_name"]).date.nunique().unstack(fill_value=0)
    for f in config.FEATURES:
        for frame in (uf_events, uf_sessions, uf_days, uf_complete, uf_complete_days):
            if f not in frame.columns:
                frame[f] = 0

    ctx.events, ctx.sessions, ctx.tasks, ctx.users, ctx.user_day = e, s, t, u, ud
    ctx.extra.update(uf_events=uf_events[config.FEATURES], uf_sessions=uf_sessions[config.FEATURES],
                     uf_days=uf_days[config.FEATURES], uf_complete=uf_complete[config.FEATURES],
                     uf_complete_days=uf_complete_days[config.FEATURES])

    # persist the PII-free analytical layer
    save_table(e, "events_clean", config.DATA_ANALYTICAL)
    save_table(s, "sessions_clean", config.DATA_ANALYTICAL)
    save_table(t, "tasks_clean", config.DATA_ANALYTICAL)
    save_table(u, "users_analytical", config.DATA_ANALYTICAL)
    save_table(ud, "user_day", config.DATA_ANALYTICAL)
    save_table(uf_events[config.FEATURES].reset_index(), "user_feature_events", config.DATA_ANALYTICAL)
    for key in ("users", "sessions", "daily", "tasks", "milestones"):
        df = raw[key].drop(columns=[c for c in config.PII_COLUMNS if c in raw[key].columns])
        save_table(df, f"{config.SHEETS[key]}_nopii", config.DATA_PROCESSED)
    # shareable dataset for independent verification: every sheet, unmodified except personal fields removed
    config.DATA_ANONYMISED.mkdir(parents=True, exist_ok=True)
    for key, sheet in config.SHEETS.items():
        df = raw[key].drop(columns=[c for c in config.PII_COLUMNS if c in raw[key].columns])
        save_table(df, sheet, config.DATA_ANONYMISED)

    ctx.R["clean"] = {
        "events_raw": len(raw["events"]), "events_clean": len(e), "events_removed": len(raw["events"]) - len(e),
        "sessions": len(s), "valid_sessions": int(s.is_valid.sum()), "tasks": len(t), "users": len(u),
        "user_days": len(ud),
    }
