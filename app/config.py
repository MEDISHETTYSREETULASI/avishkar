"""
Editable configuration for the anomaly / trust-score engine.

ALL numeric thresholds here are ILLUSTRATIVE values chosen for the
hackathon prototype.  Change them to reflect real policy.
"""

# --- Trust score signal weights (deducted from 100) ---
# Each weight is the maximum penalty for that signal.
TRUST_SCORE_WEIGHTS: dict[str, int] = {
    "gps_mismatch": -20,           # Inspector was > GPS_TOLERANCE_METRES away
    "duplicate_photo": -25,        # Perceptual hash matches a previous photo
    "cctv_headcount_mismatch": -15,# Reported count vs CCTV count outside tolerance
    "missed_vc": -10,              # Staff did not answer random VC within deadline
    "liveness_failed": -15,        # MediaPipe blink check not passed
    "unusual_attendance": -10,     # Statistical outlier in attendance pattern
    "identical_checkin_time": -5,  # Same HH:MM:SS across multiple days
}

# --- GPS ---
GPS_TOLERANCE_METRES: int = 200   # Flag if inspector > 200 m from institute

# --- Headcount ---
HEADCOUNT_TOLERANCE_PCT: float = 0.10  # Flag if mismatch > 10 %

# --- Video-call ---
VC_DEADLINE_SECONDS: int = 60     # Staff must accept within 60 s

# --- Assignment conflict rules ---
ASSIGNMENT_CONFLICT_KM: float = 50.0   # Inspector must be at least this far from institute
MAX_INSPECTIONS_PER_INSPECTOR_WEEK: int = 5

# --- Risk score decay (days without new flags lower risk slowly) ---
RISK_DECAY_PER_DAY: float = 0.5
RISK_INCREASE_PER_FLAG: dict[str, float] = {
    "high": 15.0,
    "medium": 8.0,
    "low": 3.0,
}
