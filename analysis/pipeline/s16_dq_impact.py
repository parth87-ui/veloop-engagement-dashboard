"""Work Package V — Data-quality impact on behavioural conclusions.

For each issue, compute the metric BEFORE cleaning (naive use of the field/sheet) and AFTER cleaning
(the analytical layer), with absolute and percent change, and state whether the conclusion changes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from analysis import config
from analysis.pipeline.context import Context
from analysis.pipeline.s08_engagement_score import COMPONENTS, compute_components, score
from analysis.utils.io import save_table
from analysis.utils.metrics import pct


def run(ctx: Context) -> None:
    raw, e, s, u, t = ctx.raw, ctx.events, ctx.sessions, ctx.users, ctx.tasks
    rows = []

    def add(scenario, metric, before, after, changes, explanation):
        before_f, after_f = float(before), float(after)
        rows.append({"scenario": scenario, "metric": metric, "before_cleaning": round(before_f, 3),
                     "after_cleaning": round(after_f, 3), "absolute_change": round(after_f - before_f, 3),
                     "percent_change": round((after_f - before_f) / before_f * 100, 2) if before_f else None,
                     "conclusion_changes": changes, "explanation": explanation})

    re_ = raw["events"]
    act_n = int(u.is_active.sum())
    v = s[s.is_valid]
    # 1 duplicate events
    add("Duplicate events (17 identical copies)", "Total events", len(re_), len(e), "No", "0.05% of events; immaterial.")
    add("Duplicate events (17 identical copies)", "Events per active user", len(re_) / act_n, len(e) / act_n, "No",
        "Immaterial at population level.")
    rank_raw = re_.feature_name.value_counts().index[:5].tolist()
    rank_cln = e.feature_name.value_counts().index[:5].tolist()
    add("Duplicate events (17 identical copies)", "Top-5 feature ranking identical (1 = yes)", 1, int(rank_raw == rank_cln),
        "No" if rank_raw == rank_cln else "Yes", "Feature popularity ranking unchanged.")
    # 2 audit sheet as-is
    a = raw["audit"]
    add("Audit sheet used as-is (duplicates, case variants)", "Distinct feature labels", a.feature_name.nunique(),
        e.feature_name.nunique(), "Yes (if uncorrected)", "Lower-case variants create 5 phantom features.")
    add("Audit sheet used as-is (duplicates, case variants)", "Event rows", len(a), len(a.drop_duplicates("event_id")),
        "No", "10 duplicated rows double-count a handful of events.")
    st_raw = (a.event_status == "Success").sum()
    st_norm = (a.drop_duplicates("event_id").event_status.str.strip().str.title() == "Success").sum()
    dup_success = int((a[a.event_id.duplicated()].event_status == "Success").sum())
    add("Audit sheet used as-is (duplicates, case variants)", "Events with status 'Success'", st_raw, st_norm, "No",
        f"Offsetting errors: {dup_success} duplicated 'Success' rows are added while the drifted statuses ('success ') "
        "drop out of exact-match filters – the totals agree only by coincidence.")
    # 3 session counter fields
    add("Session-sheet counters (events_in_session)", "Events per session", raw["sessions"].events_in_session.mean(),
        len(e) / len(v), "Yes", "Field overstates session depth by >2×; session depth conclusions would be wrong.")
    add("Session-sheet counters (features_used_count)", "Distinct features per session",
        raw["sessions"].features_used_count.mean(), v.raw_feature_count.mean(), "Partly",
        "Field understates breadth relative to raw events.")
    # 4 zero-event sessions
    add("Zero-event sessions included vs excluded", "Events per session", len(e) / len(s), len(e) / len(v), "No",
        "Small (~4%) dilution.")
    add("Zero-event sessions included vs excluded", "Sessions per active user", len(s) / act_n, len(v) / act_n, "No",
        "Small dilution.")
    # 5 overlapping sessions
    s_no = s[~s.is_overlapping]
    add("Overlapping sessions removed", "Total sessions", len(s), len(s_no), "No", "0.5% of sessions.")
    add("Overlapping sessions removed", "Median session duration (s)", s.session_duration_seconds.median(),
        s_no.session_duration_seconds.median(), "No", "Unchanged.")
    # 6 milestone sheet vs raw derivation
    mil = ctx.R["lifecycle"]["milestones"].set_index("milestone")
    for m_ in ["first_login", "first_task_completion", "third_active_day", "seventh_active_day"]:
        add("Milestone sheet vs raw derivation", f"Users reaching {m_}", mil.loc[m_, "users_in_milestone_sheet"],
            mil.loc[m_, "users_derived_from_raw"], "Yes", "Milestone sheet is not consistent with raw activity.")
    # 7 daily duration field
    d = raw["daily"]
    sd = s.groupby(["user_id", "date"]).session_duration_seconds.sum() / 60
    add("Daily-activity duration field vs sessions", "Mean minutes per active user-day", d.session_duration_minutes.mean(),
        sd.mean(), "Yes", "Daily field implies ~5 min/day vs ~1 min/day from session windows.")
    # 8 strict linkage of completion to start (impossible / unlinkable sequences)
    pairs = {"ad_completed": "ad_started", "spin_completed": "spin_started", "mission_completed": "mission_started",
             "captcha_completed": "captcha_started", "tap_completed": "tap_started", "mining_activity": "mining_started"}
    lenient = strict = 0
    es = e.sort_values(["session_id", "event_datetime", "event_id"])
    for c_ev, s_ev in pairs.items():
        comp = es[es.event_name == c_ev]
        st = es[es.event_name == s_ev].groupby("session_id").event_datetime.min()
        lenient += len(comp)
        strict += int((comp.event_datetime >= comp.session_id.map(st)).sum())
    add("Require a preceding start in the same session (strict funnel)", "Countable completions (6 start/complete pairs)",
        lenient, strict, "Yes", "Strict sequence logic would discard most completions – conclusions about completion "
        "volume depend entirely on the linkage rule; user-level 'ever completed' logic is used instead.")
    # 9 streak_broken status
    sc_status = e[(e.feature_name == "Streak Rewards") & (e.event_status == "Success")].user_id.nunique()
    sc_tax = e[e.event_name == "streak_claimed"].user_id.nunique()
    add("streak_broken logged as 'Success'", "Users with a successful streak event", sc_status, sc_tax, "Yes",
        "Status-based success would count users who only broke a streak.")
    # 10 simulated missing timestamps (2% random events dropped)
    rng = np.random.default_rng(config.RANDOM_SEED)
    keep = rng.random(len(e)) > 0.02
    e2 = e[keep]
    ad2 = e2.groupby("user_id").date.nunique()
    add("Simulated: 2% of events lose timestamps and are dropped", "Mean active days per active user",
        u.loc[u.is_active, "n_active_days"].mean(), ad2.mean(), "No", "Active-day metrics are robust to small random loss.")
    add("Simulated: 2% of events lose timestamps and are dropped", "One-time users (1 active day)",
        (u.n_active_days == 1).sum(), (ad2 == 1).sum(), "No", "Slight shift only.")
    # 11 simulated missing user ids (2% of events)
    add("Simulated: 2% of events lose user_id", "Active users", act_n, e2.user_id.nunique(), "No",
        "Active-user counts barely move because users have many events.")

    # 12 PDF stress test: one high-volume user's events duplicated 20×
    top_user = u.loc[u.n_events.idxmax(), "user_id"]
    dup = pd.concat([e] + [e[e.user_id == top_user]] * 19)
    add("Stress test: top user's events duplicated 20×", "Total events", len(e), len(dup), "Yes (volume)",
        "Event volume inflated by one user.")
    add("Stress test: top user's events duplicated 20×", "Mean events per active user", len(e) / act_n, len(dup) / act_n,
        "Yes (mean)", "Means are fragile to a single duplicated user.")
    med_b = e.groupby("user_id").size().median()
    med_a = dup.groupby("user_id").size().median()
    add("Stress test: top user's events duplicated 20×", "Median events per active user", med_b, med_a, "No",
        "Medians are robust – reason medians are reported alongside means.")
    r_b = e.feature_name.value_counts()
    r_a = dup.feature_name.value_counts()
    top_b, top_a = r_b.index[0], r_a.index[0]
    rank_corr = pd.Series(r_b.rank()).corr(pd.Series(r_a.rank()), method="spearman")
    add("Stress test: top user's events duplicated 20×", "Feature event-count rank correlation (Spearman)", 1.0, rank_corr,
        "Yes" if rank_corr < 0.9 else "Partly", f"Event-count popularity is distorted (top feature {top_b} → {top_a}); "
        "user-count based adoption metrics are unaffected.")
    add("Stress test: top user's events duplicated 20×", "Unique users of top feature",
        e[e.feature_name == top_b].user_id.nunique(), dup[dup.feature_name == top_b].user_id.nunique(), "No",
        "Unique-user metrics are immune to duplication.")
    # engagement score of that user and others
    u2 = u.copy()
    idx = u2.user_id == top_user
    u2.loc[idx, "n_meaningful"] = u2.loc[idx, "n_meaningful"] * 20
    u2.loc[idx, "n_level_up"] = u2.loc[idx, "n_level_up"] * 20
    u2.loc[idx, "n_badge_earned"] = u2.loc[idx, "n_badge_earned"] * 20
    w = {k: wt for k, _, wt, _, _ in COMPONENTS}
    sc2 = score(compute_components(u2), w)
    add("Stress test: top user's events duplicated 20×", "That user's engagement score", u.loc[idx, "engagement_score"].iloc[0],
        sc2[idx].iloc[0], "No", "P99 winsorisation caps count components, so duplication barely moves the score.")
    add("Stress test: top user's events duplicated 20×", "Median engagement score (active users)",
        u.loc[u.is_active, "engagement_score"].median(), sc2[u.is_active].median(), "No", "Population score robust.")

    imp = pd.DataFrame(rows)
    save_table(imp, "data_quality_impact")
    ctx.R["dq_impact"] = {"table": imp, "stress_user": top_user,
                          "material": imp[imp.conclusion_changes.str.startswith("Yes")].scenario.unique().tolist(),
                          "immaterial": imp[imp.conclusion_changes == "No"].scenario.unique().tolist()}
