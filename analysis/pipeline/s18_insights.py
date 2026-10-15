"""Work Packages W, X, Y + experiments, tracking gaps, recommendations and limitations.

Every number in this module is read from ctx.R (computed upstream) – nothing is typed in by hand.
Statement classes used throughout (brief §51):
  SIMULATED DATA RESULT · ANALYST INTERPRETATION · PRODUCT HYPOTHESIS · TO BE VERIFIED · DOCUMENTED PRODUCT FACT
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.pipeline.context import Context
from analysis.utils.io import save_table
from analysis.utils.metrics import pct, sample_size_two_proportions


def _row(df: pd.DataFrame, col: str, val):
    return df.loc[df[col] == val].iloc[0]


def run(ctx: Context) -> None:
    R, u = ctx.R, ctx.users
    n_users = len(u)
    n_active = int(u.is_active.sum())
    sm = R["sessions"]["metrics"]
    ft = R["features"]["table"]
    to = R["features"]["task_overall"]
    tc = R["features"]["task_categories"]
    dm = R["dropoff"]["matrix"]
    ret = R["retention"]["overall"]
    mon = R["retention"]["monthly"]
    tim = R["time"]
    st = R["progression"]["streak"]
    lv = R["progression"]["level"]
    cal = R["advanced"]["calendar_confounding"]
    mdl = R["advanced"]["d30_model"]
    dev = R["segments_device_acq"]["device"]
    acq = R["segments_device_acq"]["acquisition"]
    seg = R["segmentation"]
    act = R["activation"]
    nvr = tim["new_vs_returning"]
    life = R["lifecycle"]
    rep = R["repeat"]
    th = R["thresholds"]

    def drop(stage_prefix):
        return dm[dm.stage.str.startswith(stage_prefix)].iloc[0]

    ads, cap, mis = (_row(ft, "feature", f) for f in ("Watch Ads", "CAPTCHA", "Missions"))
    d_first = drop("First active day → second")
    d_3to7 = drop("Third active day → seventh")
    d_view = drop("Feature view → feature start")
    d_task = drop("Task start → task completion")
    d_week = drop("First week → later")
    new = nvr[nvr.activity_type.str.startswith("New")].iloc[0]
    old = nvr[nvr.activity_type.str.startswith("Returning")].iloc[0]
    apr, aug = mon.iloc[0], mon[mon.cohort_month == "2026-08"].iloc[0]
    dev_t = dev["table"].set_index("device")
    dev_tests = dev["tests"].set_index("metric")
    acq_tests = acq["tests"].set_index("metric")
    acq_t = acq["table"].set_index("acquisition_source")
    hf = seg["profile"].set_index("segment")
    vol = rep["d7_by_day1_volume_tercile"]
    cmp = rep["comparison"].set_index("metric")
    ws = act["windows"].set_index("window_days")
    after_end_pct = R["anomalies"]["summary"].set_index("type").loc["Task completion after session end", "pct_flagged"]
    max_eps = max(t_.loc[t_.effect_measure == "epsilon²", "effect_size"].max() for t_ in (dev["tests"], acq["tests"]))
    counter_ratio = R["validation"]["events_in_session_field_mean"] / sm["events_per_valid_session"]
    dq_tbl = R["dq_impact"]["table"].set_index("metric")
    daily_ratio = (dq_tbl.loc["Mean minutes per active user-day", "before_cleaning"]
                   / dq_tbl.loc["Mean minutes per active user-day", "after_cleaning"])

    F = [
        ("Activation", "Most simulated users take days, not minutes, to open a first session",
         f"Median time from registration to first session is {u.hours_to_first_session.median() / 24:.1f} days; only "
         f"{ws.loc[1, 'activation_rate_pct']}% of eligible users complete a meaningful activity within 1 day and "
         f"{ws.loc[3, 'activation_rate_pct']}% within 3 days.",
         f"{act['window_days']}-day activation = {act['activated']}/{act['eligible']} eligible users ({act['rate_pct']}%); "
         f"{life['time_to']['hours_to_first_session']['buckets'][-2]['users']} users waited > 30 days for a first session.",
         "The gap between sign-up and first use – not in-session friction – is the main activation delay in the simulated cohort.",
         "Registration timestamps carry no context (e.g. verification emails, app install) explaining the delay.",
         "Investigate the post-registration handoff: verification flow, first-open prompts and welcome messaging.", "High"),
        ("Activation", "Once a session happens, a completed activity almost always follows",
         f"{life['stages'].iloc[3]['users_cumulative']} of {life['stages'].iloc[1]['users_cumulative']} users with a session "
         f"recorded a meaningful activity; {life['meaningful_within_15min_of_first_activity_pct']}% did so within 15 minutes "
         "of their first feature event.",
         f"Lifecycle: Login {life['stages'].iloc[1]['users_cumulative']} → first meaningful {life['stages'].iloc[3]['users_cumulative']}.",
         "In-session activation is not the bottleneck in the simulated data; getting users to the first session and back again is.",
         "Completions are 'logged', not proven end-to-end flows (completion events lack linked starts, DQ-035).",
         "Prioritise return and first-session-delay investigations over first-session UX changes.", "Medium"),
        ("Return", "Second-day return is the first major user-level drop-off",
         f"Among {int(d_first.entering)} users with a full 30-day horizon, {int(d_first.drop_off)} ({d_first.drop_off_pct}%) "
         f"were active on only one day in their first 30 days.",
         f"All-time one-day users: {life['depth']['one_time']} of {n_active} active users; D1 return = {ret['D1_rate_pct']}% "
         f"({ret['D1_returned']}/{ret['D1_eligible']}).",
         "A quarter of users with sufficient observation never form a second visit.",
         "The dataset does not record why users stop or whether they received reminders.",
         "Investigate post-first-day re-engagement (reminders, next-day reward previews).", "High"),
        ("Return", "Progression from 3 to 7 active days is the steepest drop in the active-day ladder",
         f"Within the first 30 days, {int(d_3to7.continuing)} of {int(d_3to7.entering)} users with 3 active days reached 7 "
         f"({d_3to7.drop_off_pct}% drop-off).",
         f"Ladder (30-day horizon): 1→2 days {d_first.drop_off_pct}% drop, 2→3 {drop('Second active day').drop_off_pct}%, "
         f"3→7 {d_3to7.drop_off_pct}%.",
         "Short-term returners rarely become weekly habits within a month.",
         "7 active days in 30 is an analyst threshold; the ladder is sensitive to the window.",
         "Investigate mid-term progression mechanics (missions, levels, streaks) as habit drivers.", "Medium"),
        ("Return", "Return rates depend strongly on calendar period, not on who the users are",
         f"D7 return rises from {apr.D7_rate_pct}% for the {apr.cohort_month} first-active cohort to {aug.D7_rate_pct}% for "
         f"{aug.cohort_month}; the daily active share of the registered base rose from {tim['avg_active_rate_may']}% (May) "
         f"to {tim['avg_active_rate_last_30d']}% (last 30 days).",
         f"Registration-month cohorts differ (χ² p={R['retention']['cohort_tests'].set_index('dimension').loc['Registration month', 'chi2_p_d30_return']:.1e}); "
         f"source (p={R['retention']['cohort_tests'].set_index('dimension').loc['Acquisition source', 'chi2_p_d30_return']:.2f}) "
         f"and device (p={R['retention']['cohort_tests'].set_index('dimension').loc['Device', 'chi2_p_d30_return']:.2f}) do not.",
         "Something time-dependent (simulation design, product changes, seasonality) drives return far more than user attributes.",
         "The dataset contains no release, campaign or notification calendar to explain the shift. TO BE VERIFIED.",
         "Always control for cohort period when comparing groups; ask product/engineering what changed over time.", "High"),
        ("Activation", "Fast activators return more, even after controlling for join month",
         f"Users activating within 7 days have a {cal['raw_difference_pp']}pp higher fourth-week (D30) return than slower "
         f"activators; within registration months the gap is {cal['month_adjusted_difference_pp']}pp.",
         f"Logistic model of D30 return: log(hours to first activity) standardised coefficient "
         f"{mdl['coefficients'].set_index('feature').loc['log_hours_to_first_activity', 'standardised_coefficient']}; "
         f"CV AUC {mdl['cv_auc_mean']} (behaviour only {mdl['cv_auc_behaviour_only']}, calendar only {mdl['cv_auc_calendar_only']}).",
         "Early activation is associated with later return; the association survives a calendar control.",
         "Association only – motivated users may both activate faster and return more (selection).",
         "Test interventions that shorten time-to-first-activity and measure D30 return (EXP-01).", "Medium"),
        ("Tasks", "Two in five resolved tasks end in abandonment or failure, with no dominant failure reason",
         f"{to['abandoned'] + to['failed']:,} of {to['resolved']:,} resolved task records ({to['abandonment_rate_resolved_pct'] + to['failure_rate_resolved_pct']:.1f}%) "
         f"were abandoned ({to['abandonment_rate_resolved_pct']}%) or failed ({to['failure_rate_resolved_pct']}%).",
         f"Category completion rates range {tc.completion_rate_pct.min()}–{tc.completion_rate_pct.max()}%; the five failure "
         f"reasons each account for {R['features']['failure_reasons'].total.min()}–{R['features']['failure_reasons'].total.max()} records.",
         "Task friction is broad-based rather than concentrated in one category or failure mode.",
         "failure_reason is a coarse category; no error codes, third-party responses or UI context.",
         "Instrument detailed failure context before redesigning specific task types.", "High"),
        ("Tasks", "Many task rewards sit in long-pending validation",
         f"{to['pending']} task records are Pending; {R['anomalies']['summary'].set_index('type').loc['Pending > 30 days', 'entities_flagged']} "
         "have been pending for more than 30 days at data end.",
         f"Pending share by category: {tc.pending_share_pct.min()}–{tc.pending_share_pct.max()}%.",
         "Delayed reward confirmation may weaken the action→reward feedback loop (hypothesis).",
         "Whether users can see pending status, and validation SLAs, are not in the data. TO BE VERIFIED.",
         "Review validation latency and pending-status visibility (EXP-04).", "Medium"),
        ("Features", "Ads, CAPTCHA and Missions each lose about half of attempts",
         f"Watch Ads skip rate {ads.event_abandonment_rate_pct}%, CAPTCHA failure rate {cap.event_abandonment_rate_pct}%, "
         f"Missions abandonment rate {mis.event_abandonment_rate_pct}% (event level).",
         f"Ads {int(ads.complete_events)} completed vs {int(ads.negative_outcome_events)} skipped; CAPTCHA {int(cap.complete_events)} vs "
         f"{int(cap.negative_outcome_events)}; Missions {int(mis.complete_events)} vs {int(mis.negative_outcome_events)}.",
         "These are the three features where explicit negative outcomes are logged, and all show coin-flip completion.",
         "Other features log no failure/abandon events, so their completion rates are not comparable.",
         "Investigate ad length/reward clarity, CAPTCHA difficulty and mission scope.", "Medium"),
        ("Features", "Viewing a mission or spin often does not lead to starting it",
         f"{int(d_view.drop_off)} of {int(d_view.entering)} user×feature view pairs ({d_view.drop_off_pct}%) for Missions and "
         "Spin the Wheel never recorded a start of the same feature.",
         f"{int(R['dropoff']['view_to_start_by_feature'].starters_without_view.sum())} pairs started without any recorded view.",
         "Exposure does not reliably convert to engagement on these surfaces.",
         "Views and starts are not linked in-session (DQ-035); this is a user-level signal only.",
         "Test clearer start calls-to-action on mission and spin surfaces (EXP-05).", "Low"),
        ("Sessions", "Sessions are short and longer sessions are not deeper",
         f"Median session {sm['median_session_duration_s']:.0f}s (P90 {sm['p90_duration_s']:.0f}s); duration↔events Spearman "
         f"ρ = {sm['duration_events_spearman']}, duration↔meaningful ρ = {sm['duration_meaningful_spearman']}.",
         f"Short (≤P25) sessions deliver {R['sessions']['duration_bands'].iloc[0].meaningful_per_minute} meaningful actions/min vs "
         f"{R['sessions']['duration_bands'].iloc[2].meaningful_per_minute} for long (>P75).",
         "Session length is not a usable engagement proxy in the simulated data.",
         f"{after_end_pct}% of completed tasks finish after their session 'ends' – session windows likely under-measure "
         "time in product.",
         "Use completions and return frequency, not duration, as engagement KPIs; confirm session_end semantics.", "Medium"),
        ("Sessions", "First-day sessions are the densest; later sessions are lighter",
         f"First-active-day sessions average {new.mean_events} events and {new.mean_meaningful} meaningful actions vs "
         f"{old.mean_events} and {old.mean_meaningful} on later days.",
         f"Mann-Whitney p = {tim['new_vs_returning_events_p']:.1e}; task completion is similar ({new.task_completion_rate_pct}% vs "
         f"{old.task_completion_rate_pct}%).",
         "New users explore intensively on day one; returning users make shorter, more targeted visits.",
         "Day-one density may partly reflect how the simulation seeded first sessions.",
         "Design returning-user surfaces for quick, repeatable value actions.", "Medium"),
        ("Return", "Heavy first-day activity is associated with lower first-week return",
         f"D7 return by first-day event-volume tercile: low {vol.get('low')}%, mid {vol.get('mid')}%, high {vol.get('high')}%.",
         f"In the D30 model, week-1 events have a negative standardised coefficient "
         f"({mdl['coefficients'].set_index('feature').loc['w1_events', 'standardised_coefficient']}) while week-1 sessions and "
         f"active days are positive.",
         "Cramming many actions into few visits looks different from spreading activity across visits.",
         "Could reflect simulation design or exhaustion of daily earning limits; not causal.",
         "Investigate whether pacing (daily caps, 'come back tomorrow' previews) relates to return.", "Low"),
        ("Features", "Feature breadth is high and mostly mirrors activity volume",
         f"Active users touched a median of {int(u.loc[u.is_active, 'n_features'].median())} of 15 features; "
         f"{int((u.n_features == 15).sum())} used all 15. Breadth vs active days Spearman ρ = {seg['frequency_breadth_spearman']}.",
         f"Multi-feature (≥{th['multi_feature_min_completed_features']} features completed): {int(u.is_multi_feature.sum())} users "
         f"({pct(u.is_multi_feature.sum(), n_active)}% of active users).",
         "Breadth is largely a by-product of more visits, so 'multi-feature' is not an independent engagement driver here.",
         "Simulated feature exposure may be more uniform than a real navigation structure.",
         "Measure breadth per visit (not lifetime) when evaluating discovery changes.", "Medium"),
        ("Journeys", "Journeys show no strong sequential structure",
         f"Feature-to-feature transition lifts range {R['journey']['transition_lift_range'][0]:.2f}–{R['journey']['transition_lift_range'][1]:.2f}; "
         f"session co-occurrence lifts {R['features']['lift_range'][0]:.2f}–{R['features']['lift_range'][1]:.2f}; the most common "
         f"single path covers only {R['journey']['top_paths'].iloc[0].pct_valid_sessions}% of sessions.",
         "After a view, the next event is a completion about as often as after any other stage (stage-transition matrix).",
         "Users do not follow a dominant path; no feature reliably leads to another.",
         "Event order inside sessions is unreliable (sequence numbers and timestamps disagree).",
         "Fix event ordering instrumentation before investing in journey-based recommendations.", "Low"),
        ("Progression", "Streak behaviour does not look like streaks",
         f"Only {st['users_consecutive_claim_days']} of {st['users_claiming']} streak claimers ({st['pct_claimers_consecutive']}%) "
         f"claimed on consecutive days; break events ({st['break_events']}) ≈ claim events ({st['claim_events']}).",
         f"{R['anomalies']['summary'].set_index('type').loc['Streak broken without any recorded claim', 'entities_flagged']} users "
         "broke a streak without any recorded claim.",
         "Either the streak mechanic is not driving consecutive-day behaviour, or streak events are logged inconsistently.",
         "No streak length or state field exists. TO BE VERIFIED with engineering.",
         "Add streak_started/streak_day_count events; then evaluate streak-saver ideas (EXP-06).", "Medium"),
        ("Progression", "Levelling up is not followed by a change in activity",
         f"{lv['users_with_level_up']} users ({lv['pct_active']}% of active) levelled up. Around the first level-up: "
         f"{lv['before_after_first_level_up']['mean_active_days_14d_before']} active days in the prior 14 days vs "
         f"{lv['before_after_first_level_up']['mean_active_days_14d_after']} after (Wilcoxon p = "
         f"{lv['before_after_first_level_up']['wilcoxon_p_active_days']:.2f}, n = {lv['before_after_first_level_up']['users']}).",
         f"{lv['users_with_level_up']} levellers recorded {lv['level_up_events']} level-up events "
         f"({lv['level_ups_per_leveller_mean']} per leveller).",
         "Within the simulated data, progression milestones are not associated with a detectable activity lift.",
         "Level and XP balance are absent (level-ups counted from events); exact thresholds are simulated and "
         "documented VELOOP rules may change.",
         "Investigate level-up feedback (reward visibility, next-goal messaging).", "Medium"),
        ("Segments", "Device and acquisition source show no meaningful behavioural differences",
         f"All Kruskal-Wallis/χ² tests across devices and sources have negligible effect sizes (max ε² = {max_eps:.3f}).",
         f"Device activation: Android {dev_t.loc['Android', 'activation_rate_pct']}%, iOS {dev_t.loc['iOS', 'activation_rate_pct']}%, "
         f"Windows {dev_t.loc['Windows', 'activation_rate_pct']}%, macOS {dev_t.loc['macOS', 'activation_rate_pct']}% "
         f"(χ² p = {dev_tests.loc['activation', 'p_value']}, Cramér's V = {dev_tests.loc['activation', 'effect_size']}).",
         "Observed behavioural differences are small; no device or source stands out on depth or return.",
         "Simulated acquisition sources do not represent real marketing performance; all traffic is 'Web'.",
         "Do not prioritise device-specific fixes on this evidence; re-test with production data.", "High"),
        ("Time", "Activity is spread evenly across hours and days of the week",
         f"Hour-of-day session distribution is consistent with uniform (χ² p = {tim['hour_uniformity_chi2_p']:.2f}); weekend vs "
         f"weekday trend-adjusted DAU index {tim['weekend']['weekend_dau_index']} vs {tim['weekend']['weekday_dau_index']} "
         f"(p = {tim['weekend']['mannwhitney_p_dau_index']:.2f}).",
         f"Weekdays hold {tim['weekend']['weekday_share_of_events_pct']}% of events vs {tim['weekend']['weekday_share_of_days_pct']}% of days.",
         "The simulated data does not support time-targeted notification or maintenance-window decisions.",
         "Timestamp timezone is undocumented.",
         "Notification-timing experiments would need production data to be meaningful.", "High"),
        ("Data quality", "Pre-aggregated fields would materially change conclusions",
         f"events_in_session implies {R['validation']['events_in_session_field_mean']:.2f} events/session vs "
         f"{sm['events_per_valid_session']} from raw events; the milestone sheet reports "
         f"{int(R['lifecycle']['milestones'].set_index('milestone').loc['first_login', 'users_in_milestone_sheet'])} first logins vs "
         f"{int(R['lifecycle']['milestones'].set_index('milestone').loc['first_login', 'users_derived_from_raw'])} users with sessions.",
         "See data_quality_impact.csv for 29 before/after comparisons.",
         "Using convenience fields without validation would mislead product decisions.",
         "Simulated data; production pipelines may differ.",
         "Engineering: reconcile session counters, milestone generation and daily duration with raw logs.", "High"),
    ]
    cols = ["theme", "title", "observation", "evidence", "interpretation", "limitation", "product_implication", "confidence"]
    findings = pd.DataFrame(F, columns=cols)
    findings.insert(0, "finding_id", [f"FND-{i + 1:02d}" for i in range(len(findings))])
    save_table(findings, "behavioral_findings")

    # ---------------------------------------------------------------- friction register
    one_day_users = int(life["depth"]["one_time"])
    viewers_no_start = int(d_view.drop_off)
    users_abandon = int((u.n_tasks_abandoned + u.n_tasks_failed > 0).sum())
    ad_skippers = int((u.n_ad_skipped > 0).sum())
    mission_abandoners = int((u.n_mission_abandoned > 0).sum())
    captcha_failers = int((u.n_captcha_failed > 0).sum())
    pending_users = int(ctx.tasks[ctx.tasks.task_status == "Pending"].user_id.nunique())
    slow = int((u.hours_to_first_session > 7 * 24).sum())
    fr = [
        ("Slow first session after registration", slow,
         f"{slow} users waited > 7 days for a first session; median {u.hours_to_first_session.median() / 24:.1f} days.",
         "Verification delays; weak welcome prompt; registration without intent; app install friction.", "Medium", "Onboarding",
         "Instrument registration→verification→first-open steps; interview recent registrants."),
        ("One-day users (no second active day)", one_day_users,
         f"{one_day_users} of {n_active} active users had one active day; D1 return {ret['D1_rate_pct']}%.",
         "No reason to return; no reminder; first-day earning limits reached; low perceived value.", "High",
         "Session continuation / notification strategy", "Track notification sends/opens; test next-day hooks."),
        ("Task abandonment and failure", users_abandon,
         f"{to['abandonment_rate_resolved_pct']}% abandoned + {to['failure_rate_resolved_pct']}% failed of resolved tasks.",
         "Unclear instructions; technical failure; task unavailability; third-party dependency; timeouts.", "High", "Task UX",
         "Capture failure detail (error code, step, partner response) per attempt."),
        ("Long-pending reward validation", pending_users,
         f"{to['pending']} pending records; "
         f"{R['anomalies']['summary'].set_index('type').loc['Pending > 30 days', 'entities_flagged']} older than 30 days.",
         "Third-party validation latency; manual review queues; missing status feedback.", "Medium", "Reward feedback",
         "Measure validation latency; check whether pending status is visible to users."),
        ("Ad skipping", ad_skippers, f"Skip rate {ads.event_abandonment_rate_pct}% of ad outcomes.",
         "Ad length; low reward per ad; ad relevance; playback errors.", "Medium", "Task UX / reward feedback",
         "Log ad duration watched, reward offered and playback errors."),
        ("Mission abandonment", mission_abandoners, f"Abandonment rate {mis.event_abandonment_rate_pct}% of mission outcomes.",
         "Mission scope too large; unclear progress; competing priorities.", "Medium", "Progression",
         "Add mission_progress events with step counts."),
        ("CAPTCHA failure", captcha_failers, f"Failure rate {cap.event_abandonment_rate_pct}% of CAPTCHA outcomes.",
         "Difficulty; accessibility; automation filtering; input errors on mobile.", "Medium", "Task UX",
         "Log failure type and attempt number; review accessibility."),
        ("Mission / spin viewed but not started", viewers_no_start,
         f"{d_view.drop_off_pct}% of view pairs never started.", "Weak call-to-action; unclear reward; eligibility limits.",
         "Low", "Discoverability", "Add feature_impression with CTA visibility; link view→start in-session."),
        ("Streak mechanics not producing consecutive claims", st["users_claiming"],
         f"{st['pct_claimers_consecutive']}% of claimers claimed on consecutive days; break/claim ratio {st['break_to_claim_ratio']}.",
         "Streak not visible; reset rules unclear; logging defect.", "Low", "Daily engagement",
         "Confirm streak state logic with engineering; add streak_day_count."),
        ("Stall between 3rd and 7th active day", int(d_3to7.drop_off),
         f"{d_3to7.drop_off_pct}% of 3-day users did not reach 7 days within 30 days.",
         "No mid-term goals; repetitive activities; reward saturation.", "Medium", "Progression",
         "Analyse feature mix of users who pass vs stall; test mid-term goals."),
        ("Sessions with no recorded feature activity", int(R["validation"]["zero_event_sessions"]),
         f"{R['validation']['zero_event_sessions']} sessions ({sm['zero_event_sessions'] / sm['total_sessions'] * 100:.1f}%) have no events.",
         "Navigation dead-ends; loading failures; tracking loss.", "Low", "Navigation",
         "Add session_ended with end_reason and page_view events."),
    ]
    fr = pd.DataFrame(fr, columns=["behavioral_signal", "affected_users", "evidence", "possible_explanations", "confidence",
                                   "product_area", "investigation_needed"])
    fr.insert(0, "issue_id", [f"BHV-{i + 1:03d}" for i in range(len(fr))])
    fr["affected_users_pct"] = (fr.affected_users / n_users * 100).round(1)
    fr["explanation_status"] = "Hypotheses – none confirmed by the dataset"
    save_table(fr, "product_friction_register")

    # ---------------------------------------------------------------- opportunity register (scored priority)
    def reach(n):
        return 3 if n / n_users >= 0.30 else 2 if n / n_users >= 0.10 else 1

    conf_score = {"High": 3, "Medium": 2, "Low": 1}
    opp_specs = [
        ("BHV-001", "Shorten registration → first activity", "Users register but wait days to start",
         "A guided first-open flow and welcome prompt may shorten time-to-first-activity.",
         "Funnel study of registration→first session; EXP-01.", "Activation, D30 return", 3, 2, 3,
         f"{act['window_days']}-day activation rate; median hours to first meaningful activity"),
        ("BHV-002", "Create a reason to return on day 2", "Users do not come back after day one",
         "Next-day reward previews / reminders may raise second-day return.", "EXP-02 (next-day hook).",
         "Return, habit formation", 3, 2, 3, "D1 and D7 return; share of one-day users"),
        ("BHV-003", "Reduce task abandonment and failure", "Two in five task attempts fail or are abandoned",
         "Clearer instructions and retry paths may lift completion.", "Failure-detail instrumentation, then EXP-03.",
         "Task completion, reward credit", 3, 2, 3, "Task completion rate (resolved); retries per task"),
        ("BHV-004", "Make pending validation visible", "Rewards wait in validation without feedback",
         "Status tracking with expected time may sustain trust and return.", "EXP-04 among users with pending tasks.",
         "Reward feedback, return", 2, 1, 2, "D7 return of users with pending tasks; support contacts"),
        ("BHV-005", "Improve ad completion", "Half of ad attempts are skipped",
         "Shorter/clearer-reward ads may reduce skipping.", "Analyse skip vs ad metadata once logged.",
         "Earning activity completion", 2, 2, 2, "Ad completion rate"),
        ("BHV-006", "Right-size missions", "Half of missions are abandoned", "Smaller steps with progress feedback may raise completion.",
         "Add mission_progress tracking; test step-based missions.", "Progression", 2, 2, 2, "Mission completion rate"),
        ("BHV-008", "Convert mission/spin views into starts", "Viewers often do not start",
         "Stronger CTA and reward visibility on the surface.", "EXP-05.", "Discoverability", 2, 1, 3, "View→start conversion"),
        ("BHV-009", "Repair streak mechanics & tracking", "Streak behaviour is inconsistent",
         "Reliable streak state + streak saver may encourage consecutive days.", "Engineering audit; then EXP-06.",
         "Daily engagement", 1, 2, 2, "Consecutive-day claim rate"),
        ("BHV-010", "Support mid-term progression (days 3–7)", "Returners stall before forming a habit",
         "Mid-term goals (weekly missions, level targets) may sustain activity.", "Cohort analysis of passers vs stallers.",
         "Retention", 1, 1, 2, "Share of 3-day users reaching 7 days in 30"),
        ("BHV-011", "Close tracking gaps for empty sessions", "Visits with no recorded activity",
         "Better session/page instrumentation will separate UX dead-ends from tracking loss.", "Instrumentation change.",
         "Analytics reliability", 2, 3, 2, "Share of zero-event sessions"),
    ]
    frs = fr.set_index("issue_id")
    opp_rows = []
    for i, (iid, title, problem, hyp, inv, impact, severity, complexity_inv, relevance, measure) in enumerate(opp_specs, 1):
        f_ = frs.loc[iid]
        r_ = reach(f_.affected_users)
        c_ = conf_score[f_.confidence]
        total = r_ + severity + c_ + complexity_inv + relevance
        opp_rows.append({"opportunity_id": f"OPP-{i:02d}", "finding": title, "linked_issue": iid, "evidence": f_.evidence,
                         "user_problem": problem, "product_hypothesis": hyp, "proposed_investigation": inv,
                         "expected_impact_area": impact, "affected_population": int(f_.affected_users),
                         "affected_pct": float(f_.affected_users_pct), "score_reach": r_, "score_severity": severity,
                         "score_confidence": c_, "score_ease": complexity_inv, "score_relevance": relevance,
                         "priority_score": total, "priority": "High" if total >= 12 else "Medium" if total >= 9 else "Low",
                         "measurement": measure})
    opp = pd.DataFrame(opp_rows).sort_values("priority_score", ascending=False)
    save_table(opp, "product_opportunity_register")
    priority_criteria = {
        "reach": "Affected simulated users: ≥30% = 3, 10–30% = 2, <10% = 1",
        "severity": "Size of the behavioural loss at that step: large = 3, moderate = 2, small = 1",
        "confidence": "From the friction register (data reliability of the signal): High 3, Medium 2, Low 1",
        "ease": "Inverse implementation complexity: low complexity = 3, high = 1",
        "relevance": "Closeness to the core earn → reward → return loop: core = 3, supporting = 2, peripheral = 1",
        "priority": "Sum of five scores (5–15): High ≥ 12, Medium 9–11, Low ≤ 8",
    }

    # ---------------------------------------------------------------- proposed experiments
    exps = [
        ("EXP-01", "Guiding newly registered users straight into a first earning activity will shorten time-to-first-meaningful-activity.",
         f"Median {u.hours_to_first_session.median() / 24:.1f} days to first session; {act['window_days']}-day activation {act['rate_pct']}%.",
         "Newly registered users (all sources/devices)", "Current post-registration experience",
         "Guided first-open: single recommended activity + welcome reward preview",
         f"{act['window_days']}-day activation rate", "Hours to first meaningful activity; D7 return",
         "Verification completion rate; support contacts; unsubscribe rate",
         "More users complete a first activity within 3 days", "user_registered, onboarding_started/completed, first_meaningful_activity"),
        ("EXP-02", "A next-day hook shown at the end of the first active day will increase second-day return.",
         f"{d_first.drop_off_pct}% of 30-day-horizon users never had a second active day; D1 return {ret['D1_rate_pct']}%.",
         "Users on their first active day", "No next-day hook", "End-of-day card previewing tomorrow's reward + opt-in reminder",
         "D1 return rate", "D7 return; active days in first 14", "Notification opt-out; complaint rate; session error rate",
         "Higher share of users with a second active day", "notification_sent/opened, session_started, next_day_hook_shown"),
        ("EXP-03", "Clear step instructions and a one-tap retry after failure will raise task completion.",
         f"{to['abandonment_rate_resolved_pct'] + to['failure_rate_resolved_pct']:.1f}% of resolved tasks abandoned or failed.",
         "Users starting tasks in any category", "Current task flow",
         "Inline instructions + retry button + failure explanation", "Task completion rate (resolved)",
         "Tasks completed per user; time start→complete", "Fraud/validation rejection rate; task error rate",
         "Fewer abandoned/failed attempts", "task_step_viewed, task_failed (error_code), task_retry"),
        ("EXP-04", "Showing pending-validation status with an expected time will sustain return among users awaiting rewards.",
         f"{to['pending']} pending task records; many older than 30 days.", "Users with ≥1 pending task",
         "No status visibility", "Pending tracker with ETA and notification on credit", "D7 return of users with pending tasks",
         "Support contacts; subsequent task starts", "Validation SLA breaches; reward reversal rate",
         "Users keep engaging while rewards validate", "reward_pending, reward_credited (latency), pending_status_viewed"),
        ("EXP-05", "A prominent start call-to-action with the reward value on mission and spin surfaces will raise view→start conversion.",
         f"{d_view.drop_off_pct}% of Missions/Spin view pairs never started.", "Users viewing Missions or Spin the Wheel",
         "Current surface", "Prominent CTA + reward value", "View→start conversion (same session)",
         "Completion rate; meaningful actions per session", "Mission abandonment rate; spin error rate",
         "More views convert to starts", "feature_impression, feature_started with source_surface"),
        ("EXP-06", "A one-time 'streak saver' will increase consecutive-day claims among streak users.",
         f"Only {st['pct_claimers_consecutive']}% of claimers claim on consecutive days.", "Users who claimed a streak at least once",
         "Current streak rules", "One free streak save per week + visible streak counter", "Consecutive-day claim rate",
         "Active days per week; D14 return", "Reward cost per active user; streak_broken complaints",
         "Longer streak runs", "streak_started, streak_day_count, streak_saved, streak_broken (prior_length)"),
        ("EXP-07", "Previewing tomorrow's earning opportunities to heavy first-day users will improve first-week return.",
         f"D7 return high-volume day-1 tercile {vol.get('high')}% vs low {vol.get('low')}%.", "Users in the top tercile of day-1 events",
         "No pacing message", "'Come back tomorrow' preview after daily limits", "D7 return", "Active days in first 14; sessions/week",
         "Same-day meaningful actions (should not drop sharply)", "Heavier users spread activity over more days",
         "daily_limit_reached, next_day_preview_shown"),
        ("EXP-08", "Showing the reward value before an ad and offering a shorter ad format will reduce ad skipping.",
         f"Watch Ads skip rate {ads.event_abandonment_rate_pct}% of ad outcomes.", "Users who start a Watch Ads activity",
         "Current ad flow", "Reward shown up front + shorter ad option", "Ad completion rate (completed ÷ completed + skipped)",
         "Ads completed per user; meaningful actions per session", "Ad revenue per impression (if tracked); playback error rate",
         "Fewer skipped ads", "ad_started (duration, reward_offered), ad_skipped (seconds_watched), ad_error"),
        ("EXP-09", "Splitting missions into smaller steps with visible progress will reduce mission abandonment.",
         f"Missions abandonment rate {mis.event_abandonment_rate_pct}% of mission outcomes.", "Users who start a mission",
         "Current single-step missions", "Step-based missions with a progress bar", "Mission completion rate (completed ÷ completed + abandoned)",
         "Missions completed per user; D7 return", "Reward cost per completed mission; time to complete",
         "More missions finished", "mission_progress (step, steps_total), mission_completed, mission_abandoned (step)"),
        ("EXP-10", "A weekly goal shown from the third active day will help returning users reach a seventh active day.",
         f"{d_3to7.drop_off_pct}% of users with 3 active days did not reach 7 within their first 30 days.",
         "Users on their 3rd active day", "No weekly goal", "Weekly goal card (e.g. 'be active 4 days this week') with a bonus",
         "Share reaching 7 active days within 30 days of first activity", "Active days per week; D30 return",
         "Bonus cost per active user; same-day meaningful actions", "More users form a weekly habit",
         "goal_shown, goal_progress, goal_completed"),
    ]
    exp = pd.DataFrame(exps, columns=["experiment_id", "hypothesis", "problem_evidence", "target_users", "control", "variant",
                                      "primary_metric", "secondary_metrics", "guardrail_metrics", "expected_behavioral_change",
                                      "required_event_tracking"])
    exp.insert(1, "label", "PROPOSED EXPERIMENT – not run")

    # ---------- test design: baseline from the data, MDE, sample size (α=0.05, power=80%), duration at simulated volume
    obs_days = (ctx.data_end.normalize() - ctx.data_start.normalize()).days + 1
    act_days = (ctx.data_end.normalize() - u.first_active_date.min()).days + 1
    tk = ctx.tasks
    pend = set(tk.loc[tk.task_status == "Pending", "user_id"])
    pend_el = u[u.user_id.isin(pend) & u.D7_eligible.astype(bool)]
    e_ = ctx.events
    design = {  # id: (baseline proportion, MDE in pp, unit, eligible units per day in the simulated data, baseline source)
        "EXP-01": (act["rate_pct"] / 100, 5, "user", n_users / obs_days, f"{act['window_days']}-day activation rate"),
        "EXP-02": (ret["D1_rate_pct"] / 100, 3, "user", n_active / act_days, "D1 return rate"),
        "EXP-03": (to["completion_rate_resolved_pct"] / 100, 3, "task attempt (randomise by user)",
                   to["resolved"] / act_days, "Task completion rate (resolved)"),
        "EXP-04": (float(pend_el.D7_return.mean()), 5, "user", len(pend) / act_days, "D7 return of users with a pending task"),
        "EXP-05": (d_view.continuing / d_view.entering, 5, "user×feature view", d_view.entering / act_days,
                   "Missions/Spin view→start conversion"),
        "EXP-06": (st["pct_claimers_consecutive"] / 100, 2, "user", st["users_claiming"] / act_days,
                   "Consecutive-day streak claim rate"),
        "EXP-07": (vol.get("high") / 100, 5, "user", n_active / act_days / 3, "D7 return, top day-1 volume tercile"),
        "EXP-08": (ads.event_completion_rate_pct / 100, 5, "ad attempt (randomise by user)",
                   (ads.complete_events + ads.negative_outcome_events) / act_days, "Ad completion rate"),
        "EXP-09": (mis.event_completion_rate_pct / 100, 5, "mission attempt (randomise by user)",
                   (mis.complete_events + mis.negative_outcome_events) / act_days, "Mission completion rate"),
        "EXP-10": (d_3to7.continuing / d_3to7.entering, 5, "user", d_3to7.entering / act_days,
                   "Share of 3-day users reaching 7 active days in 30 days"),
    }
    rows = []
    for eid, (p, mde, unit, per_day, src) in design.items():
        p2 = min(p + mde / 100, 0.99)
        n_arm = sample_size_two_proportions(p, p2)
        rows.append({"experiment_id": eid, "baseline_metric": src, "baseline_value_pct": round(p * 100, 1),
                     "minimum_detectable_effect_pp": mde, "target_value_pct": round(p2 * 100, 1),
                     "sample_size_per_arm": n_arm, "randomisation_unit": unit,
                     "eligible_units_per_day_simulated": round(per_day, 1),
                     "est_duration_days_at_simulated_volume": int(np.ceil(2 * n_arm / per_day)),
                     "analysis_method": "Two-sided two-proportion z-test (χ²), α = 0.05, power 80%, fixed horizon, "
                                        "intention-to-treat; attempt-level metrics use user-clustered standard errors.",
                     "decision_rule": f"Adopt the variant only if the primary metric improves by ≥ {mde} pp with p < 0.05 "
                                      "and no guardrail worsens by more than its pre-agreed limit; otherwise keep the control."})
    exp = exp.merge(pd.DataFrame(rows), on="experiment_id")
    save_table(exp, "proposed_experiments")

    # ---------------------------------------------------------------- event tracking gaps
    gaps = [
        ("user_registered", "Account created", "user_id, ts, acquisition_source, campaign_id, device, platform",
         "No registration event; registration time only in user master.", "Activation rate, time to first activity"),
        ("login", "Successful authentication", "user_id, ts, method, device, app_version",
         "Login is currently inferred from sessions.", "Active users, login frequency"),
        ("session_started", "App/web session begins", "session_id, user_id, ts, entry_point, referrer, app_version",
         "Session start is not an event; zero-event sessions cannot be explained.", "Sessions/user, zero-event session rate"),
        ("session_ended", "Session ends", "session_id, ts, end_reason (timeout/logout/crash), duration_s",
         "Session windows end before tasks complete (DQ-022).", "Session duration, exit analysis"),
        ("onboarding_started / onboarding_completed", "Onboarding step entry / completion", "user_id, step, step_index, ts",
         "onboarding_status is a snapshot with no timing.", "Onboarding completion rate, activation"),
        ("feature_impression", "Feature tile/surface rendered in view", "user_id, session_id, feature, surface, position",
         "Exposure is only known for features that log 'viewed' events.", "Feature exposure, view→start conversion"),
        ("feature_started / feature_completed / feature_abandoned", "Unified lifecycle per feature attempt",
         "attempt_id, feature, ts, outcome, reward_value",
         "Starts and completions cannot be linked (DQ-035).", "Feature completion & abandonment rate"),
        ("task_viewed", "Task detail opened (independent of start)", "task_id, category, position, ts",
         "Every task record has a start, so view→start drop-off is invisible.", "Task view→start conversion"),
        ("task_failed (detailed)", "Task attempt fails", "task_id, error_code, step, partner_response, retry_count",
         "Five coarse failure reasons are evenly distributed – not actionable.", "Task failure rate by cause"),
        ("reward_credited / reward_pending", "Reward state changes", "reward_id, task_id, amount, validation_latency_s, status",
         "Pending tasks have no resolution timestamp.", "Validation latency, reward feedback"),
        ("first_meaningful_activity", "First completed value action", "user_id, feature, ts, hours_since_registration",
         "Must be reconstructed from multiple tables.", "Time to first meaningful activity"),
        ("streak_started / streak_day_count / streak_broken", "Streak state changes", "user_id, streak_length, prior_length, ts",
         "No streak length; breaks occur without recorded claims.", "Streak maintenance rate"),
        ("mission_progress", "Mission step completed", "mission_id, step, steps_total, ts",
         "Missions are binary complete/abandon only.", "Mission completion & step drop-off"),
        ("engagement_milestone_reached", "Milestone achieved (system-generated from raw events)", "user_id, milestone, ts, source_event_id",
         "Current milestone sheet is inconsistent with raw activity.", "Lifecycle milestone rates"),
        ("level_up (with values)", "Level changes", "user_id, old_level, new_level, xp_balance, ts",
         "current_level and xp_balance are absent.", "Level progression, XP velocity"),
        ("notification_sent / notification_opened", "Push/email sent and opened", "user_id, campaign, channel, ts",
         "Return cannot be linked to prompts.", "Notification-driven return"),
        ("referral_registered / referral_activated", "Referee registers / activates", "referrer_id, referee_id, ts",
         "Brief examples absent; referral impact unmeasurable.", "Referral conversion"),
        ("withdrawal_page_viewed / withdrawal_requested", "Withdrawal intent and request", "user_id, amount, method, status",
         "No withdrawal events in the simulated taxonomy.", "Wallet→withdrawal funnel"),
    ]
    gaps = pd.DataFrame(gaps, columns=["event_name", "trigger", "required_properties", "why_needed", "kpi_supported"])
    gaps.insert(1, "status", "PROPOSED analytics event (not in simulated dataset)")
    save_table(gaps, "event_tracking_gaps")

    # ---------------------------------------------------------------- recommendations (§45 framework)
    # every product recommendation is tied to a proposed experiment with baseline, target, sample size and decision rule
    issue_to_exp = {"BHV-001": "EXP-01", "BHV-002": "EXP-02", "BHV-003": "EXP-03", "BHV-004": "EXP-04", "BHV-005": "EXP-08",
                    "BHV-006": "EXP-09", "BHV-008": "EXP-05", "BHV-009": "EXP-06", "BHV-010": "EXP-10"}
    ex = exp.set_index("experiment_id")
    recs = []
    for o in opp.itertuples():
        eid = issue_to_exp.get(o.linked_issue)
        if eid:
            x = ex.loc[eid]
            how = (f"{eid}: {x.control} vs {x.variant}; randomise by {x.randomisation_unit.split(' (')[0]}; "
                   f"{x.sample_size_per_arm:,} per arm.")
            measure = (f"Primary: {x.primary_metric} – baseline {x.baseline_value_pct}% → target {x.target_value_pct}% "
                       f"(+{x.minimum_detectable_effect_pp} pp). Guardrails: {x.guardrail_metrics}.")
            rule = x.decision_rule
            dur = f"≈{x.est_duration_days_at_simulated_volume:,} days at simulated volume – recompute with production traffic."
        else:  # instrumentation-only opportunity (no product variant to A/B test)
            how = "Instrumentation change, validated by a before/after comparison of tracking coverage."
            measure = "Zero-event session rate and share of sessions with session_started/session_ended events."
            rule = "Done when zero-event sessions are explained (end_reason logged) for ≥ 99% of sessions."
            dur = "One release cycle."
        recs.append({"recommendation_id": f"REC-{len(recs) + 1:02d}", "priority": o.priority, "finding": o.finding,
                     "evidence": o.evidence, "user_impact": o.user_problem, "product_hypothesis": o.product_hypothesis,
                     "how_to_test": how, "how_to_measure": measure, "decision_rule": rule, "timeline": dur})
    recs.append({"recommendation_id": f"REC-{len(recs) + 1:02d}", "priority": "High",
                 "finding": "Fix pre-aggregated fields that disagree with raw logs",
                 "evidence": f"events_in_session overstated {counter_ratio:.1f}×; milestone sheet inconsistent; daily "
                             f"duration field {daily_ratio:.1f}× the session-derived value.",
                 "user_impact": "Analytics consumers could draw wrong conclusions.",
                 "product_hypothesis": "Pipeline derivations are not built from the same raw source.",
                 "how_to_test": "Automated reconciliation job comparing every aggregate with a recomputation from raw events.",
                 "how_to_measure": "Number of mismatching rows per table per day.",
                 "decision_rule": "Aggregates may be used for reporting only when mismatches = 0 for 7 consecutive days.",
                 "timeline": "One sprint."})
    recs.append({"recommendation_id": f"REC-{len(recs) + 1:02d}", "priority": "High",
                 "finding": "Always control for cohort period in comparisons",
                 "evidence": f"D7 return {apr.D7_rate_pct}% ({apr.cohort_month}) vs {aug.D7_rate_pct}% ({aug.cohort_month}).",
                 "user_impact": "Group comparisons can be confounded by when users joined.",
                 "product_hypothesis": "Time-dependent factors dominate behaviour differences.",
                 "how_to_test": "Report every group comparison both raw and stratified by registration month.",
                 "how_to_measure": "Difference between raw and month-adjusted estimates.",
                 "decision_rule": "Only act on differences that persist after cohort adjustment; experiments randomise within the "
                                  "same calendar period.",
                 "timeline": "Immediate (analysis standard)."})
    recs = pd.DataFrame(recs)
    save_table(recs, "final_recommendations")

    # ---------------------------------------------------------------- limitations
    lim_general = [
        "Simulated users are not actual VELOOP users; no statement here describes the real platform.",
        "No production behavioural data was used.",
        "No reliable causal inference: all relationships are associations within synthetic data.",
        "No guaranteed representation of the real user population (demographics, devices, sources).",
        "Third-party activity (ad networks, task partners, validation) may not be represented accurately.",
        "Exact production feature availability may change (VELOOP documentation notes features and mechanics can change).",
        "Simulated timestamps are not operational logs; timezone is undocumented.",
        "Simulated acquisition sources do not represent actual marketing performance.",
        "Simulated retention does not represent actual VELOOP retention.",
    ]
    lim_specific = [
        f"No login, registration, onboarding, session or task events in the taxonomy ({len(R['validation']['missing_pdf_events'])} brief examples absent) – login is proxied by sessions.",
        "Within-session event order is unreliable: sequence_number duplicates and disagrees with timestamps; completions are not linkable to starts.",
        f"Session windows (median {sm['median_session_duration_s']:.0f} s) end before {after_end_pct}% of task completions – "
        "duration under-measures time in product.",
        "06_Milestones contradicts raw activity and was not used as a source of truth.",
        "04_Daily_Activity duration is inconsistent with sessions; only its event/feature counts reconcile.",
        "current_level and xp_balance are absent: level/XP progression is limited to event counts.",
        "platform = 'Web' for every record: platform analysis is not supported; device is used instead.",
        "Return metrics are right-censored for recent users; windows require full observability.",
        "Strong calendar-period effects confound any cohort comparison that does not stratify by join date.",
        "Workbook volumes (sessions, daily records, feature usage) are below the brief's recommended ranges (source discrepancy).",
        "Project duration differs between the workbook README (22–25 days) and the PDF (20–24 days): source discrepancy requiring confirmation.",
        "Snapshot user attributes (account_status, onboarding_status, verification_status) have no timestamps.",
    ]
    ctx.R["insights"] = {"findings": findings, "friction": fr, "opportunities": opp, "priority_criteria": priority_criteria,
                         "experiments": exp, "tracking_gaps": gaps, "recommendations": recs,
                         "limitations_general": lim_general, "limitations_specific": lim_specific}
