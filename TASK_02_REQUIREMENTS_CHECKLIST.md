# Task 02 Requirements Checklist

Checked against every work package in `Data_Analyst_02.pdf` (the formal requirement document). Report section numbers refer to
`outputs/reports/VELOOP_Task02_User_Behavior_Engagement_Intelligence_Report.pdf`. All tables are in `outputs/tables/`.

| # | Requirement (PDF section) | Implemented? | Evidence / file | Notes |
|---|---|---|---|---|
| 1 | Data authenticity wording (§2, §50, §51) | Yes | Report cover + statement-class tags; README disclaimer; dashboard footer | Five statement classes tagged throughout the report |
| 2 | Standalone (§4) | Yes | Uses only the Task 02 workbook | No Task 01 assets, credentials or production data |
| 3 | **Dataset validation** – WP-A (§14) | Yes | `data_quality_report.csv/.xlsx`, `dq_sheet_profile.csv`, `dq_column_profile.csv`; report §02 | 73 checks, VALID/WARNING/INVALID/INVESTIGATE, count, %, severity, impact, action |
| 4 | **User lifecycle** – WP-B (§15) | Yes | `lifecycle_stages.csv`, `lifecycle_time_to_activity_buckets.csv`, `milestones_derived_vs_sheet.csv`; report §03 | Meaningful activity defined from taxonomy with inclusions, exclusions, rationale, limitations |
| 5 | **Activation funnel** – WP-C (§16) | Yes | `activation_windows.csv`, `activation_funnel.csv`, `activation_by_reg_month.csv`; chart C04; report §04 | 1/3/7/14/30-day windows tested; window chosen by documented rule |
| 6 | **Session analysis** – WP-D (§17) | Yes | `session_duration_bands.csv`, `session_frequency_distribution.csv`, `session_entry_points.csv`; C02, C03; report §05 | Mean, median, P25–P99; bands from observed quartiles; duration ≠ quality tested |
| 7 | **Feature usage** – WP-E (§18) | Yes | `feature_usage_metrics.csv`, `task_category_metrics.csv`; report §06 | All 11 required per-feature metrics; 07_Feature_Usage used as reference |
| 8 | **Feature adoption** – WP-F (§19) | Yes | `feature_adoption_stages.csv`; C05; report §07 | Exposure / adoption / completion / repeat / depth kept separate |
| 9 | **Repeat usage** (§18–19) | Yes | `feature_usage_metrics.csv` (repeat_usage_rate, repeat_completion_rate); C06 | |
| 10 | **Segmentation** – WP-G (§20) | Yes | `engagement_segments.csv`, `segment_frequency_breadth_matrix.csv`; C07; report §08 | Neutral labels, quantile thresholds, mutually exclusive |
| 11 | **Engagement score** – WP-H (§21) | Yes | `engagement_score_components.csv`, `_sensitivity.csv`, `_predictive_check.csv`, `_extremes.csv`; C17; report §09 | Labelled "Analyst-Created Simulated Engagement Score"; not official |
| 12 | **Daily behaviour** – WP-I (§22) | Yes | `daily_activity_timeseries.csv`, `monthly_activity.csv`, `day_of_week_activity.csv`, `weekly_feature_events.csv`; C01 | Spikes flagged statistically; no campaign attribution |
| 13 | **Time-of-day** – WP-J (§23) | Yes | `hour_of_day_activity.csv`, `daypart_activity.csv`, `feature_by_daypart_pct.csv`, `sessions_dow_hour_heatmap.csv`; C13 | Observed vs hypothesis separated (timezone undocumented) |
| 14 | **New vs returning** – WP-K (§24) | Yes | `new_vs_returning_sessions.csv`, `new_vs_returning_feature_mix.csv`; report §10 | Descriptive comparison, no "better" claim |
| 15 | **Device analysis** – WP-L (§25) | Yes | `device_behaviour_comparison.csv`, `device_significance_tests.csv`; C09; report §11 | Platform single-valued ("Web") – documented; differences framed as observed + hypotheses |
| 16 | **Acquisition analysis** – WP-M (§26) | Yes | `acquisition_behaviour_comparison.csv`, `acquisition_significance_tests.csv`; C08; report §12 | Not ranked by volume |
| 17 | **Journey analysis** – WP-N (§27) | Yes | `journey_*.csv` (first/second, paths, successful vs abandoned, exits, transitions, sankey links); C11; report §13 | Timestamp ordering; no causal reading |
| 18 | **Drop-off analysis** – WP-O (§28) | Yes | `dropoff_matrix.csv`; C12; report §14 | All 7 brief stages + extras, with observation/limitation/implication |
| 19 | **Repeat engagement** – WP-P (§29) | Yes | `repeat_vs_single_session_users.csv`, `day1_feature_vs_d7_return_association.csv`; report §15 | Association language only |
| 20 | **Streak / progression** – WP-Q (§30) | Yes (partial data) | `streak_summary.csv`, `progression_summary.csv`; report §15 | current_level / xp_balance: **Not supported by available dataset** |
| 21 | **Cohort analysis** – WP-R (§31) | Yes | `cohort_monthly_returns.csv`, `cohort_weekly_matrix.csv`, `behavioural_cohorts_30d.csv`, `behavioural_cohort_tests.csv`; C10, C16 | Registration month, source, device, first feature, activation timing |
| 22 | **D1 retention** – WP-S (§32) | Yes | `return_rates_overall.csv`; report §16 | Cohort date & denominator documented |
| 23 | **D7 retention** | Yes | same | |
| 24 | **D14 retention** | Yes | same | |
| 25 | **D30 retention where supported** | Yes | same | Supported (users with full window); defined as days 24–30 |
| 26 | **Engagement funnel** – WP-T (§33) | Yes | `engagement_funnel.csv`; report §14 | Definition, count, %, denominator, source, limitation per stage |
| 27 | **Anomaly analysis** – WP-U (§34) | Yes | `anomaly_register.csv` (anomaly_id, type, entity, metric, value, threshold, severity, interpretation, investigation), `anomaly_summary.csv`; C14 | No fraud determination |
| 28 | **Data quality impact** – WP-V (§35) | Yes | `data_quality_impact.csv`; C18; report §18 | Before/after/abs/% change; includes 20× duplication stress test |
| 29 | **15+ findings** – WP-W (§36) | Yes (20) | `behavioral_findings.csv`, `docs/findings.md`; report §19 | Observation → Evidence → Interpretation → Limitation → Implication |
| 30 | **Friction register** – WP-X (§37) | Yes (11) | `product_friction_register.csv`; report §20 | Multiple hypotheses, none asserted |
| 31 | **Opportunity register** – WP-Y (§38) | Yes (10) | `product_opportunity_register.csv`; report §21 | Documented 5-criterion priority score; mixed High/Medium/Low |
| 32 | **Dashboard** – WP-Z (§39) | Yes | `dashboard/` (5 views); report §22 | Filters: source, device, segment, feature, date |
| 33 | **10–14+ visualizations** (§40) | Yes (18) | `outputs/charts/C01–C18`; all 14 required types present | |
| 34 | Every chart documented (§41) | Yes | `chart_catalogue.csv`, `docs/chart_catalogue.md`; report Appendix B | All 11 fields per chart |
| 35 | **30+ KPIs** (§42) | Yes (44) | `kpi_catalogue.csv`, `docs/kpi_catalogue.md`; report §23 | Definition, formula, unit, denominator, source, value, interpretation, limitation |
| 36 | 22 analytical questions answered (§43) | Yes | Report Appendix A | |
| 37 | **5+ advanced analyses** (§44) | Yes (15) | `advanced_analysis_register.csv`; report §27 | Association vs explanation vs causation distinguished |
| 38 | Recommendation framework (§45) | Yes | `final_recommendations.csv`; report §27 | Finding/evidence/impact/hypothesis/investigation/measurement |
| 39 | **5+ experiment hypotheses** (§46) | Yes (10) | `proposed_experiments.csv`; report §24 | Labelled PROPOSED EXPERIMENT – not run; each with baseline, MDE, sample size, decision rule |
| 40 | **Event tracking gaps** (§47) | Yes (18) | `event_tracking_gaps.csv`; report §25 | Labelled PROPOSED analytics events |
| 41 | **Limitations** – "What This Dataset Cannot Tell Us" (§48) | Yes | Report §26; README | 9 brief limitations + 12 dataset-specific |
| 42 | Final report structure, 27 sections, exec summary ≤ 3 pages (§49) | Yes | PDF (exec summary = pages 2–3) | |
| 43 | **Final recommendations** | Yes | Report §27, `docs/recommendations.md` | |
| 44 | Privacy / no unnecessary PII (§50, Phase 3) | Yes | `.gitignore`; PII dropped at load; privacy test in `tests/test_outputs.py` | |
| 45 | Cross-validation of sheets (Phase 35) | Yes | `docs/methodology.md` §2; DQ-016…DQ-069; `dq_feature_usage_reconciliation.csv` | Discrepancies quantified; source chosen and documented |
| 46 | Source discrepancy flagged (Phase 37) | Yes | DQ-070, DQ-072; report §02 | README "22–25 day" vs PDF "20–24 Days": **Source discrepancy requiring confirmation** |
| 47 | Tests (Phase 34) | Yes | `tests/` (24 pytest), `dashboard/src/lib/*.test.ts` (43 vitest incl. 35 filter cases), `verify_headline_metrics.py` (19 independent checks) | Percentages, denominators, KPI equality report ↔ dashboard ↔ tables |
| 48 | **README** | Yes | `README.md` | All requested sections |
| 49 | **GitHub-ready project** | Yes | `.gitignore`, `requirements.txt`, structure | Raw workbook excluded; not yet pushed (no remote configured) |
| 50 | **Vercel-ready dashboard** | Yes | `dashboard/vercel.json`, data in `dashboard/public/data`; `npm run build` succeeds | Root directory = `dashboard`; not deployed (needs the owner's Vercel account) |

## Items not supported by the dataset (documented, not invented)

- Login, registration, onboarding, session_started/ended and task_* events → proxies documented; listed as tracking gaps.
- current_level and xp_balance → progression limited to event counts.
- Platform analysis (all records = "Web") → device used instead.
- Task view → start drop-off (every task record has a start) → limitation recorded.
- Causes of spikes, return differences or friction → hypotheses only.
