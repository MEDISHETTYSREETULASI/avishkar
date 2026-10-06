"""
Trust score calculation engine combining weighted anomaly signals.
Score ranges from 0 to 100.
"""
from ..config import TRUST_SCORE_WEIGHTS


def compute_inspection_trust_score(flags_list, liveness_passed: bool = True, gps_dist_m: float = 0.0):
    """
    Compute overall inspection trust score starting from 100.0,
    deducting penalty weights based on detected anomaly signals.
    """
    score = 100.0
    deductions = []

    # 1. Deduct based on raised flags
    applied_flag_types = set()
    for flag in flags_list:
        ftype = flag.flag_type if hasattr(flag, "flag_type") else flag.get("flag_type")
        if ftype in TRUST_SCORE_WEIGHTS and ftype not in applied_flag_types:
            penalty = abs(TRUST_SCORE_WEIGHTS[ftype])
            score -= penalty
            applied_flag_types.add(ftype)
            deductions.append({"signal": ftype, "penalty": penalty})

    # 2. Check liveness penalty if not already covered
    if not liveness_passed and "liveness_failed" not in applied_flag_types:
        penalty = abs(TRUST_SCORE_WEIGHTS.get("liveness_failed", 15))
        score -= penalty
        deductions.append({"signal": "liveness_failed", "penalty": penalty})

    # Clamp between 0.0 and 100.0
    final_score = max(0.0, min(100.0, round(score, 1)))
    return final_score, deductions
