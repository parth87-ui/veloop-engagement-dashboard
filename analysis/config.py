"""Central configuration: paths, analysis constants and the analyst-defined event taxonomy.

Every behavioural definition used downstream (meaningful activity, feature stages,
time-of-day buckets, etc.) lives here so that it is documented in exactly one place.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RAW_WORKBOOK = ROOT / "data" / "raw" / "VELOOP_Simulated_User_Behavior_1000.xlsx"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_ANALYTICAL = ROOT / "data" / "analytical"
DATA_ANONYMISED = ROOT / "data" / "anonymised"   # shareable copy of every sheet, personal fields removed
OUT_TABLES = ROOT / "outputs" / "tables"
OUT_CHARTS = ROOT / "outputs" / "charts"
OUT_REPORTS = ROOT / "outputs" / "reports"
OUT_DASH = ROOT / "outputs" / "dashboard_data"
DASHBOARD_PUBLIC_DATA = ROOT / "dashboard" / "public" / "data"

SHEETS = {
    "users": "01_Users_1000",
    "sessions": "02_Sessions",
    "events": "03_Feature_Events",
    "daily": "04_Daily_Activity",
    "tasks": "05_Task_Activity",
    "milestones": "06_Milestones",
    "feature_usage": "07_Feature_Usage",
    "dictionary": "08_Data_Dictionary",
    "readme": "09_README_Status",
    "audit": "10_Event_Data_Quality_Audit",
}

# Personal fields present in the Users sheet. They are never written to processed,
# analytical or dashboard outputs (Phase 3 privacy rule).
PII_COLUMNS = ["full_name", "email", "age", "gender", "city", "state", "referral_code"]

RANDOM_SEED = 42

# --------------------------------------------------------------------------------------
# Event taxonomy (derived from the 35 event names observed in 03_Feature_Events)
# --------------------------------------------------------------------------------------
# stage meanings
#   exposure    – user saw / opened a feature surface (no commitment)
#   start       – user explicitly began an activity
#   complete    – user finished a user-initiated value action  (=> "meaningful activity")
#   abandon     – user explicitly skipped / abandoned an activity
#   fail        – activity attempt failed
#   progression – system-awarded progression outcome (badge earned, level up)
#   neutral     – state change that is neither success nor failure (mining_stopped)
#   negative    – negative state (streak_broken; logged with status "Success" in the raw data)
EVENT_STAGE = {
    "ad_started": "start", "ad_completed": "complete", "ad_skipped": "abandon",
    "badge_viewed": "exposure", "badge_earned": "progression",
    "captcha_started": "start", "captcha_completed": "complete", "captcha_failed": "fail",
    "daily_reward_viewed": "exposure", "daily_reward_claimed": "complete",
    "exchange_viewed": "exposure",
    "follow_task_viewed": "exposure", "follow_task_completed": "complete",
    "leaderboard_viewed": "exposure",
    "level_viewed": "exposure", "level_up": "progression",
    "mining_started": "start", "mining_activity": "complete", "mining_stopped": "neutral",
    "mission_viewed": "exposure", "mission_started": "start",
    "mission_completed": "complete", "mission_abandoned": "abandon",
    "referral_page_viewed": "exposure", "referral_created": "complete", "referral_shared": "complete",
    "spin_opened": "exposure", "spin_started": "start", "spin_completed": "complete",
    "streak_viewed": "exposure", "streak_claimed": "complete", "streak_broken": "negative",
    "tap_started": "start", "tap_completed": "complete",
    "wallet_viewed": "exposure",
}

MEANINGFUL_EVENTS = sorted(k for k, v in EVENT_STAGE.items() if v == "complete")
START_EVENTS = sorted(k for k, v in EVENT_STAGE.items() if v == "start")
EXPOSURE_EVENTS = sorted(k for k, v in EVENT_STAGE.items() if v == "exposure")
NEGATIVE_OUTCOME_EVENTS = sorted(k for k, v in EVENT_STAGE.items() if v in ("abandon", "fail"))
PROGRESSION_EVENTS = ["badge_earned", "level_up"]

# Features whose only events are views – "usage" == "exposure" for these surfaces.
VIEW_ONLY_FEATURES = ["Exchange Center", "Leaderboard", "Wallet"]

# Features with an explicit negative outcome event => event-level completion/abandonment
# rates are measurable: complete / (complete + negative outcome).
OUTCOME_PAIRS = {
    "Watch Ads": ("ad_completed", "ad_skipped", "abandonment (skip)"),
    "CAPTCHA": ("captcha_completed", "captcha_failed", "failure"),
    "Missions": ("mission_completed", "mission_abandoned", "abandonment"),
}

# Analyst grouping of the 15 simulated features into product areas (not an official taxonomy).
FEATURE_AREA = {
    "Watch Ads": "Earning Activities", "CAPTCHA": "Earning Activities",
    "Tap & Earn": "Earning Activities", "Follow & Earn": "Earning Activities",
    "Mining Rewards": "Earning Activities",
    "Daily Reward": "Habit Rewards", "Streak Rewards": "Habit Rewards",
    "Spin the Wheel": "Gamification & Progression", "Missions": "Gamification & Progression",
    "Badges": "Gamification & Progression", "Level System": "Gamification & Progression",
    "Leaderboard": "Gamification & Progression",
    "Referral": "Social / Referral",
    "Wallet": "Wallet & Exchange", "Exchange Center": "Wallet & Exchange",
}
FEATURES = sorted(FEATURE_AREA)

# Time-of-day buckets (timezone of the simulated timestamps is undocumented).
DAYPART_BINS = [(5, 12, "Morning (05-11)"), (12, 17, "Afternoon (12-16)"),
                (17, 21, "Evening (17-20)"), (21, 29, "Night (21-04)")]

ACTIVATION_WINDOWS = [1, 3, 7, 14, 30]
# primary activation window is selected in s04_activation from the capture curve (not hard-coded)
RETURN_WINDOWS = {                     # (first day offset, last day offset) after cohort day 0
    "D1": (1, 1),                      # next calendar day
    "D7": (1, 7),                      # first week
    "D14": (8, 14),                    # second week
    "D30": (24, 30),                   # fourth week (7-day window ending on day 30, comparable width to D7/D14)
}

COLORS = {
    "primary": "#2563eb", "secondary": "#0d9488", "accent": "#d97706",
    "muted": "#94a3b8", "negative": "#dc2626", "ink": "#0f172a",
    "series": ["#2563eb", "#0d9488", "#d97706", "#7c3aed", "#db2777", "#65a30d", "#0891b2", "#64748b"],
}
