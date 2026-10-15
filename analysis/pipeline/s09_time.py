"""Work Packages I, J, K — Daily patterns, time-of-day behaviour, new vs returning activity.

Observed data and hypotheses are kept separate in the outputs: every 'spike' is only a statistical
flag; no campaign or cause is inferred.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from analysis import config
from analysis.pipeline.context import Context
from analysis.utils.io import save_table
from analysis.utils.metrics import pct, robust_z

DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def run(ctx: Context) -> None:
    e, s, t, u, ud = ctx.events, ctx.sessions, ctx.tasks, ctx.users, ctx.user_day
    days = pd.date_range(ctx.data_start.normalize(), ctx.data_end.normalize(), freq="D")

    daily = pd.DataFrame(index=days)
    daily["dau"] = e.groupby("date").user_id.nunique()
    daily["sessions"] = s.groupby("date").size()
    daily["valid_sessions"] = s[s.is_valid].groupby("date").size()
    daily["events"] = e.groupby("date").size()
    daily["meaningful_events"] = e[e.is_meaningful].groupby("date").size()
    daily["registrations"] = u.groupby("reg_date").size()
    daily["tasks_viewed"] = t.groupby("date").size()
    daily["tasks_completed"] = t[t.is_completed].groupby(t.task_completed_at.dt.normalize()).size()
    daily["first_active_users"] = u.groupby("first_active_date").size()
    daily = daily.fillna(0)
    daily["cumulative_registered"] = daily.registrations.cumsum()
    daily["active_rate_of_registered_pct"] = (daily.dau / daily.cumulative_registered.replace(0, np.nan) * 100).round(2)
    daily["events_per_active_user"] = (daily.events / daily.dau.replace(0, np.nan)).round(2)
    daily["sessions_per_active_user"] = (daily.sessions / daily.dau.replace(0, np.nan)).round(2)
    daily["dau_7d_avg"] = daily.dau.rolling(7, min_periods=1).mean().round(2)
    daily["returning_dau"] = daily.dau - daily.first_active_users
    # spike / drop detection on log DAU vs centred 15-day rolling median (robust z on the residual)
    base = np.log1p(daily.dau.rolling(15, center=True, min_periods=5).median())
    resid = np.log1p(daily.dau) - base
    daily["robust_z"] = robust_z(resid).round(2)
    # only flag once the baseline is large enough for a ratio to be meaningful (median DAU ≥ 10)
    enough = daily.dau.rolling(15, center=True, min_periods=5).median() >= 10
    daily["flag"] = np.select([enough & (daily.robust_z >= 3), enough & (daily.robust_z <= -3)], ["Spike", "Drop"], "")
    daily["dow"] = daily.index.day_name()
    daily.index.name = "date"
    save_table(daily.reset_index(), "daily_activity_timeseries")

    flags = daily[daily.flag != ""].reset_index()[["date", "dow", "dau", "dau_7d_avg", "registrations", "events",
                                                   "robust_z", "flag"]]
    monthly = daily.groupby(daily.index.to_period("M")).agg(
        registrations=("registrations", "sum"), sessions=("sessions", "sum"), events=("events", "sum"),
        avg_dau=("dau", "mean"), peak_dau=("dau", "max"), cumulative_registered=("cumulative_registered", "max"),
        avg_active_rate_pct=("active_rate_of_registered_pct", "mean")).round(2)
    monthly.index = monthly.index.astype(str)
    monthly["mau"] = e.groupby(e.date.dt.to_period("M").astype(str)).user_id.nunique()
    save_table(monthly.reset_index(names="month"), "monthly_activity")

    # weekday vs weekend — DAU normalised by trailing/centred 7-day mean to remove the growth trend
    active_period = daily[daily.index >= daily.index[daily.dau > 0][0]]
    norm = (active_period.dau / active_period.dau.rolling(7, center=True, min_periods=4).mean())
    dow_tbl = pd.DataFrame({
        "avg_dau": active_period.groupby("dow").dau.mean(),
        "avg_sessions": active_period.groupby("dow").sessions.mean(),
        "avg_events": active_period.groupby("dow").events.mean(),
        "dau_index_vs_7d_mean": norm.groupby(active_period.dow).mean(),
    }).reindex(DOW)
    ev_dow = e.groupby("dow").agg(events=("event_id", "size"), users=("user_id", "nunique"))
    dow_tbl["events_per_active_user_day"] = (ud.assign(dow=ud.date.dt.day_name()).groupby("dow").events.mean()).reindex(DOW)
    dow_tbl["meaningful_share_pct"] = (e.groupby("dow").is_meaningful.mean() * 100).reindex(DOW)
    tdow = t.assign(dow=t.task_viewed_at.dt.day_name())
    dow_tbl["task_completion_rate_pct"] = (tdow[tdow.is_resolved].groupby("dow").is_completed.mean() * 100).reindex(DOW)
    dow_tbl = dow_tbl.round(3).reset_index(names="dow")
    save_table(dow_tbl, "day_of_week_activity")
    wk = active_period.assign(weekend=active_period.index.dayofweek >= 5, idx=norm)
    mw = stats.mannwhitneyu(wk.loc[wk.weekend, "idx"].dropna(), wk.loc[~wk.weekend, "idx"].dropna())
    udw = ud.assign(weekend=ud.date.dt.dayofweek >= 5)
    weekend = {
        "weekday_avg_dau": round(wk.loc[~wk.weekend, "dau"].mean(), 2), "weekend_avg_dau": round(wk.loc[wk.weekend, "dau"].mean(), 2),
        "weekday_dau_index": round(wk.loc[~wk.weekend, "idx"].mean(), 3), "weekend_dau_index": round(wk.loc[wk.weekend, "idx"].mean(), 3),
        "mannwhitney_p_dau_index": float(mw.pvalue),
        "weekday_events_per_user_day": round(udw.loc[~udw.weekend, "events"].mean(), 3),
        "weekend_events_per_user_day": round(udw.loc[udw.weekend, "events"].mean(), 3),
        "weekday_share_of_events_pct": pct((~e.is_weekend).sum(), len(e)),
        "weekday_share_of_days_pct": round(5 / 7 * 100, 1),
    }

    # hour of day
    hour = pd.DataFrame(index=range(24))
    hour["sessions"] = s.groupby("hour").size()
    hour["events"] = e.groupby("hour").size()
    hour["meaningful_events"] = e[e.is_meaningful].groupby("hour").size()
    hour["active_users"] = e.groupby("hour").user_id.nunique()
    hour["avg_session_duration_s"] = s.groupby("hour").session_duration_seconds.mean().round(1)
    hour["events_per_valid_session"] = (s[s.is_valid].groupby("hour").raw_event_count.mean()).round(2)
    tr = t[t.is_resolved]
    hour["task_completion_rate_pct"] = (tr.groupby("hour").is_completed.mean() * 100).round(1)
    hour = hour.fillna(0)
    hour["pct_sessions"] = (hour.sessions / hour.sessions.sum() * 100).round(2)
    save_table(hour.reset_index(names="hour"), "hour_of_day_activity")
    chi_hour = stats.chisquare(hour.sessions)

    dp_order = [lab for *_, lab in config.DAYPART_BINS]
    dp = pd.DataFrame({
        "sessions": s.groupby("daypart").size(), "events": e.groupby("daypart").size(),
        "meaningful_events": e[e.is_meaningful].groupby("daypart").size(),
        "avg_session_duration_s": s.groupby("daypart").session_duration_seconds.mean(),
        "task_completion_rate_pct": tr.groupby("daypart").is_completed.mean() * 100,
    }).reindex(dp_order)
    dp["hours_in_bucket"] = [7, 5, 4, 8]
    dp["pct_sessions"] = dp.sessions / dp.sessions.sum() * 100
    dp["sessions_per_hour_of_bucket"] = dp.sessions / dp.hours_in_bucket
    dp = dp.round(2).reset_index(names="daypart")
    save_table(dp, "daypart_activity")
    feat_dp = pd.crosstab(e.feature_name, e.daypart, normalize="index").reindex(columns=dp_order).round(4) * 100
    save_table(feat_dp.reset_index(), "feature_by_daypart_pct")
    heat = pd.crosstab(s.dow, s.hour).reindex(DOW)
    save_table(heat.reset_index(), "sessions_dow_hour_heatmap")

    # weekly feature usage (for trend chart)
    wf = e.assign(week=e.date.dt.to_period("W-SUN").dt.start_time).pivot_table(
        index="week", columns="feature_name", values="event_id", aggfunc="count", fill_value=0)
    save_table(wf.reset_index(), "weekly_feature_events")

    # new vs returning activity (session level)
    sv = s[s.is_valid].merge(u[["user_id", "first_active_date"]], on="user_id")
    sv["activity_type"] = np.where(sv.date <= sv.first_active_date, "New (first active day)", "Returning (later days)")
    tt = t.merge(sv[["session_id", "activity_type"]], on="session_id", how="inner")
    em = e.merge(sv[["session_id", "activity_type"]], on="session_id")
    nvr = sv.groupby("activity_type").agg(sessions=("session_id", "size"), users=("user_id", "nunique"),
                                          mean_events=("raw_event_count", "mean"), mean_features=("raw_feature_count", "mean"),
                                          mean_meaningful=("raw_meaningful_count", "mean"),
                                          median_duration_s=("session_duration_seconds", "median"))
    nvr["task_records"] = tt.groupby("activity_type").size()
    nvr["task_completion_rate_pct"] = tt[tt.is_resolved].groupby("activity_type").is_completed.mean() * 100
    nvr["ad_skip_rate_pct"] = em[em.event_name.isin(["ad_completed", "ad_skipped"])].groupby("activity_type").apply(
        lambda g: (g.event_name == "ad_skipped").mean() * 100, include_groups=False)
    nvr["mission_abandon_rate_pct"] = em[em.event_name.isin(["mission_completed", "mission_abandoned"])].groupby(
        "activity_type").apply(lambda g: (g.event_name == "mission_abandoned").mean() * 100, include_groups=False)
    nvr["exposure_share_pct"] = em.groupby("activity_type").stage.apply(lambda x: (x == "exposure").mean() * 100)
    nvr = nvr.round(2).reset_index()
    save_table(nvr, "new_vs_returning_sessions")
    mix = pd.crosstab(em.feature_name, em.activity_type, normalize="columns").round(4) * 100
    mix["difference_pp"] = (mix.iloc[:, 1] - mix.iloc[:, 0]).round(2)
    save_table(mix.reset_index(), "new_vs_returning_feature_mix")
    mw_ev = stats.mannwhitneyu(sv.loc[sv.activity_type.str.startswith("New"), "raw_event_count"],
                               sv.loc[~sv.activity_type.str.startswith("New"), "raw_event_count"])

    busiest = daily.nlargest(5, "dau").reset_index()[["date", "dow", "dau", "events", "sessions"]]
    quiet = active_period[active_period.index >= pd.Timestamp("2026-06-01")].nsmallest(5, "dau").reset_index()[
        ["date", "dow", "dau", "events", "sessions"]]
    ctx.R["time"] = {
        "daily": daily.reset_index(), "monthly": monthly.reset_index(names="month"), "flags": flags,
        "dow": dow_tbl, "weekend": weekend, "hour": hour.reset_index(names="hour"), "daypart": dp,
        "feature_daypart": feat_dp.reset_index(), "heatmap": heat.reset_index(),
        "weekly_feature": wf.reset_index(), "new_vs_returning": nvr, "new_vs_returning_mix": mix.reset_index(),
        "new_vs_returning_events_p": float(mw_ev.pvalue),
        "busiest_days": busiest, "quietest_days_since_june": quiet,
        "busiest_hours": hour.sessions.nlargest(3).index.tolist(), "quietest_hours": hour.sessions.nsmallest(3).index.tolist(),
        "hour_uniformity_chi2_p": float(chi_hour.pvalue),
        "peak_dau": int(daily.dau.max()), "peak_dau_date": daily.dau.idxmax(),
        "avg_dau_last_30d": round(daily.dau.iloc[-30:].mean(), 2), "avg_dau_first_active_30d": round(active_period.dau.iloc[:30].mean(), 2),
        "first_activity_date": active_period.index[0],
        "corr_dau_cumreg": round(float(stats.spearmanr(daily.dau, daily.cumulative_registered).statistic), 3),
        "avg_active_rate_last_30d": round(daily.active_rate_of_registered_pct.iloc[-30:].mean(), 2),
        "avg_active_rate_may": round(daily.loc["2026-05", "active_rate_of_registered_pct"].mean(), 2),
    }
