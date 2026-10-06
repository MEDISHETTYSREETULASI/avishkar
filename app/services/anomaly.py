"""
Comprehensive Anomaly Engine & Flag Lifecycle Service:
1. Perceptual Image Hash Duplicate Detection (pHash Hamming distance)
2. GPS Proximity Check (200m radius threshold)
3. Subject Liveness Verification (Anti-spoofing)
4. Cryptographic HMAC-SHA256 Tamper Evident Signatures
5. Attendance Pattern Analysis (Flatlining & sudden statistical drops)
6. CCTV Headcount Reconciliation Discrepancy Detection
7. Human-in-the-loop Flag Review & Audit Logging
"""
import hmac
import hashlib
import math
import io
import json
from datetime import datetime, date, timedelta
from PIL import Image
import imagehash
from flask import current_app
from ..extensions import db
from ..models import Flag, Evidence, Institute, Inspection, AttendanceRecord, AuditLog, User
from ..config import GPS_TOLERANCE_METRES, HEADCOUNT_TOLERANCE_PCT, RISK_INCREASE_PER_FLAG
from .event_bus import emit_flag_event, emit_headcount_mismatch


def haversine_distance_metres(lat1, lon1, lat2, lon2):
    """Calculate geographic distance between two coordinates in metres."""
    if any(coord is None for coord in (lat1, lon1, lat2, lon2)):
        return 999999.0
    R = 6371000.0  # Earth radius in metres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def compute_perceptual_hash(image_bytes: bytes) -> str:
    """Compute 64-bit perceptual hash (pHash) for image duplicate detection."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        phash = imagehash.phash(img)
        return str(phash)
    except Exception as e:
        return hashlib.md5(image_bytes).hexdigest()[:16]


def compute_evidence_hmac(sha256_hash: str, otp_code: str, timestamp_iso: str) -> str:
    """
    Generate tamper-proof HMAC-SHA256 signature.
    Signature = HMAC(SECRET_KEY, sha256_hash + ":" + otp_code + ":" + timestamp_iso)
    """
    secret = current_app.config.get("SECRET_KEY", "sih26095-default-secret").encode("utf-8")
    message = f"{sha256_hash}:{otp_code}:{timestamp_iso}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def check_evidence_anomalies(inspection: Inspection, evidence_bytes: bytes, client_lat: float, client_lng: float, otp_code: str, liveness_passed: bool):
    """Run full suite of anomaly checks on newly captured inspection evidence."""
    institute = inspection.institute
    captured_at = datetime.utcnow()
    captured_iso = captured_at.isoformat()

    # 1. SHA-256
    sha256_hash = hashlib.sha256(evidence_bytes).hexdigest()

    # 2. Perceptual Hash
    phash_str = compute_perceptual_hash(evidence_bytes)

    # 3. HMAC Signature
    hmac_sig = compute_evidence_hmac(sha256_hash, otp_code, captured_iso)

    # 4. GPS Distance check
    gps_dist_m = haversine_distance_metres(client_lat, client_lng, institute.lat, institute.lng)
    
    flags_raised = []
    is_suspicious = False

    # Check A: GPS Out of Tolerance (> 200 metres)
    if gps_dist_m > GPS_TOLERANCE_METRES:
        is_suspicious = True
        flag = Flag(
            institute_id=institute.id,
            inspection_id=inspection.id,
            flag_type="gps_mismatch",
            severity="high",
            description=f"GPS Mismatch: Evidence captured {round(gps_dist_m, 1)}m away from registered coordinates (tolerance: {GPS_TOLERANCE_METRES}m).",
            status="open",
        )
        db.session.add(flag)
        flags_raised.append(flag)
        institute.risk_score = min(100.0, institute.risk_score + RISK_INCREASE_PER_FLAG.get("high", 15.0))

    # Check B: Duplicate / Reused Photo Detection
    try:
        current_phash_obj = imagehash.hex_to_hash(phash_str)
        existing_evidence = Evidence.query.filter(Evidence.inspection_id != inspection.id).all()
        for prev_ev in existing_evidence:
            if prev_ev.perceptual_hash:
                try:
                    prev_phash_obj = imagehash.hex_to_hash(prev_ev.perceptual_hash)
                    hamming_dist = current_phash_obj - prev_phash_obj
                    if hamming_dist <= 6:
                        is_suspicious = True
                        flag = Flag(
                            institute_id=institute.id,
                            inspection_id=inspection.id,
                            flag_type="duplicate_photo",
                            severity="high",
                            description=f"Duplicate Photo Detected: Perceptual hash matches previous evidence #{prev_ev.id} (distance: {hamming_dist} bits). Possible photo reuse.",
                            status="open",
                        )
                        db.session.add(flag)
                        flags_raised.append(flag)
                        institute.risk_score = min(100.0, institute.risk_score + RISK_INCREASE_PER_FLAG.get("high", 15.0))
                        break
                except Exception:
                    continue
    except Exception as e:
        print("[Anomaly] Perceptual hash check exception:", e)

    # Check C: Liveness Failure
    if not liveness_passed:
        is_suspicious = True
        flag = Flag(
            institute_id=institute.id,
            inspection_id=inspection.id,
            flag_type="liveness_failed",
            severity="medium",
            description="Liveness verification failed during evidence capture (no blink/movement detected).",
            status="open",
        )
        db.session.add(flag)
        flags_raised.append(flag)
        institute.risk_score = min(100.0, institute.risk_score + RISK_INCREASE_PER_FLAG.get("medium", 8.0))

    db.session.commit()

    for f in flags_raised:
        emit_flag_event(f)

    return {
        "sha256": sha256_hash,
        "phash": phash_str,
        "gps_distance_m": round(gps_dist_m, 1),
        "hmac_signature": hmac_sig,
        "flags_raised": flags_raised,
        "is_suspicious": is_suspicious,
        "captured_at": captured_at,
    }


def scan_attendance_anomalies(institute_id: int):
    """
    Analyze attendance history for statistical patterns:
    - Identical counts over 7 consecutive days (statistical flatlining)
    - Significant discrepancy against CCTV headcount
    """
    institute = Institute.query.get(institute_id)
    if not institute:
        return []

    records = (
        AttendanceRecord.query.filter_by(institute_id=institute.id)
        .order_by(AttendanceRecord.date.desc())
        .limit(14)
        .all()
    )

    new_flags = []

    # 1. Check for flatlining (identical count for 7+ consecutive records)
    if len(records) >= 7:
        first_7_counts = [r.reported_count for r in records[:7]]
        if len(set(first_7_counts)) == 1:
            # Check if open flag already exists
            existing = Flag.query.filter_by(
                institute_id=institute.id,
                flag_type="unusual_attendance",
                status="open"
            ).first()
            if not existing:
                flag = Flag(
                    institute_id=institute.id,
                    flag_type="unusual_attendance",
                    severity="medium",
                    description=f"Statistical Flatlining: Attendance has remained exactly at {first_7_counts[0]} for 7 consecutive days.",
                    status="open",
                )
                db.session.add(flag)
                institute.risk_score = min(100.0, institute.risk_score + 10.0)
                new_flags.append(flag)

    # 2. Check latest headcount reconciliation
    if records:
        latest = records[0]
        if latest.reported_count and latest.cctv_count:
            diff = abs(latest.reported_count - latest.cctv_count)
            diff_pct = (diff / max(1, latest.reported_count)) * 100.0
            if diff_pct > (HEADCOUNT_TOLERANCE_PCT * 100):
                latest.mismatch_flag = True
                existing_cctv_flag = Flag.query.filter_by(
                    institute_id=institute.id,
                    flag_type="cctv_headcount_mismatch",
                    status="open"
                ).first()
                if not existing_cctv_flag:
                    flag = Flag(
                        institute_id=institute.id,
                        flag_type="cctv_headcount_mismatch",
                        severity="high",
                        description=f"Headcount Mismatch: Reported {latest.reported_count} occupants vs CCTV count of {latest.cctv_count} ({round(diff_pct, 1)}% difference).",
                        status="open",
                    )
                    db.session.add(flag)
                    institute.risk_score = min(100.0, institute.risk_score + 15.0)
                    new_flags.append(flag)
                    emit_headcount_mismatch(institute, latest.reported_count, latest.cctv_count, diff_pct)

    db.session.commit()
    for f in new_flags:
        emit_flag_event(f)

    return new_flags


def resolve_flag_with_audit(flag_id: int, officer_id: int, new_status: str, officer_comment: str):
    """
    Review and resolve a flag lead (Human-in-the-Loop decision).
    Actions:
    - 'genuine': Confirmed irregularity -> Maintain/increase risk score.
    - 'needs_action': Dispatches priority inspection -> Increases risk score.
    - 'dismissed': Cleared explanation -> Lowers institute risk score.
    """
    flag = Flag.query.get_or_404(flag_id)
    institute = flag.institute

    old_status = flag.status
    flag.status = new_status
    flag.officer_comment = officer_comment
    flag.resolved_at = datetime.utcnow()
    flag.resolved_by_id = officer_id

    # Adjust institute risk score
    if new_status == "dismissed":
        # Relieve risk penalty
        penalty_relief = 12.0 if flag.severity == "high" else 6.0
        institute.risk_score = max(10.0, institute.risk_score - penalty_relief)
    elif new_status == "needs_action":
        institute.risk_score = min(100.0, institute.risk_score + 10.0)

    # Log to immutable AuditLog
    audit = AuditLog(
        actor_id=officer_id,
        action="flag_reviewed",
        entity_type="Flag",
        entity_id=flag.id,
        detail_json=json.dumps({
            "flag_id": flag.id,
            "flag_type": flag.flag_type,
            "institute_id": institute.id,
            "institute_name": institute.name,
            "old_status": old_status,
            "new_status": new_status,
            "officer_comment": officer_comment,
            "new_risk_score": institute.risk_score,
        }),
    )
    db.session.add(audit)
    db.session.commit()

    return flag
