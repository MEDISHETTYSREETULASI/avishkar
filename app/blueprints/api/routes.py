import json
import uuid
import os
import base64
from datetime import datetime, date, timedelta
from flask import Response, stream_with_context, jsonify, request, current_app
from flask_login import login_required, current_user
from . import api_bp
from ...extensions import db, sse_subscribe, sse_unsubscribe, sse_broadcast
from ...models import Institute, Flag, Inspection, VCRequest, AttendanceRecord, AuditLog, OTPToken, Evidence, User
from ...services.event_bus import emit_flag_event, emit_vc_event, emit_headcount_mismatch, emit_inspection_event
from ...services.assignment import auto_assign_inspection
from ...services.anomaly import check_evidence_anomalies
from ...services.trust_score import compute_inspection_trust_score


@api_bp.route("/stream")
@login_required
def sse_stream():
    """Server-Sent Events endpoint."""
    client_id = str(uuid.uuid4())
    q = sse_subscribe(client_id)

    def generate():
        yield "event: heartbeat\ndata: {}\n\n"
        try:
            while True:
                try:
                    msg = q.get(timeout=25)
                    yield f"event: {msg['event']}\ndata: {msg['data']}\n\n"
                except Exception:
                    yield ": keepalive\n\n"
        finally:
            sse_unsubscribe(client_id)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@api_bp.route("/institutes")
@login_required
def institutes_json():
    """Return all institutes as JSON for Leaflet map and overview filtering."""
    data = []
    for inst in Institute.query.all():
        latest_att = (
            AttendanceRecord.query.filter_by(institute_id=inst.id)
            .order_by(AttendanceRecord.date.desc())
            .first()
        )
        data.append({
            "id": inst.id,
            "name": inst.name,
            "type": inst.type,
            "type_label": inst.type_label,
            "district": inst.district,
            "state": inst.state,
            "lat": inst.lat,
            "lng": inst.lng,
            "risk_score": inst.risk_score,
            "rag": inst.rag_status,
            "rag_label": inst.rag_label,
            "reported_capacity": inst.reported_capacity,
            "open_flags": inst.open_flags_count(),
            "grant_amount_lakhs": inst.grant_amount_lakhs,
            "contact_name": inst.contact_name or "N/A",
            "contact_phone": inst.contact_phone or "N/A",
            "last_attendance": latest_att.reported_count if latest_att else None,
            "cctv_status": "Simulated" if not inst.cctv_stream_url else "Online",
        })
    return jsonify(data)


@api_bp.route("/institutes/<int:institute_id>")
@login_required
def institute_detail_json(institute_id):
    """Detailed institute information for quick view modal."""
    inst = Institute.query.get_or_404(institute_id)
    recent_flags = [
        {
            "id": f.id,
            "type_label": f.flag_type_label,
            "severity": f.severity,
            "status": f.status,
            "description": f.description,
            "created_at": f.created_at.strftime("%d %b %Y, %H:%M"),
        }
        for f in inst.flags.order_by(Flag.created_at.desc()).limit(5).all()
    ]
    recent_inspections = [
        {
            "id": insp.id,
            "inspector_name": insp.inspector.name if insp.inspector else "Unknown",
            "status": insp.status,
            "trust_score": insp.trust_score,
            "assigned_at": insp.assigned_at.strftime("%d %b %Y"),
            "completed_at": insp.completed_at.strftime("%d %b %Y") if insp.completed_at else None,
        }
        for insp in inst.inspections.order_by(Inspection.assigned_at.desc()).limit(5).all()
    ]
    latest_att = (
        AttendanceRecord.query.filter_by(institute_id=inst.id)
        .order_by(AttendanceRecord.date.desc())
        .first()
    )

    return jsonify({
        "id": inst.id,
        "name": inst.name,
        "type": inst.type,
        "type_label": inst.type_label,
        "district": inst.district,
        "state": inst.state,
        "address": inst.address or f"{inst.district}, {inst.state}",
        "lat": inst.lat,
        "lng": inst.lng,
        "risk_score": round(inst.risk_score, 1),
        "rag": inst.rag_status,
        "rag_label": inst.rag_label,
        "reported_capacity": inst.reported_capacity,
        "grant_amount_lakhs": inst.grant_amount_lakhs,
        "ngo_reg": inst.ngo_registration_no or "N/A",
        "contact_name": inst.contact_name or "N/A",
        "contact_phone": inst.contact_phone or "N/A",
        "last_inspection": inst.last_inspection_date.strftime("%d %b %Y") if inst.last_inspection_date else "None",
        "open_flags_count": inst.open_flags_count(),
        "recent_flags": recent_flags,
        "recent_inspections": recent_inspections,
        "latest_attendance": {
            "date": latest_att.date.strftime("%d %b %Y") if latest_att else None,
            "reported_count": latest_att.reported_count if latest_att else None,
            "cctv_count": latest_att.cctv_count if latest_att else None,
            "mismatch": latest_att.mismatch_flag if latest_att else False,
        } if latest_att else None,
    })


@api_bp.route("/stats")
@login_required
def live_stats():
    """Live KPI counters for instant dashboard synchronization."""
    total_institutes = Institute.query.count()
    week_ago = date.today() - timedelta(days=7)
    inspections_this_week = Inspection.query.filter(Inspection.assigned_at >= week_ago).count()
    open_flags = Flag.query.filter_by(status="open").count()
    missed_calls = VCRequest.query.filter_by(status="missed").count()

    institutes = Institute.query.all()
    red_count = sum(1 for i in institutes if i.rag_status == "red")
    amber_count = sum(1 for i in institutes if i.rag_status == "amber")
    green_count = sum(1 for i in institutes if i.rag_status == "green")

    return jsonify({
        "total_institutes": total_institutes,
        "inspections_this_week": inspections_this_week,
        "open_flags": open_flags,
        "missed_calls": missed_calls,
        "red_count": red_count,
        "amber_count": amber_count,
        "green_count": green_count,
    })


@api_bp.route("/otp/<int:inspection_id>", methods=["GET"])
@login_required
def generate_otp(inspection_id):
    """
    Generate a 60-second one-time token (OTP) before evidence capture.
    Guarantees photo was taken live within the valid session window.
    """
    inspection = Inspection.query.get_or_404(inspection_id)
    if current_user.role != "inspector" and current_user.role != "officer":
        return jsonify({"error": "Unauthorized"}), 403

    now = datetime.utcnow()
    token_str = f"OTP-{uuid.uuid4().hex[:8].upper()}"
    expires_at = now + timedelta(seconds=60)

    otp = OTPToken(
        token=token_str,
        inspection_id=inspection.id,
        inspector_id=current_user.id,
        created_at=now,
        expires_at=expires_at,
        is_used=False,
    )
    db.session.add(otp)
    db.session.commit()

    return jsonify({
        "token": token_str,
        "expires_at": expires_at.isoformat(),
        "valid_seconds": 60,
        "server_time": now.isoformat(),
    })


@api_bp.route("/evidence", methods=["POST"])
@login_required
def upload_evidence():
    """
    Process live camera evidence captured by inspector:
    - Verifies 60s OTP
    - Runs anomaly detection (GPS, duplicate pHash, liveness)
    - Computes HMAC-SHA256 signature
    - Saves photo and records Evidence
    """
    if current_user.role != "inspector" and current_user.role != "officer":
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json() or {}
    inspection_id = data.get("inspection_id")
    photo_b64 = data.get("photo_base64", "")
    otp_code = data.get("otp_code", "")
    client_lat = data.get("lat")
    client_lng = data.get("lng")
    liveness_passed = bool(data.get("liveness_passed", True))

    inspection = Inspection.query.get_or_404(inspection_id)

    # 1. Validate OTP
    now = datetime.utcnow()
    otp_record = OTPToken.query.filter_by(
        token=otp_code,
        inspection_id=inspection.id,
        is_used=False,
    ).first()

    if not otp_record or otp_record.expires_at < now:
        return jsonify({
            "error": "Invalid or expired OTP token. Evidence must be captured within 60 seconds."
        }), 400

    otp_record.is_used = True
    otp_record.used_at = now

    # 2. Decode Image Bytes
    if "," in photo_b64:
        photo_b64 = photo_b64.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(photo_b64)
    except Exception:
        return jsonify({"error": "Invalid image data."}), 400

    # 3. Anomaly & Integrity Checks
    client_lat = float(client_lat) if client_lat is not None else None
    client_lng = float(client_lng) if client_lng is not None else None

    analysis = check_evidence_anomalies(
        inspection=inspection,
        evidence_bytes=image_bytes,
        client_lat=client_lat,
        client_lng=client_lng,
        otp_code=otp_code,
        liveness_passed=liveness_passed,
    )

    # 4. Save Image File
    filename = f"ev_{inspection.id}_{uuid.uuid4().hex[:8]}.jpg"
    upload_dir = os.path.join(current_app.root_path, "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as f:
        f.write(image_bytes)

    rel_photo_path = f"uploads/{filename}"

    # 5. Create Evidence Record
    evidence = Evidence(
        inspection_id=inspection.id,
        photo_path=rel_photo_path,
        sha256_hash=analysis["sha256"],
        perceptual_hash=analysis["phash"],
        lat=client_lat,
        lng=client_lng,
        gps_distance_m=analysis["gps_distance_m"],
        otp_code=otp_code,
        captured_at=analysis["captured_at"],
        hmac_signature=analysis["hmac_signature"],
        liveness_passed=liveness_passed,
        is_suspicious=analysis["is_suspicious"],
    )
    db.session.add(evidence)

    # Update inspection status to in_progress if not already
    if inspection.status == "assigned":
        inspection.status = "in_progress"
        inspection.started_at = now

    db.session.commit()

    return jsonify({
        "status": "success",
        "evidence_id": evidence.id,
        "sha256": analysis["sha256"],
        "gps_distance_m": analysis["gps_distance_m"],
        "is_suspicious": analysis["is_suspicious"],
        "flags_count": len(analysis["flags_raised"]),
        "hmac_signature": analysis["hmac_signature"],
    })


@api_bp.route("/assign_auto", methods=["POST"])
@login_required
def assign_auto():
    """API endpoint to trigger risk-weighted automated assignment."""
    if current_user.role != "officer":
        return jsonify({"error": "Only officers can assign inspections."}), 403

    target_institute_id = request.json.get("institute_id") if request.is_json else None
    inspection, message = auto_assign_inspection(
        officer_id=current_user.id,
        target_institute_id=target_institute_id
    )

    if not inspection:
        return jsonify({"status": "error", "message": message}), 400

    return jsonify({
        "status": "success",
        "inspection_id": inspection.id,
        "institute_name": inspection.institute.name,
        "inspector_name": inspection.inspector.name,
        "random_seed": inspection.random_seed,
        "message": message,
    })


@api_bp.route("/trigger_live_demo", methods=["POST"])
@login_required
def trigger_live_demo():
    """Simulate a live anomaly event broadcast via SSE."""
    scenario = request.json.get("scenario", "cctv_mismatch") if request.is_json else request.form.get("scenario", "cctv_mismatch")
    inst = Institute.query.first()
    if not inst:
        return jsonify({"error": "No institutes"}), 404

    if scenario == "cctv_mismatch":
        flag = Flag(
            institute_id=inst.id,
            flag_type="cctv_headcount_mismatch",
            severity="high",
            description=f"Live Alert: Real-time CCTV scan detected 24 occupants vs 48 reported for {inst.name}.",
            status="open",
        )
        inst.risk_score = min(100.0, inst.risk_score + 15.0)
        db.session.add(flag)
        db.session.commit()
        emit_flag_event(flag)
        return jsonify({"status": "ok", "event": "flag_raised", "institute": inst.name, "type": "CCTV Headcount Mismatch"})

    elif scenario == "missed_vc":
        flag = Flag(
            institute_id=inst.id,
            flag_type="missed_vc",
            severity="medium",
            description=f"Live Alert: Random video call check was unanswered by staff at {inst.name} within 60s.",
            status="open",
        )
        inst.risk_score = min(100.0, inst.risk_score + 8.0)
        db.session.add(flag)
        db.session.commit()
        emit_flag_event(flag)
        return jsonify({"status": "ok", "event": "vc_missed", "institute": inst.name, "type": "Missed Video Call"})

    elif scenario == "gps_mismatch":
        flag = Flag(
            institute_id=inst.id,
            flag_type="gps_mismatch",
            severity="high",
            description=f"Live Alert: Inspection evidence submitted 840m away from registered coordinates for {inst.name}.",
            status="open",
        )
        inst.risk_score = min(100.0, inst.risk_score + 12.0)
        db.session.add(flag)
        db.session.commit()
        emit_flag_event(flag)
        return jsonify({"status": "ok", "event": "flag_raised", "institute": inst.name, "type": "GPS Coordinate Mismatch"})

@api_bp.route("/cctv/stream/<int:institute_id>")
def cctv_stream(institute_id):
    """Stream live simulated MJPEG frames for an institute."""
    institute = Institute.query.get_or_404(institute_id)
    from ...services.cctv import cctv_mjpeg_generator
    return Response(
        stream_with_context(cctv_mjpeg_generator(institute)),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache"}
    )


@api_bp.route("/cctv/reconcile/<int:institute_id>", methods=["POST"])
@login_required
def cctv_reconcile(institute_id):
    """Run headcount reconciliation algorithm between staff attendance and CCTV count."""
    from ...services.cctv import reconcile_institute_headcount
    result = reconcile_institute_headcount(
        institute_id,
        officer_id=current_user.id if current_user.is_authenticated and current_user.role == "officer" else None
    )
    return jsonify({"status": "success", "result": result})


@api_bp.route("/vc/initiate", methods=["POST"])
@login_required
def vc_initiate():
    """Officer initiates a random risk-weighted video-call check."""
    if current_user.role != "officer":
        return jsonify({"error": "Unauthorized"}), 403

    target_inst_id = request.json.get("institute_id") if request.is_json else None
    from ...services.vc import initiate_random_vc
    vc, message = initiate_random_vc(
        officer_id=current_user.id,
        target_institute_id=target_inst_id
    )

    if not vc:
        return jsonify({"status": "error", "message": message}), 400

    return jsonify({
        "status": "success",
        "vc_id": vc.id,
        "institute_name": vc.institute.name,
        "staff_name": vc.staff.name if vc.staff else "Staff",
        "room_name": vc.room_name,
        "jitsi_url": f"https://meet.jit.si/{vc.room_name}",
        "deadline": vc.deadline.isoformat(),
        "message": message,
    })


@api_bp.route("/vc/accept/<int:vc_id>", methods=["POST"])
@login_required
def vc_accept(vc_id):
    """Staff accepts incoming VC check."""
    from ...services.vc import accept_vc_request
    vc, message = accept_vc_request(vc_id, staff_id=current_user.id)
    return jsonify({
        "status": "success" if vc.status == "accepted" else "error",
        "vc_status": vc.status,
        "room_name": vc.room_name,
        "jitsi_url": f"https://meet.jit.si/{vc.room_name}",
        "message": message,
    })


@api_bp.route("/status")
def status():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})
