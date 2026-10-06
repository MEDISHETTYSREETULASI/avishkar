from datetime import date, timedelta, datetime
import uuid
import json
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from functools import wraps
from . import officer_bp
from ...models import Institute, Inspection, Flag, VCRequest, AuditLog, User, AttendanceRecord, Evidence
from ...extensions import db
from ...services.assignment import auto_assign_inspection, evaluate_inspector_suitability
from ...services.anomaly import resolve_flag_with_audit, scan_attendance_anomalies
from ...services.event_bus import emit_inspection_event


def officer_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != "officer":
            flash("Officer privileges required.", "error")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@officer_bp.route("/")
@officer_bp.route("/overview")
@officer_required
def overview():
    total_institutes = Institute.query.count()
    week_ago = date.today() - timedelta(days=7)
    inspections_this_week = Inspection.query.filter(Inspection.assigned_at >= week_ago).count()
    open_flags = Flag.query.filter_by(status="open").count()
    missed_calls = VCRequest.query.filter_by(status="missed").count()
    recent_flags = Flag.query.order_by(Flag.created_at.desc()).limit(10).all()
    institutes = Institute.query.all()
    red_count = sum(1 for i in institutes if i.rag_status == "red")
    amber_count = sum(1 for i in institutes if i.rag_status == "amber")
    green_count = sum(1 for i in institutes if i.rag_status == "green")
    trend_labels, trend_values = [], []
    for offset in range(29, -1, -1):
        d = date.today() - timedelta(days=offset)
        count = Inspection.query.filter(db.func.date(Inspection.assigned_at) == d).count()
        trend_labels.append(d.strftime("%d %b"))
        trend_values.append(count)
    return render_template(
        "officer/overview.html",
        total_institutes=total_institutes,
        inspections_this_week=inspections_this_week,
        open_flags=open_flags,
        missed_calls=missed_calls,
        recent_flags=recent_flags,
        red_count=red_count,
        amber_count=amber_count,
        green_count=green_count,
        institutes=institutes,
        trend_labels=trend_labels,
        trend_values=trend_values,
    )


@officer_bp.route("/map")
@officer_required
def map_view():
    institutes = Institute.query.all()
    return render_template("officer/map.html", institutes=institutes)


@officer_bp.route("/cctv")
@officer_required
def cctv_wall():
    institutes = Institute.query.all()
    return render_template("officer/cctv_wall.html", institutes=institutes)


@officer_bp.route("/inspections")
@officer_required
def inspections():
    all_inspections = Inspection.query.order_by(Inspection.assigned_at.desc()).all()
    return render_template("officer/inspections.html", inspections=all_inspections)


@officer_bp.route("/inspections/<int:inspection_id>/report")
@officer_required
def inspection_report(inspection_id):
    from ...services.report import get_inspection_report_data
    report_data = get_inspection_report_data(inspection_id)
    return render_template("officer/report.html", **report_data)


@officer_bp.route("/flags")
@officer_required
def flags():
    status_filter = request.args.get("status", "all")
    severity_filter = request.args.get("severity", "all")

    query = Flag.query

    if status_filter != "all":
        query = query.filter_by(status=status_filter)
    if severity_filter != "all":
        query = query.filter_by(severity=severity_filter)

    all_flags = query.order_by(Flag.created_at.desc()).all()
    open_count = Flag.query.filter_by(status="open").count()

    return render_template(
        "officer/flags.html",
        flags=all_flags,
        open_count=open_count,
        current_status=status_filter,
        current_severity=severity_filter,
    )


@officer_bp.route("/flags/resolve/<int:flag_id>", methods=["POST"])
@officer_required
def resolve_flag(flag_id):
    new_status = request.form.get("status", "genuine")
    comment = request.form.get("comment", "").strip()

    if not comment:
        flash("Review decision comment is mandatory for human-in-the-loop audit integrity.", "error")
        return redirect(url_for("officer.flags"))

    resolve_flag_with_audit(
        flag_id=flag_id,
        officer_id=current_user.id,
        new_status=new_status,
        officer_comment=comment,
    )
    flash(f"Flag #{flag_id} resolved as '{new_status.replace('_', ' ').title()}'. Audit trail updated.", "success")
    return redirect(url_for("officer.flags"))


@officer_bp.route("/assignments", methods=["GET", "POST"])
@officer_required
def assignments():
    if request.method == "POST":
        action = request.form.get("action", "auto")

        if action == "auto":
            target_inst_id = request.form.get("target_institute_id")
            inst_id_val = int(target_inst_id) if target_inst_id else None
            inspection, message = auto_assign_inspection(
                officer_id=current_user.id, target_institute_id=inst_id_val
            )
            if inspection:
                flash(f"Successfully assigned {inspection.institute.name} to {inspection.inspector.name} (Seed: {inspection.random_seed})", "success")
            else:
                flash(f"Assignment failed: {message}", "error")

        elif action == "manual":
            institute_id = request.form.get("institute_id")
            inspector_id = request.form.get("inspector_id")

            if not institute_id or not inspector_id:
                flash("Please select both an institute and an inspector.", "error")
            else:
                inst = Institute.query.get(int(institute_id))
                insp = User.query.get(int(inspector_id))

                is_ok, reason, conflict_type = evaluate_inspector_suitability(insp, inst)
                if not is_ok:
                    flash(f"Conflict Warning: {reason}", "error")
                else:
                    random_seed = f"MANUAL-{uuid.uuid4().hex[:8].upper()}"
                    inspection = Inspection(
                        institute_id=inst.id,
                        inspector_id=insp.id,
                        assigned_at=datetime.utcnow(),
                        status="assigned",
                        random_seed=random_seed,
                        notes=f"Manually assigned by {current_user.name}. Seed: {random_seed}",
                    )
                    db.session.add(inspection)
                    db.session.flush()

                    log = AuditLog(
                        actor_id=current_user.id,
                        action="inspection_manually_assigned",
                        entity_type="Inspection",
                        entity_id=inspection.id,
                        detail_json=json.dumps({
                            "random_seed": random_seed,
                            "institute": inst.name,
                            "inspector": insp.name,
                        }),
                    )
                    db.session.add(log)
                    db.session.commit()
                    emit_inspection_event(inspection, "inspection_assigned")
                    flash(f"Inspection assigned to {insp.name} for {inst.name}.", "success")

        return redirect(url_for("officer.assignments"))

    inspectors = User.query.filter_by(role="inspector").all()
    institutes = Institute.query.order_by(Institute.risk_score.desc()).all()
    recent_assignments = (
        Inspection.query.filter(Inspection.status.in_(["assigned", "in_progress"]))
        .order_by(Inspection.assigned_at.desc())
        .all()
    )

    return render_template(
        "officer/assignments.html",
        inspectors=inspectors,
        institutes=institutes,
        recent_assignments=recent_assignments,
    )


@officer_bp.route("/audit")
@officer_required
def audit_log():
    action_filter = request.args.get("action", "all")
    search_query = request.args.get("q", "").strip().lower()

    query = AuditLog.query
    if action_filter != "all":
        query = query.filter(AuditLog.action == action_filter)

    logs = query.order_by(AuditLog.timestamp.desc()).limit(200).all()

    if search_query:
        logs = [
            l for l in logs
            if search_query in (l.action.lower() + (l.detail_json or "").lower() + (l.actor.name.lower() if l.actor else "system"))
        ]

    distinct_actions = list(
        db.session.scalars(db.select(AuditLog.action).distinct().order_by(AuditLog.action)).all()
    )

    return render_template(
        "officer/audit_log.html",
        logs=logs,
        distinct_actions=distinct_actions,
        current_action=action_filter,
        current_search=search_query,
    )
