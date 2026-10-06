"""
Risk-weighted random inspection assignment service with conflict resolution rules.
"""
import random
import uuid
import json
import math
from datetime import datetime, timedelta
from ..extensions import db
from ..models import Institute, User, Inspection, AuditLog
from ..config import ASSIGNMENT_CONFLICT_KM, MAX_INSPECTIONS_PER_INSPECTOR_WEEK
from .event_bus import emit_inspection_event


def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in kilometers."""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 999.0
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def evaluate_inspector_suitability(inspector: User, institute: Institute):
    """
    Check conflict rules for assigning an inspector to an institute.
    Returns (is_eligible, reason, conflict_type)
    """
    # 1. Conflict Rule A: Home District Conflict
    # Inspector cannot inspect an institute located in their own home district
    if inspector.district and institute.district:
        if inspector.district.strip().lower() == institute.district.strip().lower():
            return False, f"Conflict: Inspector resides in the same district ({inspector.district})", "home_district_conflict"

    # 2. Conflict Rule B: Consecutive Repeat Inspection Conflict
    # The same inspector cannot inspect the same institute twice in a row
    last_inspection = (
        Inspection.query.filter_by(institute_id=institute.id, status="completed")
        .order_by(Inspection.completed_at.desc())
        .first()
    )
    if last_inspection and last_inspection.inspector_id == inspector.id:
        return False, "Conflict: Inspector conducted the previous inspection at this institute", "repeat_inspection_conflict"

    # 3. Conflict Rule C: Workload balancing
    # Inspector cannot exceed max weekly assigned inspections
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_active_count = Inspection.query.filter(
        Inspection.inspector_id == inspector.id,
        Inspection.assigned_at >= week_ago,
        Inspection.status.in_(["assigned", "in_progress"])
    ).count()

    if recent_active_count >= MAX_INSPECTIONS_PER_INSPECTOR_WEEK:
        return False, f"Conflict: Inspector at max weekly capacity ({recent_active_count} active tasks)", "workload_cap_exceeded"

    return True, "Eligible and conflict-free", None


def select_risk_weighted_institute():
    """
    Select an institute using risk score + days since last inspection weighting.
    Returns (selected_institute, weight_breakdown)
    """
    institutes = Institute.query.all()
    if not institutes:
        return None, None

    now = datetime.utcnow()
    candidates = []

    for inst in institutes:
        # Check if institute already has an active pending inspection
        has_pending = Inspection.query.filter(
            Inspection.institute_id == inst.id,
            Inspection.status.in_(["assigned", "in_progress"])
        ).first()

        if has_pending:
            continue

        days_since_inspection = 30
        if inst.last_inspection_date:
            days_since_inspection = max(1, (now - inst.last_inspection_date).days)

        # Risk-weight formula: 60% risk score + 40% time elapsed since last audit
        time_factor = min(100.0, days_since_inspection * 2.0)
        composite_weight = (inst.risk_score * 0.6) + (time_factor * 0.4)

        candidates.append((inst, composite_weight, {
            "risk_score": inst.risk_score,
            "days_since_inspection": days_since_inspection,
            "composite_weight": round(composite_weight, 2)
        }))

    if not candidates:
        return None, None

    # Sort descending by composite weight
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0], candidates[0][2]


def auto_assign_inspection(officer_id: int = None, target_institute_id: int = None):
    """
    Run the full automated, conflict-checked, risk-weighted assignment algorithm.
    Generates a reproducible random seed and logs everything to AuditLog.
    """
    # 1. Select institute
    if target_institute_id:
        institute = Institute.query.get(target_institute_id)
        inst_meta = {"manual_target": True, "risk_score": institute.risk_score if institute else 0}
    else:
        institute, inst_meta = select_risk_weighted_institute()

    if not institute:
        return None, "No eligible institute found requiring inspection."

    # 2. Find all inspectors and filter by conflict rules
    all_inspectors = User.query.filter_by(role="inspector", is_active_account=True).all()
    if not all_inspectors:
        return None, "No active PMU inspectors available in system."

    eligible_inspectors = []
    conflict_log = []

    for insp in all_inspectors:
        is_ok, reason, conflict_type = evaluate_inspector_suitability(insp, institute)
        if is_ok:
            # Calculate total historical workload for fair balancing
            total_tasks = Inspection.query.filter_by(inspector_id=insp.id).count()
            eligible_inspectors.append((insp, total_tasks))
        else:
            conflict_log.append({"inspector": insp.name, "reason": reason, "conflict": conflict_type})

    if not eligible_inspectors:
        return None, f"All inspectors disqualified due to conflict rules: {conflict_log}"

    # 3. Seeded Random Selection among lowest-workload eligible inspectors
    # Generate cryptographic random seed for full transparent auditability
    random_seed = f"ASSIGN-{uuid.uuid4().hex[:12].upper()}"
    rng = random.Random(random_seed)

    # Sort eligible inspectors by workload (ascending)
    eligible_inspectors.sort(key=lambda x: x[1])
    min_workload = eligible_inspectors[0][1]
    best_tier = [insp for insp, w in eligible_inspectors if w <= min_workload + 1]

    chosen_inspector = rng.choice(best_tier)

    # 4. Create Inspection Record
    inspection = Inspection(
        institute_id=institute.id,
        inspector_id=chosen_inspector.id,
        assigned_at=datetime.utcnow(),
        status="assigned",
        random_seed=random_seed,
        notes=f"Auto-assigned via risk-weighted engine (Composite Priority: {inst_meta.get('composite_weight', 'N/A')}). Seed: {random_seed}",
    )
    db.session.add(inspection)
    db.session.flush()

    # 5. Record Immutable Audit Log
    audit_detail = {
        "event": "risk_weighted_assignment",
        "random_seed": random_seed,
        "institute_id": institute.id,
        "institute_name": institute.name,
        "institute_risk_score": institute.risk_score,
        "inspector_id": chosen_inspector.id,
        "inspector_name": chosen_inspector.name,
        "inspector_district": chosen_inspector.district,
        "eligible_candidates_count": len(eligible_inspectors),
        "disqualified_conflicts": conflict_log,
        "assigned_by_officer_id": officer_id,
    }

    audit_entry = AuditLog(
        actor_id=officer_id,
        action="inspection_auto_assigned",
        entity_type="Inspection",
        entity_id=inspection.id,
        detail_json=json.dumps(audit_detail),
    )
    db.session.add(audit_entry)
    db.session.commit()

    # 6. Broadcast SSE event
    emit_inspection_event(inspection, "inspection_assigned")

    return inspection, "Assignment successful."
