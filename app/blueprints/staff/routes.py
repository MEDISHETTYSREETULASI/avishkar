from datetime import date, datetime
import json
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from . import staff_bp
from ...models import AttendanceRecord, VCRequest, Flag, Inspection, Institute, AuditLog
from ...extensions import db
from ...services.cctv import get_simulated_cctv_count, reconcile_institute_headcount
from ...services.vc import accept_vc_request


def staff_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != "staff":
            flash("Institute staff privileges required.", "error")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@staff_bp.route("/")
@staff_bp.route("/attendance", methods=["GET", "POST"])
@staff_required
def attendance():
    institute = current_user.institute
    if request.method == "POST":
        if not institute:
            flash("You are not associated with any registered institute.", "error")
            return redirect(url_for("staff.attendance"))

        count_str = request.form.get("count", "").strip()
        if not count_str or not count_str.isdigit():
            flash("Please enter a valid occupant number.", "error")
            return redirect(url_for("staff.attendance"))

        count_val = int(count_str)
        today = date.today()

        # Check if already submitted today
        existing = AttendanceRecord.query.filter_by(
            institute_id=institute.id, date=today
        ).first()

        cctv_count = get_simulated_cctv_count(institute)
        diff_pct = (abs(count_val - cctv_count) / max(1, count_val)) * 100.0
        is_mismatch = diff_pct > 10.0

        if existing:
            existing.reported_count = count_val
            existing.cctv_count = cctv_count
            existing.mismatch_flag = is_mismatch
            existing.submitted_at = datetime.utcnow()
            existing.submitted_by = current_user.id
            flash(f"Today's attendance updated: {count_val} residents logged.", "success")
        else:
            rec = AttendanceRecord(
                institute_id=institute.id,
                date=today,
                reported_count=count_val,
                cctv_count=cctv_count,
                mismatch_flag=is_mismatch,
                submitted_by=current_user.id,
                submitted_at=datetime.utcnow(),
            )
            db.session.add(rec)
            flash(f"Daily attendance submitted successfully: {count_val} residents present.", "success")

        db.session.commit()

        # Run automated reconciliation check
        reconcile_institute_headcount(institute.id, officer_id=None)

        return redirect(url_for("staff.attendance"))

    today_record = None
    recent_records = []
    if institute:
        today_record = AttendanceRecord.query.filter_by(
            institute_id=institute.id, date=date.today()
        ).first()
        recent_records = (
            AttendanceRecord.query.filter_by(institute_id=institute.id)
            .order_by(AttendanceRecord.date.desc())
            .limit(10)
            .all()
        )

    return render_template(
        "staff/attendance.html",
        institute=institute,
        today_record=today_record,
        recent_records=recent_records,
    )


@staff_bp.route("/vc", methods=["GET", "POST"])
@staff_required
def vc_incoming():
    pending_vc = None
    if current_user.institute_id:
        pending_vc = (
            VCRequest.query.filter_by(
                institute_id=current_user.institute_id, status="pending"
            )
            .order_by(VCRequest.requested_at.desc())
            .first()
        )

    # Check if there is an active accepted call to join
    active_vc = None
    if current_user.institute_id:
        active_vc = (
            VCRequest.query.filter_by(
                institute_id=current_user.institute_id, status="accepted"
            )
            .order_by(VCRequest.requested_at.desc())
            .first()
        )

    return render_template(
        "staff/vc_incoming.html",
        pending_vc=pending_vc,
        active_vc=active_vc,
    )


@staff_bp.route("/vc/accept/<int:vc_id>", methods=["POST"])
@staff_required
def accept_call(vc_id):
    vc, message = accept_vc_request(vc_id, staff_id=current_user.id)
    if vc.status == "accepted":
        flash("Video call accepted! Connecting to secure Jitsi Meet room...", "success")
    else:
        flash(message, "error")
    return redirect(url_for("staff.vc_incoming"))


@staff_bp.route("/flags")
@staff_required
def flags():
    institute_flags = []
    if current_user.institute_id:
        institute_flags = (
            Flag.query.filter_by(institute_id=current_user.institute_id)
            .order_by(Flag.created_at.desc())
            .all()
        )
    return render_template("staff/flags.html", flags=institute_flags)


@staff_bp.route("/flags/respond", methods=["POST"])
@staff_required
def respond_flag():
    flag_id = request.form.get("flag_id")
    response_text = request.form.get("response", "").strip()

    if not flag_id or not response_text:
        flash("Please enter an explanation before submitting.", "error")
        return redirect(url_for("staff.flags"))

    flag = Flag.query.get_or_404(int(flag_id))

    if flag.institute_id != current_user.institute_id:
        flash("Unauthorized to respond to flags for this institute.", "error")
        return redirect(url_for("staff.flags"))

    flag.staff_response = response_text

    audit = AuditLog(
        actor_id=current_user.id,
        action="staff_flag_response_submitted",
        entity_type="Flag",
        entity_id=flag.id,
        detail_json=json.dumps({
            "flag_id": flag.id,
            "institute_id": flag.institute_id,
            "response": response_text,
            "staff_name": current_user.name,
        }),
    )
    db.session.add(audit)
    db.session.commit()

    flash(f"Official response for Flag #{flag.id} submitted successfully.", "success")
    return redirect(url_for("staff.flags"))


@staff_bp.route("/results")
@staff_required
def results():
    institute_inspections = []
    if current_user.institute_id:
        institute_inspections = (
            Inspection.query.filter_by(
                institute_id=current_user.institute_id, status="completed"
            )
            .order_by(Inspection.completed_at.desc())
            .all()
        )
    return render_template("staff/results.html", inspections=institute_inspections)
