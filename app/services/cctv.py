"""
CCTV Camera Gateway & Headcount Reconciliation Service.

Handles:
- Camera gateway feed streaming (MJPEG simulation with AI bounding box overlays)
- Headcount detection estimation
- Daily attendance vs CCTV headcount reconciliation algorithm
- Automated flag generation when discrepancy exceeds tolerance (10%)
"""
import io
import time
import math
import random
import json
from datetime import datetime, date
from PIL import Image, ImageDraw, ImageFont
from ..extensions import db
from ..models import Institute, AttendanceRecord, Flag, AuditLog
from ..config import HEADCOUNT_TOLERANCE_PCT, RISK_INCREASE_PER_FLAG
from .event_bus import emit_flag_event, emit_headcount_mismatch


def get_simulated_cctv_count(institute: Institute) -> int:
    """
    Compute real-time detected occupant count for an institute.
    Uses capacity, historical baseline, and scripted anomaly overrides.
    """
    # Check if latest attendance record exists
    today_att = (
        AttendanceRecord.query.filter_by(institute_id=institute.id)
        .order_by(AttendanceRecord.date.desc())
        .first()
    )

    if today_att and today_att.cctv_count is not None:
        return today_att.cctv_count

    # Scripted scenario for Institute #1 (Naya Savera) - significant discrepancy
    if institute.id == 1:
        return 29  # vs 48 reported

    # Otherwise simulate realistic occupancy (~85-95% of reported capacity)
    base_cap = institute.reported_capacity or 50
    return max(5, int(base_cap * 0.88))


def reconcile_institute_headcount(institute_id: int, officer_id: int = None):
    """
    Reconcile reported staff attendance against CCTV detected headcount.
    Tolerance: 10% (HEADCOUNT_TOLERANCE_PCT).
    If discrepancy > 10%, raises a high-severity cctv_headcount_mismatch flag.
    """
    institute = Institute.query.get_or_404(institute_id)
    cctv_count = get_simulated_cctv_count(institute)

    # Get latest attendance record
    att = (
        AttendanceRecord.query.filter_by(institute_id=institute.id)
        .order_by(AttendanceRecord.date.desc())
        .first()
    )

    reported_count = att.reported_count if att else int(institute.reported_capacity * 0.85)

    diff = abs(reported_count - cctv_count)
    diff_pct = (diff / max(1, reported_count)) * 100.0
    is_mismatch = diff_pct > (HEADCOUNT_TOLERANCE_PCT * 100.0)

    if att:
        att.cctv_count = cctv_count
        att.mismatch_flag = is_mismatch

    flag_raised = None

    if is_mismatch:
        # Check if active flag already exists for this mismatch
        existing_flag = Flag.query.filter_by(
            institute_id=institute.id,
            flag_type="cctv_headcount_mismatch",
            status="open"
        ).first()

        if not existing_flag:
            flag_raised = Flag(
                institute_id=institute.id,
                flag_type="cctv_headcount_mismatch",
                severity="high",
                description=(
                    f"CCTV Headcount Mismatch: Staff reported {reported_count} occupants, but CCTV scan "
                    f"detected {cctv_count}. Discrepancy: {round(diff_pct, 1)}% (tolerance: 10%)."
                ),
                status="open",
            )
            db.session.add(flag_raised)
            institute.risk_score = min(100.0, institute.risk_score + RISK_INCREASE_PER_FLAG.get("high", 15.0))
            db.session.flush()

            # Emit SSE Event
            emit_headcount_mismatch(institute, reported_count, cctv_count, diff_pct)
            emit_flag_event(flag_raised)

    # Audit log
    audit_detail = {
        "event": "headcount_reconciliation_scan",
        "institute_id": institute.id,
        "institute_name": institute.name,
        "reported_count": reported_count,
        "cctv_count": cctv_count,
        "diff_pct": round(diff_pct, 1),
        "mismatch_detected": is_mismatch,
        "flag_id": flag_raised.id if flag_raised else None,
    }
    log = AuditLog(
        actor_id=officer_id,
        action="cctv_headcount_reconciled",
        entity_type="Institute",
        entity_id=institute.id,
        detail_json=json.dumps(audit_detail),
    )
    db.session.add(log)
    db.session.commit()

    return {
        "institute_id": institute.id,
        "institute_name": institute.name,
        "reported_count": reported_count,
        "cctv_count": cctv_count,
        "diff_pct": round(diff_pct, 1),
        "is_mismatch": is_mismatch,
        "flag_raised": flag_raised is not None,
    }


def generate_cctv_frame(institute_name: str, detected_count: int, frame_idx: int) -> bytes:
    """
    Generate a realistic CCTV surveillance frame with HUD overlays,
    timestamp, and AI bounding boxes.
    """
    width, height = 480, 270
    # CCTV dark bluish-gray surface
    img = Image.new("RGB", (width, height), color=(18, 26, 38))
    draw = ImageDraw.Draw(img)

    # Grid / perspective lines simulating surveillance room
    draw.line([(0, 210), (width, 210)], fill=(30, 42, 60), width=1)
    draw.line([(60, 270), (140, 210)], fill=(28, 38, 55), width=1)
    draw.line([(width - 60, 270), (width - 140, 210)], fill=(28, 38, 55), width=1)

    # Draw simulated detected occupants with bounding boxes
    num_boxes = min(6, max(2, int(detected_count / 8)))
    rng = random.Random(frame_idx + hash(institute_name) % 1000)

    for i in range(num_boxes):
        bx = int(50 + (i * 65) + rng.uniform(-4, 4))
        by = int(120 + rng.uniform(-10, 10))
        bw = 36
        bh = 75

        # Bounding box (Teal/Green AI detection box)
        draw.rectangle([bx, by, bx + bw, by + bh], outline=(13, 148, 136), width=2)
        # Person tag
        draw.rectangle([bx, by - 14, bx + 36, by], fill=(13, 148, 136))
        draw.text((bx + 2, by - 13), "0.92", fill=(255, 255, 255))

    # Top HUD Bar
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # 1. SIMULATED watermark badge
    draw.rectangle([10, 10, 85, 26], fill=(245, 158, 11))
    draw.text((15, 12), "SIMULATED", fill=(0, 0, 0))

    # 2. REC Dot
    draw.ellipse([95, 14, 103, 22], fill=(220, 38, 38))
    draw.text((108, 12), "REC", fill=(220, 38, 38))

    # 3. Timestamp
    draw.text((width - 170, 12), now_str, fill=(200, 210, 225))

    # Bottom HUD Bar
    draw.rectangle([0, height - 32, width, height], fill=(10, 15, 25))
    draw.text((10, height - 24), f"CAM-01 · {institute_name[:24]}", fill=(255, 255, 255))
    draw.text((width - 140, height - 24), f"AI DETECTED: {detected_count}", fill=(13, 148, 136))

    # Output JPEG bytes
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=75)
    return buffer.getvalue()


def cctv_mjpeg_generator(institute: Institute):
    """
    Generator yielding multipart/x-mixed-replace MJPEG frames
    for real-time CCTV stream in HTML5 <img> tags.
    """
    count = get_simulated_cctv_count(institute)
    frame_idx = 0

    while True:
        frame_bytes = generate_cctv_frame(institute.name, count, frame_idx)
        frame_idx = (frame_idx + 1) % 100

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )
        time.sleep(1.0)  # 1 frame per second for efficient dashboard playback
