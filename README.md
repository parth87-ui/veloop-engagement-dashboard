# VELOOP Rewards — User Behavior & Engagement Intelligence

**Author:** Parth Khandelwal · VELOOP Rewards Data Analyst Internship — Task 02

🔗 **Live dashboard:** https://veloop-data-analyst-task02.vercel.app/ 

> ** data – VELOOP Rewards — User Behavior & Engagement Intelligence

> dataset supplied for the Data Analyst task (Task 02). It describe actual VELoop Rewards users, retention,
> engagement, acquisition or product performance. The engagement score is an analyst-created model, not an official
> VELoop metric, and every experiment is a proposal that has not been run.

**Verify the results yourself:** `python verify_headline_metrics.py` recomputes the headline numbers from the shared
anonymised dataset (`data/anonymised/`) without using the pipeline code.
## Project Overview

An end-to-end product-analytics project: data validation → clean analytical layer → 20+ behavioural analyses → findings,
friction/opportunity registers, experiments and tracking gaps → an interactive dashboard and a 27-section PDF report.
Everything is produced by one reproducible Python pipeline.

| Deliverable | Location |
|---|---|
| Final report (PDF, 27 sections + appendices) | `outputs/reports/VELOOP_Task02_User_Behavior_Engagement_Intelligence_Report.pdf` |
| Analytical workbook (51 sheets) | `outputs/reports/VELOOP_Task02_Analytical_Outputs.xlsx` |
| Data-quality report | `outputs/tables/data_quality_report.csv` / `.xlsx` |
| 86 analytical tables | `outputs/tables/*.csv` |
| 18 documented charts | `outputs/charts/*.png`, catalogue in `docs/chart_catalogue.md` |
| Interactive dashboard (React/TS/Vite/Tailwind/Recharts) | `dashboard/` |
| Requirements checklist | `TASK_02_REQUIREMENTS_CHECKLIST.md` |
| Anonymised dataset (all 10 sheets, personal fields removed) | `data/anonymised/*.csv` |
| Independent verification script | `verify_headline_metrics.py` |
| Methodology · metric reconciliation · verification guide | `docs/methodology.md` · `docs/metric_reconciliation.md` · `docs/verification_guide.md` |

## Business Objective

Answer the brief's five questions within the simulated cohort: **A.** what happens after a user joins, **B.** which activities
turn new users into active users, **C.** which behaviours are associated with repeat use, **D.** how users interact with each
feature, and **E.** which evidence-based product improvements deserve investigation.

## Dataset

`VELOOP_Simulated_User_Behavior_1000.xlsx` — 10 sheets: Users (1,000), Sessions (7,913), Feature Events (35,704), Daily Activity
(6,667), Task Activity (9,846), Milestones (4,799), Feature Usage (15 aggregate rows), Data Dictionary, README/Status, and an
Event Data-Quality Audit copy (35,714). Observation window 2026-04-01 → 2026-09-15. The workbook is **not committed** (it holds
simulated personal fields); place it in `data/raw/` to reproduce.

## Data Architecture

```
data/raw/ (git-ignored workbook)
   └─ s01 validation ──► outputs/tables/data_quality_report.*
   └─ s02 cleaning  ──► data/processed/ (PII-free sheets) · data/analytical/ (clean events, sessions, tasks, users, user-day)
        └─ s03–s17 analyses ──► outputs/tables/*.csv
        └─ s18–s19 insights & KPIs
        └─ s20 charts ──► outputs/charts/  · s21 export ──► outputs/dashboard_data/ → dashboard/public/data/
        └─ s22 PDF report · s23 generated docs
```

Source hierarchy: raw **Feature Events** are the primary behavioural source; Sessions and Task Activity supply windows and the
task funnel; Daily Activity, Milestones and Feature Usage are validation references (see `docs/methodology.md` §2).

## Analytical Methodology

Definitions (meaningful activity, active day, valid session, feature stages, activation window, return windows, segmentation,
score) are in **`docs/methodology.md`**. Key choices:

- Event order from timestamps — `sequence_number` is invalid; completions cannot be linked to starts, so funnels are user-level.
- Activation window chosen by a capture-curve rule, with censoring-aware denominators.
- Return anchored on first active date, 7-day windows (D1, D7, D14, D30 = days 24–30), registration-anchored rates reported separately.
- All thresholds are quantiles of the observed data, computed at run time.

## Data Validation

73 checks classified **VALID / WARNING / INVALID / INVESTIGATE** with count, %, severity, analytical impact and action
(`outputs/tables/data_quality_report.csv`). Material issues: session counters overstate depth, the milestone sheet contradicts raw
activity, daily duration does not reconcile with sessions, in-session event order is unreliable, `streak_broken` is logged as
"Success", and the brief's login/registration/session/task events are absent. The **Data Quality Impact** table quantifies
before/after values for 29 metrics, including the brief's "duplicate one user 20×" stress test.

## KPIs

44 KPIs across user activity, session behaviour, activation, feature engagement, return, engagement depth and data quality —
each with definition, formula, unit, denominator, source, current simulated value, interpretation and limitation
(`docs/kpi_catalogue.md`).

<!-- AUTO:START (generated by analysis/pipeline/s23_docs.py – do not edit by hand) -->
| Headline metric (simulated dataset) | Value |
|---|---|
| Registered / active users | 1,000 / 984 |
| Sessions · active user-days | 7,913 · 6,667 |
| Avg sessions per user | 7.91 |
| Repeat-user rate (≥2 active days) | 83.9% |
| Multi-feature user rate | 26.9% |
| Activation rate (14-day) | 58.8% |
| D1 / D7 / D14 / D30 return | 14.5% / 47.3% / 45.4% / 41.8% |
| Median session duration | 42 s |
| Task completion rate (resolved) | 61.2% |
| Findings · KPIs · experiments · charts | 20 · 44 · 10 · 18 |
<!-- AUTO:END -->

## Engagement Segmentation

Six mutually exclusive, quantile-derived segments: No Recorded Activity, One-Time, Occasional, Returning, Multi-Feature and
High-Frequency Users (`outputs/tables/engagement_segments.csv`).

## Engagement Score

**Analyst-Created Simulated Engagement Score** (0–100): active days 25%, meaningful completions 25%, consistency 15%, feature
diversity 15%, sessions 10%, progression 10%; log-scaled, P99-capped. Validated with 9 sensitivity scenarios, PCA weights and an
early-score predictive check. Not an official VELOOP metric.

## Advanced Analytics

15 advanced analyses (`outputs/tables/advanced_analysis_register.csv`): cohort analysis, behavioural segmentation, sequence /
transition analysis, feature affinity (lift), activation window sensitivity, retention, anomaly detection, distribution analysis,
time-series spike detection, correlation matrix, calendar-confounding stratification, a cross-validated logistic model of
fourth-week return, funnel analysis, device/acquisition significance testing and score validation.

## Dashboard

A client-facing dashboard with five views — **Overview, User Behaviour, Features, Retention, Insights & Actions** — and
filters for acquisition source, device, user group, feature and activity dates. It shows business content only; technical
material (data-quality register, anomaly queue, metric reconciliation, model details) stays in the report and this repository.
Filtered numbers are recomputed in the browser and tested against pandas for every filter value
(`dashboard/src/lib/*.test.ts`). Panels marked *Overall* show all users. Live: https://veloop-data-analyst-task02.vercel.app/

## Key Findings

Full Observation → Evidence → Interpretation → Limitation → Implication write-ups for 20 findings are in `docs/findings.md`.
Within the simulated cohort:

1. Users take days to open a first session; once they do, a completed activity almost always follows.
2. Second-day return is the first major user-level drop-off; progression from 3 to 7 active days is the steepest step.
3. Return depends strongly on **calendar period** (later cohorts return far more) — device and source show no meaningful differences.
4. Fast activators return more, even within the same registration month (association, not causation).
5. About two in five resolved tasks are abandoned or fail, evenly across categories and failure reasons; many rewards sit in long-pending validation.
6. Ads, CAPTCHA and Missions each lose about half of attempts; mission/spin views often do not lead to a start.
7. Sessions are short and longer sessions are not deeper; first-day sessions are the densest.
8. Journeys show no dominant path; streak events do not behave like streaks; level-ups are not followed by an activity change.
9. Several pre-aggregated fields would materially change conclusions if used without validation.

## Product Recommendations

Prioritised (documented scoring) in `docs/findings.md` and `docs/recommendations.md`: shorten registration → first activity,
create a reason to return on day 2, reduce task abandonment/failure, make pending validation visible, right-size missions and ads,
repair streak tracking, support days 3–7 progression, reconcile pipeline aggregates with raw logs, and always control for cohort period.

## Experiments

Ten **PROPOSED EXPERIMENTS** (none run). Each states the hypothesis, target users, control, variant, primary/secondary/guardrail
metrics, the **baseline measured in the data, minimum detectable effect, sample size per arm** (two-sided two-proportion test,
α = 0.05, power 80%), randomisation unit, analysis method and **decision rule**. Every product recommendation links to one of them
(`docs/recommendations.md`).

## Consistency of numbers

All journey stages (logged in, used a feature, completed, returned, established, multi-feature, regular) are defined once in
`analysis/utils/funnel.py` and reused by the lifecycle, activation funnel, engagement funnel and dashboard, so a stage with the
same name always has the same count. Funnels show both **cumulative** and **standalone** counts; all user-behaviour rates use
**active users** as denominator; retention has one primary anchor (first active date). Numbers that look alike but differ by
definition are explained in [`docs/metric_reconciliation.md`](docs/metric_reconciliation.md).

## Event Tracking Gaps

18 **proposed** analytics events (login, session_started/ended, linked feature lifecycle events, detailed task_failed,
reward_pending/credited, streak state, mission_progress, notification events, …) with trigger, properties, rationale and KPI.

## Limitations

See report §26 *"What This Dataset Cannot Tell Us"*: simulated users are not real users; no causal inference; simulated
timestamps, sources and retention do not represent VELOOP; plus 12 dataset-specific limitations (missing event types, unreliable
in-session ordering, short session windows, unreliable milestones, absent level/XP fields, single-valued platform, right-censoring,
calendar confounding, and source discrepancies between the workbook README and the PDF).

## Project Structure

```
.
├── analysis/
│   ├── config.py               # paths, taxonomy, definitions
│   ├── run_pipeline.py         # orchestrator (python -m analysis.run_pipeline)
│   ├── pipeline/               # s01_validation … s23_docs (one module per analysis area)
│   ├── utils/                  # io, metric helpers, return-flag logic
│   └── notebooks/
├── data/{raw,processed,analytical}/   # raw is git-ignored; others regenerated
├── outputs/{tables,charts,reports,dashboard_data}/
├── dashboard/                  # React + TS + Vite + Tailwind + Recharts (Vercel-ready)
├── docs/                       # methodology, data dictionary, KPI catalogue, findings, recommendations, charts
├── tests/                      # pytest unit + output-integrity tests
├── requirements.txt
└── TASK_02_REQUIREMENTS_CHECKLIST.md
```

## Environment Setup

Python 3.11+ and Node 18+ (tested with Python 3.11.9, Node 24).

```bash
python -m pip install -r requirements.txt
```

## How to Run Analysis

```bash
python -m analysis.run_pipeline
```

Runs all 23 steps (≈1–2 min), writes every table, chart, the Excel workbook, the PDF report, the generated docs and the dashboard
data. Then verify:

```bash
python -m pytest -q tests
```

## How to Run Dashboard

```bash
cd dashboard
npm install
npm run dev
```

`npm test` checks dashboard calculations against the pipeline outputs; `npm run build` produces `dashboard/dist`.

## Deployment

The dashboard is a static Vite site with its data committed in `dashboard/public/data/` (aggregate, identifier-free), so Vercel
needs no Python. In Vercel: **New Project → import the repository → Root Directory `dashboard`** (framework auto-detected as
Vite; `dashboard/vercel.json` sets build command and output directory). Re-run the pipeline and commit `dashboard/public/data`
to update the deployed numbers.

## Data Privacy

- Names, emails, age, gender, city, state and referral codes are dropped at load and never appear in outputs, charts, the
  dashboard or the report (enforced by `tests/test_outputs.py::test_no_pii_in_dashboard_or_analytical_outputs`).
- The raw workbook and regenerable user-level layers are git-ignored.
- Dashboard filter data contains no identifiers; only the anomaly investigation queue shows simulated pseudonymous IDs.

## Disclaimer

This is an internship analysis of fictional data. It must not be presented as actual VELOOP behaviour, retention, engagement,
growth, revenue or product performance. Product statements tagged *Documented Product Fact* are limited to what the brief
attributes to VELOOP's official materials; everything else is a simulated result, an analyst interpretation or a hypothesis to verify.
