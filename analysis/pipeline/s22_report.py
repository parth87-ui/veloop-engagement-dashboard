"""Final PDF report: VELOOP REWARDS — USER BEHAVIOR & ENGAGEMENT INTELLIGENCE REPORT.

Structured exactly around the 27 sections of the brief (§49) plus appendices (22 required questions,
chart catalogue, source register). All numbers are read from ctx.R.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from analysis import config
from analysis.pipeline.context import Context

FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("DV", str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DVI", str(FONT_DIR / "DejaVuSans-Oblique.ttf")))
from reportlab.lib.fonts import addMapping  # noqa: E402

addMapping("DV", 0, 0, "DV")
addMapping("DV", 1, 0, "DVB")
addMapping("DV", 0, 1, "DVI")
addMapping("DV", 1, 1, "DVB")

INK, INK2, BLUE, RULE, TINT = colors.HexColor("#0b0b0b"), colors.HexColor("#52514e"), colors.HexColor("#1c5cab"), \
    colors.HexColor("#d9d8d2"), colors.HexColor("#f1f5fb")
ST = {
    "title": ParagraphStyle("t", fontName="DVB", fontSize=20, leading=25, textColor=INK, spaceAfter=8),
    "sub": ParagraphStyle("s", fontName="DV", fontSize=11, leading=15, textColor=INK2, spaceAfter=4),
    "h1": ParagraphStyle("h1", fontName="DVB", fontSize=14, leading=18, textColor=BLUE, spaceBefore=6, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName="DVB", fontSize=10.5, leading=14, textColor=INK, spaceBefore=6, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="DV", fontSize=8.6, leading=12, textColor=INK, spaceAfter=4, alignment=TA_LEFT),
    "small": ParagraphStyle("sm", fontName="DV", fontSize=7.2, leading=9.2, textColor=INK2),
    "cell": ParagraphStyle("c", fontName="DV", fontSize=6.9, leading=8.6, textColor=INK),
    "cellb": ParagraphStyle("cb", fontName="DVB", fontSize=6.9, leading=8.6, textColor=colors.white),
    "bullet": ParagraphStyle("b", fontName="DV", fontSize=8.6, leading=12, leftIndent=10, bulletIndent=2, spaceAfter=2),
    "box": ParagraphStyle("box", fontName="DV", fontSize=8.2, leading=11.5, textColor=INK, backColor=TINT,
                          borderPadding=6, spaceBefore=4, spaceAfter=8),
}
TAG_COL = {"SIMULATED DATA RESULT": "#1c5cab", "ANALYST INTERPRETATION": "#6b4fbb", "PRODUCT HYPOTHESIS": "#b45309",
           "TO BE VERIFIED": "#b91c1c", "DOCUMENTED PRODUCT FACT": "#047857"}
W = A4[0] - 3.2 * cm


def esc(x) -> str:
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def P(text, style="p"):
    return Paragraph(text, ST[style])


def tagged(tag, text):
    return P(f'<font name="DVB" color="{TAG_COL[tag]}" size="6.8">[{tag}]</font> {text}')


def bullets(items):
    return [Paragraph(esc(i), ST["bullet"], bulletText="•") for i in items]


def table(df: pd.DataFrame, cols=None, widths=None, max_rows=None, headers=None):
    df = df.copy()
    cols = cols or list(df.columns)
    df = df[cols]
    if max_rows:
        df = df.head(max_rows)
    def pretty(h):
        h = str(h)
        if "_" not in h:
            return h
        for suffix, unit in (("_pct", " %"), ("_pp", " (pp)"), ("_s", " (s)")):
            if h.endswith(suffix):
                h = h[: -len(suffix)] + unit
                break
        return h.replace("_", " ").strip().capitalize()

    head = [Paragraph(esc(h), ST["cellb"]) for h in (headers or [pretty(c) for c in cols])]
    body = []
    for r in df.itertuples(index=False):
        row = []
        for v in r:
            if isinstance(v, float):
                v = "" if pd.isna(v) else (f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}".rstrip("0").rstrip("."))
            row.append(Paragraph(esc(v if v is not None else ""), ST["cell"]))
        body.append(row)
    if widths is None:
        widths = [W / len(cols)] * len(cols)
    else:
        tot = sum(widths)
        widths = [w / tot * W for w in widths]
    t = Table([head] + body, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f5")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE), ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def chart(name, width=W, ratio=None):
    path = config.OUT_CHARTS / name
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        w, h = im.size
    return Image(str(path), width=width, height=width * h / w)


def _page(canvas, doc):
    canvas.saveState()
    canvas.setFont("DV", 6.8)
    canvas.setFillColor(INK2)
    canvas.drawString(1.6 * cm, 1.0 * cm, "VELOOP Rewards — User Behavior & Engagement Intelligence · Parth Khandelwal · "
                                          "SIMULATED DATA – not actual VELOOP user data")
    canvas.drawRightString(A4[0] - 1.6 * cm, 1.0 * cm, f"Page {doc.page}")
    canvas.restoreState()


def answers(R, u) -> pd.DataFrame:
    sm, ret, life, ft = R["sessions"]["metrics"], R["retention"]["overall"], R["lifecycle"], R["features"]["table"]
    top_use = ft.sort_values("unique_users", ascending=False).head(3)
    top_rep = ft.sort_values("repeat_usage_rate_pct", ascending=False).head(3)
    outcome = ft[ft.event_abandonment_rate_pct.notna()]
    pair = R["features"]["affinity_top_pairs"].iloc[0]
    dm = R["dropoff"]["matrix"]
    cohorts = R["retention"]["cohort_tests"].set_index("dimension")
    rp = R["repeat"]["comparison"].set_index("metric")
    fr = R["insights"]["friction"].sort_values("affected_users", ascending=False)
    qa = [
        ("User Lifecycle", "1. How many simulated users become active?",
         f"{int(u.is_active.sum())} of {len(u)} ({u.is_active.mean() * 100:.1f}%) recorded ≥1 feature event; "
         f"{life['stages'].iloc[3].users_cumulative} completed a meaningful activity."),
        ("User Lifecycle", "2. How quickly do users perform their first activity?",
         f"Median {life['median_days_reg_to_first_activity']:.1f} days from registration to first feature event; "
         f"{R['activation']['windows'].set_index('window_days').loc[1, 'activation_rate_pct']}% complete a meaningful activity within 1 day."),
        ("User Lifecycle", "3. How many users never progress beyond initial activity?",
         f"{life['depth']['one_time']} active users had only one active day; "
         f"{life['depth']['never_beyond_first_meaningful_day']} never had meaningful activity on a second day; 16 never became active."),
        ("User Lifecycle", "4. How many users become repeat users?",
         f"{life['depth']['repeat']} users ({life['depth']['repeat'] / u.is_active.sum() * 100:.1f}% of active) had ≥2 active days; "
         f"{int(u.is_regular.sum())} were active in ≥3 distinct weeks."),
        ("Sessions", "5. How frequently do users return?",
         f"Median gap between active days {sm['median_gap_between_active_days']:.0f} days; D1 {ret['D1_rate_pct']}%, "
         f"D7 {ret['D7_rate_pct']}%, D14 {ret['D14_rate_pct']}%, D30 {ret['D30_rate_pct']}% (week windows)."),
        ("Sessions", "6. How long do sessions typically last?",
         f"Median {sm['median_session_duration_s']:.0f}s (mean {sm['avg_session_duration_s']:.0f}s, P90 {sm['p90_duration_s']:.0f}s)."),
        ("Sessions", "7. How many users have only one session?",
         f"{sm['one_session_users']} users ({sm['one_session_users'] / len(u) * 100:.1f}% of registered)."),
        ("Sessions", "8. What does the session distribution look like?",
         f"Right-skewed: median {sm['median_sessions_per_active_user']:.0f} sessions per active user, top quartile ≥{sm['high_frequency_session_threshold']}; "
         f"{sm['events_per_valid_session']} events and {sm['distinct_features_per_valid_session']:.2f} features per valid session."),
        ("Features", "9. Which features receive the most usage?",
         "; ".join(f"{r.feature} ({r.unique_users} users, {r.total_events:,} events)" for r in top_use.itertuples())),
        ("Features", "10. Which features have high repeat usage?",
         "; ".join(f"{r.feature} {r.repeat_usage_rate_pct}%" for r in top_rep.itertuples()) + " of their users used them in ≥2 sessions."),
        ("Features", "11. Which features have significant drop-off?",
         "; ".join(f"{r.feature} {r.event_abandonment_rate_pct}% {r.negative_outcome_type}" for r in outcome.itertuples())
         + f"; {dm.iloc[3].drop_off_pct}% of Missions/Spin viewers never start."),
        ("Features", "12. Which feature combinations occur most frequently?",
         f"{pair.feature_a} + {pair.feature_b} ({pair.sessions_together} sessions, lift {pair.lift}); all pair lifts are "
         f"{R['features']['lift_range'][0]:.2f}–{R['features']['lift_range'][1]:.2f} (weak affinity)."),
        ("Acquisition", "13. Do behavioural patterns differ by acquisition source?",
         "Only negligibly – no source shows a non-trivial effect size on activity, depth, activation or return."),
        ("Acquisition", "14. Are some sources associated with deeper engagement?",
         "'Other' and Telegram show the highest mean active days and scores, but differences are not statistically "
         f"detectable (30-day active days p={cohorts.loc['Acquisition source', 'kruskal_p_active_days_30d']:.2f})."),
        ("Devices", "15. Are there meaningful behavioural differences across devices?",
         "No meaningful differences; activation differs slightly (Android/iOS higher) with a negligible effect size."),
        ("Time", "16. When are users most active?",
         f"No significant hour-of-day peak (χ² p={R['time']['hour_uniformity_chi2_p']:.2f}); DAU grows with calendar time, peaking "
         f"at {R['time']['peak_dau']} in September."),
        ("Time", "17. Are there meaningful weekday/weekend differences?",
         f"No (trend-adjusted DAU index p={R['time']['weekend']['mannwhitney_p_dau_index']:.2f})."),
        ("Retention", "18. Which cohorts return more frequently?",
         f"Later first-active cohorts (Aug–Sep) and fast activators; registration-month cohorts differ strongly "
         f"(p={cohorts.loc['Registration month', 'chi2_p_d30_return']:.1e}), source/device do not."),
        ("Retention", "19. What behaviours are common among returning users?",
         f"Multi-session users more often claim daily rewards ({rp.loc['daily_reward_claim_users_pct', 'Multi-session users']}% vs "
         f"{rp.loc['daily_reward_claim_users_pct', 'Single-session users']}%), streaks, spins and level-ups – associations reflecting "
         "more visits, not causes."),
        ("Product", "20. Where are the largest behavioural friction points?",
         "Second-day return, task abandonment/failure, 3→7 active-day stall, ad/CAPTCHA/mission negative outcomes, long-pending validation."),
        ("Product", "21. Which areas deserve further product investigation?",
         "; ".join(R["insights"]["opportunities"].head(4).finding)),
        ("Product", "22. What additional data should VELOOP collect?",
         f"{len(R['insights']['tracking_gaps'])} proposed events, led by login/session_started/session_ended, linked feature "
         "lifecycle events, detailed task_failed, reward_pending/credited and streak state."),
    ]
    return pd.DataFrame(qa, columns=["area", "question", "answer (simulated data)"])


def run(ctx: Context) -> None:
    R, u = ctx.R, ctx.users
    path = config.OUT_REPORTS / "VELOOP_Task02_User_Behavior_Engagement_Intelligence_Report.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.5 * cm,
                            bottomMargin=1.6 * cm, title="VELOOP Rewards — User Behavior & Engagement Intelligence Report",
                            author="Parth Khandelwal")
    v, sm, ft, ret = R["validation"], R["sessions"]["metrics"], R["features"]["table"], R["retention"]["overall"]
    ins, kp, act, life = R["insights"], R["executive_kpis"], R["activation"], R["lifecycle"]
    rc = v["record_counts"]
    dm = R["dropoff"]["matrix"]
    S: list = []

    # ------------------------------------------------------------------ cover
    S += [Spacer(1, 3.5 * cm), P("VELOOP REWARDS — USER BEHAVIOR &amp; ENGAGEMENT INTELLIGENCE REPORT", "title"),
          P("Data Analyst Internship · Task 02 · Product Analytics / User Behavior / Engagement Intelligence", "sub"),
          P("<b>Prepared by: Parth Khandelwal</b> · Data Analyst Intern", "sub"),
          P(f"Observation window: {ctx.data_start.date()} – {ctx.data_end.date()} · Generated from the pipeline in this repository", "sub"),
          Spacer(1, 0.6 * cm),
          P("<b>Data authenticity statement.</b> Every figure in this report is calculated from the fictional, simulated workbook "
            "<i>VELOOP_Simulated_User_Behavior_1000.xlsx</i> supplied for the internship. Nothing here describes actual VELOOP "
            "users, retention, engagement, acquisition or product performance. Wording follows the brief: “In the provided simulated "
            "dataset…”. The engagement score is an analyst-created model, not an official VELOOP metric. All experiments are "
            "proposals; none was run.", "box"),
          P("<b>Statement classes used throughout</b>", "h2")]
    for tag, desc in [("DOCUMENTED PRODUCT FACT", "Supported by official VELOOP documentation as cited in the brief"),
                      ("SIMULATED DATA RESULT", "Calculated from the simulated dataset"),
                      ("ANALYST INTERPRETATION", "What a result may indicate"),
                      ("PRODUCT HYPOTHESIS", "A proposed explanation or change to test"),
                      ("TO BE VERIFIED", "Requires confirmation from product/engineering")]:
        S.append(tagged(tag, desc))
    S.append(PageBreak())

    # ------------------------------------------------------------------ 01 executive summary (1 page)
    S.append(P("01. Executive Summary", "h1"))
    S.append(P("<b>SIMULATED DATA – NOT ACTUAL VELOOP REWARDS USER DATA.</b> Every figure in this report is calculated from the "
               "fictional dataset supplied for this task. It shows how the analysis works and what it would find; it does not "
               "describe real VELOOP users, retention or performance.", "box"))
    S.append(P(f"Scope: {rc['users']:,} simulated users, {rc['sessions']:,} sessions and {rc['events']:,} feature events, "
               f"{ctx.data_start.date()} – {ctx.data_end.date()}. All metrics are recomputed from raw logs; every user count uses one "
               "shared definition (Appendix D reconciles numbers that look alike)."))
    to = R["features"]["task_overall"]
    kp_tbl = pd.DataFrame([
        ("Active users", f"{kp['active_users']:,}", f"of {kp['total_users']:,} registered"),
        (f"Activation ({kp['activation_window_days']}-day)", f"{act['rate_pct']}%", f"{act['activated']} of {act['eligible']} eligible users"),
        ("Repeat users (≥2 active days)", f"{kp['repeat_user_rate_pct']}%",
         f"{int((u.n_active_days >= 2).sum())} of {kp['active_users']} active users"),
        ("D7 return (days 1–7)", f"{ret['D7_rate_pct']}%", f"{ret['D7_returned']} of {ret['D7_eligible']} eligible users"),
        ("D30 return (days 24–30)", f"{ret['D30_rate_pct']}%", f"{ret['D30_returned']} of {ret['D30_eligible']} eligible users"),
        ("Task completion", f"{to['completion_rate_resolved_pct']}%", f"{to['completed']:,} of {to['resolved']:,} finished task attempts"),
    ], columns=["KPI (simulated)", "Value", "Numerator / denominator"])
    S.append(table(kp_tbl, widths=[2.4, 1, 3]))
    S.append(P("Most important findings", "h2"))
    top = ins["findings"].set_index("finding_id")
    for fid in ["FND-01", "FND-03", "FND-05", "FND-06", "FND-07"]:
        r = top.loc[fid]
        S.append(tagged("SIMULATED DATA RESULT", f"<b>{esc(r.title)}.</b> {esc(r.observation)}"))
    S.append(P("Top actions and how to test them", "h2"))
    recs_all = ins["recommendations"]
    recs3 = recs_all[recs_all.how_to_test.str.startswith("EXP")].head(3)
    ex = ins["experiments"].set_index("experiment_id")
    rows = []
    for r in recs3.itertuples():
        eid = r.how_to_test.split(":")[0]
        x = ex.loc[eid]
        rows.append((r.finding, f"{eid} (proposed A/B test)", f"{x.primary_metric}: {x.baseline_value_pct}% → {x.target_value_pct}%",
                     f"{x.sample_size_per_arm:,} per arm"))
    S.append(table(pd.DataFrame(rows, columns=["Action", "Test", "Primary metric: baseline → target", "Sample size"]),
                   widths=[2.6, 1.5, 3.2, 1.1]))
    S.append(P("These are associations in simulated data, not proven causes. Each action should be validated by its experiment "
               "(Section 24) on production traffic before roll-out. Source code, the anonymised dataset and an independent "
               "verification script are provided (Appendix E).", "small"))
    S.append(PageBreak())

    # ------------------------------------------------------------------ 02 dataset validation
    S.append(P("02. Dataset Validation", "h1"))
    S.append(P("Dataset Validation &amp; Data Quality Impact", "h2"))
    S.append(P("Ten sheets were profiled before any analysis. 03_Feature_Events is the primary behavioural source; 02_Sessions and "
               "05_Task_Activity supply session windows and the task funnel; 04_Daily_Activity, 06_Milestones and 07_Feature_Usage "
               "are treated as validation references; 10_Event_Data_Quality_Audit is a QA copy with injected issues."))
    S.append(table(v["sheet_profile"], ["sheet", "rows", "columns", "null_cells", "duplicate_rows", "min_datetime", "max_datetime"],
                   [3, 1, 1, 1, 1, 2.2, 2.2]))
    S.append(P(f"Classification summary of {len(v['issues'])} checks: " + ", ".join(f"{k} {n}" for k, n in v["summary"].items()) + "."))
    iss = v["issues"]
    iss = iss[iss.classification != "VALID"]
    S.append(table(iss, ["issue_id", "dataset", "check", "count", "pct", "classification", "severity", "action_taken"],
                   [1, 1.3, 4, 0.9, 0.8, 1.3, 1, 4]))
    S.append(P("Full register (including VALID checks, denominators and analytical impact): outputs/tables/data_quality_report.csv / .xlsx.", "small"))
    S.append(tagged("TO BE VERIFIED", "Source discrepancy requiring confirmation: the workbook README describes a '22–25 day' project "
                    "while the PDF states '20–24 Days'; sheet volumes (sessions, daily activity, feature usage) are below the PDF's recommended ranges."))
    S.append(PageBreak())

    # ------------------------------------------------------------------ 03 lifecycle
    S.append(P("03. User Lifecycle Analysis", "h1"))
    md = life["meaningful_definition"]
    S.append(P("<b>Meaningful activity (definition).</b> " + esc(md["rationale"]) + " Included: " + esc(", ".join(md["included_events"]))
               + "; plus completed tasks. Excluded: views/opens, starts, skips/failures/abandons, badge_earned, level_up, mining_stopped, "
               "streak_broken. Limitation: " + esc(md["limitations"])))
    S.append(P("Two counts are shown for every stage: <b>cumulative</b> = users who met this stage and every earlier one; "
               "<b>standalone</b> = users who meet this stage's rule regardless of earlier stages. Stages with the same name have "
               "identical counts in the lifecycle, activation funnel, engagement funnel and dashboard.", "small"))
    S.append(table(life["stages"], ["stage", "definition", "users_cumulative", "pct_of_registered", "pct_of_previous", "users_standalone"],
                   [2, 4.2, 1, 1, 1, 1], headers=["Stage", "Definition", "Users (cumulative)", "% of registered",
                                                  "% of previous", "Users (standalone)"]))
    tt = life["time_to"]
    S.append(table(pd.DataFrame([{"metric": d["label"], **{b["bucket"]: b["users"] for b in d["buckets"]}} for d in tt.values()]),
                   widths=[3] + [1] * 8))
    S.append(table(life["milestones"], ["milestone", "users_derived_from_raw", "users_in_milestone_sheet", "difference", "pct_of_registered_derived"],
                   [2.5, 1.5, 1.5, 1, 1.5]))
    S.append(tagged("ANALYST INTERPRETATION", "The lifecycle is front-loaded: the first session reliably produces a completion, while "
                    "repeat and regular engagement are where the cohort thins out."))

    # ------------------------------------------------------------------ 04 activation
    S.append(P("04. Activation Analysis", "h1"))
    S.append(P("<b>Definition.</b> " + esc(act["definition"]) + " <b>Window choice.</b> " + esc(act["window_rationale"])))
    S.append(table(act["windows"], ["window_days", "eligible_users", "activated_users", "activation_rate_pct",
                                    "capture_of_60d_activators_pct", "gain_per_extra_day_pp", "selected"]))
    S.append(chart("C04_activation_funnel.png", W * 0.82))
    S.append(table(act["funnel"], ["stage", "definition", "users", "pct_of_registered", "pct_of_previous", "users_standalone",
                                   "data_source", "limitation"], [1.8, 2.8, 0.8, 0.8, 0.8, 0.8, 1, 2.6],
                   headers=["Stage", "Definition", "Users (cumulative)", "% of 1,000 registered", "% of previous",
                            "Users (standalone)", "Source", "Limitation"]))

    # ------------------------------------------------------------------ 05 sessions
    S.append(PageBreak())
    S.append(P("05. Session Behavior Analysis", "h1"))
    srows = [("Total sessions", sm["total_sessions"]), ("Valid (event-backed) sessions", sm["valid_sessions"]),
             ("Sessions / registered user", sm["sessions_per_registered_user"]), ("Sessions / active user", sm["sessions_per_active_user"]),
             ("Average duration (s)", sm["avg_session_duration_s"]), ("Median duration (s)", sm["median_session_duration_s"]),
             ("P25 / P75 / P90 / P95 (s)", f"{sm['p25_duration_s']:.0f} / {sm['p75_duration_s']:.0f} / {sm['p90_duration_s']:.0f} / {sm['p95_duration_s']:.0f}"),
             ("Events / valid session", sm["events_per_valid_session"]), ("Features / valid session", sm["distinct_features_per_valid_session"]),
             ("One-session users", sm["one_session_users"]), ("Repeat-session users", sm["repeat_session_users"]),
             (f"High-frequency users (≥{sm['high_frequency_session_threshold']} sessions, P75)", sm["high_frequency_session_users"])]
    S.append(table(pd.DataFrame(srows, columns=["Metric", "Value"]).astype(str), widths=[3, 2]))
    S.append(P("Duration bands: " + esc(R["sessions"]["duration_band_rule"])))
    S.append(table(R["sessions"]["duration_bands"], ["duration_band", "sessions", "pct_sessions", "mean_raw_events", "mean_meaningful",
                                                     "meaningful_session_share", "meaningful_per_minute"]))
    S.append(chart("C03_session_duration.png", W * 0.8))
    S.append(chart("C02_session_frequency.png", W * 0.7))
    S.append(tagged("ANALYST INTERPRETATION", f"Longer sessions are not deeper (ρ={sm['duration_events_spearman']}); short sessions "
                    "deliver the most meaningful actions per minute. Duration should not be treated as 'good engagement'."))

    # ------------------------------------------------------------------ 06 feature usage
    S.append(PageBreak())
    S.append(P("06. Feature Usage Analysis", "h1"))
    S.append(table(ft, ["feature", "unique_users", "share_of_active_users_pct", "total_events", "sessions_with_feature",
                        "first_feature_users", "repeat_users", "avg_uses_per_user", "median_uses_per_user",
                        "event_completion_rate_pct", "event_abandonment_rate_pct", "repeat_usage_rate_pct"],
                   [2] + [1] * 11, headers=["Feature", "Users", "% active", "Events", "Sessions", "First-feature users", "Repeat users",
                                            "Avg uses", "Median uses", "Completion %", "Abandon %", "Repeat %"]))
    S.append(P("Completion/abandonment rates exist only for features that log an explicit negative outcome (Watch Ads, CAPTCHA, "
               "Missions). Task categories (05_Task_Activity):", "small"))
    S.append(table(R["features"]["task_categories"], ["task_category", "records", "users", "completion_rate_pct", "abandonment_rate_pct",
                                                      "failure_rate_pct", "pending_share_pct", "median_start_to_complete_s"]))
    S.append(chart("C15_task_outcomes.png", W * 0.8))

    # ------------------------------------------------------------------ 07 adoption & repeat
    S.append(PageBreak())
    S.append(P("07. Feature Adoption &amp; Repeat Usage", "h1"))
    S.append(P("Exposure (any event) → Adoption (interaction beyond viewing) → Completion (≥1 'complete' event) → Repeat adoption "
               "(completed on ≥2 days) → Depth (completions per completer). View-only features have no adoption/completion stage."))
    S.append(table(ft, ["feature", "exposure_users", "adoption_users", "completion_users", "completion_user_rate_pct",
                        "repeat_completion_users", "repeat_completion_rate_pct", "depth_mean_completions", "depth_median_completions"],
                   [2] + [1] * 8))
    S.append(chart("C05_feature_adoption.png", W * 0.75))
    S.append(chart("C06_feature_repeat_use.png", W * 0.75))

    # ------------------------------------------------------------------ 08 segmentation
    S.append(PageBreak())
    S.append(P("08. Engagement Segmentation", "h1"))
    sg = R["segmentation"]
    S.append(table(sg["profile"], ["segment", "rule", "users", "pct_users", "mean_active_days", "mean_sessions", "mean_features_completed",
                                   "task_completion_rate_pct", "rationale"], [1.5, 2.6, 0.7, 0.7, 0.8, 0.8, 0.9, 0.9, 3]))
    S.append(P(f"Segments are mutually exclusive (hierarchical rules). Feature breadth correlates with frequency (Spearman ρ = "
               f"{sg['frequency_breadth_spearman']}), so 'Multi-Feature Users' captures broad explorers who are not yet high-frequency."))
    S.append(chart("C07_engagement_segments.png", W * 0.7))

    # ------------------------------------------------------------------ 09 engagement score
    es = R["engagement_score"]
    S.append(P("09. Engagement Score", "h1"))
    S.append(P("<b>Analyst-Created Simulated Engagement Score.</b> " + esc(es["disclaimer"]), "box"))
    S.append(table(es["components"], ["component", "weight", "transformation", "reason"], [3, 0.6, 1.8, 5]))
    S.append(table(es["sensitivity"], ["scenario", "spearman_vs_base", "top_decile_overlap_pct", "bottom_decile_overlap_pct"], [4, 1, 1, 1]))
    pc = es["predictive_check"]
    S.append(P(f"Distribution (active users): min {es['summary_active']['min']:.1f}, median {es['summary_active']['p50']:.1f}, max "
               f"{es['summary_active']['max']:.1f}. Predictive check: {esc(pc['method'])} Spearman ρ = {pc['spearman']} (n = {pc['users']})."))
    S.append(table(es["by_segment"], widths=[2, 1, 1, 1, 1, 1]))
    S += bullets(es["limitations"])
    S.append(chart("C17_engagement_score.png", W * 0.7))

    # ------------------------------------------------------------------ 10 time
    S.append(PageBreak())
    tm = R["time"]
    S.append(P("10. Daily &amp; Time-Based Behavior", "h1"))
    S.append(chart("C01_daily_active_users.png"))
    S.append(tagged("SIMULATED DATA RESULT", f"DAU tracks the cumulative registered base (ρ = {tm['corr_dau_cumreg']}); the daily active share "
                    f"of registered users rose from {tm['avg_active_rate_may']}% (May) to {tm['avg_active_rate_last_30d']}% (last 30 days). "
                    f"{len(tm['flags'])} day(s) flagged by robust-z detection."))
    if len(tm["flags"]):
        S.append(table(tm["flags"]))
    S.append(tagged("ANALYST INTERPRETATION", "Flags are statistical only. No campaign, release or notification calendar is available, so "
                    "no flagged day is attributed to a cause."))
    S.append(table(tm["dow"], ["dow", "avg_dau", "avg_sessions", "dau_index_vs_7d_mean", "events_per_active_user_day",
                               "meaningful_share_pct", "task_completion_rate_pct"]))
    S.append(table(tm["daypart"], ["daypart", "sessions", "pct_sessions", "sessions_per_hour_of_bucket", "events", "avg_session_duration_s",
                                   "task_completion_rate_pct"]))
    S.append(chart("C13_time_of_day.png", W * 0.8))
    S.append(P("New vs returning activity (session level: first active day vs later days)", "h2"))
    S.append(table(tm["new_vs_returning"], ["activity_type", "sessions", "users", "mean_events", "mean_features", "mean_meaningful",
                                            "median_duration_s", "task_completion_rate_pct", "ad_skip_rate_pct", "mission_abandon_rate_pct"]))
    S.append(tagged("PRODUCT HYPOTHESIS", "Because hour/day patterns are flat in the simulated data, it cannot inform notification timing, "
                    "campaign scheduling or maintenance windows; those decisions need production data."))

    # ------------------------------------------------------------------ 11 device
    S.append(PageBreak())
    da = R["segments_device_acq"]
    S.append(P("11. Device Analysis", "h1"))
    S.append(P(esc(da["platform_note"])))
    S.append(chart("C09_device_behaviour.png"))
    S.append(table(da["device"]["tests"], ["metric", "test", "p_value", "effect_size", "effect_measure", "interpretation"], [2.5, 1.2, 0.8, 0.8, 1, 3.5]))
    S.append(tagged("ANALYST INTERPRETATION", "Observed behavioural differences between devices are small. Possible explanations for the "
                    "minor activation gap (e.g. desktop users registering with lower intent) are hypotheses only."))

    # ------------------------------------------------------------------ 12 acquisition
    S.append(P("12. Acquisition Behavior Analysis", "h1"))
    S.append(chart("C08_acquisition_behaviour.png"))
    S.append(table(da["acquisition"]["table"], ["acquisition_source", "users", "activation_rate_pct", "median_days_to_first_activity",
                                                "d7_return_pct", "d30_return_pct", "mean_active_days", "mean_feature_diversity",
                                                "task_completion_rate_pct", "mean_engagement_score"]))
    S.append(tagged("ANALYST INTERPRETATION", "Organic Search brings the most registrations, but no source shows materially deeper "
                    "behaviour; ranking sources by volume would be misleading. Simulated sources do not reflect real marketing performance."))

    # ------------------------------------------------------------------ 13 journey
    S.append(PageBreak())
    jn = R["journey"]
    S.append(P("13. User Journey Analysis", "h1"))
    S.append(P("Order uses event_datetime (sequence_number is invalid). Consecutive events of the same feature are collapsed."))
    S.append(table(jn["first_second"].head(8), ["feature", "first_feature_users", "first_pct_of_active", "second_feature_users"]))
    S.append(table(jn["top_paths"].head(8), widths=[5, 1, 1]))
    S.append(table(jn["successful_vs_abandoned"], widths=[2, 5, 1]))
    S.append(table(jn["exits"].head(8), ["feature", "last_raw_event_feature", "last_raw_pct", "exit_feature_field", "field_pct"]))
    S.append(chart("C11_feature_journey_transitions.png", W * 0.85))
    S.append(tagged("ANALYST INTERPRETATION", f"No path dominates (top path = {jn['top_paths'].iloc[0].pct_valid_sessions}% of sessions); "
                    f"transition lifts {jn['transition_lift_range'][0]:.2f}–{jn['transition_lift_range'][1]:.2f}. Sequence frequency does not imply causation."))

    # ------------------------------------------------------------------ 14 drop-off
    S.append(PageBreak())
    S.append(P("14. Drop-Off Analysis", "h1"))
    S.append(table(dm, ["stage", "unit", "entering", "continuing", "drop_off", "drop_off_pct", "observation", "limitation", "product_implication"],
                   [2, 0.9, 0.8, 0.8, 0.7, 0.7, 2.6, 2.2, 2.4]))
    S.append(chart("C12_dropoff.png", W * 0.85))
    S.append(P("Engagement funnel (Work Package T)", "h2"))
    S.append(P("Uses the same canonical stages as the activation funnel; the first six stages are identical. No 'viewed a "
               "feature' stage is used because Ads, CAPTCHA, Tap &amp; Earn and Mining log no view events.", "small"))
    S.append(table(R["dropoff"]["engagement_funnel"], ["stage", "definition", "users", "pct_of_registered", "pct_of_previous",
                                                       "users_standalone", "limitation"], [1.8, 2.8, 0.8, 0.8, 0.8, 0.8, 2.8],
                   headers=["Stage", "Definition", "Users (cumulative)", "% of 1,000 registered", "% of previous",
                            "Users (standalone)", "Limitation"]))

    # ------------------------------------------------------------------ 15 repeat
    S.append(PageBreak())
    rp = R["repeat"]
    S.append(P("15. Repeat Engagement Analysis", "h1"))
    S.append(table(rp["comparison"], widths=[3, 1.5, 1.5]))
    S.append(P("First-active-day feature completion vs D7 return (volume-adjusted by first-day event tercile):", "h2"))
    S.append(table(rp["day1_association"], ["feature", "users_completed_day1", "d7_return_if_completed_pct", "d7_return_if_not_pct",
                                            "raw_difference_pp", "volume_adjusted_difference_pp", "chi2_p_value", "reading"]))
    S.append(tagged("ANALYST INTERPRETATION", "The simulated dataset shows an association between spreading activity over visits and "
                    "repeated engagement. It does not show that any feature causes return; raw feature differences mostly vanish after "
                    "adjusting for first-day volume."))
    pr = R["progression"]
    S.append(P("Streak &amp; progression behaviour (Work Package Q)", "h2"))
    stx = pr["streak"]
    lvx = pr["level"]
    S += bullets([
        f"Users claiming streaks: {stx['users_claiming']} ({stx['pct_active_claiming']}% of active); breaking: {stx['users_breaking']}; both: {stx['users_claim_and_break']}.",
        f"Maintaining (claims on consecutive days): {stx['users_consecutive_claim_days']} users ({stx['pct_claimers_consecutive']}%); longest run {stx['max_consecutive_claim_days']} days.",
        f"Activity around first streak break: {stx.get('around_first_break', {}).get('mean_active_days_7d_before')} active days in prior 7 vs "
        f"{stx.get('around_first_break', {}).get('mean_active_days_7d_after')} after (p = {stx.get('around_first_break', {}).get('wilcoxon_p', float('nan')):.2f}).",
        f"Level-ups: {lvx['users_with_level_up']} users ({lvx['pct_active']}%), {lvx['level_up_events']} events; "
        f"{lvx['users_interacting_progression_features']} users touched progression features (Level, Badges, Leaderboard, Missions).",
        f"Activity 14 days before vs after first level-up: {lvx['before_after_first_level_up']['mean_active_days_14d_before']} vs "
        f"{lvx['before_after_first_level_up']['mean_active_days_14d_after']} active days (p = {lvx['before_after_first_level_up']['wilcoxon_p_active_days']:.2f}).",
        lvx["current_level_and_xp_balance"],
    ])
    S.append(tagged("DOCUMENTED PRODUCT FACT", "Per the brief, VELOOP's level system describes XP as a progression mechanism based on valid "
                    "activity and notes thresholds and benefits may change; simulated thresholds are therefore dataset-specific."))

    # ------------------------------------------------------------------ 16 retention
    S.append(PageBreak())
    rt = R["retention"]
    S.append(P("16. Cohort &amp; Return Analysis", "h1"))
    S += bullets([f"{k}: {v_}" for k, v_ in rt["definitions"].items() if k != "windows"] +
                 [f"Windows: " + "; ".join(f"{k} = {v_}" for k, v_ in rt["definitions"]["windows"].items())])
    S.append(P("<b>Primary retention table</b> – one anchor (first active date), one active definition, eligible users only:", "small"))
    S.append(table(rt["table"], headers=["Window", "Days after first active day", "Eligible users", "Returned users", "Return rate %"]))
    S.append(P("D1 is a single day; D7, D14 and D30 are 7-day windows, so the rates are not cumulative and D30 can be close to D7. "
               "The registration-anchored comparison is in Appendix D.", "small"))
    S.append(P("Exact-day ('classic') return for comparison: " + ", ".join(
        f"day {k.split('_')[1]} {v_['rate_pct']}% (n={v_['eligible']})" for k, v_ in rt["classic_exact_day"].items()) + "."))
    S.append(table(rt["monthly"], ["cohort_month", "users", "D1_rate_pct", "D7_rate_pct", "D14_rate_pct", "D30_rate_pct", "mean_active_days"]))
    S.append(chart("C16_calendar_effect.png", W * 0.6))
    S.append(chart("C10_cohort_return_heatmap.png", W * 0.85))
    S.append(P("Behavioural cohorts on a fixed 30-day horizon", "h2"))
    S.append(table(rt["cohorts_30d"], widths=[1.6, 1.6, 0.6, 1, 1, 1, 1, 1, 0.9, 0.9]))
    S.append(table(rt["cohort_tests"]))

    # ------------------------------------------------------------------ 17 anomalies
    S.append(PageBreak())
    an = R["anomalies"]
    S.append(P("17. Behavioral Anomaly Analysis", "h1"))
    S.append(P("Detect → quantify → document → flag for investigation. No fraud determination is made and no confidential "
               "anti-fraud rule is implied."))
    S.append(table(an["summary"], ["type", "entities_flagged", "population", "pct_flagged", "threshold", "recommended_investigation"],
                   [3, 1, 1, 0.8, 2, 3]))
    S.append(chart("C14_behavioural_anomalies.png", W * 0.7))
    S.append(table(an["top_examples"].head(10), ["anomaly_id", "type", "entity", "metric", "observed_value", "threshold", "severity"],
                   [1, 2.5, 1.6, 2, 0.8, 0.8, 0.8]))
    S.append(P(f"Full register: outputs/tables/anomaly_register.csv ({len(an['register'])} records).", "small"))

    # ------------------------------------------------------------------ 18 dq impact
    S.append(PageBreak())
    S.append(P("18. Data Quality Impact", "h1"))
    S.append(table(R["dq_impact"]["table"], ["scenario", "metric", "before_cleaning", "after_cleaning", "absolute_change", "percent_change",
                                             "conclusion_changes", "explanation"], [2.2, 2, 0.9, 0.9, 0.9, 0.8, 0.9, 3]))
    S.append(chart("C18_data_quality_impact.png", W * 0.8))

    # ------------------------------------------------------------------ 19 findings
    S.append(PageBreak())
    S.append(P("19. Behavioral Findings", "h1"))
    for r in ins["findings"].itertuples():
        S.append(KeepTogether([
            P(f"{r.finding_id} · {esc(r.title)} <font size='7' color='#52514e'>({esc(r.theme)} · confidence {r.confidence})</font>", "h2"),
            tagged("SIMULATED DATA RESULT", "<b>Observation:</b> " + esc(r.observation)),
            tagged("SIMULATED DATA RESULT", "<b>Evidence:</b> " + esc(r.evidence)),
            tagged("ANALYST INTERPRETATION", "<b>Interpretation:</b> " + esc(r.interpretation)),
            P("<b>Limitation:</b> " + esc(r.limitation)),
            tagged("PRODUCT HYPOTHESIS", "<b>Product implication:</b> " + esc(r.product_implication)),
        ]))

    # ------------------------------------------------------------------ 20-21 registers
    S.append(PageBreak())
    S.append(P("20. Product Friction Register", "h1"))
    S.append(table(ins["friction"], ["issue_id", "behavioral_signal", "affected_users", "evidence", "possible_explanations", "confidence",
                                     "product_area", "investigation_needed"], [0.8, 1.8, 0.8, 2.2, 2.4, 0.8, 1.2, 2.2]))
    S.append(P("Possible explanations are hypotheses; none is confirmed by the dataset.", "small"))
    S.append(P("21. Product Opportunity Register", "h1"))
    S += bullets([f"{k}: {v_}" for k, v_ in ins["priority_criteria"].items()])
    S.append(table(ins["opportunities"], ["opportunity_id", "finding", "user_problem", "product_hypothesis", "proposed_investigation",
                                          "affected_population", "priority_score", "priority", "measurement"],
                   [0.9, 1.6, 1.6, 2.2, 1.8, 0.8, 0.7, 0.7, 1.8]))

    # ------------------------------------------------------------------ 22 dashboard
    S.append(PageBreak())
    S.append(P("22. Dashboard", "h1"))
    S.append(P("Live: https://veloop-data-analyst-task02.vercel.app/ · An interactive, client-facing dashboard (React + TypeScript + "
               "Vite + Tailwind + Recharts, folder <i>dashboard/</i>) built on aggregate, identifier-free data. It keeps business "
               "content only; technical material (data-quality register, anomaly queue, metric reconciliation, model details) stays "
               "in this report and the repository. Filters: acquisition source, device, user group, feature and activity dates. A "
               "simulated-data banner is shown on every page."))
    S.append(table(pd.DataFrame([
        ("Overview", "Registered and active users, sessions, active days, activation, return, broad-usage and task-completion rates; daily active users; user journey; key findings"),
        ("User Behaviour", "Active users over time, visit frequency, session length, active days and the six user groups"),
        ("Features", "Feature usage vs completion, features users come back to, where attempts are lost (ads, CAPTCHA, missions), task results by category"),
        ("Retention", "Next-day, first-week, second-week and fourth-week return; weekly retention curve; first-week return by month joined"),
        ("Insights & Actions", "Where users drop off, the biggest problems found, and recommended actions with how to test them and what success looks like"),
    ], columns=["View", "Content"]), widths=[1.5, 6]))
    S.append(P("Run locally: <i>cd dashboard &amp;&amp; npm install &amp;&amp; npm run dev</i>. Deploy: import the repository in Vercel with "
               "root directory <i>dashboard</i> (see README).", "small"))

    # ------------------------------------------------------------------ 23 KPI catalogue
    S.append(P("23. KPI Catalogue", "h1"))
    S.append(table(R["kpis"]["catalogue"], ["kpi_id", "category", "kpi_name", "formula", "denominator", "data_source", "current_value_simulated",
                                            "limitation"], [0.7, 1.1, 1.6, 2.2, 1.4, 1.1, 1.2, 1.8]))
    S.append(P("Definitions, units and interpretations for every KPI: outputs/tables/kpi_catalogue.csv and docs/kpi_catalogue.md.", "small"))

    # ------------------------------------------------------------------ 24 experiments
    S.append(PageBreak())
    S.append(P("24. Product Experiment Hypotheses", "h1"))
    S.append(P("<b>PROPOSED EXPERIMENTS.</b> None of these was run; they are designs for future testing. Each design states the "
               "baseline (measured in the simulated data), the smallest change worth detecting, the sample size needed "
               "(two-sided two-proportion test, α = 0.05, power 80%) and the decision rule, so results can be judged objectively.", "box"))
    S.append(table(ins["experiments"], ["experiment_id", "baseline_metric", "baseline_value_pct", "minimum_detectable_effect_pp",
                                        "target_value_pct", "sample_size_per_arm", "randomisation_unit",
                                        "est_duration_days_at_simulated_volume"], [0.8, 2.4, 0.8, 0.8, 0.8, 0.9, 1.6, 1],
                   headers=["ID", "Primary metric", "Baseline %", "MDE (pp)", "Target %", "Sample / arm", "Unit",
                            "Days at simulated volume"]))
    S.append(P("Duration uses the simulated data's tiny volume (≈6 new users per day), so most tests would take months; the sample "
               "size is the useful number – with production traffic, duration = 2 × sample size ÷ eligible users per day.", "small"))
    for r in ins["experiments"].itertuples():
        S.append(KeepTogether([P(f"{r.experiment_id} · PROPOSED EXPERIMENT", "h2"), table(pd.DataFrame([
            ("Hypothesis", r.hypothesis), ("Problem (evidence)", r.problem_evidence), ("Target users", r.target_users),
            ("Control", r.control), ("Variant", r.variant),
            ("Primary metric", f"{r.primary_metric} – baseline {r.baseline_value_pct}%, target {r.target_value_pct}% "
                               f"(+{r.minimum_detectable_effect_pp} pp)"),
            ("Sample size", f"{r.sample_size_per_arm:,} {r.randomisation_unit.split(' (')[0]}s per arm; randomise by "
                            f"{'user' if 'user' in r.randomisation_unit else r.randomisation_unit}"),
            ("Secondary metrics", r.secondary_metrics), ("Guardrail metrics", r.guardrail_metrics),
            ("Analysis", r.analysis_method), ("Decision rule", r.decision_rule),
            ("Expected behavioural change", r.expected_behavioral_change), ("Required event tracking", r.required_event_tracking)],
            columns=["Field", "Value"]), widths=[1.4, 6])]))

    # ------------------------------------------------------------------ 25 tracking gaps
    S.append(PageBreak())
    S.append(P("25. Event Tracking Gaps", "h1"))
    S.append(P("All events below are PROPOSED analytics events – none exists in the simulated taxonomy."))
    S.append(table(ins["tracking_gaps"], ["event_name", "trigger", "required_properties", "why_needed", "kpi_supported"], [1.8, 1.6, 2.2, 2.4, 1.6]))

    # ------------------------------------------------------------------ 26 limitations
    S.append(P("26. Limitations — What This Dataset Cannot Tell Us", "h1"))
    S.append(P("From the brief", "h2"))
    S += bullets(ins["limitations_general"])
    S.append(P("Discovered during analysis", "h2"))
    S += bullets(ins["limitations_specific"])

    # ------------------------------------------------------------------ 27 recommendations
    S.append(PageBreak())
    S.append(P("27. Final Product Analytics Recommendations", "h1"))
    S.append(P("Framework (brief §45): Finding → Evidence → User impact → Product hypothesis → <b>how it will be tested</b> → "
               "<b>how success is measured</b> → decision rule. None claims a change will definitely improve retention; each must "
               "pass its test first."))
    for r in ins["recommendations"].itertuples():
        S.append(KeepTogether([P(f"{r.recommendation_id} · {esc(r.finding)} <font size='7' color='#52514e'>(priority {r.priority})</font>",
                                 "h2"), table(pd.DataFrame([
            ("Evidence (simulated)", r.evidence), ("User impact", r.user_impact), ("Product hypothesis", r.product_hypothesis),
            ("How to test", r.how_to_test), ("How to measure", r.how_to_measure), ("Decision rule", r.decision_rule),
            ("Timeline", r.timeline)], columns=["Field", "Value"]), widths=[1.4, 6])]))
    S.append(P("Advanced analyses performed", "h2"))
    S.append(table(R["advanced"]["register"], ["analysis", "method", "key_result"], [1.6, 3, 3.4]))

    # ------------------------------------------------------------------ appendices
    S.append(PageBreak())
    S.append(P("Appendix A — Answers to the 22 required analytical questions (brief §43)", "h1"))
    S.append(table(answers(R, u), widths=[1, 2.6, 5]))
    S.append(PageBreak())
    S.append(P("Appendix B — Chart catalogue", "h1"))
    S.append(table(R["charts"]["catalogue"], ["chart_id", "chart_name", "business_question", "dataset", "calculation", "population",
                                              "limitation", "product_relevance"], [0.6, 1.4, 1.8, 1, 2, 1, 1.6, 1.4]))
    S.append(P("Appendix C — Source register", "h1"))
    S += bullets([
        "Task 02 brief (Data_Analyst_02.pdf) – formal requirement document.",
        "VELOOP_Simulated_User_Behavior_1000.xlsx – simulated dataset (10 sheets).",
        "Product-context baseline cited by the brief (not independently accessed for this analysis): VELOOP Rewards Help Center, "
        "About Us, Privacy Policy, Level System and Disclaimer pages. Statements tagged DOCUMENTED PRODUCT FACT are limited to what the brief "
        "itself attributes to these sources.",
    ])
    S.append(PageBreak())
    S.append(P("Appendix D — Metric reconciliation", "h1"))
    S.append(P("Numbers that look alike but differ by definition or denominator. Every pair below was recomputed by the pipeline; "
               "differences are explained, not errors."))
    S.append(table(R["kpis"]["reconciliation"], ["id", "metrics_compared", "value_a", "value_b", "definition_difference", "explanation"],
                   [0.7, 2, 1.1, 1.1, 2.4, 2.6], headers=["ID", "Metrics compared", "Value A", "Value B", "Definition difference",
                                                          "Why they differ"]))
    S.append(P("Registration-anchored return (comparison only)", "h2"))
    S.append(table(R["retention"]["registration_anchor_table"],
                   headers=["Window", "Days after registration", "Eligible users", "Returned users", "Return rate %"]))
    S.append(P("Appendix E — Independent verification", "h1"))
    S += bullets([
        "Source code: analysis/ (23 pipeline steps, one per analysis area) and dashboard/ – shared with this report.",
        "Dataset: data/anonymised/ contains every sheet of the supplied workbook as CSV with personal fields (name, email, age, "
        "gender, city, state, referral code) removed; simulated user IDs are kept so joins can be checked.",
        "Methodology: docs/methodology.md (every definition), docs/verification_guide.md (step-by-step checks).",
        "verify_headline_metrics.py recomputes the headline numbers directly from data/anonymised/ with plain pandas, without "
        "using the pipeline code, and compares them with the published outputs.",
        "Automated tests: tests/ (Python) and dashboard/src/lib/*.test.ts check arithmetic, denominators, funnel consistency and that "
        "the dashboard reproduces the pipeline numbers for every filter value.",
    ])
    doc.build(S, onFirstPage=_page, onLaterPages=_page)
    ctx.R["report_path"] = str(path)
