"""Export: dashboard data (JSON), analytical Excel workbook, data-quality workbook.

Dashboard privacy: no names/emails/demographics, and no user_id in the filterable arrays – users are
represented only by an array position. Anomaly entities keep simulated pseudonymous IDs because an
investigation queue needs a reference (no personal data is attached to them).
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from analysis import config
from analysis.pipeline.context import Context
from analysis.utils.io import save_json, to_jsonable

EXCEL_SHEETS = [
    ("data_quality_report", "DQ_Issues"), ("dq_sheet_profile", "DQ_Sheet_Profile"), ("data_quality_impact", "DQ_Impact"),
    ("lifecycle_stages", "Lifecycle"), ("milestones_derived_vs_sheet", "Milestones_Check"), ("activation_windows", "Activation_Windows"),
    ("activation_funnel", "Activation_Funnel"), ("engagement_funnel", "Engagement_Funnel"), ("session_duration_bands", "Session_Bands"),
    ("session_frequency_distribution", "Session_Frequency"), ("feature_usage_metrics", "Feature_Usage"),
    ("feature_adoption_stages", "Feature_Stages"), ("task_category_metrics", "Task_Categories"), ("task_failure_reasons", "Task_Failures"),
    ("feature_affinity_pairs", "Feature_Affinity"), ("engagement_segments", "Segments"), ("engagement_score_components", "Score_Components"),
    ("engagement_score_sensitivity", "Score_Sensitivity"), ("daily_activity_timeseries", "Daily_Series"), ("day_of_week_activity", "Day_of_Week"),
    ("hour_of_day_activity", "Hour_of_Day"), ("daypart_activity", "Daypart"), ("new_vs_returning_sessions", "New_vs_Returning"),
    ("device_behaviour_comparison", "Device"), ("device_significance_tests", "Device_Tests"),
    ("acquisition_behaviour_comparison", "Acquisition"), ("acquisition_significance_tests", "Acquisition_Tests"),
    ("journey_top_session_paths", "Journey_Paths"), ("journey_transition_probabilities", "Journey_Transitions"),
    ("journey_exit_points", "Exit_Points"), ("dropoff_matrix", "Dropoff_Matrix"), ("repeat_vs_single_session_users", "Repeat_vs_Single"),
    ("day1_feature_vs_d7_return_association", "Day1_Assoc"), ("return_rates_overall", "Return_Rates"),
    ("cohort_monthly_returns", "Cohorts_Monthly"), ("cohort_weekly_matrix", "Cohorts_Weekly"), ("behavioural_cohorts_30d", "Cohorts_30d"),
    ("anomaly_summary", "Anomaly_Summary"), ("anomaly_register", "Anomaly_Register"), ("correlation_matrix_spearman", "Correlation"),
    ("d30_return_logistic_coefficients", "D30_Model"), ("advanced_analysis_register", "Advanced_Register"),
    ("behavioral_findings", "Findings"), ("product_friction_register", "Friction_Register"),
    ("product_opportunity_register", "Opportunity_Register"), ("proposed_experiments", "Experiments"),
    ("event_tracking_gaps", "Tracking_Gaps"), ("kpi_catalogue", "KPI_Catalogue"), ("chart_catalogue", "Chart_Catalogue"),
    ("final_recommendations", "Recommendations"),
]


def _iso(d):
    return None if pd.isna(d) else pd.Timestamp(d).strftime("%Y-%m-%d")


def run(ctx: Context) -> None:
    R, u = ctx.R, ctx.users
    start_day = ctx.data_start.normalize()
    sources = sorted(u.acquisition_source.unique())
    devices = sorted(u.device.unique())
    segments = R["segmentation"]["order"]
    feats = config.FEATURES

    # ------------------------------------------------------------------ filterable arrays (no ids)
    uf_ev = ctx.extra["uf_events"].reindex(u.user_id).fillna(0).astype(int)
    uf_c = ctx.extra["uf_complete"].reindex(u.user_id).fillna(0).astype(int)
    idx = {uid: i for i, uid in enumerate(u.user_id)}
    e = ctx.events
    started_users = set(e.loc[e.stage == "start", "user_id"]) | set(ctx.tasks.user_id)
    exposed_users = set(e.loc[e.stage == "exposure", "user_id"])

    def flag(v):
        return None if pd.isna(v) else int(v)

    users_rows = []
    for i, r in enumerate(u.itertuples()):
        users_rows.append([
            sources.index(r.acquisition_source), devices.index(r.device), segments.index(r.segment),
            int((r.reg_date - start_day).days),
            None if pd.isna(r.first_active_date) else int((r.first_active_date - start_day).days),
            int(r.n_active_days), int(r.n_sessions), int(r.n_valid_sessions), int(r.n_events), int(r.n_features),
            int(r.n_features_completed), int(r.n_meaningful), int(r.n_tasks_resolved), int(r.n_tasks_completed),
            round(float(r.engagement_score), 1),
            None if not r.activation_eligible else int(r.is_activated),
            flag(r.D1_return), flag(r.D7_return), flag(r.D14_return), flag(r.D30_return),
            int(r.has_session), int(r.is_active), int(r.is_multi_feature), int(r.is_regular), int(r.n_meaningful_days_all),
            None if pd.isna(r.hours_to_first_activity) else round(float(r.hours_to_first_activity), 1),
            uf_ev.iloc[i].tolist(), uf_c.iloc[i].tolist(),
            int(r.user_id in started_users), int(r.user_id in exposed_users), int(pd.notna(r.first_meaningful_dt)),
        ])
    user_fields = ["source", "device", "segment", "reg_day", "first_active_day", "active_days", "sessions", "valid_sessions",
                   "events", "features", "features_completed", "meaningful", "tasks_resolved", "tasks_completed", "score",
                   "activated", "d1", "d7", "d14", "d30", "has_session", "is_active", "is_multi", "is_regular",
                   "meaningful_days", "hours_to_first_activity", "feature_events", "feature_completions",
                   "started", "exposed", "completed_any"]
    ud = ctx.user_day
    ud_rows = [[idx[r.user_id], int((r.date - start_day).days), int(r.events), int(r.sessions), int(r.meaningful)]
               for r in ud.itertuples()]
    s = ctx.sessions
    s_rows = [[idx[r.user_id], int((r.date - start_day).days), int(r.hour), int(r.session_start.dayofweek),
               int(r.session_duration_seconds), int(r.raw_event_count), int(r.raw_meaningful_count)] for r in s.itertuples()]
    save_json({"start_date": _iso(start_day), "end_date": _iso(ctx.data_end), "sources": sources, "devices": devices,
               "segments": segments, "features": feats, "user_fields": user_fields, "users": users_rows,
               "userday_fields": ["user", "day", "events", "sessions", "meaningful"], "userday": ud_rows,
               "session_fields": ["user", "day", "hour", "dow", "duration_s", "events", "meaningful"], "sessions": s_rows},
              "filterable")

    # ------------------------------------------------------------------ static aggregates
    an = R["anomalies"]["register"]
    an_sample = pd.concat([g.head(12) for _, g in an.groupby("type")]).reset_index(drop=True)
    agg = {
        "validation": {k: R["validation"][k] for k in ("sheet_profile", "issues", "summary", "record_counts", "unique",
                                                       "date_ranges", "feature_usage_reconciliation")},
        "clean": R["clean"], "thresholds": R["thresholds"],
        "lifecycle": {k: v for k, v in R["lifecycle"].items()},
        "activation": R["activation"], "sessions": R["sessions"],
        "features": R["features"], "segmentation": R["segmentation"],
        "engagement_score": {k: v for k, v in R["engagement_score"].items()},
        "time": {k: v for k, v in R["time"].items() if k not in ("daily",)},
        "daily": R["time"]["daily"][["date", "dau", "sessions", "events", "meaningful_events", "registrations",
                                     "cumulative_registered", "dau_7d_avg", "active_rate_of_registered_pct", "flag"]],
        "device_acq": R["segments_device_acq"], "journey": R["journey"], "dropoff": R["dropoff"],
        "repeat": R["repeat"], "progression": R["progression"], "retention": R["retention"],
        "anomalies": {"summary": R["anomalies"]["summary"], "by_severity": R["anomalies"]["by_severity"],
                      "by_type": R["anomalies"]["by_type"], "flagged_users": R["anomalies"]["flagged_users"],
                      "register_sample": an_sample, "register_total": len(an), "fences": R["anomalies"]["fences"],
                      "density_hist": R["anomalies"]["density_hist"]},
        "dq_impact": R["dq_impact"], "advanced": R["advanced"], "insights": R["insights"], "kpis": R["kpis"],
        "charts": R["charts"],
    }
    save_json(agg, "aggregates")
    kp = {
        "total_users": len(u), "active_users": int(u.is_active.sum()), "sessions": int(len(s)),
        "active_user_days": int(len(ud)), "avg_sessions_per_user": round(len(s) / len(u), 3),
        "repeat_user_rate_pct": round((u.n_active_days >= 2).sum() / u.is_active.sum() * 100, 1),
        "multi_feature_user_rate_pct": round(u.is_multi_feature.sum() / u.is_active.sum() * 100, 1),
        "activation_rate_pct": R["activation"]["rate_pct"], "activation_window_days": R["activation"]["window_days"],
    }
    meta = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "observation_start": _iso(ctx.data_start), "observation_end": _iso(ctx.data_end),
            "disclaimer": "All figures are calculated from a fictional, simulated dataset supplied for the VELOOP Data Analyst "
                          "Internship (Task 02). They do not describe actual VELOOP users, retention, engagement or performance.",
            "executive_kpis": kp, "record_counts": R["validation"]["record_counts"]}
    save_json(meta, "meta", compact=False)
    ctx.R["executive_kpis"] = kp

    # ------------------------------------------------------------------ expected values for dashboard filter tests
    # Computed here with pandas, independently of the TypeScript code, for every single-value filter.
    sd = s.assign(day=(s.date - start_day).dt.days)
    udd = ud.assign(day=(ud.date - start_day).dt.days)
    last_day = int(max(udd.day.max(), sd.day.max()))

    def expect(mask: pd.Series, d0: int = 0, d1: int = last_day) -> dict:
        sel = u[mask.values]
        ids = set(sel.user_id)
        w_ud = udd[udd.user_id.isin(ids) & udd.day.between(d0, d1)]
        ad = w_ud.groupby("user_id").size()
        elig = sel[sel.activation_eligible]
        act_sel = sel[sel.is_active]
        d7 = sel[sel.D7_eligible.astype(bool)]
        stages = [sel.has_session, sel.is_active, sel.started, sel.completed_any, sel.n_active_days >= 2,
                  sel.n_meaningful_days_all >= 3]
        cum, funnel = pd.Series(True, index=sel.index), [len(sel)]
        for st_ in stages:
            cum = cum & st_
            funnel.append(int(cum.sum()))
        r1 = lambda a, b: None if b == 0 else round(a / b * 100, 1)  # noqa: E731
        return {"totalUsers": len(sel), "activeUsers": int(len(ad)), "activeDays": int(len(w_ud)),
                "sessions": int(sd[sd.user_id.isin(ids) & sd.day.between(d0, d1)].shape[0]),
                "repeatUserRatePct": r1((ad >= 2).sum(), len(ad)),
                "multiFeatureRatePct": r1(sel.is_multi_feature.sum(), len(act_sel)),
                "activationRatePct": r1(elig.is_activated.sum(), len(elig)),
                "d7RatePct": r1(d7.D7_return.sum(), len(d7)), "funnel": funnel}

    cases = []
    for i, v_ in enumerate(sources):
        cases.append({"name": f"source={v_}", "filter": {"sources": [i]}, "expected": expect(u.acquisition_source == v_)})
    for i, v_ in enumerate(devices):
        cases.append({"name": f"device={v_}", "filter": {"devices": [i]}, "expected": expect(u.device == v_)})
    for i, v_ in enumerate(segments):
        cases.append({"name": f"segment={v_}", "filter": {"segments": [i]}, "expected": expect(u.segment == v_)})
    for i, f_ in enumerate(feats):
        cases.append({"name": f"feature={f_}", "filter": {"feature": i},
                      "expected": expect(pd.Series(uf_ev[f_].values > 0, index=u.index))})
    jul0, jul1 = (pd.Timestamp("2026-07-01") - start_day).days, (pd.Timestamp("2026-07-31") - start_day).days
    cases.append({"name": "date=July 2026", "filter": {"dayFrom": jul0, "dayTo": jul1},
                  "expected": expect(pd.Series(True, index=u.index), jul0, jul1)})
    cases.append({"name": "device=Android + date=July 2026", "filter": {"devices": [devices.index("Android")], "dayFrom": jul0,
                                                                        "dayTo": jul1},
                  "expected": expect(u.device == "Android", jul0, jul1)})
    (config.ROOT / "dashboard" / "src" / "lib").mkdir(parents=True, exist_ok=True)
    save_json({"note": "Expected values computed by analysis/pipeline/s21_export.py with pandas. Simulated data.",
               "cases": cases}, "expected_filters", config.ROOT / "dashboard" / "src" / "lib", compact=False)

    # final PII-free user table with every derived field (segments, score, return flags)
    u.to_csv(config.DATA_ANALYTICAL / "users_analytical.csv", index=False)

    # copy to dashboard/public/data
    config.DASHBOARD_PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    for f in config.OUT_DASH.glob("*.json"):
        shutil.copy2(f, config.DASHBOARD_PUBLIC_DATA / f.name)

    # ------------------------------------------------------------------ Excel outputs
    with pd.ExcelWriter(config.OUT_REPORTS / "VELOOP_Task02_Analytical_Outputs.xlsx", engine="openpyxl") as xw:
        pd.DataFrame({"Item": ["Title", "Disclaimer", "Generated (UTC)", "Observation window", "Sheets"],
                      "Value": ["VELOOP Rewards — User Behavior & Engagement Intelligence: analytical outputs", meta["disclaimer"],
                                meta["generated_at_utc"], f"{meta['observation_start']} – {meta['observation_end']}",
                                ", ".join(sh for _, sh in EXCEL_SHEETS)]}).to_excel(xw, sheet_name="README", index=False)
        for name, sheet in EXCEL_SHEETS:
            df = pd.read_csv(config.OUT_TABLES / f"{name}.csv")
            df.to_excel(xw, sheet_name=sheet, index=False)
        for ws in xw.book.worksheets:
            for col in ws.columns:
                width = min(60, max(10, max(len(str(c.value or "")) for c in col[:200]) + 2))
                ws.column_dimensions[col[0].column_letter].width = width
            ws.freeze_panes = "A2"
    with pd.ExcelWriter(config.OUT_TABLES / "data_quality_report.xlsx", engine="openpyxl") as xw:
        pd.read_csv(config.OUT_TABLES / "data_quality_report.csv").to_excel(xw, sheet_name="Issue_Register", index=False)
        pd.read_csv(config.OUT_TABLES / "dq_sheet_profile.csv").to_excel(xw, sheet_name="Sheet_Profile", index=False)
        pd.read_csv(config.OUT_TABLES / "dq_column_profile.csv").to_excel(xw, sheet_name="Column_Profile", index=False)
        pd.read_csv(config.OUT_TABLES / "dq_feature_usage_reconciliation.csv").to_excel(xw, sheet_name="Feature_Usage_Recon", index=False)
        pd.read_csv(config.OUT_TABLES / "data_quality_impact.csv").to_excel(xw, sheet_name="Impact_Before_After", index=False)
        for ws in xw.book.worksheets:
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(70, max(10, max(len(str(c.value or "")) for c in col) + 2))
            ws.freeze_panes = "A2"
