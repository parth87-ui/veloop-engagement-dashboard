"""Work Package U — Behavioural anomaly investigation.

Detect → quantify → document → flag for investigation. No fraud determination is made and no
confidential anti-fraud rule is implied; thresholds are generic statistical rules (Tukey far-out
fence Q3 + 3·IQR) or logical impossibilities.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.pipeline.context import Context
from analysis.utils.io import save_table
from analysis.utils.metrics import pct, tukey_upper_fence


def _sev(ratio: float) -> str:
    return "High" if ratio >= 1.5 else "Medium" if ratio >= 1.15 else "Low"


def run(ctx: Context) -> None:
    u, s, e, t = ctx.users, ctx.sessions, ctx.events, ctx.tasks
    rows: list[dict] = []
    summary: list[dict] = []

    def add(type_, entity_type, entity, metric, value, threshold, severity, interp, invest):
        rows.append({"type": type_, "entity_type": entity_type, "entity": entity, "metric": metric,
                     "observed_value": value, "threshold": threshold, "severity": severity,
                     "interpretation": interp, "recommended_investigation": invest})

    def summarise(type_, flagged, population, threshold, interp, invest):
        summary.append({"type": type_, "entities_flagged": int(flagged), "population": int(population),
                        "pct_flagged": pct(flagged, population, 2), "threshold": threshold,
                        "interpretation": interp, "recommended_investigation": invest})

    act = u[u.is_active]
    # 1. user event volume
    f = tukey_upper_fence(act.n_events)
    hit = act[act.n_events > f]
    for r in hit.itertuples():
        add("Extremely high event volume", "user", r.user_id, "total events", int(r.n_events), round(f, 1),
            _sev(r.n_events / f), "Event volume far above the simulated population.",
            "Review event logging for duplication; review activity pattern for automation signals.")
    summarise("Extremely high event volume (user)", len(hit), len(act), f"> {f:.0f} events (Q3+3·IQR)",
              "Far-out heavy users.", "Logging duplication / automation review.")
    # 2. events per active day
    epd = act.n_events / act.n_active_days
    f2 = tukey_upper_fence(epd)
    hit = act[epd > f2]
    for r in hit.itertuples():
        v = r.n_events / r.n_active_days
        add("Unusual activity concentration", "user", r.user_id, "events per active day", round(v, 1), round(f2, 1),
            _sev(v / f2), "Activity packed into few days.", "Check whether activity is concentrated in a single burst.")
    summarise("Unusual activity concentration (events / active day)", len(hit), len(act), f"> {f2:.1f} events/day",
              "Bursty users.", "Burst review.")
    # 3. session event count
    v = s[s.is_valid]
    f3 = tukey_upper_fence(v.raw_event_count)
    hit = v[v.raw_event_count > f3]
    for r in hit.itertuples():
        add("Suspiciously high session event count", "session", r.session_id, "raw events in session",
            int(r.raw_event_count), round(f3, 1), _sev(r.raw_event_count / f3),
            f"Session duration only {r.session_duration_seconds}s.", "Inspect raw event stream for this session.")
    summarise("High session event count", len(hit), len(v), f"> {f3:.0f} events", "Dense sessions.", "Event-stream review.")
    # 4. event density (events per minute)
    f4 = tukey_upper_fence(v.event_density_per_min)
    hit = v[v.event_density_per_min > f4]
    for r in hit.itertuples():
        add("Many events in very short time", "session", r.session_id, "events per minute",
            round(r.event_density_per_min, 1), round(f4, 1), _sev(r.event_density_per_min / f4),
            f"{r.raw_event_count} events in {r.session_duration_seconds}s.", "Check for scripted/rapid-fire interactions.")
    summarise("High event density (events/min)", len(hit), len(v), f"> {f4:.1f} events/min", "Rapid-fire sessions.",
              "Rate-pattern review.")
    # 5. long sessions
    fence = float(ctx.extra["session_long_fence"].fence.iloc[0])
    hit = s[s.is_long_session]
    for r in hit.itertuples():
        add("Unusually long session", "session", r.session_id, "duration (s)", int(r.session_duration_seconds),
            round(fence, 0), _sev(r.session_duration_seconds / fence), "Long relative to the simulated distribution "
            "(still < 8 minutes).", "Check idle-timeout handling.")
    summarise("Unusually long session", len(hit), len(s), f"> {fence:.0f}s", "Relative outliers only.", "Idle-timeout review.")
    # 6. identical repeated events
    raw = ctx.raw["events"]
    cols = [c for c in raw.columns if c != "event_id"]
    dups = raw[raw.duplicated(subset=cols, keep=False)].sort_values(cols)
    for (uid, sid, ts, ev), g in dups.groupby(["user_id", "session_id", "event_datetime", "event_name"]):
        add("Repeated identical events", "event group", ", ".join(g.event_id), "identical copies", len(g), 1, "Medium",
            f"{ev} logged {len(g)}× with identical fields (user {uid}, session {sid}).", "Check client retry / double-fire logic.")
    summarise("Repeated identical events", raw.duplicated(subset=cols).sum(), len(raw), "> 1 identical copy",
              "Double logging.", "Client retry logic.")
    # 7. excessive repeated feature events within one session
    per = e.groupby(["session_id", "event_name"]).size()
    f7 = max(tukey_upper_fence(per), 3)
    hit = per[per > f7]
    for (sid, ev), c in hit.items():
        add("Excessive repeated feature events", "session", sid, f"'{ev}' count in session", int(c), round(f7, 1),
            _sev(c / f7), "Same event fired repeatedly in one session.", "Check reward-claim idempotency for this event.")
    summarise("Excessive repeated event in a session", len(hit), len(per), f"> {f7:.0f} of the same event",
              "Repeated firing.", "Idempotency review.")
    # 8. repeated identical sequences (≥4 events, identical event-name sequence)
    seq = e.sort_values(["session_id", "event_datetime", "event_id"]).groupby("session_id").event_name.agg(tuple)
    seq = seq[seq.str.len() >= 4]
    vc = seq.value_counts()
    rep = vc[vc >= 2]
    for sq, c in rep.items():
        sids = seq[seq == sq].index.tolist()
        add("Repeated identical sequences", "session group", ", ".join(sids[:5]), "sessions sharing exact sequence", int(c),
            1, "Low", "Identical ≥4-event sequence: " + " → ".join(sq), "Compare users/devices behind these sessions.")
    summarise("Repeated identical ≥4-event sequences", int(rep.sum()), len(seq), "≥2 sessions with same sequence",
              "Template-like behaviour.", "Session comparison.")
    # 9. impossible timestamp sequences (completion before start in the same session)
    pairs = {"ad_completed": "ad_started", "spin_completed": "spin_started", "mission_completed": "mission_started",
             "captcha_completed": "captcha_started", "tap_completed": "tap_started", "mining_activity": "mining_started"}
    ft_ = e.groupby(["session_id", "event_name"]).event_datetime.min().unstack()
    n_imp = 0
    for c_ev, s_ev in pairs.items():
        b = ft_[[c_ev, s_ev]].dropna()
        bad = b[b[c_ev] < b[s_ev]]
        n_imp += len(bad)
        for sid, r in bad.iterrows():
            add("Impossible timestamp sequence", "session", sid, f"{c_ev} before {s_ev} (s)",
                round((r[s_ev] - r[c_ev]).total_seconds(), 0), 0, "Medium",
                "Completion logged before the matching start.", "Check client clock / event ordering pipeline.")
    summarise("Completion before start (same session)", n_imp, int(sum(len(ft_[[c, s_]].dropna()) for c, s_ in pairs.items())),
              "completion ts < start ts", "Ordering defect.", "Clock/ordering pipeline.")
    # 10. overlapping sessions
    hit = s[s.is_overlapping]
    for r in hit.itertuples():
        add("Overlapping sessions", "session", r.session_id, "starts before previous session ended", 1, 0, "Low",
            f"User {r.user_id} has concurrent sessions.", "Check session-id assignment across tabs/devices.")
    summarise("Overlapping sessions", len(hit), len(s), "start < previous end", "Concurrency.", "Session-id logic.")
    # 11. streak broken without any streak claimed
    claimers = set(e.loc[e.event_name == "streak_claimed", "user_id"])
    breakers = e.loc[e.event_name == "streak_broken"].groupby("user_id").size()
    nb = breakers[~breakers.index.isin(claimers)]
    for uid, c in nb.items():
        add("Streak broken with no streak claimed", "user", uid, "streak_broken events", int(c), 0, "Low",
            "A streak cannot break if it was never claimed (in the observed log).", "Confirm streak state logic / missing claim events.")
    summarise("Streak broken without any recorded claim", len(nb), len(breakers), "claims = 0",
              "State-logic gap.", "Streak state logging.")
    # 12. systemic: task completed after session end
    tk = t.merge(s[["session_id", "session_end"]], on="session_id")
    n_after = int((tk.task_completed_at > tk.session_end).sum())
    add("Task completion after session end (systemic)", "dataset", "05_Task_Activity × 02_Sessions",
        "completed tasks finishing after session_end", n_after, 0, "High",
        "Session windows do not contain task flows.", "Confirm how session_end is defined (inactivity timeout?).")
    summarise("Task completion after session end", n_after, int(t.is_completed.sum()), "completed_at > session_end",
              "Systemic timing mismatch.", "Session definition.")
    # 13. very old pending tasks
    old = t[(t.task_status == "Pending") & (t.task_viewed_at < ctx.data_end - pd.Timedelta(days=30))]
    add("Long-pending task validation (systemic)", "dataset", "05_Task_Activity", "pending > 30 days", len(old), 0,
        "Medium", "Rewards may be stuck in validation.", "Review validation pipeline / third-party confirmation SLAs.")
    summarise("Pending > 30 days", len(old), int((t.task_status == "Pending").sum()), "> 30 days pending",
              "Validation backlog.", "Validation SLA.")

    an = pd.DataFrame(rows)
    sev_rank = {"High": 0, "Medium": 1, "Low": 2}
    an = an.sort_values(["type", "severity"], key=lambda c: c.map(sev_rank) if c.name == "severity" else c).reset_index(drop=True)
    an.insert(0, "anomaly_id", [f"ANM-{i + 1:04d}" for i in range(len(an))])
    save_table(an, "anomaly_register")
    sm = pd.DataFrame(summary)
    save_table(sm, "anomaly_summary")

    flagged_users = set(an.loc[an.entity_type == "user", "entity"])
    user_scatter = act[["user_id", "n_events", "n_active_days", "n_sessions"]].assign(
        flagged=lambda d: d.user_id.isin(flagged_users))
    ctx.extra["anomaly_flagged_users"] = pd.DataFrame({"user_id": sorted(flagged_users)})
    ctx.R["anomalies"] = {
        "register": an, "summary": sm, "by_type": an.type.value_counts().to_dict(),
        "by_severity": an.severity.value_counts().to_dict(), "flagged_users": len(flagged_users),
        "user_scatter": user_scatter.drop(columns="user_id"),
        "density_hist": np.histogram(v.event_density_per_min.clip(upper=40), bins=range(0, 42, 2))[0].tolist(),
        "fences": {"user_events": f, "events_per_active_day": f2, "session_events": f3, "events_per_min": f4,
                   "long_session_s": fence, "same_event_in_session": f7},
        "top_examples": an[an.severity == "High"].head(15),
    }
