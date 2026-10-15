"""Independent check of the headline metrics.

Recomputes the main numbers straight from data/anonymised/*.csv with plain pandas – it does NOT import the
analysis pipeline – and compares them with the published outputs (outputs/dashboard_data, outputs/tables).

    python verify_headline_metrics.py

Definitions mirror docs/methodology.md and are written out here in full so a reviewer can read them in one place.
All data is simulated; nothing here describes actual VELOOP Rewards users.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
D = ROOT / "data" / "anonymised"
OUT = ROOT / "outputs"

MEANINGFUL = {"ad_completed", "captcha_completed", "daily_reward_claimed", "follow_task_completed", "mining_activity",
              "mission_completed", "referral_created", "referral_shared", "spin_completed", "streak_claimed", "tap_completed"}
STARTS = {"ad_started", "captcha_started", "mining_started", "mission_started", "spin_started", "tap_started"}
WINDOWS = {"D1": (1, 1), "D7": (1, 7), "D14": (8, 14), "D30": (24, 30)}
ACTIVATION_DAYS = 14


def load(name: str, dates: list[str]) -> pd.DataFrame:
    return pd.read_csv(D / f"{name}.csv", parse_dates=dates)


def main() -> int:
    users = load("01_Users_1000", ["registration_datetime"])
    sess = load("02_Sessions", ["session_start", "session_end"])
    ev = load("03_Feature_Events", ["event_datetime"])
    tasks = load("05_Task_Activity", ["task_viewed_at", "task_started_at", "task_completed_at"])

    # clean events: drop rows identical in every field except event_id (17 rows)
    ev = ev[~ev.drop(columns="event_id").duplicated()].copy()
    ev["date"] = ev.event_datetime.dt.normalize()
    end = max(sess.session_end.max(), ev.event_datetime.max())
    end_day = end.normalize()

    n_users = users.user_id.nunique()
    active = ev.user_id.unique()
    active_days = ev.groupby("user_id").date.nunique()
    first_active = ev.groupby("user_id").date.min()

    # meaningful activity = completion event or completed task
    m_ev = ev[ev.event_name.isin(MEANINGFUL)]
    done = tasks[tasks.task_status == "Completed"]
    first_meaningful = pd.concat([m_ev.groupby("user_id").event_datetime.min(),
                                  done.groupby("user_id").task_completed_at.min()], axis=1).min(axis=1)
    m_days = pd.concat([m_ev[["user_id", "date"]],
                        done.assign(date=done.task_completed_at.dt.normalize())[["user_id", "date"]]]).drop_duplicates()
    m_days = m_days.groupby("user_id").size()

    # activation: first meaningful activity within 14 days of registration; eligible = registered ≥14 days before end
    reg = users.set_index("user_id").registration_datetime
    eligible = reg[reg <= end - pd.Timedelta(days=ACTIVATION_DAYS)]
    lag = (first_meaningful.reindex(eligible.index) - eligible)
    activated = int((lag <= pd.Timedelta(days=ACTIVATION_DAYS)).sum())

    # return windows anchored on first active date, eligible only if the whole window is observable
    off = ev[["user_id", "date"]].drop_duplicates()
    off["offset"] = (off.date - off.user_id.map(first_active)).dt.days
    returns = {}
    for k, (lo, hi) in WINDOWS.items():
        el = first_active[first_active + pd.Timedelta(days=hi) <= end_day].index
        hit = off[(off.offset >= lo) & (off.offset <= hi) & off.user_id.isin(el)].user_id.nunique()
        returns[k] = round(hit / len(el) * 100, 1)

    started = set(ev.loc[ev.event_name.isin(STARTS), "user_id"]) | set(tasks.user_id)
    resolved = tasks[tasks.task_status.isin(["Completed", "Failed", "Abandoned"])]
    valid_sessions = sess.session_id.isin(ev.session_id).sum()
    feats_done = m_ev.groupby("user_id").feature_name.nunique().reindex(active).fillna(0)
    multi_thr = int(feats_done.quantile(0.75))

    mine = {
        "Registered users": n_users,
        "Active users": len(active),
        "Sessions": len(sess),
        "Active user-days": int(active_days.sum()),
        "Repeat-user rate % (≥2 active days ÷ active)": round((active_days >= 2).mean() * 100, 1),
        "Multi-feature user rate % (÷ active)": round((feats_done >= multi_thr).mean() * 100, 1),
        f"Activation rate % ({ACTIVATION_DAYS}-day)": round(activated / len(eligible) * 100, 1),
        "D1 return %": returns["D1"], "D7 return %": returns["D7"], "D14 return %": returns["D14"], "D30 return %": returns["D30"],
        "Task completion rate % (resolved)": round((resolved.task_status == "Completed").mean() * 100, 1),
        "Events per valid session": round(len(ev) / valid_sessions, 3),
        "Median session duration (s)": float(sess.session_duration_seconds.median()),
        "Funnel: logged in": int(sess.user_id.nunique()),
        "Funnel: started an activity": len(started),
        "Funnel: completed a meaningful activity": int(first_meaningful.notna().sum()),
        "Funnel: returned (cumulative)": int((active_days >= 2).sum()),
        "Funnel: established (cumulative)": int(((active_days >= 2) & (m_days.reindex(active_days.index).fillna(0) >= 3)).sum()),
    }

    meta = json.loads((OUT / "dashboard_data" / "meta.json").read_text(encoding="utf-8"))
    agg = json.loads((OUT / "dashboard_data" / "aggregates.json").read_text(encoding="utf-8"))
    k, ret = meta["executive_kpis"], agg["retention"]["overall"]
    sm, to = agg["sessions"]["metrics"], agg["features"]["task_overall"]
    fn = pd.read_csv(OUT / "tables" / "activation_funnel.csv").set_index("canonical_stage").users
    published = {
        "Registered users": k["total_users"], "Active users": k["active_users"], "Sessions": k["sessions"],
        "Active user-days": k["active_user_days"],
        "Repeat-user rate % (≥2 active days ÷ active)": k["repeat_user_rate_pct"],
        "Multi-feature user rate % (÷ active)": k["multi_feature_user_rate_pct"],
        f"Activation rate % ({ACTIVATION_DAYS}-day)": k["activation_rate_pct"],
        "D1 return %": ret["D1_rate_pct"], "D7 return %": ret["D7_rate_pct"], "D14 return %": ret["D14_rate_pct"],
        "D30 return %": ret["D30_rate_pct"],
        "Task completion rate % (resolved)": to["completion_rate_resolved_pct"],
        "Events per valid session": sm["events_per_valid_session"],
        "Median session duration (s)": sm["median_session_duration_s"],
        "Funnel: logged in": int(fn["Logged in"]), "Funnel: started an activity": int(fn["Started an activity"]),
        "Funnel: completed a meaningful activity": int(fn["Completed a meaningful activity"]),
        "Funnel: returned (cumulative)": int(fn["Returned (2nd active day)"]),
        "Funnel: established (cumulative)": int(fn["Established (≥3 meaningful days)"]),
    }

    rows = [(name, mine[name], published[name], "PASS" if abs(float(mine[name]) - float(published[name])) < 1e-6 else "FAIL")
            for name in mine]
    width = max(len(r[0]) for r in rows)
    print("Independent recomputation from data/anonymised/ (simulated data)\n")
    print(f"{'Metric':<{width}}  {'Recomputed':>12}  {'Published':>12}  Result")
    for name, a, b, res in rows:
        print(f"{name:<{width}}  {a:>12}  {b:>12}  {res}")
    fails = sum(r[3] == "FAIL" for r in rows)
    print(f"\n{len(rows) - fails}/{len(rows)} metrics match.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
