from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from . import inspector_bp
from ...models import Inspection, User, Evidence, Flag
from ...extensions import db
from ...services.trust_score import compute_inspection_trust_score
from ...services.event_bus import emit_inspection_event


def inspector_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != "inspector":
            flash("Inspector access required.", "error")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@inspector_bp.route("/")
@inspector_bp.route("/tasks")
@inspector_required
def tasks():
    assigned = (
        Inspection.query.filter_by(inspector_id=current_user.id, status="assigned")
        .order_by(Inspection.assigned_at.desc())
        .all()
    )
    in_progress = (
        Inspection.query.filter_by(inspector_id=current_user.id, status="in_progress")
        .order_by(Inspection.assigned_at.desc())
        .all()
    )
    return render_template(
        "inspector/tasks.html",
        assigned=assigned,
        in_progress=in_progress,
    )


@inspector_bp.route("/start/<int:inspection_id>", methods=["POST", "GET"])
@inspector_required
def start_inspection(inspection_id):
    inspection = Inspection.query.filter_by(
        id=inspection_id, inspector_id=current_user.id
    ).first_or_404()

    if inspection.status == "assigned":
        inspection.status = "in_progress"
        inspection.started_at = datetime.utcnow()
        db.session.commit()
        emit_inspection_event(inspection, "inspection_started")

    return redirect(url_for("inspector.capture", inspection_id=inspection.id))


@inspector_bp.route("/capture")
@inspector_bp.route("/capture/<int:inspection_id>")
@inspector_required
def capture(inspection_id=None):
    inspection = None
    if inspection_id:
        inspection = Inspection.query.filter_by(
            id=inspection_id, inspector_id=current_user.id
        ).first_or_404()
    else:
        # Get latest in-progress or assigned inspection
        inspection = (
            Inspection.query.filter(
                Inspection.inspector_id == current_user.id,
                Inspection.status.in_(["in_progress", "assigned"]),
            )
            .order_by(Inspection.assigned_at.desc())
            .first()
        )

    evidence_items = []
    if inspection:
        evidence_items = inspection.evidence.order_by(Evidence.captured_at.desc()).all()

    return render_template(
        "inspector/capture.html",
        inspection=inspection,
        evidence_items=evidence_items,
    )


@inspector_bp.route("/complete/<int:inspection_id>", methods=["POST"])
@inspector_required
def complete_inspection(inspection_id):
    inspection = Inspection.query.filter_by(
        id=inspection_id, inspector_id=current_user.id
    ).first_or_404()

    notes = request.form.get("notes", "").strip()
    evidence_count = inspection.evidence.count()

    if evidence_count == 0:
        flash("You must capture at least one piece of photo evidence before completing the inspection.", "error")
        return redirect(url_for("inspector.capture", inspection_id=inspection.id))

    # Calculate trust score based on all flags associated with this inspection
    flags_list = inspection.flags.all()
    evidence_items = inspection.evidence.all()
    all_liveness = all(e.liveness_passed for e in evidence_items)
    max_gps_dist = max((e.gps_distance_m or 0.0) for e in evidence_items) if evidence_items else 0.0

    trust_score, deductions = compute_inspection_trust_score(
        flags_list=flags_list,
        liveness_passed=all_liveness,
        gps_dist_m=max_gps_dist,
    )

    inspection.status = "completed"
    inspection.completed_at = datetime.utcnow()
    inspection.trust_score = trust_score
    if notes:
        inspection.notes = notes

    # Update institute last inspection date
    inspection.institute.last_inspection_date = inspection.completed_at

    db.session.commit()
    emit_inspection_event(inspection, "inspection_completed")

    flash(f"Inspection #{inspection.id} completed successfully! Trust Score: {int(trust_score)}/100", "success")
    return redirect(url_for("inspector.history"))


@inspector_bp.route("/history")
@inspector_required
def history():
    completed = (
        Inspection.query.filter_by(inspector_id=current_user.id, status="completed")
        .order_by(Inspection.completed_at.desc())
        .all()
    )
    return render_template("inspector/history.html", completed=completed)


@inspector_bp.route("/profile")
@inspector_required
def profile():
    total_done = Inspection.query.filter_by(
        inspector_id=current_user.id, status="completed"
    ).count()
    active_count = Inspection.query.filter(
        Inspection.inspector_id == current_user.id,
        Inspection.status.in_(["assigned", "in_progress"]),
    ).count()
    return render_template(
        "inspector/profile.html",
        total_done=total_done,
        active_count=active_count,
    )
