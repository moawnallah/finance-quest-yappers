"""Numbers for the admin panel and the user profile (docs/admin_and_profile.md).

Pure functions over rows (lists of dicts with the same field names as the database tables),
so every metric is tested with hand-made rows and the API only fetches rows and calls these.
"""
from .metrics import (calibration_series, first_attempts, hard_overview, item_stats, profile_summary,
                      report_alerts, study_report, tutor_overview)
from .study import CONSENT_TEXT, CONSENT_VERSION, participant_id

__all__ = ["CONSENT_TEXT", "CONSENT_VERSION", "calibration_series", "first_attempts", "hard_overview", "item_stats",
           "participant_id", "profile_summary", "report_alerts", "study_report", "tutor_overview"]
