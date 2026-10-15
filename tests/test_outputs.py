"""Integration tests on the generated outputs: joins, KPI arithmetic, report/dashboard consistency, privacy.

Run the pipeline first (python -m analysis.run_pipeline). Tests are skipped if outputs are missing.
"""
import json
import re
from pathlib import Path

import pandas as pd
import pytest

from analysis import config

T = config.OUT_TABLES
pytestmark = pytest.mark.skipif(not (T / "kpi_catalogue.csv").exists(), reason="pipeline outputs not generated")


@pytest.fixture(scope="module")
def users():
    return pd.read_csv(config.DATA_ANALYTICAL / "users_analytical.csv")


@pytest.fixture(scope="module")
def agg():
    return json.loads((config.OUT_DASH / "aggregates.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def meta():
    return json.loads((config.OUT_DASH / "meta.json").read_text(encoding="utf-8"))


def test_record_counts_reconcile(meta, users):
    rc = meta["record_counts"]
    assert rc["users"] == len(users) == 1000
    ev = pd.read_csv(config.DATA_ANALYTICAL / "events_clean.csv", usecols=["event_id", "user_id", "session_id"])
    assert len(ev) == rc["events"] - 17           # only the 17 identical duplicates are excluded
    assert ev.event_id.is_unique
    assert ev.user_id.isin(users.user_id).all()   # no orphan joins
    s = pd.read_csv(config.DATA_ANALYTICAL / "sessions_clean.csv", usecols=["session_id", "user_id", "raw_event_count"])
    assert ev.session_id.isin(s.session_id).all()
    assert s.raw_event_count.sum() == len(ev)     # session counters recomputed from raw events


def test_executive_kpis_match_users_table(meta, users):
    k = meta["executive_kpis"]
    assert k["active_users"] == int(users.is_active.sum())
    assert k["sessions"] == int(users.n_sessions.sum())
    assert k["repeat_user_rate_pct"] == round((users.n_active_days >= 2).sum() / users.is_active.sum() * 100, 1)
    elig = users[users.activation_eligible]
    assert k["activation_rate_pct"] == round(elig.is_activated.mean() * 100, 1)
    assert k["active_user_days"] == int(users.n_active_days.sum())


def test_funnels_are_monotonic_and_percentages_correct():
    for name in ("activation_funnel", "engagement_funnel"):
        f = pd.read_csv(T / f"{name}.csv")
        assert f.users.is_monotonic_decreasing
        assert (f.pct_of_registered.round(1) == (f.users / f.denominator * 100).round(1)).all()


def test_same_stage_same_count_everywhere():
    """Point 1 of the client review: a stage with the same name must have the same count in every funnel."""
    counts = {}
    for name in ("lifecycle_stages", "activation_funnel", "engagement_funnel"):
        f = pd.read_csv(T / f"{name}.csv")
        for r in f.itertuples():
            counts.setdefault(r.canonical_stage, set()).add(int(r.users_standalone))
        # cumulative counts of the shared prefix must match too
    a = pd.read_csv(T / "activation_funnel.csv").set_index("canonical_stage").users
    e = pd.read_csv(T / "engagement_funnel.csv").set_index("canonical_stage").users
    shared = [s for s in a.index if s in e.index]
    assert len(shared) >= 6 and (a[shared] == e[shared]).all()
    assert all(len(v) == 1 for v in counts.values()), counts


def test_user_rates_share_active_denominator(meta, users):
    k = meta["executive_kpis"]
    act = users.is_active.sum()
    assert k["multi_feature_user_rate_pct"] == round(users.is_multi_feature.sum() / act * 100, 1)
    kpi = pd.read_csv(T / "kpi_catalogue.csv").set_index("kpi_name")
    for name in ("Multi-Feature Usage Rate", "High-Frequency User Rate", "Regular Engagement Rate", "Repeat User Rate",
                 "One-Time User Rate"):
        assert kpi.loc[name, "denominator"] == "Active users", name


def test_every_recommendation_has_a_test_plan():
    r = pd.read_csv(T / "final_recommendations.csv")
    assert r[["how_to_test", "how_to_measure", "decision_rule"]].notna().all().all()
    e = pd.read_csv(T / "proposed_experiments.csv")
    assert (e.sample_size_per_arm > 0).all() and (e.target_value_pct > e.baseline_value_pct).all()


def test_reconciliation_and_anonymised_dataset():
    assert len(pd.read_csv(T / "metric_reconciliation.csv")) >= 10
    files = list(config.DATA_ANONYMISED.glob("*.csv"))
    assert len(files) == 10
    for p in files:
        cols = set(pd.read_csv(p, nrows=1).columns)
        assert not cols & set(config.PII_COLUMNS), p.name


def test_dropoff_arithmetic():
    d = pd.read_csv(T / "dropoff_matrix.csv")
    assert (d.drop_off == d.entering - d.continuing).all()
    assert ((d.drop_off / d.entering * 100).round(1) == d.drop_off_pct).all()


def test_return_rates_consistent():
    r = pd.read_csv(T / "return_rates_overall.csv")
    assert ((r.returned_users / r.eligible_users * 100).round(1) == r.return_rate_pct).all()
    assert list(r.window) == ["D1", "D7", "D14", "D30"]


def test_segments_partition_users(users):
    seg = pd.read_csv(T / "engagement_segments.csv")
    assert seg.users.sum() == len(users)
    assert seg.pct_users.sum() == pytest.approx(100, abs=0.2)


def test_engagement_score_bounds(users):
    assert users.engagement_score.between(0, 100).all()
    assert (users.loc[~users.is_active, "engagement_score"] == 0).all()


def test_deliverable_minimums():
    assert len(pd.read_csv(T / "behavioral_findings.csv")) >= 15
    assert len(pd.read_csv(T / "kpi_catalogue.csv")) >= 30
    assert len(pd.read_csv(T / "proposed_experiments.csv")) >= 5
    assert len(pd.read_csv(T / "advanced_analysis_register.csv")) >= 5
    assert len(list(config.OUT_CHARTS.glob("*.png"))) >= 14
    cat = pd.read_csv(T / "chart_catalogue.csv")
    for col in ("business_question", "dataset", "fields_used", "calculation", "filter", "population", "time_period",
                "interpretation", "limitation", "product_relevance"):
        assert cat[col].notna().all(), col


def test_opportunity_priority_follows_documented_rule():
    o = pd.read_csv(T / "product_opportunity_register.csv")
    total = o[["score_reach", "score_severity", "score_confidence", "score_ease", "score_relevance"]].sum(axis=1)
    assert (total == o.priority_score).all()
    expected = total.map(lambda x: "High" if x >= 12 else "Medium" if x >= 9 else "Low")
    assert (expected == o.priority).all()
    assert o.priority.nunique() > 1   # not everything HIGH


def test_experiments_labelled_as_proposed():
    e = pd.read_csv(T / "proposed_experiments.csv")
    assert e.label.str.contains("PROPOSED").all()


EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def test_no_pii_in_dashboard_or_analytical_outputs():
    raw = pd.read_excel(config.RAW_WORKBOOK, sheet_name=config.SHEETS["users"]) if config.RAW_WORKBOOK.exists() else None
    names = set(raw.full_name) if raw is not None else set()
    paths = list(config.OUT_DASH.glob("*.json")) + list(config.DATA_ANALYTICAL.glob("*.csv")) + list(T.glob("*.csv"))
    for p in paths:
        txt = p.read_text(encoding="utf-8")
        assert not EMAIL.search(txt), f"email-like string in {p.name}"
        for n in list(names)[:200]:
            assert n not in txt, f"name found in {p.name}"
    filt = json.loads((config.OUT_DASH / "filterable.json").read_text(encoding="utf-8"))
    assert "VLUSR" not in json.dumps(filt["users"])     # no user identifiers in filterable arrays


def test_dashboard_data_copied():
    for name in ("meta", "aggregates", "filterable"):
        a = (config.OUT_DASH / f"{name}.json").read_bytes()
        b = (config.DASHBOARD_PUBLIC_DATA / f"{name}.json").read_bytes()
        assert a == b


def test_report_exists_and_numbers_trace_to_outputs(meta):
    pdf = config.OUT_REPORTS / "VELOOP_Task02_User_Behavior_Engagement_Intelligence_Report.pdf"
    assert pdf.exists() and pdf.stat().st_size > 100_000
    try:
        import pymupdf
    except ImportError:
        pytest.skip("pymupdf not installed")
    text = "".join(p.get_text() for p in pymupdf.open(str(pdf)))
    k = meta["executive_kpis"]
    for v in (f"{k['activation_rate_pct']}%", f"{k['repeat_user_rate_pct']}%", f"{k['sessions']:,}"):
        assert v in text, v
    for section in ("01. Executive Summary", "19. Behavioral Findings", "26. Limitations", "27. Final Product Analytics Recommendations"):
        assert section in text
