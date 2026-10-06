"""
Event bus service for publishing real-time Server-Sent Events (SSE)
to the connected officer and staff dashboards.
"""
import json
from datetime import datetime
from ..extensions import sse_broadcast


def emit_flag_event(flag):
    """Broadcast a new flag creation or update to all connected clients."""
    payload = {
        "id": flag.id,
        "institute_id": flag.institute_id,
        "institute_name": flag.institute.name if flag.institute else "Unknown Institute",
        "flag_type": flag.flag_type,
        "flag_type_label": flag.flag_type_label,
        "severity": flag.severity,
        "description": flag.description,
        "status": flag.status,
        "time": flag.created_at.strftime("%H:%M:%S") if flag.created_at else datetime.utcnow().strftime("%H:%M:%S"),
        "timestamp": flag.created_at.isoformat() if flag.created_at else datetime.utcnow().isoformat(),
    }
    sse_broadcast("flag_raised", json.dumps(payload))


def emit_vc_event(vc_request, event_type="vc_incoming"):
    """
    Broadcast a video call event (vc_incoming, vc_accepted, vc_missed).
    """
    payload = {
        "id": vc_request.id,
        "institute_id": vc_request.institute_id,
        "institute_name": vc_request.institute.name if vc_request.institute else "Unknown",
        "staff_id": vc_request.staff_id,
        "staff_name": vc_request.staff.name if vc_request.staff else "Staff",
        "room_name": vc_request.room_name,
        "status": vc_request.status,
        "time": datetime.utcnow().strftime("%H:%M:%S"),
        "timestamp": datetime.utcnow().isoformat(),
    }
    sse_broadcast(event_type, json.dumps(payload))


def emit_inspection_event(inspection, event_type="inspection_assigned"):
    """Broadcast an inspection assignment or completion."""
    payload = {
        "id": inspection.id,
        "institute_id": inspection.institute_id,
        "institute_name": inspection.institute.name if inspection.institute else "Unknown",
        "inspector_id": inspection.inspector_id,
        "inspector_name": inspection.inspector.name if inspection.inspector else "Inspector",
        "status": inspection.status,
        "trust_score": inspection.trust_score,
        "time": datetime.utcnow().strftime("%H:%M:%S"),
        "timestamp": datetime.utcnow().isoformat(),
    }
    sse_broadcast(event_type, json.dumps(payload))


def emit_headcount_mismatch(institute, reported, cctv, diff_pct):
    """Broadcast a CCTV headcount discrepancy detection."""
    payload = {
        "institute_id": institute.id,
        "institute_name": institute.name,
        "reported_count": reported,
        "cctv_count": cctv,
        "diff_pct": round(diff_pct, 1),
        "time": datetime.utcnow().strftime("%H:%M:%S"),
        "timestamp": datetime.utcnow().isoformat(),
    }
    sse_broadcast("headcount_mismatch", json.dumps(payload))
