"""Work Packages P & Q — Repeat engagement and streak / progression behaviour.

Association language only. To reduce the circularity of "repeat users use more features" (they simply
had more visits), the feature-association test uses FIRST-ACTIVE-DAY behaviour against LATER return,
and adjusts for first-day activity volume by stratification.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from analysis import config
from analysis.pipeline.context import Context
from analysis.utils.io import save_table
from analysis.utils.metrics import pct


def _max_run(dates: pd.Series) -> int:
    d = np.sort(dates.unique())
    if len(d) == 0:
        return 0
    best = cur = 1
    for a, b in zip(d[:-1], d[1:]):
        cur = cur + 1 if (b - a) == np.timedelta64(1, "D") else 1
        best = max(best, cur)
    return best


def _around(ud: pd.DataFrame, anchor: pd.Series, days: int) -> pd.DataFrame:
    """Active days / events in the `days` before vs after each user's anchor date (anchor day excluded)."""
    x = ud[ud.user_id.isin(anchor.index)].copy()
    x["off"] = (x.date - x.user_id.map(anchor)).dt.days
    before = x[x.off.between(-days, -1)].groupby("user_id").agg(active_days_before=("date", "size"), events_before=("events", "sum"))
    after = x[x.off.between(1, days)].groupby("user_id").agg(active_days_after=("date", "size"), events_after=("events", "sum"))
    return pd.DataFrame(index=anchor.index).join(before).join(after).fillna(0)


def run(ctx: Context) -> None:
    u, e, t, s, ud = ctx.users, ctx.events, ctx.tasks, ctx.sessions, ctx.user_day
    act = u[u.is_active].copy()
    act["group"] = np.where(act.n_sessions >= 2, "Multi-session users", "Single-session users")
    uc = ctx.extra["uf_complete"].reindex(act.user_id).fillna(0)
    g = act.groupby("group")

    comp = pd.DataFrame({
        "users": g.size(), "mean_feature_types": g.n_features.mean(), "mean_features_completed": g.n_features_completed.mean(),
        "mean_active_days": g.n_active_days.mean(), "mean_sessions": g.n_sessions.mean(),
        "mean_session_s": g.total_session_seconds.sum() / g.n_sessions.sum(), "median_session_s": g.median_session_seconds.median(),
        "task_completion_rate_pct": g.n_tasks_completed.sum() / g.n_tasks_resolved.sum() * 100,
        "daily_reward_claim_users_pct": g.n_daily_reward_claimed.apply(lambda x: (x > 0).mean() * 100),
        "streak_claim_users_pct": g.n_streak_claimed.apply(lambda x: (x > 0).mean() * 100),
        "streak_broken_users_pct": g.n_streak_broken.apply(lambda x: (x > 0).mean() * 100),
        "mission_completed_users_pct": g.n_mission_completed.apply(lambda x: (x > 0).mean() * 100),
        "spin_completed_users_pct": g.n_spin_completed.apply(lambda x: (x > 0).mean() * 100),
        "level_up_users_pct": g.n_level_up.apply(lambda x: (x > 0).mean() * 100),
        "referral_action_users_pct": g.n_referral_actions.apply(lambda x: (x > 0).mean() * 100),
        "meaningful_per_session": g.n_meaningful.sum() / g.n_valid_sessions.sum(),
    }).round(2).T.reset_index(names="metric")
    save_table(comp, "repeat_vs_single_session_users")
    multi = act[act.group == "Multi-session users"]
    em = e[e.user_id.isin(multi.user_id)]
    most_used = em.feature_name.value_counts(normalize=True).mul(100).round(2).rename_axis("feature").reset_index(name="share_of_events_pct")
    save_table(most_used, "repeat_users_most_used_features")

    # first-active-day feature completion vs D7 return, adjusted for first-day volume
    fa = u.set_index("user_id").first_active_date
    e1 = e[e.date == e.user_id.map(fa)]
    day1_events = e1.groupby("user_id").size()
    day1_comp = e1[e1.is_meaningful].pivot_table(index="user_id", columns="feature_name", values="event_id",
                                                 aggfunc="count", fill_value=0) > 0
    base = u[u.D7_eligible.astype(bool)].set_index("user_id")
    base = base[base.is_active]
    vol = day1_events.reindex(base.index).fillna(0)
    tercile = pd.qcut(vol.rank(method="first"), 3, labels=["low", "mid", "high"])
    rows = []
    for f in sorted(day1_comp.columns):
        x = day1_comp[f].reindex(base.index, fill_value=False).astype(bool)
        y = base.D7_return.astype(float)
        if x.sum() < 20 or (~x).sum() < 20:
            continue
        raw_diff = y[x].mean() - y[~x].mean()
        ct = pd.crosstab(x, y)
        p = stats.chi2_contingency(ct)[1] if ct.shape == (2, 2) else np.nan
        diffs, weights = [], []
        for tl in ["low", "mid", "high"]:
            m = tercile == tl
            if x[m].sum() >= 5 and (~x[m]).sum() >= 5:
                diffs.append(y[m & x].mean() - y[m & ~x].mean())
                weights.append(m.sum())
        adj = np.average(diffs, weights=weights) if diffs else np.nan
        rows.append({"feature": f, "users_completed_day1": int(x.sum()), "d7_return_if_completed_pct": round(y[x].mean() * 100, 1),
                     "d7_return_if_not_pct": round(y[~x].mean() * 100, 1), "raw_difference_pp": round(raw_diff * 100, 1),
                     "volume_adjusted_difference_pp": round(adj * 100, 1), "chi2_p_value": float(f"{p:.4g}")})
    assoc = pd.DataFrame(rows).sort_values("volume_adjusted_difference_pp", ascending=False)
    assoc["reading"] = np.where(assoc.chi2_p_value < 0.05, "Association detectable (not causal)",
                                "No detectable association")
    save_table(assoc, "day1_feature_vs_d7_return_association")
    vol_ret = pd.DataFrame({"tercile": tercile, "ret": base.D7_return}).groupby("tercile", observed=True).ret.mean().mul(100).round(1)

    # ---------------------------------------------------------------- streaks
    sc = e[e.event_name == "streak_claimed"]
    sb = e[e.event_name == "streak_broken"]
    runs = sc.groupby("user_id").date.apply(_max_run)
    streak = {
        "users_claiming": int(sc.user_id.nunique()), "pct_active_claiming": pct(sc.user_id.nunique(), len(act)),
        "users_breaking": int(sb.user_id.nunique()), "pct_active_breaking": pct(sb.user_id.nunique(), len(act)),
        "users_claim_and_break": int(len(set(sc.user_id) & set(sb.user_id))),
        "users_consecutive_claim_days": int((runs >= 2).sum()),
        "pct_claimers_consecutive": pct((runs >= 2).sum(), len(runs)),
        "max_consecutive_claim_days": int(runs.max()), "claim_events": len(sc), "break_events": len(sb),
        "break_to_claim_ratio": round(len(sb) / max(len(sc), 1), 3),
        "run_length_distribution": runs.value_counts().sort_index().to_dict(),
    }
    act["streak_claimer"] = act.n_streak_claimed > 0
    streak_cmp = act.groupby("streak_claimer").agg(users=("user_id", "size"), mean_active_days=("n_active_days", "mean"),
                                                   median_active_days=("n_active_days", "median"),
                                                   mean_events=("n_events", "mean")).round(2).reset_index()
    streak["claimer_vs_non"] = streak_cmp
    # activity in the 7 days before vs after the first streak break
    fb = sb.groupby("user_id").date.min()
    end_day = ctx.data_end.normalize()
    first_day = ud.groupby("user_id").date.min()
    elig_b = fb[(fb + pd.Timedelta(days=7) <= end_day) & (fb - pd.Timedelta(days=7) >= first_day.reindex(fb.index))]
    wdf = _around(ud, elig_b, 7)
    if len(wdf):
        wb = wdf[["active_days_before", "active_days_after"]].to_numpy()
        w = stats.wilcoxon(wb[:, 0], wb[:, 1]) if (wb[:, 0] != wb[:, 1]).any() else None
        streak["around_first_break"] = {"users": len(wb), "mean_active_days_7d_before": round(wb[:, 0].mean(), 2),
                                        "mean_active_days_7d_after": round(wb[:, 1].mean(), 2),
                                        "wilcoxon_p": float(w.pvalue) if w else None}

    # ---------------------------------------------------------------- levels / progression
    lu = e[e.event_name == "level_up"]
    first_lu = lu.groupby("user_id").date.min()
    # need full 14-day windows on both sides and ≥14 days of active life before the first level-up
    ok = ((first_lu + pd.Timedelta(days=14) <= end_day) & (first_lu - pd.Timedelta(days=14) >= ctx.data_start.normalize())
          & ((first_lu - fa.reindex(first_lu.index)).dt.days >= 14))
    lv = _around(ud, first_lu[ok], 14)
    level = {
        "users_with_level_up": int(lu.user_id.nunique()), "pct_active": pct(lu.user_id.nunique(), len(act)),
        "level_up_events": len(lu), "level_ups_per_leveller_mean": round(lu.groupby("user_id").size().mean(), 2),
        "level_ups_per_leveller_dist": lu.groupby("user_id").size().value_counts().sort_index().to_dict(),
        "users_viewing_level_system": int(e[e.event_name == "level_viewed"].user_id.nunique()),
        "xp_related_event_users": int(e[e.xp_related_flag == "Yes"].user_id.nunique()),
        "xp_related_events": int((e.xp_related_flag == "Yes").sum()),
        "badge_earned_users": int(e[e.event_name == "badge_earned"].user_id.nunique()),
        "current_level_and_xp_balance": "Not supported by available dataset (fields absent from 01_Users_1000).",
    }
    if len(lv):
        wl = stats.wilcoxon(lv.active_days_before, lv.active_days_after)
        level["before_after_first_level_up"] = {
            "users": len(lv), "mean_active_days_14d_before": round(lv.active_days_before.mean(), 2),
            "mean_active_days_14d_after": round(lv.active_days_after.mean(), 2),
            "mean_events_14d_before": round(lv.events_before.mean(), 2), "mean_events_14d_after": round(lv.events_after.mean(), 2),
            "wilcoxon_p_active_days": float(wl.pvalue)}
    prog_feats = ["Level System", "Badges", "Leaderboard", "Missions"]
    level["users_interacting_progression_features"] = int(e[e.feature_name.isin(prog_feats)].user_id.nunique())
    save_table(pd.DataFrame([{k: v for k, v in streak.items() if not isinstance(v, (dict, pd.DataFrame))}]), "streak_summary")
    save_table(pd.DataFrame([{k: v for k, v in level.items() if not isinstance(v, (dict, pd.DataFrame))}]), "progression_summary")

    ctx.R["repeat"] = {"comparison": comp, "most_used_multi": most_used, "day1_association": assoc,
                       "d7_by_day1_volume_tercile": vol_ret.to_dict(), "multi_session_users": int(len(multi)),
                       "single_session_users": int((act.group == "Single-session users").sum())}
    ctx.R["progression"] = {"streak": streak, "level": level}
