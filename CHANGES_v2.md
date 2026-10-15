# Version 2 – changes made after review

All figures remain based on **simulated data – not actual VELoop Rewards user data**.

| # | Review point | What changed | Where to check |
|---|---|---|---|
| 1 | Inconsistent user counts, funnel metrics and retention | All journey stages are now defined once (`analysis/utils/funnel.py`) and reused by the lifecycle, activation funnel, engagement funnel and dashboard, so a stage with the same name always shows the same count. Fixed specifically: (a) "Repeated activity" (831, meaningful on ≥2 days) and "Returned" (826, ≥2 active days) now use one rule – 826; (b) removed the "Viewed a feature" stage from the engagement funnel, which wrongly dropped 9 users (Ads, CAPTCHA, Tap & Earn and Mining log no view events) and produced 975/821 instead of 984/826; (c) "Became repeat user" (733) renamed "Established (≥3 meaningful days)" so "repeat user" has one meaning; (d) every funnel shows cumulative and standalone counts side by side (e.g. regular engagement 211 cumulative vs 615 standalone); (e) all user-behaviour rates now use active users as denominator (multi-feature rate 26.5% → 26.9%, high-frequency and regular rates likewise); (f) retention shows one primary anchor (first active date) – the registration-anchored version moved to a labelled comparison table. A reconciliation table explains 13 pairs of numbers that look alike. | Report §03, §04, §14, §16, Appendix D · `docs/metric_reconciliation.md` |
| 2 | State clearly that data is simulated | Prominent notice on the report cover, first line of the executive summary, every page footer, every chart, a banner on every dashboard page, and the top of every README. | Report p.1–2 · dashboard banner |
| 3 | Shorter executive summary | Cut from two pages to one: six KPIs with numerator/denominator, the five most important findings, and the top three actions with their test and target. | Report §01 |
| 4 | Recommendations: how to test and measure | Every recommendation now links to a proposed A/B test with the baseline measured in the data, minimum detectable effect, target, sample size per arm (α = 0.05, power 80%), randomisation unit, analysis method, guardrails and a decision rule. Three experiments added (ads, missions, days 3–7), total 10. | Report §24, §27 · `docs/recommendations.md` · dashboard Diagnostics |
| 5 | Verify filters, charts, KPIs and calculations | New automated test checks every single filter value (7 sources, 4 devices, 6 segments, 15 features) and two date windows against values computed independently in pandas – users, active users, sessions, active days, repeat rate, multi-feature rate, activation, D7 return and the full funnel (35 cases, all pass). Python tests extended to 24 (incl. same-stage-same-count and shared-denominator checks). | `dashboard/src/lib/filters.test.ts` · `tests/` |
| 6 | Share code, dataset and methodology | Full source code, all 10 sheets as anonymised CSV (personal fields removed), methodology, verification guide, and `verify_headline_metrics.py`, which recomputes 19 headline numbers from the CSVs with plain pandas (no pipeline code) – 19/19 match. | `data/anonymised/` · `docs/verification_guide.md` · `verify_headline_metrics.py` |

## Numbers that changed

| Metric | v1 | v2 | Reason |
|---|---|---|---|
| Multi-feature user rate | 26.5% (÷ 1,000 registered) | 26.9% (÷ 984 active) | Common denominator for user rates |
| Lifecycle "Repeated activity" | 831 | 826 | One definition of repeat (≥2 active days) |
| Engagement funnel: started / completed / returned | 975 / 975 / 821 | 984 / 984 / 826 | Removed misleading "viewed a feature" stage |
| Multi-feature (cumulative): lifecycle vs engagement funnel | 236 vs 235 | 235 in both | Same stage rules and order everywhere |
| Regular engagement (cumulative) | 211 | 211 (standalone 615 now shown alongside) | Cumulative vs standalone labelled explicitly |
| High-frequency / regular engagement rate | ÷ registered | ÷ active users | Common denominator |

No other figure changed; the independent recomputation confirms all headline numbers.
