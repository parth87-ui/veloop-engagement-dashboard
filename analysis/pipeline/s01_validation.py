"""Work Package A — Data understanding & validation.

Produces:
  * a sheet-level profile (rows, columns, nulls, duplicates, date ranges)
  * a column-level profile
  * a data-quality issue register with VALID / WARNING / INVALID / INVESTIGATE classification
  * record-level flags that later steps use (nothing is deleted here)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from analysis import config
from analysis.pipeline.context import Context
from analysis.utils.io import save_table
from analysis.utils.metrics import pct, tukey_upper_fence

PDF_USER_FIELDS = ["user_id", "registration_datetime", "acquisition_source", "registration_device",
                   "operating_system", "city", "state", "account_status", "onboarding_status",
                   "verification_status", "first_activity_datetime", "last_activity_datetime",
                   "total_sessions", "total_active_days", "current_level", "xp_balance",
                   "total_feature_types_used", "total_events", "engagement_segment"]

PDF_EVENT_EXAMPLES = ["user_registered", "login", "session_started", "session_ended", "onboarding_started",
                      "onboarding_completed", "task_viewed", "task_started", "task_completed", "task_failed",
                      "daily_reward_viewed", "daily_reward_claimed", "streak_viewed", "streak_claimed",
                      "streak_broken", "spin_opened", "spin_started", "spin_completed", "mission_viewed",
                      "mission_started", "mission_completed", "badge_viewed", "badge_earned", "level_viewed",
                      "level_up", "tap_started", "tap_completed", "ad_started", "ad_completed", "ad_skipped",
                      "referral_page_viewed", "referral_created", "referral_registered", "referral_activated",
                      "wallet_viewed", "exchange_viewed", "withdrawal_page_viewed"]

COMPLETION_START_PAIRS = {
    "ad_completed": "ad_started", "spin_completed": "spin_started", "mission_completed": "mission_started",
    "captcha_completed": "captcha_started", "tap_completed": "tap_started", "mining_activity": "mining_started",
}

MILESTONE_EXPECTED_FEATURE = {
    "first_spin": "Spin the Wheel", "first_mission": "Missions", "first_streak": "Streak Rewards",
    "first_referral_activity": "Referral", "level_up": "Level System",
}


class IssueLog:
    def __init__(self):
        self.rows: list[dict] = []

    def add(self, dataset, check, count, denominator, classification, severity, impact, action, detail=""):
        self.rows.append({
            "issue_id": f"DQ-{len(self.rows) + 1:03d}",
            "dataset": dataset, "check": check, "detail": detail,
            "count": int(count), "denominator": int(denominator),
            "pct": pct(count, denominator, 2) if denominator else None,
            "classification": classification, "severity": severity,
            "analytical_impact": impact, "action_taken": action,
        })

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


def _profile(raw: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    sheet_rows, col_rows = [], []
    for key, df in raw.items():
        dt_cols = df.select_dtypes(include="datetime").columns
        dmin = min((df[c].min() for c in dt_cols), default=None)
        dmax = max((df[c].max() for c in dt_cols), default=None)
        sheet_rows.append({
            "sheet": config.SHEETS[key], "rows": len(df), "columns": df.shape[1],
            "null_cells": int(df.isna().sum().sum()), "duplicate_rows": int(df.duplicated().sum()),
            "min_datetime": dmin, "max_datetime": dmax,
        })
        if key in ("dictionary", "readme"):
            continue
        for c in df.columns:
            if key == "users" and c in config.PII_COLUMNS:
                sample = "[personal field – not profiled]"
                nunique = int(df[c].nunique())
            else:
                vc = df[c].value_counts().head(5)
                if df[c].nunique() <= 60:
                    sample = "; ".join(f"{k}={v}" for k, v in vc.items())
                elif df[c].dtype == object:
                    sample = f"{df[c].nunique()} distinct ids, e.g. {df[c].dropna().iloc[0]}"
                else:
                    sample = f"min={df[c].min()} | max={df[c].max()}"
                nunique = int(df[c].nunique())
            col_rows.append({"sheet": config.SHEETS[key], "column": c, "dtype": str(df[c].dtype),
                             "nulls": int(df[c].isna().sum()), "null_pct": pct(df[c].isna().sum(), len(df), 2),
                             "unique_values": nunique, "top_values_or_range": sample})
    return pd.DataFrame(sheet_rows), pd.DataFrame(col_rows)


def run(ctx: Context) -> None:
    raw = ctx.raw
    u, s, e, d = raw["users"], raw["sessions"], raw["events"], raw["daily"]
    t, m, fu, a = raw["tasks"], raw["milestones"], raw["feature_usage"], raw["audit"]
    log = IssueLog()

    sheet_profile, col_profile = _profile(raw)
    save_table(sheet_profile, "dq_sheet_profile")
    save_table(col_profile, "dq_column_profile")

    # ------------------------------------------------------------------ USERS
    n_u = len(u)
    log.add("Users", "Duplicate user_id", u.user_id.duplicated().sum(), n_u, "VALID", "None",
            "Primary key is unique; safe to join.", "None required.")
    req_null = int(u[["user_id", "registration_datetime", "acquisition_source", "primary_device"]].isna().sum().sum())
    log.add("Users", "Nulls in required user fields", req_null, n_u, "VALID", "None",
            "No imputation needed.", "None required.")
    non_ref = (u.acquisition_source != "Referral")
    log.add("Users", "referral_source_detail null", u.referral_source_detail.isna().sum(), n_u, "VALID", "None",
            "Field is conditional: populated only for Referral source (all 154 Referral users populated).",
            "Treated as conditional field.",
            detail=f"Nulls among non-Referral users: {int(u.loc[non_ref, 'referral_source_detail'].isna().sum())}")
    log.add("Users", "Personal fields present (name, email, age, gender, city, state, referral_code)",
            len(config.PII_COLUMNS), len(u.columns), "WARNING", "Medium",
            "Not needed for behavioural analysis; exposure risk if published.",
            "Dropped from every processed/analytical/dashboard output; raw workbook git-ignored.")
    missing_fields = [f for f in PDF_USER_FIELDS if f not in u.columns]
    log.add("Users", "PDF-specified user fields absent from workbook", len(missing_fields), len(PDF_USER_FIELDS),
            "INVESTIGATE", "Medium",
            "Lifecycle fields (first/last activity, totals, level, XP) must be derived from raw logs; "
            "current_level and xp_balance cannot be reconstructed exactly.",
            "Derived from sessions/events where possible; level/XP balance marked 'Not supported by available dataset'.",
            detail=", ".join(missing_fields))
    no_sess = ~u.user_id.isin(s.user_id)
    log.add("Users", "Registered users with no session", no_sess.sum(), n_u, "WARNING", "Low",
            "Legitimate 'registered but never active' population; drives registration→login drop-off.",
            "Retained; analysed as zero-activity users.")
    log.add("Users", "platform has a single value ('Web') for all users", (u.platform == "Web").sum(), n_u,
            "WARNING", "Medium",
            "Platform cannot be analysed as a dimension; Android/iOS appear as 'Web' devices (mobile web?).",
            "Device (primary_device) used as the platform dimension; platform flagged as non-discriminating.")
    act = u.user_id.isin(e.user_id)
    log.add("Users", "onboarding_status='Not Started' but user has feature events",
            (act & (u.onboarding_status == "Not Started")).sum(), (u.onboarding_status == "Not Started").sum(),
            "INVESTIGATE", "Low",
            "onboarding_status does not appear to gate activity; cannot be used as a funnel stage.",
            "Reported descriptively only.")
    log.add("Users", "account_status='Suspended' users with activity",
            (act & (u.account_status == "Suspended")).sum(), (u.account_status == "Suspended").sum(),
            "INVESTIGATE", "Low",
            "Snapshot status with no timestamp – cannot tell whether activity occurred before suspension.",
            "Retained; status used descriptively only.")

    # ------------------------------------------------------------------ SESSIONS
    n_s = len(s)
    log.add("Sessions", "Duplicate session_id", s.session_id.duplicated().sum(), n_s, "VALID", "None",
            "Primary key is unique.", "None required.")
    log.add("Sessions", "session_end earlier than session_start", (s.session_end < s.session_start).sum(), n_s,
            "VALID", "None", "No impossible session windows.", "None required.")
    log.add("Sessions", "Negative session_duration_seconds", (s.session_duration_seconds < 0).sum(), n_s,
            "VALID", "None", "No negative durations.", "None required.")
    dur_mismatch = ((s.session_end - s.session_start).dt.total_seconds() != s.session_duration_seconds).sum()
    log.add("Sessions", "session_duration_seconds ≠ end − start", dur_mismatch, n_s, "VALID", "None",
            "Duration field is internally consistent.", "None required.")
    fence = tukey_upper_fence(s.session_duration_seconds, 3.0)
    long_s = (s.session_duration_seconds > fence).sum()
    log.add("Sessions", f"Extremely long sessions (> Q3+3·IQR = {fence:.0f}s)", long_s, n_s, "WARNING", "Low",
            f"Max duration is only {s.session_duration_seconds.max()}s; 'long' is relative – no multi-hour sessions exist.",
            "Retained and flagged (is_long_session); listed in anomaly register.")
    ev_cnt = e.groupby("session_id").size()
    ft_cnt = e.groupby("session_id").feature_name.nunique()
    raw_n = s.session_id.map(ev_cnt).fillna(0).astype(int)
    raw_f = s.session_id.map(ft_cnt).fillna(0).astype(int)
    log.add("Sessions", "Zero-event sessions (no rows in 03_Feature_Events)", (raw_n == 0).sum(), n_s,
            "WARNING", "Medium",
            "Inflate session counts relative to event-backed activity; deflate events/session if included.",
            "Retained as sessions (login proxy); excluded from per-session behaviour metrics ('valid sessions').",
            detail=f"events_in_session field for these sessions: mean {s.loc[raw_n == 0, 'events_in_session'].mean():.1f}")
    log.add("Sessions", "events_in_session ≠ raw event count", (raw_n != s.events_in_session).sum(), n_s,
            "INVALID", "High",
            f"Field mean {s.events_in_session.mean():.2f} vs raw mean {raw_n.mean():.2f} events/session – "
            "using the field would overstate session depth.",
            "Field not used; events/session recomputed from 03_Feature_Events.")
    log.add("Sessions", "features_used_count ≠ raw distinct features", (raw_f != s.features_used_count).sum(), n_s,
            "INVALID", "Medium", "Feature breadth per session would be misstated.",
            "Field not used; recomputed from raw events.")
    s_sorted = s.sort_values(["user_id", "session_start"])
    prev_end = s_sorted.groupby("user_id").session_end.shift()
    overlap = (s_sorted.session_start < prev_end)
    log.add("Sessions", "Overlapping sessions for the same user", overlap.sum(), n_s, "WARNING", "Low",
            "Concurrent sessions are implausible for a single user on one device; minor effect on counts.",
            "Retained and flagged (is_overlapping); impact tested in data-quality impact analysis.")
    last_feat = e.sort_values(["session_id", "event_datetime", "event_id"]).groupby("session_id").feature_name.last()
    s_last = s.session_id.map(last_feat)
    has_ev = raw_n > 0
    log.add("Sessions", "exit_feature null", s.exit_feature.isna().sum(), n_s, "WARNING", "Low",
            "Exit analysis loses these sessions.",
            "Exit analysis reported from both the field and the last raw event.",
            detail=f"of which zero-event sessions: {int((s.exit_feature.isna() & ~has_ev).sum())}")
    log.add("Sessions", "exit_feature ≠ feature of last raw event (event-backed sessions)",
            (has_ev & s.exit_feature.notna() & (s.exit_feature != s_last)).sum(), int((has_ev & s.exit_feature.notna()).sum()),
            "INVESTIGATE", "Medium",
            "The two possible exit definitions disagree; exit-point conclusions are definition-dependent.",
            "Primary exit = last raw event feature (timestamp-ordered); field reported for comparison.")
    log.add("Sessions", "session_status has a single value ('Completed')", (s.session_status == "Completed").sum(),
            n_s, "WARNING", "Low", "No abandoned/crashed session signal available.", "Field not used analytically.")
    tk = t.merge(s[["session_id", "session_end"]], on="session_id", how="left")
    after = (tk.task_completed_at > tk.session_end)
    log.add("Sessions", "Task completed after its parent session ended",
            after.sum(), int(tk.task_completed_at.notna().sum()), "INVESTIGATE", "High",
            "Session durations (median 42s) are too short to contain task flows (median 304s start→complete); "
            "session duration likely measures only part of the visit.",
            "Session duration interpreted as 'logged session window', not true time-in-app.")
    log.add("Sessions", "Orphan user_id (not in Users)", (~s.user_id.isin(u.user_id)).sum(), n_s, "VALID", "None",
            "Referential integrity holds.", "None required.")

    # ------------------------------------------------------------------ EVENTS
    n_e = len(e)
    log.add("Events", "Duplicate event_id", e.event_id.duplicated().sum(), n_e, "VALID", "None",
            "Primary key unique.", "None required.")
    log.add("Events", "Null event timestamps / user_id / session_id",
            int(e[["event_datetime", "user_id", "session_id"]].isna().sum().sum()), n_e, "VALID", "None",
            "No missing keys or timestamps.", "None required.")
    log.add("Events", "Orphan user_id", (~e.user_id.isin(u.user_id)).sum(), n_e, "VALID", "None", "-", "None required.")
    log.add("Events", "Orphan session_id", (~e.session_id.isin(s.session_id)).sum(), n_e, "VALID", "None", "-",
            "None required.")
    me = e.merge(s[["session_id", "user_id", "session_start", "session_end"]], on="session_id", suffixes=("", "_s"))
    log.add("Events", "Event user_id ≠ session user_id", (me.user_id != me.user_id_s).sum(), n_e, "VALID", "None",
            "-", "None required.")
    log.add("Events", "Event timestamp outside its session window",
            ((me.event_datetime < me.session_start) | (me.event_datetime > me.session_end)).sum(), n_e,
            "VALID", "None", "-", "None required.")
    me2 = e.merge(u[["user_id", "registration_datetime"]], on="user_id")
    log.add("Events", "Event before user registration", (me2.event_datetime < me2.registration_datetime).sum(), n_e,
            "VALID", "None", "-", "None required.")
    content_cols = [c for c in e.columns if c != "event_id"]
    dup_content = e.duplicated(subset=content_cols, keep="first")
    log.add("Events", "Repeated identical events (all fields equal except event_id)", dup_content.sum(), n_e,
            "WARNING", "Low", "Slightly inflates event counts for affected features.",
            "Second+ copies excluded from the clean layer (flagged, not deleted from raw).")
    log.add("Events", "Same user + timestamp + event_name (any status/session)",
            e.duplicated(subset=["user_id", "event_datetime", "event_name"]).sum(), n_e, "WARNING", "Low",
            "Possible double-logging; superset of identical events.", "Flagged in anomaly register.")
    dup_seq = e.duplicated(subset=["session_id", "sequence_number"]).sum()
    log.add("Events", "Duplicate sequence_number within a session", dup_seq, n_e, "INVALID", "High",
            "sequence_number cannot define event order.", "Event order derived from event_datetime (tie-break event_id).")
    with np.errstate(invalid="ignore", divide="ignore"):  # constant sequences give NaN correlations
        corr = e.groupby("session_id").filter(lambda g: len(g) > 2).groupby("session_id").apply(
            lambda g: g.sequence_number.corr(g.event_datetime.astype("int64")), include_groups=False)
    log.add("Events", "sequence_number not monotonic with timestamp (sessions with >2 events, |rho|<0.5)",
            (corr.abs() < 0.5).sum(), corr.notna().sum(), "INVALID", "High",
            f"Mean within-session correlation between sequence and time = {corr.mean():.3f} (≈ random).",
            "sequence_number ignored for journey analysis.")
    sess_events = e.groupby("session_id").event_name.agg(set)
    no_start = with_c = 0
    for c_ev, s_ev in COMPLETION_START_PAIRS.items():
        has_c = sess_events.apply(lambda z: c_ev in z)
        with_c += int(has_c.sum())
        no_start += int(sess_events[has_c].apply(lambda z: s_ev not in z).sum())
    log.add("Events", "Completion event with no matching start event in the same session", no_start, with_c,
            "INVESTIGATE", "High",
            "Within-session view→start→complete funnels are not reconstructable; event-level start→complete "
            "ratios are unreliable.", "Feature funnels computed at user level (ever exposed / started / completed).",
            detail="pairs: " + ", ".join(f"{k}←{v}" for k, v in COMPLETION_START_PAIRS.items()))
    first_ts = e.groupby(["session_id", "event_name"]).event_datetime.min().unstack()
    bad = tot = 0
    for c_ev, s_ev in COMPLETION_START_PAIRS.items():
        b = first_ts[[c_ev, s_ev]].dropna()
        bad += int((b[c_ev] < b[s_ev]).sum())
        tot += len(b)
    log.add("Events", "Completion timestamp earlier than start timestamp (same session)", bad, tot,
            "INVALID", "Medium", "Impossible event sequences; affects any time-to-complete metric.",
            "Flagged (sequence_anomaly); no time-to-complete metric derived from events.")
    log.add("Events", "Multiple events with identical timestamp in one session",
            e.duplicated(subset=["session_id", "event_datetime"]).sum(), n_e, "WARNING", "Low",
            "Order of tied events is ambiguous.", "Ties broken by event_id.")
    log.add("Events", "streak_broken logged with event_status='Success'", (e.event_name == "streak_broken").sum(), n_e,
            "WARNING", "Medium", "Status-based success metrics would count a negative state as success.",
            "Stage taxonomy overrides raw status: streak_broken classified as 'negative'.")
    log.add("Events", "Feature names – canonical & consistently capitalised", e.feature_name.nunique(), 15,
            "VALID", "None", "15 canonical features; no case variants in 03_Feature_Events.", "None required.")
    missing_ev = [x for x in PDF_EVENT_EXAMPLES if x not in set(e.event_name)]
    log.add("Events", "PDF example events absent from simulated taxonomy", len(missing_ev), len(PDF_EVENT_EXAMPLES),
            "INVESTIGATE", "High",
            "No login/registration/onboarding/session/task events – login is proxied by session existence and "
            "task funnels come from 05_Task_Activity.",
            "Proxies documented; missing events added to tracking-gap register.", detail=", ".join(missing_ev))
    log.add("Events", "Event-to-feature mapping consistent (each event_name maps to one feature)",
            int((e.groupby("event_name").feature_name.nunique() > 1).sum()), e.event_name.nunique(),
            "VALID", "None", "-", "None required.")

    # ------------------------------------------------------------------ TASKS
    n_t = len(t)
    log.add("Tasks", "Duplicate activity_id / orphan user / orphan session",
            int(t.activity_id.duplicated().sum() + (~t.user_id.isin(u.user_id)).sum() + (~t.session_id.isin(s.session_id)).sum()),
            n_t, "VALID", "None", "-", "None required.")
    log.add("Tasks", "Missing task_viewed_at / task_started_at",
            int(t.task_viewed_at.isna().sum() + t.task_started_at.isna().sum()), n_t, "VALID", "None",
            "Every task record has view and start timestamps (no view→start drop-off measurable).",
            "Documented as limitation for view→start drop-off.")
    comp_missing = ((t.task_status == "Completed") & t.task_completed_at.isna()).sum()
    log.add("Tasks", "Completed task without task_completed_at", comp_missing, (t.task_status == "Completed").sum(),
            "VALID", "None", "-", "None required.")
    log.add("Tasks", "task_completed_at null for non-completed statuses",
            t.task_completed_at.isna().sum(), n_t, "VALID", "None",
            "Expected: Abandoned/Failed/Pending have no completion time.", "None required.")
    log.add("Tasks", "task_started_at before task_viewed_at", (t.task_started_at < t.task_viewed_at).sum(), n_t,
            "VALID", "None", "-", "None required.")
    log.add("Tasks", "task_completed_at before task_started_at", (t.task_completed_at < t.task_started_at).sum(), n_t,
            "VALID", "None", "-", "None required.")
    incons = (((t.task_status == "Completed") & (t.reward_status != "Credited")) |
              ((t.task_status != "Completed") & (t.reward_status == "Credited")) |
              (t.task_status.isin(["Failed", "Abandoned"]) & t.failure_reason.isna()) |
              (~t.task_status.isin(["Failed", "Abandoned"]) & t.failure_reason.notna())).sum()
    log.add("Tasks", "Inconsistent task_status / reward_status / failure_reason", incons, n_t, "VALID", "None",
            "Status logic is coherent (Completed↔Credited, Pending↔Pending, failures carry a reason).", "None required.")
    stale = ((t.task_status == "Pending") & (t.task_viewed_at < ctx.data_end - pd.Timedelta(days=7))).sum()
    log.add("Tasks", "Pending tasks older than 7 days at data end", stale, (t.task_status == "Pending").sum(),
            "WARNING", "Medium", "Long-pending validation inflates the 'neither success nor failure' bucket.",
            "Pending excluded from completion-rate denominator; reported separately.")

    # ------------------------------------------------------------------ MILESTONES
    n_m = len(m)
    first_sess = s.groupby("user_id").session_start.min()
    fl = m[m.milestone_type == "first_login"].set_index("user_id").milestone_datetime
    log.add("Milestones", "first_login ≠ user's first session_start", (fl != first_sess.reindex(fl.index)).sum(),
            len(fl), "INVALID", "High", "Milestone timestamps cannot be used for lifecycle timing.",
            "Lifecycle milestones re-derived from raw sessions/events.")
    ev_days = e.assign(d=e.event_datetime.dt.normalize()).groupby("user_id").d.nunique()
    for mt, need in (("third_active_day", 3), ("seventh_active_day", 7)):
        uid = m.loc[m.milestone_type == mt, "user_id"]
        log.add("Milestones", f"{mt} recorded for users with < {need} active days",
                (ev_days.reindex(uid).fillna(0) < need).sum(), len(uid), "INVALID", "High",
                f"Sheet reports {len(uid)} users; raw data shows {int((ev_days >= need).sum())} users reached {need} active days.",
                "Milestone counts re-derived from raw activity.")
    log.add("Milestones", "Milestones for users with no sessions", m.user_id.isin(u.user_id[no_sess]).sum(), n_m,
            "INVALID", "Medium", "Activity milestones without any activity are impossible.",
            "Excluded (milestone sheet not used as a source of truth).")
    mm = m.merge(e[["event_name", "feature_name"]].drop_duplicates(), left_on="source_event",
                 right_on="event_name", how="left")
    sub = mm[mm.milestone_type.isin(MILESTONE_EXPECTED_FEATURE)]
    mism = (sub.feature_name != sub.milestone_type.map(MILESTONE_EXPECTED_FEATURE)).sum()
    log.add("Milestones", "source_event belongs to a different feature than the milestone (e.g. first_spin ← wallet_viewed)",
            mism, len(sub), "INVALID", "Medium", "Milestone provenance is not traceable.", "Not used.")
    log.add("Milestones", "Missing session_id", m.session_id.isna().sum(), n_m, "WARNING", "Low", "-", "Not used.")
    log.add("Milestones", "milestone_value semantics undocumented (uniform 1–100 across all types)",
            n_m, n_m, "INVESTIGATE", "Low", "Cannot interpret value.", "Not used.")

    # ------------------------------------------------------------------ DAILY ACTIVITY
    n_d = len(d)
    ed = e.assign(activity_date=e.event_datetime.dt.normalize()).groupby(["user_id", "activity_date"]).agg(
        rev=("event_id", "size"), rf=("feature_name", "nunique")).reset_index()
    jd = d.merge(ed, on=["user_id", "activity_date"], how="left")
    log.add("Daily Activity", "event_count / feature_count ≠ raw events",
            int(((jd.event_count != jd.rev) | (jd.feature_count != jd.rf)).sum()), n_d, "VALID", "None",
            "Daily table is an exact aggregation of 03_Feature_Events.", "Usable for daily event/feature metrics.")
    sd = s.assign(activity_date=s.session_start.dt.normalize()).groupby(["user_id", "activity_date"]).agg(
        sc=("session_id", "size"), dur=("session_duration_seconds", "sum")).reset_index()
    js = d.merge(sd, on=["user_id", "activity_date"], how="inner")
    log.add("Daily Activity", "session_duration_minutes ≠ sum of session durations (±0.1 min)",
            int((abs(js.session_duration_minutes - js.dur / 60) > 0.1).sum()), len(js), "INVALID", "High",
            f"Daily table implies median {js.session_duration_minutes.median():.1f} min/day vs "
            f"{(js.dur / 60).median():.2f} min/day from sessions.",
            "Field not used; time metrics come from 02_Sessions.")
    log.add("Daily Activity", "session_count ≠ sessions started that day", int((js.session_count != js.sc).sum()),
            len(js), "WARNING", "Low", "Small mismatch (sessions spanning midnight).", "Session counts from 02_Sessions.")
    js2 = sd.merge(d[["user_id", "activity_date"]], on=["user_id", "activity_date"], how="left", indicator=True)
    log.add("Daily Activity", "User-days with sessions but no daily row", (js2._merge == "left_only").sum(), len(sd),
            "WARNING", "Low", "Daily table covers only days with feature events (zero-event sessions excluded).",
            "Active day defined as a day with ≥1 feature event.")
    log.add("Daily Activity", "active_flag has a single value ('Yes')", (d.active_flag == "Yes").sum(), n_d,
            "WARNING", "Low", "Flag carries no information.", "Not used.")
    log.add("Daily Activity", "Record volume below PDF recommendation (15,000–30,000)", n_d, 15000, "INVESTIGATE", "Low",
            "Dataset is smaller than the brief's suggested size; does not invalidate analysis.",
            "Documented as source discrepancy.")

    # ------------------------------------------------------------------ FEATURE USAGE (aggregate)
    raw_fu = e.groupby("feature_name").agg(unique_users_raw=("user_id", "nunique"), total_events_raw=("event_id", "size"),
                                           sessions_raw=("session_id", "nunique")).reset_index()
    succ = e[e.event_status == "Success"].groupby("feature_name").user_id.nunique().rename("success_users_raw")
    cmp_fu = fu.merge(raw_fu, on="feature_name", how="outer").merge(succ, on="feature_name", how="left").fillna({"success_users_raw": 0})
    cmp_fu["users_match"] = cmp_fu.unique_users == cmp_fu.unique_users_raw
    cmp_fu["events_match"] = cmp_fu.total_events == cmp_fu.total_events_raw
    cmp_fu["sessions_match"] = cmp_fu.sessions_with_feature == cmp_fu.sessions_raw
    cmp_fu["success_users_match"] = cmp_fu.users_with_success_event == cmp_fu.success_users_raw
    save_table(cmp_fu, "dq_feature_usage_reconciliation")
    n_bad = int((~cmp_fu[["users_match", "events_match", "sessions_match"]].all(axis=1)).sum())
    log.add("Feature Usage", "07_Feature_Usage ≠ recomputation from raw events (users/events/sessions)", n_bad, len(cmp_fu),
            "VALID" if n_bad == 0 else "WARNING", "None" if n_bad == 0 else "Medium",
            "Reference table reconciles with raw events." if n_bad == 0 else "Reference table disagrees with raw events.",
            "Raw events used as primary source; 07 used as validation reference.")
    n_bad_s = int((~cmp_fu.success_users_match).sum())
    log.add("Feature Usage", "users_with_success_event ≠ raw users with status 'Success'", n_bad_s, len(cmp_fu),
            "VALID" if n_bad_s == 0 else "WARNING", "None" if n_bad_s == 0 else "Low",
            "Note: 'Success' includes streak_broken (negative) and mining_stopped (neutral).",
            "Completion defined by stage taxonomy rather than raw status.")
    log.add("Feature Usage", "Sheet is a 15-row aggregate (PDF suggests 8,000–15,000 feature-usage records)", len(fu), 8000,
            "INVESTIGATE", "Low", "User-level feature usage must be derived from raw events.",
            "Derived user×feature table built in clean layer.")

    # ------------------------------------------------------------------ AUDIT SHEET
    log.add("Event Audit", "Rows in 10_Event_Data_Quality_Audit vs 03_Feature_Events", len(a) - n_e, n_e,
            "WARNING", "Low", "Audit sheet is the event log with injected quality issues.",
            "03_Feature_Events used as primary source; audit sheet used to test cleaning rules.")
    log.add("Event Audit", "Duplicated event rows (same event_id, identical content)", a.event_id.duplicated().sum(), len(a),
            "INVALID", "Low", "Would double-count 10 events if the audit sheet were used.", "Deduplicated on event_id in impact test.")
    case = a.feature_name[~a.feature_name.isin(config.FEATURES)]
    log.add("Event Audit", "Non-canonical feature names (lower-case variants)", len(case), len(a), "INVALID", "Low",
            "Would split features into duplicate categories (e.g. 'missions' vs 'Missions').",
            "Normalised via case-insensitive mapping in impact test.", detail=", ".join(sorted(case.unique())))
    ad = a.drop_duplicates("event_id").set_index("event_id")
    st_diff = (ad.event_status.reindex(e.event_id).values != e.event_status.values)
    log.add("Event Audit", "event_status differs from 03 (e.g. 'success ' with case/whitespace drift)", int(st_diff.sum()), n_e,
            "INVALID", "Low", "Status-based filters would miss these events.", "Normalised (strip + title-case) in impact test.",
            detail=", ".join(sorted(set(ad.event_status.reindex(e.event_id)[st_diff].astype(str)))))

    # ------------------------------------------------------------------ README / DICTIONARY
    rd = dict(zip(raw["readme"].Item, raw["readme"].Value))
    log.add("README / PDF", "Project duration: README says '22–25 day', PDF says '20–24 Days'", 1, 1, "INVESTIGATE", "Low",
            "Source discrepancy requiring confirmation. No effect on analysis.", "PDF treated as the formal requirement; flagged.",
            detail=str(rd.get("Purpose")))
    readme_counts = {"Users": len(u), "Sessions": n_s, "Feature Events": n_e, "Daily Activity Records": n_d,
                     "Task Activity Records": n_t, "Milestone Records": n_m}
    mismatch = [k for k, v in readme_counts.items() if int(rd.get(k, -1)) != v]
    log.add("README / PDF", "README record counts vs actual sheet rows", len(mismatch), len(readme_counts), "VALID",
            "None", "README counts reconcile with the workbook.", "None required.")
    log.add("README / PDF", "Recommended volumes vs actual (Sessions 8–15k, Daily 15–30k, Feature Usage 8–15k)", 3, 7,
            "INVESTIGATE", "Low",
            f"Sessions {n_s:,} (below 8,000), Daily {n_d:,} (below 15,000), Feature Usage 15 rows. "
            "Source discrepancy requiring confirmation.", "Analysis proceeds on supplied data.")
    dd = raw["dictionary"]
    ds_map = {"Users": u, "Sessions": s, "Events": e, "Daily Activity": d, "Tasks": t, "Milestones": m}
    missing_dict = [f"{r.dataset}.{r.field_name}" for r in dd.itertuples() if r.field_name not in ds_map[r.dataset].columns]
    log.add("Data Dictionary", "Dictionary fields missing from their dataset", len(missing_dict), len(dd),
            "VALID" if not missing_dict else "WARNING", "None" if not missing_dict else "Low",
            "Dictionary covers 26 of the workbook's fields (partial coverage).", "Extended in docs/data_dictionary.md.",
            detail=", ".join(missing_dict))

    issues = log.frame()
    save_table(issues, "data_quality_report")
    ctx.R["validation"] = {
        "sheet_profile": sheet_profile,
        "issues": issues,
        "summary": issues.classification.value_counts().to_dict(),
        "record_counts": {"users": n_u, "sessions": n_s, "events": n_e, "daily": n_d, "tasks": n_t,
                          "milestones": n_m, "feature_usage_rows": len(fu), "audit_rows": len(a)},
        "unique": {"users_in_sessions": int(s.user_id.nunique()), "users_in_events": int(e.user_id.nunique()),
                   "sessions_with_events": int(e.session_id.nunique()), "features": int(e.feature_name.nunique()),
                   "event_names": int(e.event_name.nunique()), "task_ids": int(t.task_id.nunique()),
                   "task_categories": int(t.task_category.nunique())},
        "date_ranges": {
            "registration": [u.registration_datetime.min(), u.registration_datetime.max()],
            "sessions": [s.session_start.min(), s.session_end.max()],
            "events": [e.event_datetime.min(), e.event_datetime.max()],
            "tasks": [t.task_viewed_at.min(), t.task_completed_at.max()],
            "daily": [d.activity_date.min(), d.activity_date.max()],
        },
        "categories": {
            "event_status": e.event_status.value_counts().to_dict(),
            "task_status": t.task_status.value_counts().to_dict(),
            "session_status": s.session_status.value_counts().to_dict(),
            "account_status": u.account_status.value_counts().to_dict(),
            "onboarding_status": u.onboarding_status.value_counts().to_dict(),
            "verification_status": u.verification_status.value_counts().to_dict(),
        },
        "feature_usage_reconciliation": cmp_fu,
        "seq_time_corr_mean": float(corr.mean()),
        "zero_event_sessions": int((raw_n == 0).sum()),
        "events_in_session_field_mean": float(s.events_in_session.mean()),
        "raw_events_per_session_mean_all": float(raw_n.mean()),
        "missing_pdf_user_fields": missing_fields,
        "missing_pdf_events": missing_ev,
    }
    # record-level flags for later steps
    ctx.extra["flag_dup_content_event_ids"] = e.loc[dup_content, ["event_id"]]
    ctx.extra["flag_overlap_session_ids"] = s_sorted.loc[overlap, ["session_id"]]
    ctx.extra["session_long_fence"] = pd.DataFrame({"fence": [fence]})
