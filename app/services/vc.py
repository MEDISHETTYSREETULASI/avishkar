"""
Random Video-Call Verification Service.

Features:
- Risk-weighted institute & random staff selection
- Jitsi Meet room name generation (sih26095-<uuid>)
- 60-second response deadline tracking
- Background timeout monitor that auto-marks unanswered calls as 'missed'
- Flag issuance and risk score escalation upon missed calls
"""
import uuid
import json
import random
from datetime import datetime, timedelta
from ..extensions import db
from ..models import Institute, User, VCRequest, Flag, AuditLog
from ..config import VC_DEADLINE_SECONDS, RISK_INCREASE_PER_FLAG
from .event_bus import emit_vc_event, emit_flag_event


def initiate_random_vc(officer_id: int, target_institute_id: int = None):
    """
    Initiate a random video-call check.
    Selects institute (risk-weighted or target) and picks a staff member.
    """
    now = datetime.utcnow()

    # 1. Select institute
    if target_institute_id:
        institute = Institute.query.get(target_institute_id)
    else:
        # Pick risk-weighted institute
        institutes = Institute.query.all()
        if not institutes:
            return None, "No institutes registered."

        # Weight by risk score (higher risk = higher chance of VC check)
        weights = [max(10.0, inst.risk_score) for inst in institutes]
        institute = random.choices(institutes, weights=weights, k=1)[0]

    if not institute:
        return None, "Target institute not found."

    # 2. Pick a staff member from this institute
    staff_members = User.query.filter_by(
        role="staff",
        institute_id=institute.id,
        is_active_account=True
    ).all()

    if not staff_members:
        # Fallback to any staff user if unassigned
        staff_members = User.query.filter_by(role="staff", is_active_account=True).all()

    if not staff_members:
        return None, f"No staff members available for {institute.name}."

    chosen_staff = random.choice(staff_members)

    # 3. Create VCRequest Record
    room_name = f"sih26095-{uuid.uuid4().hex[:10]}"
    deadline = now + timedelta(seconds=VC_DEADLINE_SECONDS)

    vc = VCRequest(
        institute_id=institute.id,
        staff_id=chosen_staff.id,
        officer_id=officer_id,
        room_name=room_name,
        requested_at=now,
        deadline=deadline,
        status="pending",
    )
    db.session.add(vc)
    db.session.flush()

    # 4. Audit Log
    audit = AuditLog(
        actor_id=officer_id,
        action="vc_initiated",
        entity_type="VCRequest",
        entity_id=vc.id,
        detail_json=json.dumps({
            "institute_id": institute.id,
            "institute_name": institute.name,
            "staff_id": chosen_staff.id,
            "staff_name": chosen_staff.name,
            "room_name": room_name,
            "deadline_seconds": VC_DEADLINE_SECONDS,
        }),
    )
    db.session.add(audit)
    db.session.commit()

    # 5. Broadcast SSE Event to staff portal & officer dashboards
    emit_vc_event(vc, "vc_incoming")

    return vc, "Random VC check initiated."


def accept_vc_request(vc_id: int, staff_id: int):
    """Staff accepts the incoming video call within deadline."""
    vc = VCRequest.query.get_or_404(vc_id)

    if vc.status != "pending":
        return vc, f"Call is already {vc.status}."

    now = datetime.utcnow()
    if now > vc.deadline:
        # Call expired
        mark_vc_missed(vc.id)
        return vc, "Call expired. Marked as missed."

    vc.status = "accepted"
    vc.accepted_at = now

    audit = AuditLog(
        actor_id=staff_id,
        action="vc_accepted",
        entity_type="VCRequest",
        entity_id=vc.id,
        detail_json=json.dumps({
            "institute_id": vc.institute_id,
            "staff_id": staff_id,
            "room_name": vc.room_name,
            "response_time_seconds": (now - vc.requested_at).total_seconds(),
        }),
    )
    db.session.add(audit)
    db.session.commit()

    emit_vc_event(vc, "vc_accepted")
    return vc, "Call accepted."


def mark_vc_missed(vc_id: int):
    """
    Mark an unanswered VC request as missed and issue a flag.
    """
    vc = VCRequest.query.get(vc_id)
    if not vc or vc.status != "pending":
        return None

    vc.status = "missed"
    institute = vc.institute

    # Raise Missed VC Flag
    flag = Flag(
        institute_id=institute.id,
        flag_type="missed_vc",
        severity="medium",
        description=(
            f"Missed Video Call Check: Staff ({vc.staff.name if vc.staff else 'Staff'}) at "
            f"{institute.name} did not answer the random verification video call within the "
            f"{VC_DEADLINE_SECONDS}-second deadline."
        ),
        status="open",
    )
    db.session.add(flag)
    institute.risk_score = min(100.0, institute.risk_score + RISK_INCREASE_PER_FLAG.get("medium", 8.0))
    db.session.flush()

    # Audit Log
    audit = AuditLog(
        actor_id=None,
        action="vc_missed",
        entity_type="VCRequest",
        entity_id=vc.id,
        detail_json=json.dumps({
            "institute_id": institute.id,
            "institute_name": institute.name,
            "staff_id": vc.staff_id,
            "flag_id": flag.id,
        }),
    )
    db.session.add(audit)
    db.session.commit()

    emit_vc_event(vc, "vc_missed")
    emit_flag_event(flag)

    return vc


def check_and_expire_pending_vcs():
    """Background sweep that expires all pending VCs whose deadline has passed."""
    now = datetime.utcnow()
    pending_vcs = VCRequest.query.filter(
        VCRequest.status == "pending",
        VCRequest.deadline < now
    ).all()

    for vc in pending_vcs:
        mark_vc_missed(vc.id)

    return len(pending_vcs)
