"""
Inspection Report Generation Service.

Prepares comprehensive inspection audit data for government-grade
printable / PDF inspection reports.
"""
from ..models import Inspection, Evidence, Flag, Institute, User


def get_inspection_report_data(inspection_id: int):
    """
    Fetch and structure all data required for an official field inspection report:
    - Institute profile & grant details
    - Inspector verification details
    - Cryptographic evidence hashes (SHA-256, HMAC, pHash, OTP)
    - Geo-spatial GPS proximity
    - Trust score calculation breakdown
    - Anomaly leads & human review determinations
    """
    inspection = Inspection.query.get_or_404(inspection_id)
    institute = inspection.institute
    evidence_list = inspection.evidence.order_by(Evidence.captured_at.asc()).all()
    flags_list = inspection.flags.order_by(Flag.created_at.asc()).all()

    # Calculate signal deductions
    score_breakdown = []
    if inspection.trust_score is not None:
        base_score = 100.0
        for f in flags_list:
            deduction = 15 if f.severity == "high" else (8 if f.severity == "medium" else 3)
            score_breakdown.append({
                "signal": f.flag_type_label,
                "severity": f.severity,
                "deduction": deduction,
                "description": f.description
            })

    return {
        "inspection": inspection,
        "institute": institute,
        "evidence_list": evidence_list,
        "flags_list": flags_list,
        "score_breakdown": score_breakdown,
        "total_evidence_count": len(evidence_list),
        "total_flags_count": len(flags_list),
    }
