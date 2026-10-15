"""Work Package N — Feature journey / sequence analysis.

Order = event_datetime then event_id (sequence_number is unreliable, DQ-033/034). Consecutive events
of the same feature are collapsed into one journey step. Sequence frequency is descriptive only –
no causal claim is made about any path.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd
from scipy import stats

from analysis import config
from analysis.pipeline.context import Context
from analysis.utils.io import save_table
from analysis.utils.metrics import pct


def collapse(seq):
    out = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return out


def run(ctx: Context) -> None:
    e, s, u = ctx.events, ctx.sessions, ctx.users
    es = e.sort_values(["session_id", "event_datetime", "event_id"])
    paths = es.groupby("session_id").feature_name.agg(lambda x: tuple(collapse(list(x))))
    stages = es.groupby("session_id").stage.agg(list)
    last_stage = es.groupby("session_id").stage.last()
    has_meaningful = es.groupby("session_id").is_meaningful.any()
    n_sess = len(paths)

    # user-level first and second distinct features (order of first touch)
    eu = e.sort_values(["user_id", "event_datetime", "event_id"])
    first_touch = eu.drop_duplicates(["user_id", "feature_name"])
    ft = first_touch.groupby("user_id").feature_name.agg(list)
    first = ft.str[0].value_counts()
    second = ft[ft.str.len() >= 2].str[1].value_counts()
    pairs12 = Counter((x[0], x[1]) for x in ft if len(x) >= 2)
    first_second = pd.DataFrame([{"first_feature": a, "second_feature": b, "users": c} for (a, b), c in pairs12.most_common(15)])
    fs_tbl = pd.DataFrame({"first_feature_users": first, "second_feature_users": second}).fillna(0).astype(int) \
        .sort_values("first_feature_users", ascending=False).reset_index(names="feature")
    fs_tbl["first_pct_of_active"] = (fs_tbl.first_feature_users / u.is_active.sum() * 100).round(1)
    save_table(fs_tbl, "journey_first_second_features")
    save_table(first_second, "journey_first_to_second_pairs")

    # session journeys (prefix of up to 4 steps + Exit)
    def fmt(p, k=4):
        steps = list(p[:k]) + (["…"] if len(p) > k else []) + ["Exit"]
        return "Session start → " + " → ".join(steps)
    top_paths = paths.map(lambda p: fmt(p, 3)).value_counts().head(15)
    path_tbl = pd.DataFrame({"journey": top_paths.index, "sessions": top_paths.values,
                             "pct_valid_sessions": (top_paths.values / n_sess * 100).round(2)})
    save_table(path_tbl, "journey_top_session_paths")
    path_len = paths.str.len()

    succ = paths[has_meaningful]
    succ_tbl = succ.map(lambda p: fmt(p, 3)).value_counts().head(10)
    neg_end = last_stage.isin(["abandon", "fail"])
    aband = paths[neg_end]
    aband_last_evt = es.groupby("session_id").event_name.last()[neg_end].value_counts()
    browse_only = stages.map(lambda st: all(x in ("exposure",) for x in st))
    seq_tbl = pd.concat([
        pd.DataFrame({"type": "Successful (≥1 meaningful completion)", "journey": succ_tbl.index, "sessions": succ_tbl.values}),
        pd.DataFrame({"type": "Ends on abandon/fail/skip event", "journey": aband.map(lambda p: fmt(p, 3)).value_counts().head(10).index,
                      "sessions": aband.map(lambda p: fmt(p, 3)).value_counts().head(10).values}),
    ])
    save_table(seq_tbl, "journey_successful_vs_abandoned")

    # exit points: last raw feature vs exit_feature field
    exits = pd.DataFrame({"last_raw_event_feature": s[s.is_valid].last_raw_feature.value_counts(),
                          "exit_feature_field": s.exit_feature.value_counts()}).fillna(0).astype(int)
    exits["last_raw_pct"] = (exits.last_raw_event_feature / exits.last_raw_event_feature.sum() * 100).round(1)
    exits["field_pct"] = (exits.exit_feature_field / exits.exit_feature_field.sum() * 100).round(1)
    exits = exits.sort_values("last_raw_event_feature", ascending=False).reset_index(names="feature")
    save_table(exits, "journey_exit_points")
    exit_stage = last_stage.value_counts()
    exit_event = es.groupby("session_id").event_name.last().value_counts().head(10)

    # transition matrix between consecutive distinct features (+ Exit)
    trans = Counter()
    for p in paths:
        seq = list(p) + ["Exit"]
        for a, b in zip(seq[:-1], seq[1:]):
            trans[(a, b)] += 1
    states = config.FEATURES + ["Exit"]
    tm = pd.DataFrame(0, index=config.FEATURES, columns=states)
    for (a, b), c in trans.items():
        tm.loc[a, b] = c
    tm_prob = tm.div(tm.sum(axis=1), axis=0).round(4)
    save_table(tm.reset_index(names="from_feature"), "journey_transition_counts")
    save_table(tm_prob.reset_index(names="from_feature"), "journey_transition_probabilities")
    # lift of each transition vs the destination's overall share (≈1 => no sequential structure)
    dest_share = tm.drop(columns="Exit").sum() / tm.drop(columns="Exit").values.sum()
    within = tm.drop(columns="Exit").div(tm.drop(columns="Exit").sum(axis=1), axis=0)
    lift_arr = (within / dest_share).round(3).to_numpy(copy=True)
    np.fill_diagonal(lift_arr, np.nan)  # self-transitions are impossible after collapsing repeats
    lift = pd.DataFrame(lift_arr, index=within.index, columns=within.columns)
    chi2 = stats.chi2_contingency(tm.drop(columns="Exit").values + 0.5)
    top_trans = pd.DataFrame([{"from": a, "to": b, "transitions": c, "probability": tm_prob.loc[a, b]}
                              for (a, b), c in trans.most_common(20)])
    save_table(top_trans, "journey_top_transitions")

    # stage transitions (exposure/start/complete...) – tests whether flows follow view→start→complete
    st_tr = Counter()
    for st in stages:
        for a, b in zip(st[:-1], st[1:]):
            st_tr[(a, b)] += 1
    stage_names = ["exposure", "start", "complete", "abandon", "fail", "progression", "neutral", "negative"]
    stm = pd.DataFrame(0, index=stage_names, columns=stage_names)
    for (a, b), c in st_tr.items():
        stm.loc[a, b] = c
    stm_prob = stm.div(stm.sum(axis=1).replace(0, np.nan), axis=0).round(3)
    save_table(stm_prob.reset_index(names="from_stage"), "journey_stage_transition_probabilities")

    # sankey data: step1 -> step2 -> step3 (session level, top flows)
    links = Counter()
    for p in paths:
        seq = list(p[:3]) + ["Exit"] if len(p) < 3 else list(p[:3])
        for i, (a, b) in enumerate(zip(seq[:-1], seq[1:])):
            links[(f"{i + 1}. {a}", f"{i + 2}. {b}" if b != "Exit" else "Exit")] += 1
    sankey = pd.DataFrame([{"source": a, "target": b, "value": c} for (a, b), c in links.items()])
    sankey = sankey[sankey.value >= sankey.value.quantile(0.80)].sort_values("value", ascending=False)
    save_table(sankey, "journey_sankey_links")

    ctx.R["journey"] = {
        "first_second": fs_tbl, "first_to_second_pairs": first_second, "top_paths": path_tbl,
        "successful_vs_abandoned": seq_tbl, "abandon_last_events": aband_last_evt.to_dict(),
        "exits": exits, "exit_stage": exit_stage.to_dict(), "exit_event_top": exit_event.to_dict(),
        "transition_counts": tm.reset_index(names="from_feature"), "transition_prob": tm_prob.reset_index(names="from_feature"),
        "transition_lift_range": [float(np.nanmin(lift.values)), float(np.nanmax(lift.values))],
        "transition_independence_p": float(chi2[1]), "top_transitions": top_trans,
        "stage_transition_prob": stm_prob.reset_index(names="from_stage"), "sankey": sankey,
        "path_length": {"mean": round(path_len.mean(), 2), "median": float(path_len.median()),
                        "single_step_pct": pct((path_len == 1).sum(), n_sess)},
        "sessions_successful_pct": pct(has_meaningful.sum(), n_sess),
        "sessions_ending_negative_pct": pct(neg_end.sum(), n_sess),
        "browse_only_sessions_pct": pct(browse_only.sum(), n_sess), "browse_only_sessions": int(browse_only.sum()),
        "valid_sessions": n_sess,
        "exit_field_match_pct": pct((s[s.is_valid].exit_feature == s[s.is_valid].last_raw_feature).sum(),
                                    s[s.is_valid].exit_feature.notna().sum()),
    }
