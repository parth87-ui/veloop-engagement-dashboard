# Verification Guide

How to check every result independently. All data is **simulated** – it is not actual VELoop Rewards user data.

## What is shared

| Item | Location |
|---|---|
| Source code (analysis) | `analysis/` – 23 pipeline steps, one module per analysis area; definitions in `analysis/config.py` and `analysis/utils/funnel.py` |
| Source code (dashboard) | `dashboard/` |
| Dataset | `data/anonymised/` – all 10 sheets of the supplied workbook as CSV, unchanged except that personal fields (name, email, age, gender, city, state, referral code) are removed. Simulated user IDs are kept so joins can be checked. |
| Methodology | `docs/methodology.md` – every definition, threshold and decision |
| Metric reconciliation | `docs/metric_reconciliation.md` – numbers that look alike, and why they differ |
| All result tables | `outputs/tables/*.csv` (also `outputs/reports/VELOOP_Task02_Analytical_Outputs.xlsx`) |

## Level 1 – check the headline numbers in one command (no pipeline code)

```bash
pip install pandas
python verify_headline_metrics.py
```

The script reads only `data/anonymised/*.csv`, recomputes 19 headline numbers with plain pandas (users, sessions,
activation, D1/D7/D14/D30 return, task completion, funnel stages…) and compares them with the published outputs.
Every definition is written out at the top of the script.

## Level 2 – rerun the whole analysis

The full pipeline starts from the original workbook (it needs the personal-field columns only to drop them):

```bash
pip install -r requirements.txt
# place VELOOP_Simulated_User_Behavior_1000.xlsx in data/raw/
python -m analysis.run_pipeline
python -m pytest -q tests
```

The tests check arithmetic (percentages, drop-offs, return rates), that a stage with the same name has the same count in
every funnel, that user rates share one denominator, that every recommendation has a test plan, that report and dashboard
numbers trace to the tables, and that no personal data leaks into outputs.

## Level 3 – check the dashboard

```bash
cd dashboard
npm install
npm test
```

`metrics.test.ts` checks that unfiltered dashboard numbers equal the pipeline outputs. `filters.test.ts` checks every single
filter value (7 sources, 4 devices, 6 segments, 15 features) plus two date windows against values computed independently with
pandas (`src/lib/expected_filters.json`): users, active users, sessions, active days, repeat-user rate, multi-feature rate,
activation rate, D7 return and the full funnel.

## Key definitions at a glance

| Metric | Definition | Denominator |
|---|---|---|
| Active user | ≥1 feature event | – |
| Repeat user / "Returned" | Active on ≥2 distinct days | Active users |
| Multi-feature, high-frequency, regular, one-time rates | See methodology | Active users |
| Activation | First meaningful activity within 14 days of registration | Users registered ≥14 days before data end |
| D1 / D7 / D14 / D30 return | Active on day 1 / days 1–7 / 8–14 / 24–30 after the first active day | Users whose whole window is observable |
| Task completion | Completed ÷ (Completed + Failed + Abandoned) | Finished task attempts |
| Funnel "cumulative" vs "standalone" | Met this and every earlier stage vs met this stage's rule only | Registered users (1,000) |
