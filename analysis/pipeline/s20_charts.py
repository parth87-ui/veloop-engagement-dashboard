"""Static report charts (PNG) + chart documentation catalogue.

Visual rules (dataviz reference palette): single-series charts use slot-1 blue; context in gray;
highlighted/flagged marks in slot-2 orange; sequential heatmaps use one blue ramp; never dual axes;
thin marks, hairline grid, selective direct labels.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from analysis import config  # noqa: E402
from analysis.pipeline.context import Context  # noqa: E402
from analysis.utils.io import save_table  # noqa: E402

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
GRAY, INK, INK2, GRID, SURF = "#b9b8b2", "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"
SEQ = LinearSegmentedColormap.from_list("blue", ["#f3f7fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
SIM = "Simulated dataset – not actual VELOOP data"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlelocation": "left",
    "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": SURF, "axes.facecolor": SURF,
    "savefig.facecolor": SURF, "legend.frameon": False, "axes.axisbelow": True,
})


def _finish(fig, ax_or_axes, path, subtitle=None):
    fig.text(0.01, 0.005, SIM, fontsize=7, color=INK2)
    if subtitle and isinstance(ax_or_axes, plt.Axes):
        ax_or_axes.set_title(ax_or_axes.get_title(loc="left"), loc="left", pad=18)
        ax_or_axes.text(0, 1.015, subtitle, transform=ax_or_axes.transAxes, fontsize=8.5, color=INK2)
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _hbar(ax, labels, values, color=BLUE, fmt="{:.1f}", highlight=None):
    y = np.arange(len(labels))
    cols = [ORANGE if highlight is not None and lab in highlight else color for lab in labels]
    ax.barh(y, values, color=cols, height=0.62)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    for yi, v in zip(y, values):
        ax.text(v, yi, " " + fmt.format(v), va="center", fontsize=8, color=INK2)


def run(ctx: Context) -> None:
    R, out = ctx.R, config.OUT_CHARTS
    cat = []

    def doc(cid, name, file, question, dataset, fields, calc, filt, pop, period, interp, lim, rel):
        cat.append({"chart_id": cid, "chart_name": name, "file": f"outputs/charts/{file}", "business_question": question,
                    "dataset": dataset, "fields_used": fields, "calculation": calc, "filter": filt, "population": pop,
                    "time_period": period, "interpretation": interp, "limitation": lim, "product_relevance": rel})

    period = f"{ctx.data_start.date()} – {ctx.data_end.date()}"

    # C01 DAU trend --------------------------------------------------------------
    d = R["time"]["daily"]
    fig, ax = plt.subplots(figsize=(10, 3.8))
    ax.plot(d.date, d.dau, color=GRAY, lw=1, label="Daily active users")
    ax.plot(d.date, d.dau_7d_avg, color=BLUE, lw=2, label="7-day average")
    fl = R["time"]["flags"]
    if len(fl):
        ax.scatter(fl.date, fl.dau, s=40, color=ORANGE, zorder=3, edgecolor=SURF, linewidth=1.5,
                   label="Flagged day (|robust z| ≥ 3 vs rolling median)")
    ax.set_ylabel("Distinct users with ≥1 event")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title("C01 · Daily active users rose steadily with the registered base")
    _finish(fig, ax, out / "C01_daily_active_users.png", "Daily distinct active users and 7-day average")
    t = R["time"]
    doc("C01", "Daily Active User Trend", "C01_daily_active_users.png", "How has daily activity evolved; are there unusual days?",
        "03_Feature_Events", "user_id, event_datetime", "Distinct users per calendar day; 7-day trailing mean; robust z of log DAU vs 15-day rolling median",
        "Clean events", "All active users", period,
        f"DAU peaked at {t['peak_dau']} ({pd.Timestamp(t['peak_dau_date']).date()}); DAU tracks the cumulative registered base (ρ={t['corr_dau_cumreg']}). Spikes are statistical flags only.",
        "No campaign/release calendar; spikes are not attributed to causes.", "Capacity planning and anomaly monitoring.")

    # C02 session frequency -------------------------------------------------------
    f = R["sessions"]["frequency"]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.bar(f.sessions_per_user, f.users, color=BLUE, width=0.62)
    for x, v in zip(f.sessions_per_user, f.users):
        ax.text(x, v, f"{v}", ha="center", va="bottom", fontsize=8, color=INK2)
    ax.set_xlabel("Sessions per user (lifetime)")
    ax.set_ylabel("Users")
    ax.grid(axis="x", visible=False)
    one = int(f.loc[f.sessions_per_user == "1", "users"].iloc[0])
    ax.set_title(f"C02 · Most users have several sessions; {one / f.users.sum() * 100:.0f}% have exactly one")
    _finish(fig, ax, out / "C02_session_frequency.png", "Distribution of registered users by number of sessions")
    sm = R["sessions"]["metrics"]
    doc("C02", "Session Frequency Distribution", "C02_session_frequency.png", "How often do users return to open sessions?",
        "02_Sessions", "session_id, user_id", "Count of sessions per user, binned", "No filter (all records)", "All 1,000 registered users", period,
        f"{sm['one_session_users']} users have one session; median {sm['median_sessions_per_active_user']:.0f} sessions per active user.",
        "Lifetime counts are tenure-dependent.", "Sizing re-engagement audiences.")

    # C03 session duration ----------------------------------------------------------
    s = ctx.sessions
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.hist(s.session_duration_seconds.clip(upper=240), bins=np.arange(20, 245, 5), color=BLUE, rwidth=0.85)
    top = ax.get_ylim()[1]
    for (q, lab), yf in zip([(sm["p25_duration_s"], "P25"), (sm["median_session_duration_s"], "Median"),
                             (sm["p75_duration_s"], "P75")], (0.95, 0.85, 0.75)):
        ax.axvline(q, color=INK2, lw=1)
        ax.text(q, top * yf, f" {lab} {q:.0f}s", fontsize=8, color=INK2)
    ax.set_xlabel("Session duration (s, values > 240 shown at 240)")
    ax.set_ylabel("Sessions")
    ax.grid(axis="x", visible=False)
    ax.set_title(f"C03 · Sessions are short: half last {sm['median_session_duration_s']:.0f} seconds or less")
    _finish(fig, ax, out / "C03_session_duration.png", "Distribution of logged session duration")
    doc("C03", "Session Duration Distribution", "C03_session_duration.png", "How long do sessions typically last?",
        "02_Sessions", "session_duration_seconds", "Histogram (5s bins), quartile markers", "No filter (all records)", f"All {sm['total_sessions']:,} sessions", period,
        f"Median {sm['median_session_duration_s']:.0f}s, P90 {sm['p90_duration_s']:.0f}s; duration is unrelated to depth (ρ={sm['duration_events_spearman']}).",
        "Session windows end before task completions (DQ-022).", "Do not use duration as an engagement KPI.")

    # C04 activation funnel -----------------------------------------------------------
    fn = R["activation"]["funnel"]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ramp = ["#1c5cab", "#256abf", "#2a78d6", "#3987e5", "#5598e7", "#6da7ec", "#86b6ef"]
    y = np.arange(len(fn))
    ax.barh(y, fn.pct_of_registered, color=ramp[: len(fn)], height=0.62)
    ax.set_yticks(y, fn.stage)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    for yi, r in zip(y, fn.itertuples()):
        ax.text(r.pct_of_registered, yi, f"  {r.users} ({r.pct_of_registered}%)", va="center", fontsize=8, color=INK2)
    ax.set_xlim(0, 118)
    ax.set_xlabel("% of registered users")
    ax.set_title("C04 · Activation funnel: the loss is in returning, not in the first session")
    _finish(fig, ax, out / "C04_activation_funnel.png", "Cumulative users reaching each stage (ever, within observation window)")
    doc("C04", "Activation Funnel", "C04_activation_funnel.png", "What happens after a user joins?", "01, 02, 03, 05",
        "user_id, session_id, event stage, task_status", "Cumulative user counts per stage / registered users", "Stage rules per activation_funnel.csv",
        "1,000 registered users", period, "Nearly all users with a session complete an activity; the first major loss is the second active day.",
        "Login proxied by sessions; completions not linked to starts.", "Focus activation work on return and first-session delay.")

    # C05 feature adoption -----------------------------------------------------------
    ft = R["features"]["table"].sort_values("share_of_active_users_pct")
    fig, ax = plt.subplots(figsize=(8, 5))
    y = np.arange(len(ft))
    comp = (ft.completion_users.fillna(0) / ctx.users.is_active.sum() * 100).values
    ax.barh(y + 0.2, ft.share_of_active_users_pct, height=0.38, color=BLUE, label="Exposed (any event)")
    ax.barh(y - 0.2, comp, height=0.38, color=AQUA, label="Completed ≥1 (n/a for view-only)")
    ax.set_yticks(y, ft.feature)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("% of active users")
    ax.legend(loc="lower right", fontsize=8)
    ax.set_title("C05 · Exposure is broad; completion reach varies by feature")
    _finish(fig, ax, out / "C05_feature_adoption.png", "Share of active users exposed to vs completing each feature")
    doc("C05", "Feature Adoption Comparison", "C05_feature_adoption.png", "Which features reach the most users, and how many complete them?",
        "03_Feature_Events", "feature_name, event_name, user_id", "Users with any event / active users; users with ≥1 'complete' event / active users",
        "Wallet, Exchange Center, Leaderboard have no completion events", "984 active users", period,
        f"Exposure ranges {ft.share_of_active_users_pct.min()}–{ft.share_of_active_users_pct.max()}% of active users.",
        "Exposure only known when a feature logs events.", "Feature prioritisation and discovery work.")

    # C06 repeat use -------------------------------------------------------------------
    fr = R["features"]["table"].sort_values("repeat_usage_rate_pct", ascending=False)
    fig, ax = plt.subplots(figsize=(8, 4.6))
    _hbar(ax, fr.feature.tolist(), fr.repeat_usage_rate_pct.values)
    ax.set_xlabel("% of feature users who used it in ≥2 sessions")
    ax.set_xlim(0, 100)
    ax.set_title("C06 · Repeat use of each feature")
    _finish(fig, ax, out / "C06_feature_repeat_use.png", "Repeat usage rate = users with the feature in ≥2 sessions / feature users")
    doc("C06", "Feature Repeat-Use Comparison", "C06_feature_repeat_use.png", "Which features do users come back to?",
        "03_Feature_Events", "feature_name, session_id, user_id", "Users with feature in ≥2 sessions / feature users", "No filter (all records)", "Feature users", period,
        f"Repeat rates range {fr.repeat_usage_rate_pct.min()}–{fr.repeat_usage_rate_pct.max()}%.",
        "Heavier users have more chances to repeat any feature.", "Identify sticky vs one-off features.")

    # C07 segments ----------------------------------------------------------------------
    sg = R["segmentation"]["profile"]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    _hbar(ax, sg.segment.tolist(), sg.users.values, fmt="{:.0f}")
    ax.set_xlabel("Users")
    ax.set_title("C07 · Behavioural engagement segments (mutually exclusive)")
    _finish(fig, ax, out / "C07_engagement_segments.png", "Users per segment; thresholds from observed active-day quantiles")
    doc("C07", "User Engagement Segments", "C07_engagement_segments.png", "What behavioural groups exist and how big are they?",
        "Derived users table", "n_active_days, n_features_completed", "Hierarchical rules (engagement_segments.csv)", "No filter (all records)", "1,000 users", period,
        "; ".join(f"{r.segment} {r.users}" for r in sg.itertuples()), "Thresholds are quantiles of this dataset.", "Targeting and sizing.")

    # C08/C09 acquisition & device small multiples -----------------------------------------
    for cid, key, col, title in [("C08", "acquisition", "acquisition_source", "Acquisition sources differ in volume more than in behaviour"),
                                 ("C09", "device", "device", "Devices show only small behavioural differences")]:
        tb = R["segments_device_acq"][key]["table"]
        metrics = [("users", "Registered users", "{:.0f}"), ("activation_rate_pct", f"{R['activation']['window_days']}-day activation %", "{:.1f}"),
                   ("d7_return_pct", "D7 return %", "{:.1f}"), ("mean_active_days", "Mean active days", "{:.1f}"),
                   ("task_completion_rate_pct", "Task completion %", "{:.1f}"), ("mean_engagement_score", "Mean engagement score", "{:.1f}")]
        fig, axes = plt.subplots(2, 3, figsize=(11, 5.6))
        for ax, (m, lab, fmt) in zip(axes.flat, metrics):
            _hbar(ax, tb[col].tolist(), tb[m].values, fmt=fmt)
            ax.set_title(lab, fontsize=9, fontweight="normal", color=INK2)
            ax.tick_params(labelsize=7.5)
            ax.set_xlim(0, tb[m].max() * 1.3)
        fig.suptitle(f"{cid} · {title}", x=0.01, ha="left", fontsize=11, fontweight="bold", color=INK)
        _finish(fig, axes, out / f"{cid}_{key}_behaviour.png")
        tests = R["segments_device_acq"][key]["tests"]
        doc(cid, f"{'Acquisition Source' if key == 'acquisition' else 'Device'} Behaviour Comparison", f"{cid}_{key}_behaviour.png",
            f"Do behavioural patterns differ by {col.replace('_', ' ')}?", "Users + sessions + events + tasks",
            f"{col}, activation, D7 flags, active days, task_status, engagement score", "Per-group rates; Kruskal-Wallis / χ² tests",
            "Activation/D7 use eligible users only", "1,000 users", period,
            f"{(tests.interpretation.str.startswith('Observed')).sum()} of {len(tests)} tests show a non-trivial effect.",
            "Simulated sources/devices; all platform = Web.", "Avoid ranking by registration volume alone.")

    # C10 cohort heatmap ----------------------------------------------------------------------
    wm = R["retention"]["weekly_matrix"]
    weeks = [c for c in wm.columns if isinstance(c, (int, np.integer))]
    mat = wm[weeks].values.astype(float)
    fig, ax = plt.subplots(figsize=(10, 6.2))
    im = ax.imshow(np.ma.masked_invalid(mat), cmap=SEQ, aspect="auto", vmin=0, vmax=60)
    ax.set_xticks(range(len(weeks)), [f"W{w}" for w in weeks])
    ax.set_yticks(range(len(wm)), [f"{c} (n={n})" for c, n in zip(wm.cohort_week, wm.cohort_size)], fontsize=6)
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.7)
    cb.set_label("% of cohort active (W0 = 100%)")
    ax.set_xlabel("Weeks since first active day")
    ax.set_title("C10 · Weekly return by first-active cohort: later cohorts return more")
    _finish(fig, ax, out / "C10_cohort_return_heatmap.png", "Share of each weekly cohort active in each subsequent week; blank = not yet observable")
    ret = R["retention"]["overall"]
    doc("C10", "Retention / Cohort Chart", "C10_cohort_return_heatmap.png", "Which cohorts return more frequently?", "03_Feature_Events",
        "user_id, event date, first active date", "Distinct active users per cohort-week / cohort size", "Unobservable cells blanked",
        "984 active users", period, f"D7 {ret['D7_rate_pct']}%, D30 {ret['D30_rate_pct']}%; return rises for later cohorts (calendar effect).",
        "Right-censoring; small early cohorts.", "Retention monitoring; control for cohort period.")

    # C11 journey transition heatmap -----------------------------------------------------------
    tp = R["journey"]["transition_prob"].set_index("from_feature")
    fig, ax = plt.subplots(figsize=(10, 6.4))
    im = ax.imshow(tp.values * 100, cmap=SEQ, aspect="auto", vmin=0)
    ax.set_xticks(range(tp.shape[1]), tp.columns, rotation=55, ha="right", fontsize=7.5)
    ax.set_yticks(range(tp.shape[0]), tp.index, fontsize=7.5)
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.7)
    cb.set_label("% of transitions from row feature")
    ax.set_title("C11 · Feature journey: next step after each feature is spread almost evenly")
    _finish(fig, ax, out / "C11_feature_journey_transitions.png", "First-order transition probabilities between consecutive distinct features (+ Exit)")
    doc("C11", "Feature Journey Visualization", "C11_feature_journey_transitions.png", "What does a user's activity journey look like?",
        "03_Feature_Events", "session_id, feature_name, event_datetime", "Collapsed consecutive features; row-normalised transition counts",
        "Valid sessions", f"{R['journey']['valid_sessions']:,} sessions", period,
        f"Lifts {R['journey']['transition_lift_range'][0]:.2f}–{R['journey']['transition_lift_range'][1]:.2f}: no dominant path; Exit is a frequent next step.",
        "In-session order unreliable (DQ-033/034); no causal reading.", "Journey-based recommendation needs better ordering data.")

    # C12 drop-off ---------------------------------------------------------------------------
    dm = R["dropoff"]["matrix"]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    labels = [s_.replace(" (first 30 days)", "*").replace("(user×feature, Missions & Spin)", "(M&S)")
              .replace("second meaningful activity (separate session)", "second (new session)") for s_ in dm.stage]
    _hbar(ax, labels, dm.drop_off_pct.values, highlight=[labels[i] for i in dm.drop_off_pct.nlargest(3).index])
    ax.set_xlabel("Drop-off % (entering − continuing) / entering")
    ax.set_xlim(0, 100)
    ax.tick_params(axis="y", labelsize=7.5)
    ax.set_title("C12 · Behavioural drop-off matrix (largest three highlighted)")
    _finish(fig, ax, out / "C12_dropoff.png", "* = users with ≥30 observable days, first 30 days only")
    doc("C12", "Drop-Off Visualization", "C12_dropoff.png", "Where do users stop progressing?", "01, 02, 03, 05",
        "Stage-specific (dropoff_matrix.csv)", "(entering − continuing) / entering", "Stage-specific", "Varies by stage", period,
        f"Largest: {', '.join(dm.loc[dm.drop_off_pct.nlargest(3).index, 'stage'])}.", "Mixed units (users, records, user×feature).",
        "Prioritise investigation areas.")

    # C13 time of day ------------------------------------------------------------------------
    h = R["time"]["hour"]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.bar(h.hour, h.sessions, color=BLUE, width=0.7)
    ax.axhline(h.sessions.mean(), color=INK2, lw=1)
    ax.text(23.6, h.sessions.mean(), " mean", fontsize=8, color=INK2, va="bottom")
    ax.set_xticks(range(24))
    ax.set_xlabel("Hour of session start (timezone undocumented)")
    ax.set_ylabel("Sessions")
    ax.grid(axis="x", visible=False)
    ax.set_title("C13 · Sessions by hour: no statistically meaningful peak")
    _finish(fig, ax, out / "C13_time_of_day.png", f"χ² test vs uniform p = {R['time']['hour_uniformity_chi2_p']:.2f}")
    doc("C13", "Time-of-Day Activity", "C13_time_of_day.png", "When are users most active?", "02_Sessions", "session_start hour",
        "Sessions per hour; χ² uniformity test", "No filter (all records)", "All sessions", period,
        f"Busiest hours {R['time']['busiest_hours']}, quietest {R['time']['quietest_hours']}, but differences are within random variation.",
        "Timezone unknown.", "No evidence for time-targeted notifications from this data.")

    # C14 anomaly scatter ----------------------------------------------------------------------
    us = R["anomalies"]["user_scatter"]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    n_ = us[~us.flagged]
    y_ = us[us.flagged]
    ax.scatter(n_.n_active_days, n_.n_events, s=12, color=GRAY, alpha=0.7, label="Not flagged")
    ax.scatter(y_.n_active_days, y_.n_events, s=22, color=ORANGE, edgecolor=SURF, linewidth=1, label="Flagged (user-level anomaly)")
    ax.set_xlabel("Active days")
    ax.set_ylabel("Total events")
    ax.legend(fontsize=8)
    ax.set_title("C14 · Users flagged for unusual activity concentration")
    _finish(fig, ax, out / "C14_behavioural_anomalies.png", "Each dot is an active user; flags = Tukey far-out fences or logical checks")
    doc("C14", "Behavioural Anomaly Chart", "C14_behavioural_anomalies.png", "Which users behave unusually?", "Derived users + anomaly register",
        "n_events, n_active_days, anomaly flags", "Tukey Q3+3·IQR fences; streak logic check", "Active users", "984 active users", period,
        f"{R['anomalies']['flagged_users']} users flagged; mostly bursty activity on few days. Not a fraud determination.",
        "Generic statistical thresholds only.", "Operations review queue.")

    # C15 task outcomes by category -------------------------------------------------------------
    tc = R["features"]["task_categories"].sort_values("completion_rate_pct")
    fig, ax = plt.subplots(figsize=(9, 4))
    left = np.zeros(len(tc))
    for col, lab, c in [("completed", "Completed", BLUE), ("abandoned", "Abandoned", ORANGE), ("failed", "Failed", YELLOW),
                        ("pending", "Pending", GRAY)]:
        vals = tc[col].values / tc.records.values * 100
        ax.barh(tc.task_category, vals, left=left, color=c, height=0.62, label=lab, edgecolor=SURF, linewidth=2)
        left += vals
    ax.set_xlabel("% of task records")
    ax.grid(axis="y", visible=False)
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.15), fontsize=8)
    ax.set_title("C15 · Task outcomes are similar across every category")
    _finish(fig, ax, out / "C15_task_outcomes.png", "Share of task records by final status")
    doc("C15", "Task Outcome by Category", "C15_task_outcomes.png", "Where does task friction concentrate?", "05_Task_Activity",
        "task_category, task_status", "Status share of records", "No filter (all records)", "9,846 task records", period,
        f"Completion (resolved) {tc.completion_rate_pct.min()}–{tc.completion_rate_pct.max()}% across categories.",
        "Coarse failure reasons.", "Task UX prioritisation.")

    # C16 calendar effect -------------------------------------------------------------------------
    mo = R["retention"]["monthly"]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.bar(mo.cohort_month, mo.D7_rate_pct, color=BLUE, width=0.6)
    for x, v, n in zip(mo.cohort_month, mo.D7_rate_pct, mo.D7_eligible):
        ax.text(x, v, f"{v}%\n(n={n})", ha="center", va="bottom", fontsize=7.5, color=INK2)
    ax.set_ylim(0, 100)
    ax.set_ylabel("D7 return %")
    ax.grid(axis="x", visible=False)
    ax.set_title("C16 · D7 return climbs with each first-active month")
    _finish(fig, ax, out / "C16_calendar_effect.png", "First-week return by month of first activity (eligible users only)")
    doc("C16", "Calendar-Period Effect on Return", "C16_calendar_effect.png", "Is return behaviour stable over time?", "03_Feature_Events",
        "first active date, event dates", "D7 returned / D7 eligible per first-active month", "D7-eligible users", "910 users", period,
        "Return rises strongly with calendar time – a confounder for every cohort comparison.", "Cause unknown (TO BE VERIFIED).",
        "Stratify analyses by cohort period.")

    # C17 engagement score distribution ---------------------------------------------------------------
    u = ctx.users[ctx.users.is_active]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.hist(u.engagement_score, bins=np.arange(0, 102, 4), color=BLUE, rwidth=0.85)
    ax.axvline(u.engagement_score.median(), color=INK2, lw=1)
    ax.text(u.engagement_score.median(), ax.get_ylim()[1] * 0.92, f" median {u.engagement_score.median():.1f}", fontsize=8, color=INK2)
    ax.set_xlabel("Analyst-Created Simulated Engagement Score (0–100)")
    ax.set_ylabel("Active users")
    ax.grid(axis="x", visible=False)
    ax.set_title("C17 · Engagement score distribution (analyst model, not an official metric)")
    _finish(fig, ax, out / "C17_engagement_score.png", "Weighted composite of six scaled behavioural components")
    doc("C17", "Engagement Score Distribution", "C17_engagement_score.png", "How is engagement depth distributed?", "Derived users table",
        "6 score components", "Weighted sum ×100 (engagement_score_components.csv)", "Active users", "984 active users", period,
        f"Median {u.engagement_score.median():.1f}; range {u.engagement_score.min():.1f}–{u.engagement_score.max():.1f}.",
        "Analyst weights; tenure bias.", "Prioritisation of engagement cohorts.")

    # C18 data quality impact ------------------------------------------------------------------------
    di = R["dq_impact"]["table"]
    di = di[di.percent_change.notna() & (di.percent_change.abs() > 0.5)].copy()
    di["label"] = di.metric.str.slice(0, 48)
    di = di.sort_values("percent_change")
    fig, ax = plt.subplots(figsize=(9, 5))
    cols = [ORANGE if c.startswith("Yes") else GRAY for c in di.conclusion_changes]
    ax.barh(di.label, di.percent_change, color=cols, height=0.62)
    ax.axvline(0, color=INK2, lw=0.8)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("% change after cleaning (vs naive use)")
    ax.set_title("C18 · Data-quality issues that change conclusions (orange)")
    _finish(fig, ax, out / "C18_data_quality_impact.png", "Before/after cleaning; gray = immaterial")
    doc("C18", "Data Quality Impact", "C18_data_quality_impact.png", "Do data-quality problems change the conclusions?",
        "All sheets", "See data_quality_impact.csv", "(after − before) / before", "|change| > 0.5%", "Metric-specific", period,
        "Session counters, milestone sheet, daily duration and strict sequence logic change conclusions; duplicates do not.",
        "Simulated stress tests are illustrative.", "Engineering reconciliation priorities.")

    cat = pd.DataFrame(cat)
    save_table(cat, "chart_catalogue")
    ctx.R["charts"] = {"catalogue": cat}
