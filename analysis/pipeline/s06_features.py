"""Work Packages E & F — Feature usage, adoption stages, task categories and feature affinity.

Stages per feature (user level, because within-session ordering is unreliable – DQ-035/036):
  Exposure   – user has ≥1 event of the feature (opened / saw it)
  Adoption   – user has ≥1 interaction beyond viewing (start / complete / abandon / fail);
               view-only features (Wallet, Exchange Center, Leaderboard): adoption == exposure (N/A)
  Completion – user has ≥1 'complete' stage event for the feature
  Repeat     – user completed the feature on ≥2 distinct days
  Depth      – completions per completing user (mean / median)
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

from analysis import config
from analysis.pipeline.context import Context
from analysis.utils.io import save_table
from analysis.utils.metrics import pct, safe_div


def run(ctx: Context) -> None:
    e, u, s, t = ctx.events, ctx.users, ctx.sessions, ctx.tasks
    active = int(u.is_active.sum())
    uf_ev, uf_sess, uf_days = ctx.extra["uf_events"], ctx.extra["uf_sessions"], ctx.extra["uf_days"]
    uf_c, uf_cd = ctx.extra["uf_complete"], ctx.extra["uf_complete_days"]
    first_feat = u.first_feature.value_counts()
    rows = []
    for f in config.FEATURES:
        fe = e[e.feature_name == f]
        users = int((uf_ev[f] > 0).sum())
        adopt = fe[fe.stage.isin(["start", "complete", "abandon", "fail"])].user_id.nunique()
        comp_users = int((uf_c[f] > 0).sum()) if f in uf_c else 0
        rep_comp = int((uf_cd[f] >= 2).sum()) if f in uf_cd else 0
        cvals = uf_c[f][uf_c[f] > 0] if f in uf_c else pd.Series(dtype=float)
        uses = uf_ev[f][uf_ev[f] > 0]
        starts = int((fe.stage == "start").sum())
        completes = int((fe.stage == "complete").sum())
        neg = int(fe.stage.isin(["abandon", "fail"]).sum())
        view_only = f in config.VIEW_ONLY_FEATURES
        row = {
            "feature": f, "feature_area": config.FEATURE_AREA[f],
            "unique_users": users, "share_of_active_users_pct": pct(users, active),
            "total_events": len(fe), "sessions_with_feature": int(fe.session_id.nunique()),
            "first_feature_users": int(first_feat.get(f, 0)),
            "one_session_users": int((uf_sess[f] == 1).sum()), "repeat_users": int((uf_sess[f] >= 2).sum()),
            "repeat_usage_rate_pct": pct((uf_sess[f] >= 2).sum(), users),
            "repeat_day_users": int((uf_days[f] >= 2).sum()), "repeat_day_rate_pct": pct((uf_days[f] >= 2).sum(), users),
            "avg_uses_per_user": round(uses.mean(), 2), "median_uses_per_user": float(uses.median()),
            "exposure_users": users,
            "adoption_users": None if view_only else int(adopt),
            "adoption_rate_pct": None if view_only else pct(adopt, users),
            "completion_users": None if view_only else comp_users,
            "completion_user_rate_pct": None if view_only else pct(comp_users, users),
            "repeat_completion_users": None if view_only else rep_comp,
            "repeat_completion_rate_pct": None if view_only else pct(rep_comp, comp_users),
            "depth_mean_completions": None if view_only else round(cvals.mean(), 2),
            "depth_median_completions": None if view_only else float(cvals.median()),
            "start_events": starts, "complete_events": completes, "negative_outcome_events": neg,
            "event_completion_rate_pct": None, "event_abandonment_rate_pct": None, "negative_outcome_type": None,
            "start_to_complete_event_ratio": round(safe_div(completes, starts), 3) if starts else None,
            "view_only": view_only,
        }
        if f in config.OUTCOME_PAIRS:
            ce, ne, label = config.OUTCOME_PAIRS[f]
            nc, nn = int((fe.event_name == ce).sum()), int((fe.event_name == ne).sum())
            row.update(event_completion_rate_pct=pct(nc, nc + nn), event_abandonment_rate_pct=pct(nn, nc + nn),
                       negative_outcome_type=label)
        rows.append(row)
    ft = pd.DataFrame(rows).sort_values("unique_users", ascending=False)
    save_table(ft, "feature_usage_metrics")

    # streak-specific: claims vs breaks
    streak = {"claimed_events": int((e.event_name == "streak_claimed").sum()),
              "broken_events": int((e.event_name == "streak_broken").sum()),
              "users_claimed": int(e[e.event_name == "streak_claimed"].user_id.nunique()),
              "users_broken": int(e[e.event_name == "streak_broken"].user_id.nunique())}

    # adoption funnel long format (for charts / dashboard)
    stage_rows = []
    for r in ft.itertuples():
        for stage, val in [("Exposure", r.exposure_users), ("Adoption", r.adoption_users),
                           ("Completion", r.completion_users), ("Repeat completion", r.repeat_completion_users)]:
            stage_rows.append({"feature": r.feature, "stage": stage, "users": val,
                               "pct_of_active": pct(val, active) if val is not None else None})
    stages_long = pd.DataFrame(stage_rows)
    save_table(stages_long, "feature_adoption_stages")

    # ---------------------------------------------------------------- task categories
    tc = t.groupby("task_category").agg(
        records=("activity_id", "size"), users=("user_id", "nunique"), completed=("is_completed", "sum"),
        resolved=("is_resolved", "sum"), failed=("task_status", lambda x: (x == "Failed").sum()),
        abandoned=("task_status", lambda x: (x == "Abandoned").sum()),
        pending=("task_status", lambda x: (x == "Pending").sum()),
        median_view_to_start_s=("view_to_start_s", "median"),
        median_start_to_complete_s=("start_to_complete_s", "median")).reset_index()
    tc["completion_rate_pct"] = (tc.completed / tc.resolved * 100).round(1)
    tc["abandonment_rate_pct"] = (tc.abandoned / tc.resolved * 100).round(1)
    tc["failure_rate_pct"] = (tc.failed / tc.resolved * 100).round(1)
    tc["pending_share_pct"] = (tc.pending / tc.records * 100).round(1)
    tc = tc.sort_values("completion_rate_pct")
    save_table(tc, "task_category_metrics")
    fr = t[t.failure_reason.notna()].groupby(["task_status", "failure_reason"]).size().unstack(0, fill_value=0)
    fr["total"] = fr.sum(axis=1)
    fr = fr.sort_values("total", ascending=False).reset_index()
    save_table(fr, "task_failure_reasons")
    fr_cat = pd.crosstab(t.task_category, t.failure_reason)
    task_overall = {
        "records": len(t), "users": int(t.user_id.nunique()), "completed": int(t.is_completed.sum()),
        "resolved": int(t.is_resolved.sum()), "pending": int((t.task_status == "Pending").sum()),
        "abandoned": int((t.task_status == "Abandoned").sum()), "failed": int((t.task_status == "Failed").sum()),
        "completion_rate_resolved_pct": pct(t.is_completed.sum(), t.is_resolved.sum()),
        "completion_rate_all_pct": pct(t.is_completed.sum(), len(t)),
        "abandonment_rate_resolved_pct": pct((t.task_status == "Abandoned").sum(), t.is_resolved.sum()),
        "failure_rate_resolved_pct": pct((t.task_status == "Failed").sum(), t.is_resolved.sum()),
        "view_to_start_pct": pct(t.task_started_at.notna().sum(), len(t)),
        "median_view_to_start_s": float(t.view_to_start_s.median()),
        "median_start_to_complete_s": float(t.start_to_complete_s.median()),
        "users_with_any_incomplete_task_pct": pct(t[~t.is_completed].user_id.nunique(), t.user_id.nunique()),
        "distinct_tasks": int(t.task_id.nunique()),
    }
    by_task = t.groupby("task_id").agg(category=("task_category", "first"), records=("activity_id", "size"),
                                       completed=("is_completed", "sum"), resolved=("is_resolved", "sum")).reset_index()
    by_task["completion_rate_pct"] = (by_task.completed / by_task.resolved * 100).round(1)
    save_table(by_task.sort_values("completion_rate_pct"), "task_id_metrics")

    # ---------------------------------------------------------------- feature affinity (session level)
    v = s[s.is_valid]
    sess_feat = e.groupby("session_id").feature_name.agg(lambda x: tuple(sorted(set(x))))
    n_vs = len(sess_feat)
    single = {f: sess_feat.apply(lambda z: f in z).mean() for f in config.FEATURES}
    pair_counts: dict[tuple, int] = {}
    for feats in sess_feat:
        for a, b in combinations(feats, 2):
            pair_counts[(a, b)] = pair_counts.get((a, b), 0) + 1
    pr = pd.DataFrame([{"feature_a": a, "feature_b": b, "sessions_together": c, "support_pct": pct(c, n_vs, 2),
                        "lift": round((c / n_vs) / (single[a] * single[b]), 3)} for (a, b), c in pair_counts.items()])
    pr = pr.sort_values("sessions_together", ascending=False)
    save_table(pr, "feature_affinity_pairs")
    lift_matrix = pd.DataFrame(1.0, index=config.FEATURES, columns=config.FEATURES)
    for r in pr.itertuples():
        lift_matrix.loc[r.feature_a, r.feature_b] = lift_matrix.loc[r.feature_b, r.feature_a] = r.lift
    save_table(lift_matrix.reset_index().rename(columns={"index": "feature"}), "feature_affinity_lift_matrix")
    combo_counts = sess_feat[sess_feat.apply(len) >= 2].value_counts().head(15)
    combos = pd.DataFrame({"combination": [" + ".join(k) for k in combo_counts.index], "sessions": combo_counts.values})
    triples: dict[tuple, int] = {}
    for feats in sess_feat:
        for c3 in combinations(feats, 3):
            triples[c3] = triples.get(c3, 0) + 1
    tri = pd.DataFrame([{"combination": " + ".join(k), "sessions": v_} for k, v_ in triples.items()]) \
        .sort_values("sessions", ascending=False).head(15)
    save_table(tri, "feature_triples_sessions")

    ctx.R["features"] = {
        "table": ft, "stages_long": stages_long, "streak": streak, "task_categories": tc, "task_overall": task_overall,
        "failure_reasons": fr, "failure_reason_by_category": fr_cat.reset_index(),
        "affinity_top_pairs": pr.head(15), "affinity_top_lift": pr.sort_values("lift", ascending=False).head(10),
        "affinity_bottom_lift": pr.sort_values("lift").head(5), "lift_range": [float(pr.lift.min()), float(pr.lift.max())],
        "lift_matrix": lift_matrix.round(3).reset_index().rename(columns={"index": "feature"}),
        "top_exact_combinations": combos, "top_triples": tri, "valid_sessions": n_vs,
        "single_feature_session_pct": pct((sess_feat.apply(len) == 1).sum(), n_vs),
    }
