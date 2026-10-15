# Methodology

All analysis uses the **simulated** workbook `VELOOP_Simulated_User_Behavior_1000.xlsx`. Nothing here describes actual
VELOOP users or performance. Numbers are deliberately kept out of this document – they live in the generated tables
(`outputs/tables/`), `docs/findings.md`, `docs/kpi_catalogue.md` and the PDF report, so a rerun can never leave this file stale.

## 1. Statement classes

| Class | Meaning |
|---|---|
| DOCUMENTED PRODUCT FACT | Supported by official VELOOP documentation **as cited in the brief** (not independently accessed) |
| SIMULATED DATA RESULT | Calculated from the simulated dataset |
| ANALYST INTERPRETATION | What a result may indicate |
| PRODUCT HYPOTHESIS | A proposed explanation or product change to test |
| TO BE VERIFIED | Requires confirmation from product / engineering |

## 2. Source hierarchy (cross-validation decisions)

| Sheet | Role | Decision & reason |
|---|---|---|
| 03_Feature_Events | **Primary behavioural source** | Clean keys, no orphans, timestamps inside sessions. 17 rows that duplicate every field except `event_id` are excluded from the clean layer (raw is untouched). |
| 02_Sessions | Session windows, login proxy, entry points | `events_in_session` and `features_used_count` disagree with raw events for most sessions → recomputed from raw events. `exit_feature` disagrees with the last raw event for most sessions → exit analysis uses the timestamp-ordered last event and reports the field for comparison. |
| 05_Task_Activity | Task funnel | Timestamps internally consistent (view ≤ start ≤ complete); status/reward/failure logic coherent. Session windows end before almost all task completions → session duration treated as a logged window, not time-in-product. |
| 04_Daily_Activity | Validation reference | `event_count` / `feature_count` reconcile exactly with raw events; `session_duration_minutes` does not reconcile with sessions → not used. |
| 06_Milestones | Validation reference only | Contradicts raw activity (first_login ≠ first session; 3rd/7th-active-day milestones for users without those days; milestones for users with no sessions; source events from unrelated features) → all milestones re-derived from raw logs. |
| 07_Feature_Usage | Validation reference | Reconciles with raw events (it includes the 17 duplicates). Its "success" counts use raw status, which labels `streak_broken` as Success. |
| 10_Event_Data_Quality_Audit | QA copy | Event log + 10 duplicated rows + 5 lower-case feature names + 4 drifted statuses. Used to test cleaning rules in the DQ-impact analysis. |
| 09_README_Status vs PDF | — | Duration "22–25 day" vs PDF "20–24 Days", and volumes below PDF recommendations → **Source discrepancy requiring confirmation.** The PDF is treated as the formal requirement. |

## 3. Core definitions

- **Event order** – `event_datetime`, ties broken by `event_id`. `sequence_number` is duplicated within sessions and uncorrelated with time, so it is not used.
- **Active user** – ≥1 feature event. **Active day** – calendar day with ≥1 feature event (same coverage as 04_Daily_Activity).
- **Valid session** – session with ≥1 raw feature event. Per-session behaviour metrics use valid sessions; session counts include all sessions.
- **Login** – no login event exists; a session is the login proxy.
- **Event stages** (from the 35 observed event names, `analysis/config.py`): exposure (views/opens), start, complete, abandon, fail, progression (badge_earned, level_up), neutral (mining_stopped), negative (streak_broken). The stage taxonomy overrides raw `event_status` where they conflict.
- **Meaningful activity** – a user-initiated, completed value action: any `complete`-stage event (ad_completed, captcha_completed, daily_reward_claimed, follow_task_completed, mining_activity, mission_completed, referral_created, referral_shared, spin_completed, streak_claimed, tap_completed) **or** a task with status Completed. Excluded: views, starts, skips/failures/abandons, system-awarded progression outcomes, mining_stopped, streak_broken. *Limitation:* completions cannot be linked to a preceding start, so "meaningful" means a completion was logged.
- **Feature stages** (user level, because in-session order is unreliable): Exposure (any event) → Adoption (interaction beyond viewing) → Completion (≥1 complete event) → Repeat (completion on ≥2 days) → Depth (completions per completer). Wallet, Exchange Center and Leaderboard are view-only.
- **Completion / abandonment rates** – only measurable where an explicit negative outcome is logged: Watch Ads (skip), CAPTCHA (fail), Missions (abandon). Task completion rate = Completed ÷ (Completed + Failed + Abandoned); Pending excluded and reported separately.

## 4. Activation

Activated = first meaningful activity within *N* days of `registration_datetime`. Denominator = users whose whole *N*-day
window lies inside the observation period (recent registrants are excluded, not counted as failures). Windows of 1, 3, 7, 14
and 30 days were tested. **Selection rule:** the smallest window capturing the majority (≥50%) of users who activate within
60 days – the elbow where the gain per extra day roughly halves. The 7-day rate is reported alongside as "early activation".

## 5. Sessions

Duration bands are quartile-based on observed durations (Short ≤ P25, Medium ≤ P75, Long > P75, Extreme > Q3 + 3·IQR).
Duration is never treated as "good engagement"; its relationship with depth is tested (Spearman).

## 6. Segmentation (mutually exclusive, hierarchical)

Thresholds are quantiles of the active-user distribution computed at run time:
0. No Recorded Activity – 0 active days · 1. One-Time – 1 active day · 2. High-Frequency – active days ≥ P75 ·
3. Multi-Feature – 2…P75−1 active days and completions in ≥ P75 distinct features · 4. Returning – median…P75−1 days ·
5. Occasional – 2…median−1 days. Breadth is not an independent tier because it is strongly rank-correlated with frequency.

## 7. Analyst-Created Simulated Engagement Score (not an official VELOOP metric)

Score = 100 × Σ wₖ·cₖ. Count components are winsorised at P99, log1p-transformed and min-max scaled; ratio components are bounded.

| Component | Weight | Reason |
|---|---|---|
| Activity frequency (active days) | 0.25 | Most direct repeated-engagement signal |
| Meaningful completion (meaningful events + completed tasks) | 0.25 | Value actions the product rewards |
| Active-day consistency (active weeks ÷ max(observable weeks, 4)) | 0.15 | Spread over bursts; partial tenure correction |
| Feature diversity (features completed ÷ 11) | 0.15 | Breadth of value actions |
| Session frequency | 0.10 | Redundant with active days (ρ≈0.95) → low weight |
| Milestone progression (level_up + badge_earned) | 0.10 | Consequence of activity → low weight |

Tests: 9 sensitivity scenarios (equal weights, drop-one, PCA weights, percentile transform) compared by Spearman and top/bottom-decile
overlap; a predictive check recomputes the score on each user's first 14 days and correlates it with activity on days 15–59.

## 8. Return / retention

Primary cohort date = **first active date**; registration-anchored rates are reported separately and never mixed.
D1 = day 1; D7 = days 1–7; D14 = days 8–14; D30 = days 24–30 (comparable 7-day windows). Exact-day ("classic") return is also
reported. Users whose window extends past the data end are excluded from the denominator. Behavioural cohort comparisons use a
fixed 30-day horizon. Because return depends strongly on calendar period, comparisons are stratified by registration month where it matters.

## 9. Statistics & causality

Group differences: Kruskal-Wallis (ε²) for continuous metrics, χ² (Cramér's V) for rates; "observed behavioural difference" requires
p < 0.05 **and** at least a small effect. Associations use first-day behaviour vs later return and adjust for first-day volume to reduce
circularity. The logistic model is descriptive (cross-validated AUC, standardised coefficients). **No result is presented as causal.**

## 10. Anomalies

Detect → quantify → document → flag. Thresholds are generic (Tukey far-out fence Q3 + 3·IQR) or logical impossibilities. No fraud
determination and no confidential anti-fraud rule is implied.

## 11. Privacy

Personal fields (name, email, age, gender, city, state, referral code) are dropped at load. The raw workbook is git-ignored. Dashboard
filter arrays carry no identifiers (users are array positions); only the anomaly queue shows simulated pseudonymous IDs.
