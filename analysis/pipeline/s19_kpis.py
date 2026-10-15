"""KPI catalogue (≥30 behavioural KPIs) with the current value computed from the simulated dataset."""
from __future__ import annotations

import pandas as pd

from analysis.pipeline.context import Context
from analysis.utils.io import save_table
from analysis.utils.metrics import pct


def run(ctx: Context) -> None:
    R, u, e = ctx.R, ctx.users, ctx.events
    sm, to, ret = R["sessions"]["metrics"], R["features"]["task_overall"], R["retention"]["overall"]
    ft = R["features"]["table"]
    act_users = int(u.is_active.sum())
    n = len(u)
    W = R["activation"]["window_days"]
    daily = R["time"]["daily"]
    last30 = daily.tail(30)
    mau30 = e[e.date > ctx.data_end.normalize() - pd.Timedelta(days=30)].user_id.nunique()
    outcome = ft[ft.event_completion_rate_pct.notna()]
    th = R["thresholds"]
    rows = [
        # category, name, definition, formula, unit, denominator, source, value, interpretation, limitation
        ("User Activity", "Registered Users", "Simulated accounts in the user master", "COUNT(user_id)", "users", "—",
         "01_Users_1000", n, "Population size.", "Simulated population."),
        ("User Activity", "Active Users", "Users with ≥1 feature event", "COUNT DISTINCT user_id in events", "users", "—",
         "03_Feature_Events", act_users, "Users who did anything.", "Passive views count as activity."),
        ("User Activity", "Active User Rate", "Share of registered users who became active", "Active Users / Registered Users",
         "%", "Registered users", "01 + 03", pct(act_users, n), "Top-of-funnel health.", "Lifetime, not period-specific."),
        ("User Activity", "Active Days per Active User", "Mean distinct active calendar days", "SUM(active days) / Active Users",
         "days", "Active users", "03_Feature_Events", round(u.loc[u.is_active, "n_active_days"].mean(), 2),
         "Breadth of return over time.", "Tenure-dependent; median also reported "
         f"({u.loc[u.is_active, 'n_active_days'].median():.0f})."),
        ("User Activity", "Sessions per User", "Sessions per registered user", "Total Sessions / Registered Users", "sessions",
         "Registered users", "02_Sessions", sm["sessions_per_registered_user"], "Visit intensity.", "Includes zero-event sessions."),
        ("User Activity", "Sessions per Active User", "Sessions per active user", "Total Sessions / Active Users", "sessions",
         "Active users", "02_Sessions", sm["sessions_per_active_user"], "Visit intensity among actives.", "Skewed – median "
         f"{sm['median_sessions_per_active_user']:.0f}."),
        ("User Activity", "Events per Active User", "Clean feature events per active user", "Clean Events / Active Users", "events",
         "Active users", "03_Feature_Events (clean)", round(len(e) / act_users, 2), "Interaction volume.", "Mean is sensitive to duplicates."),
        ("User Activity", "Average DAU (last 30 days)", "Mean daily active users over the final 30 days", "AVG(daily distinct users)",
         "users/day", "Days", "03_Feature_Events", round(last30.dau.mean(), 2), "Current activity level.", "Grows with registered base."),
        ("User Activity", "DAU/MAU Stickiness (last 30 days)", "Average DAU ÷ distinct users active in the last 30 days",
         "AVG(DAU_30d) / MAU_30d", "%", "Users active in last 30 days", "03_Feature_Events", pct(last30.dau.mean(), mau30),
         "How often monthly actives come back.", "Single window at data end."),
        ("Session Behavior", "Average Session Duration", "Mean logged session window", "SUM(duration) / Sessions", "seconds",
         "All sessions", "02_Sessions", sm["avg_session_duration_s"], "Typical visit length.", "Windows end before tasks finish (DQ-022)."),
        ("Session Behavior", "Median Session Duration", "Median logged session window", "MEDIAN(duration)", "seconds",
         "All sessions", "02_Sessions", sm["median_session_duration_s"], "Robust visit length.", "Not an engagement-quality measure."),
        ("Session Behavior", "Events per Session", "Raw events per valid (event-backed) session", "Clean Events / Valid Sessions",
         "events", "Valid sessions", "02 + 03", sm["events_per_valid_session"], "Session depth.", "events_in_session field is invalid."),
        ("Session Behavior", "Features per Session", "Distinct features per valid session", "AVG(distinct features per session)",
         "features", "Valid sessions", "03_Feature_Events", sm["distinct_features_per_valid_session"], "Session breadth.", "—"),
        ("Session Behavior", "Repeat Session Rate", "Users with ≥2 sessions among users with a session", "Users(≥2 sessions) / Users(≥1)",
         "%", "Users with a session", "02_Sessions", sm["repeat_session_rate_pct"], "Visit repetition.", "Right-censored."),
        ("Session Behavior", "Zero-Event Session Rate", "Sessions with no feature events", "Sessions(0 events) / Sessions", "%",
         "All sessions", "02 + 03", pct(sm["zero_event_sessions"], sm["total_sessions"]), "Empty visits or tracking loss.", "Cause unknown."),
        ("Session Behavior", "Meaningful Session Rate", "Valid sessions with ≥1 meaningful completion", "Sessions(meaningful) / Valid Sessions",
         "%", "Valid sessions", "03_Feature_Events", sm["sessions_with_meaningful_pct"], "Productive visits.", "Event completions only."),
        ("Activation", f"Activation Rate ({W}-day)", f"First meaningful activity within {W} days of registration",
         f"Activated / Users registered ≥{W} days before data end", "%", "Eligible registrants", "01 + 03 + 05",
         R["activation"]["rate_pct"], "Primary activation KPI.", "Analyst definition; window chosen by capture curve."),
        ("Activation", "Early Activation Rate (7-day)", "First meaningful activity within 7 days", "Activated7 / Eligible7", "%",
         "Users registered ≥7 days before data end", "01 + 03 + 05", R["activation"]["rate_7d_pct"], "Speed of activation.", "—"),
        ("Activation", "Time to First Activity", "Median hours from registration to first feature event", "MEDIAN(first_event − registration)",
         "hours", "Active users", "01 + 03", round(u.hours_to_first_activity.median(), 1), "Onboarding delay.", "Excludes never-active users."),
        ("Activation", "Time to First Meaningful Activity", "Median hours from registration to first completed value action",
         "MEDIAN(first_meaningful − registration)", "hours", "Users with a meaningful activity", "01 + 03 + 05",
         round(u.hours_to_first_meaningful.median(), 1), "Activation speed.", "Depends on meaningful-activity definition."),
        ("Activation", "First Activity Rate", "Registered users with ≥1 feature event", "Active Users / Registered", "%",
         "Registered users", "01 + 03", pct(act_users, n), "Reach of first use.", "Same population as Active User Rate (lifetime)."),
        ("Activation", "First Session Rate", "Registered users with ≥1 session", "Users with session / Registered", "%",
         "Registered users", "01 + 02", pct(u.has_session.sum(), n), "Registration → login conversion.", "Session = login proxy."),
        ("Feature Engagement", "Feature Adoption Rate", "Share of active users using a feature (range across 15 features)",
         "Feature users / Active Users", "%", "Active users", "03_Feature_Events",
         f"{ft.share_of_active_users_pct.min()}–{ft.share_of_active_users_pct.max()}", "Feature reach.", "Exposure-level; see stages table."),
        ("Feature Engagement", "Feature Repeat Rate", "Feature users who used it in ≥2 sessions (range)", "Repeat users / Feature users",
         "%", "Feature users", "03_Feature_Events", f"{ft.repeat_usage_rate_pct.min()}–{ft.repeat_usage_rate_pct.max()}",
         "Stickiness of each feature.", "Volume-dependent."),
        ("Feature Engagement", "Feature Completion Rate", "Completion share of outcome events (Ads / CAPTCHA / Missions)",
         "Completions / (Completions + Skips/Fails/Abandons)", "%", "Outcome events", "03_Feature_Events",
         " / ".join(f"{r.feature} {r.event_completion_rate_pct}" for r in outcome.itertuples()), "Attempt success.",
         "Only 3 features log negative outcomes."),
        ("Feature Engagement", "Feature Abandonment Rate", "Negative-outcome share of outcome events",
         "Skips/Fails/Abandons / Outcome events", "%", "Outcome events", "03_Feature_Events",
         " / ".join(f"{r.feature} {r.event_abandonment_rate_pct}" for r in outcome.itertuples()), "Attempt friction.", "As above."),
        ("Feature Engagement", "Multi-Feature Usage Rate", f"Users completing ≥{th['multi_feature_min_completed_features']} distinct features",
         "Multi-feature users / Active Users", "%", "Active users", "03_Feature_Events", pct(u.is_multi_feature.sum(), act_users),
         "Breadth of value actions.", "Tied to activity volume."),
        ("Feature Engagement", "Task Completion Rate", "Completed / resolved task records", "Completed / (Completed+Failed+Abandoned)",
         "%", "Resolved tasks", "05_Task_Activity", to["completion_rate_resolved_pct"], "Task success.", "Pending excluded."),
        ("Feature Engagement", "Task Abandonment Rate", "Abandoned / resolved task records", "Abandoned / Resolved", "%",
         "Resolved tasks", "05_Task_Activity", to["abandonment_rate_resolved_pct"], "Task friction.", "Coarse failure reasons."),
        ("Feature Engagement", "Task Pending Rate", "Pending / all task records", "Pending / Tasks", "%", "All tasks",
         "05_Task_Activity", pct(to["pending"], to["records"]), "Validation backlog.", "No resolution timestamps."),
        ("Return", "D1 Return Rate", "Active on day 1 after first active day", "Returned D1 / Eligible", "%",
         "Users first active ≥1 day before data end", "03_Feature_Events", ret["D1_rate_pct"], "Next-day return.", "Calendar-dependent."),
        ("Return", "D7 Return Rate", "Active on any of days 1–7", "Returned D7 / Eligible", "%", "Users with full 7-day window",
         "03_Feature_Events", ret["D7_rate_pct"], "First-week return.", "Calendar-dependent."),
        ("Return", "D14 Return Rate", "Active on any of days 8–14", "Returned D14 / Eligible", "%", "Users with full 14-day window",
         "03_Feature_Events", ret["D14_rate_pct"], "Second-week return.", "Calendar-dependent."),
        ("Return", "D30 Return Rate", "Active on any of days 24–30", "Returned D30 / Eligible", "%", "Users with full 30-day window",
         "03_Feature_Events", ret["D30_rate_pct"], "Fourth-week return.", "Calendar-dependent."),
        ("Return", "Repeat User Rate", "Active users with ≥2 active days", "Users(≥2 days) / Active Users", "%", "Active users",
         "03_Feature_Events", pct((u.n_active_days >= 2).sum(), act_users), "Any return.", "Right-censored."),
        ("Engagement Depth", "Feature Diversity", "Mean distinct features used per active user", "AVG(distinct features)", "features",
         "Active users", "03_Feature_Events", round(u.loc[u.is_active, "n_features"].mean(), 2), "Breadth.", "Max 15."),
        ("Engagement Depth", "Activity Frequency", "Median gap between consecutive active days", "MEDIAN(date_i − date_{i−1})", "days",
         "Active-day pairs", "03_Feature_Events", sm["median_gap_between_active_days"], "Return cadence.", "Excludes one-day users."),
        ("Engagement Depth", "Engagement Score (median)", "Analyst-Created Simulated Engagement Score, median of active users",
         "Weighted sum of 6 scaled components", "0–100", "Active users", "Derived", round(u.loc[u.is_active, "engagement_score"].median(), 2),
         "Composite depth.", "NOT an official VELOOP metric."),
        ("Engagement Depth", "High-Frequency User Rate", f"Users with ≥{th['active_days_p75']} active days (P75)", "HF users / Active Users",
         "%", "Active users", "03_Feature_Events", pct((u.segment == "High-Frequency Users").sum(), act_users), "Core users.", "Tenure-dependent."),
        ("Engagement Depth", "One-Time User Rate", "Active users with exactly 1 active day", "One-time / Active Users", "%",
         "Active users", "03_Feature_Events", pct((u.n_active_days == 1).sum(), act_users), "Non-return.", "Right-censored."),
        ("Engagement Depth", "Regular Engagement Rate", f"Users active in ≥{th['regular_engagement_min_weeks']} distinct weeks",
         "Regular users / Active Users", "%", "Active users", "03_Feature_Events", pct(u.is_regular.sum(), act_users), "Habit.", "Tenure-dependent."),
        ("Engagement Depth", "Streak Consecutive-Claim Rate", "Streak claimers with claims on ≥2 consecutive days",
         "Users(consecutive) / Claimers", "%", "Streak claimers", "03_Feature_Events", R["progression"]["streak"]["pct_claimers_consecutive"],
         "Streak mechanic health.", "No streak state field."),
        ("Engagement Depth", "Level-Up Rate", "Active users with ≥1 level_up event", "Levellers / Active Users", "%", "Active users",
         "03_Feature_Events", R["progression"]["level"]["pct_active"], "Progression reach.", "No level/XP values."),
        ("Data Quality", "Session Counter Reconciliation Rate", "Sessions whose events_in_session equals raw event count",
         "Matching sessions / Sessions", "%", "All sessions", "02 vs 03", pct(sm["total_sessions"] - int(
             R["validation"]["issues"].set_index("check").loc["events_in_session ≠ raw event count", "count"]), sm["total_sessions"]),
         "Pipeline integrity.", "Raw events assumed correct."),
    ]
    kpi = pd.DataFrame(rows, columns=["category", "kpi_name", "definition", "formula", "unit", "denominator", "data_source",
                                      "current_value_simulated", "interpretation", "limitation"])
    kpi.insert(0, "kpi_id", [f"KPI-{i + 1:02d}" for i in range(len(kpi))])
    kpi["current_value_simulated"] = kpi.current_value_simulated.astype(str)
    save_table(kpi, "kpi_catalogue")

    # ------------------------------------------------------------------ metric reconciliation
    # Pairs of metrics that look alike but differ by definition/denominator, with the reason.
    fn = R["activation"]["funnel"].set_index("canonical_stage")
    dm = R["dropoff"]["matrix"]
    d30 = dm[dm.stage.str.startswith("First active day → second")].iloc[0]
    has_s = int(u.has_session.sum())
    one_sess = int((u.n_sessions == 1).sum())
    one_day = int((u.n_active_days == 1).sum())
    multi_sess_one_day = int(((u.n_sessions >= 2) & (u.n_active_days == 1)).sum())
    ef = R["dropoff"]["engagement_funnel"].set_index("canonical_stage")
    rt = R["retention"]["overall"]
    rg = R["retention"]["overall_registration_anchor"]
    ev_field = R["validation"]["events_in_session_field_mean"]
    rec = [
        ("Registered users vs active users", f"{n:,}", f"{act_users:,}",
         "All accounts vs accounts with ≥1 feature event.",
         f"{n - act_users} registered users never opened a session or used a feature."),
        ("One-session users vs one-time (1 active day) users", f"{one_sess}", f"{one_day}",
         "≥1 session counted per session vs per calendar day.",
         f"{multi_sess_one_day} users had 2+ sessions, all on the same day: one-time by days, not by sessions."),
        ("Repeat-session rate vs repeat-user rate", f"{sm['repeat_session_rate_pct']}% ({int(sm['repeat_session_users'])}/{has_s})",
         f"{pct((u.n_active_days >= 2).sum(), act_users)}% ({int((u.n_active_days >= 2).sum())}/{act_users})",
         "≥2 sessions vs ≥2 distinct active days.", "Same reason as above (several sessions on one day)."),
        ("Repeat-user rate (KPI) vs 'Returned' (funnel)", f"{int((u.n_active_days >= 2).sum())} users",
         f"{int(fn.loc['Returned (2nd active day)', 'users'])} users",
         "Identical rule: ≥2 active days.", "Equal by construction – shown to confirm consistency."),
        ("Returned vs Established", f"{int(fn.loc['Returned (2nd active day)', 'users'])}",
         f"{int(fn.loc['Established (≥3 meaningful days)', 'users'])}",
         "≥2 active days vs meaningful activity on ≥3 days.", "Established is the stricter next funnel step."),
        ("Multi-feature: KPI (standalone) vs funnel (cumulative)",
         f"{int(u.is_multi_feature.sum())} ({pct(u.is_multi_feature.sum(), act_users)}% of active)",
         f"{int(ef.loc['Multi-feature', 'users'])}",
         "Meets the breadth rule vs meets it AND every earlier funnel stage.",
         "The funnel only counts multi-feature users who also returned."),
        ("Regular engagement: standalone vs funnel (cumulative)",
         f"{int(u.is_regular.sum())} ({pct(u.is_regular.sum(), act_users)}% of active)",
         f"{int(ef.loc['Regular (≥3 active weeks)', 'users'])}",
         "≥3 active weeks vs ≥3 active weeks AND multi-feature AND returned.",
         "Cumulative counts shrink at every stage; standalone counts do not."),
        ("Completed a meaningful activity (ever) vs activation rate",
         f"{int(fn.loc['Completed a meaningful activity', 'users'])} users ({fn.loc['Completed a meaningful activity', 'pct_of_registered']}%)",
         f"{R['activation']['rate_pct']}% ({R['activation']['activated']}/{R['activation']['eligible']})",
         f"Any time in the window vs within {W} days of registration, eligible users only.",
         "Most users eventually complete something, but many only after the activation window."),
        ("Repeat-user rate (ever) vs D7 return", f"{pct((u.n_active_days >= 2).sum(), act_users)}%",
         f"{rt['D7_rate_pct']}% ({rt['D7_returned']}/{rt['D7_eligible']})",
         "Any second active day, ever vs a return within days 1–7 after the first active day.",
         "Returning eventually is far more common than returning within the first week."),
        ("One-time users (all time) vs one-day users in first 30 days",
         f"{pct(one_day, act_users)}% ({one_day}/{act_users})",
         f"{d30.drop_off_pct}% ({int(d30.drop_off)}/{int(d30.entering)})",
         "All active users, lifetime vs users with ≥30 observable days, first 30 days only.",
         "The 30-day version removes right-censoring and is the fairer comparison."),
        ("Sessions per user: registered vs active denominator", f"{sm['sessions_per_registered_user']}",
         f"{sm['sessions_per_active_user']}", "Sessions ÷ 1,000 registered vs ÷ active users.",
         "Denominator stated wherever the metric appears."),
        ("Events per session: session-sheet field vs raw events", f"{ev_field:.2f}", f"{sm['events_per_valid_session']}",
         "events_in_session field vs clean raw events ÷ valid sessions.",
         "The field does not reconcile with raw events (DQ-016) and is not used anywhere."),
        ("D7 return: first-active anchor vs registration anchor", f"{rt['D7_rate_pct']}%", f"{rg['D7_rate_pct']}%",
         "Days 1–7 after first active day vs after registration date.",
         "Primary metric uses the first active date; the registration version is a labelled comparison only."),
    ]
    recon = pd.DataFrame(rec, columns=["metrics_compared", "value_a", "value_b", "definition_difference", "explanation"])
    recon.insert(0, "id", [f"REC-M{i + 1:02d}" for i in range(len(recon))])
    save_table(recon, "metric_reconciliation")
    ctx.R["kpis"] = {"catalogue": kpi, "count": len(kpi), "reconciliation": recon}
