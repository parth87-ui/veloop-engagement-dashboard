"""Run the full VELOOP Task 02 analytical pipeline end to end.

Usage (from the project root):
    python -m analysis.run_pipeline            # all steps
    python -m analysis.run_pipeline --until s05_activation
"""
from __future__ import annotations

import argparse
import importlib
import time

import pandas as pd

from analysis.pipeline.context import Context
from analysis.utils.io import ensure_dirs, load_workbook

STEPS = [
    "s01_validation",
    "s02_cleaning",
    "s03_lifecycle",
    "s04_activation",
    "s05_sessions",
    "s06_features",
    "s07_segmentation",
    "s08_engagement_score",
    "s09_time",
    "s10_device_acquisition",
    "s11_journey",
    "s12_dropoff_funnel",
    "s13_repeat_progression",
    "s14_retention",
    "s15_anomalies",
    "s16_dq_impact",
    "s17_advanced",
    "s18_insights",
    "s19_kpis",
    "s20_charts",
    "s21_export",
    "s22_report",
    "s23_docs",
]


def build_context() -> Context:
    raw = load_workbook()
    ctx = Context(raw=raw)
    ctx.data_start = min(raw["users"].registration_datetime.min(), raw["sessions"].session_start.min())
    ctx.data_end = max(raw["sessions"].session_end.max(), raw["events"].event_datetime.max())
    return ctx


def main(until: str | None = None) -> Context:
    ensure_dirs()
    ctx = build_context()
    print(f"Observation window: {ctx.data_start} -> {ctx.data_end}")
    for name in STEPS:
        t0 = time.time()
        module = importlib.import_module(f"analysis.pipeline.{name}")
        module.run(ctx)
        print(f"  ✓ {name:<26} {time.time() - t0:5.1f}s")
        if until and name == until:
            break
    return ctx


if __name__ == "__main__":
    pd.options.mode.copy_on_write = True
    p = argparse.ArgumentParser()
    p.add_argument("--until", default=None)
    main(p.parse_args().until)
