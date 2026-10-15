"""Work Package D — Session behaviour."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from analysis.pipeline.context import Context
from analysis.utils.io import save_table
from analysis.utils.metrics import dist_summary, pct, safe_div

FREQ_BINS = [(0, 0, "0"), (1, 1, "1"), (2, 2, "2"), (3, 5, "3–5"), (6, 10, "6–10"), (11, 20, "11–20"), (21, 10_000, "21+")]


def run(ctx: Context) -> None:
    s, u, e = ctx.sessions, ctx.users, ctx.events
    v = s[s.is_valid]
    dur = s.session_duration_seconds
    n_sess, n_users = len(s), len(u)
    active_users = int(u.is_active.sum())
    users_with_sessions = int(u.has_session.sum())

    q25, q75 = dur.quantile(0.25), dur.quantile(0.75)
    fence = float(s.loc[s.is_long_session, "session_duration_seconds"].min() - 1) if s.is_long_session.any() else np.inf
    s["duration_band"] = np.select(
        [dur <= q25, dur <= q75, ~s.is_long_session], ["Short (≤P25)", "Medium (P25–P75]", "Long (>P75)"],
        "Extreme (>Q3+3·IQR)")
    band_order = ["Short (≤P25)", "Medium (P25–P75]", "Long (>P75)", "Extreme (>Q3+3·IQR)"]
    bands = s.groupby("duration_band").agg(
        sessions=("session_id", "size"), min_s=("session_duration_seconds", "min"), max_s=("session_duration_seconds", "max"),
        valid_share=("is_valid", "mean"), mean_raw_events=("raw_event_count", "mean"),
        mean_features=("raw_feature_count", "mean"), mean_meaningful=("raw_meaningful_count", "mean"),
        meaningful_session_share=("raw_meaningful_count", lambda x: (x > 0).mean())).reindex(band_order).reset_index()
    bands["pct_sessions"] = (bands.sessions / n_sess * 100).round(1)
    bands["meaningful_per_minute"] = (bands.mean_meaningful / (s.groupby("duration_band").session_duration_seconds.mean()
                                                              .reindex(band_order).values / 60)).round(2)
    save_table(bands, "session_duration_bands")

    rho, p = stats.spearmanr(v.session_duration_seconds, v.raw_event_count)
    rho_m, p_m = stats.spearmanr(v.session_duration_seconds, v.raw_meaningful_count)

    spu = u.n_sessions
    freq = []
    for lo, hi, lab in FREQ_BINS:
        c = int(((spu >= lo) & (spu <= hi)).sum())
        freq.append({"sessions_per_user": lab, "users": c, "pct_of_registered": pct(c, n_users)})
    freq = pd.DataFrame(freq)
    save_table(freq, "session_frequency_distribution")
    hf_threshold = int(u.loc[u.has_session, "n_sessions"].quantile(0.75))

    # return frequency: gap between consecutive active days
    ud = ctx.user_day.sort_values(["user_id", "date"])
    gaps = ud.groupby("user_id").date.diff().dt.days.dropna()
    user_med_gap = ud.assign(g=ud.groupby("user_id").date.diff().dt.days).groupby("user_id").g.median().dropna()

    # entry points
    ep = s.groupby("entry_point").agg(sessions=("session_id", "size"), valid_share=("is_valid", "mean"),
                                      mean_events=("raw_event_count", "mean"), median_duration=("session_duration_seconds", "median"),
                                      meaningful_share=("raw_meaningful_count", lambda x: (x > 0).mean())).reset_index()
    ep["pct_sessions"] = (ep.sessions / n_sess * 100).round(1)
    save_table(ep.round(3), "session_entry_points")

    # sessions by user session index (does depth change with experience?)
    by_idx = v.assign(idx=np.minimum(v.user_session_index, 10)).groupby("idx").agg(
        sessions=("session_id", "size"), mean_events=("raw_event_count", "mean"),
        mean_features=("raw_feature_count", "mean"), median_duration=("session_duration_seconds", "median")).reset_index()
    by_idx["idx"] = by_idx.idx.astype(str).replace({"10": "10+"})
    save_table(by_idx.round(3), "session_depth_by_session_number")

    total_events = len(e)
    metrics = {
        "total_sessions": n_sess, "valid_sessions": int(len(v)), "zero_event_sessions": int((~s.is_valid).sum()),
        "users_with_sessions": users_with_sessions, "active_users": active_users,
        "sessions_per_registered_user": round(safe_div(n_sess, n_users), 3),
        "sessions_per_user_with_session": round(safe_div(n_sess, users_with_sessions), 3),
        "sessions_per_active_user": round(safe_div(n_sess, active_users), 3),
        "avg_session_duration_s": round(dur.mean(), 2), "median_session_duration_s": float(dur.median()),
        "p25_duration_s": float(q25), "p75_duration_s": float(q75), "p90_duration_s": float(dur.quantile(0.9)),
        "p95_duration_s": float(dur.quantile(0.95)), "p99_duration_s": float(dur.quantile(0.99)),
        "max_duration_s": int(dur.max()), "min_duration_s": int(dur.min()),
        "events_per_valid_session": round(safe_div(total_events, len(v)), 3),
        "events_per_session_all": round(safe_div(total_events, n_sess), 3),
        "median_events_per_valid_session": float(v.raw_event_count.median()),
        "distinct_features_per_valid_session": round(v.raw_feature_count.mean(), 3),
        "meaningful_per_valid_session": round(v.raw_meaningful_count.mean(), 3),
        "sessions_with_meaningful_pct": pct((v.raw_meaningful_count > 0).sum(), len(v)),
        "one_session_users": int((spu == 1).sum()), "repeat_session_users": int((spu >= 2).sum()),
        "repeat_session_rate_pct": pct((spu >= 2).sum(), users_with_sessions),
        "high_frequency_session_threshold": hf_threshold,
        "high_frequency_session_users": int((spu >= hf_threshold).sum()),
        "median_sessions_per_active_user": float(u.loc[u.has_session, "n_sessions"].median()),
        "median_gap_between_active_days": float(gaps.median()), "mean_gap_between_active_days": float(gaps.mean()),
        "median_of_user_median_gap_days": float(user_med_gap.median()),
        "duration_events_spearman": round(float(rho), 3), "duration_events_p": float(p),
        "duration_meaningful_spearman": round(float(rho_m), 3),
        "total_session_hours": round(dur.sum() / 3600, 1),
    }
    ctx.R["sessions"] = {
        "metrics": metrics, "duration_summary": dist_summary(dur), "duration_bands": bands,
        "duration_band_rule": f"Quartile-based on observed durations: Short ≤ {q25:.0f}s (P25), Medium ≤ {q75:.0f}s (P75), "
                              f"Long > {q75:.0f}s, Extreme > {fence:.0f}s (Q3 + 3·IQR).",
        "frequency": freq, "entry_points": ep, "depth_by_session_number": by_idx,
        "duration_hist": np.histogram(dur, bins=list(range(20, 200, 10)) + [500])[0].tolist(),
        "duration_hist_edges": list(range(20, 200, 10)) + [500],
        "gap_distribution": gaps.clip(upper=31).value_counts().sort_index().to_dict(),
    }
    ctx.sessions = s
