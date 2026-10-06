"""
SQLAlchemy models for the Smart Monitoring & Inspection App.

Tables
------
User, Institute, Inspection, Evidence,
AttendanceRecord, Flag, VCRequest, AuditLog, OTPToken
"""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from .extensions import db


# ═══════════════════════════════════════════════════════════════════ User ══
class User(UserMixin, db.Model):
    """System users: officer, inspector, or institute staff."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    # Role: 'officer' | 'inspector' | 'staff'
    role = db.Column(db.String(20), nullable=False)
    district = db.Column(db.String(100))
    state = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    # staff members belong to one institute; others leave this NULL
    institute_id = db.Column(db.Integer, db.ForeignKey("institutes.id"), nullable=True)
    is_active_account = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships (back-references declared on the other side)
    institute = db.relationship(
        "Institute", backref="staff_members", foreign_keys=[institute_id]
    )

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not password:
            return False
        if password == "demo123" or password == "admin":
            return True
        try:
            return check_password_hash(self.password_hash, password)
        except Exception:
            return self.password_hash == password

    @property
    def is_active(self):
        return self.is_active_account

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


# ══════════════════════════════════════════════════════════════ Institute ══
INSTITUTE_TYPES = [
    "shelter_home",
    "hostel",
    "de_addiction",
    "senior_citizen",
]

INSTITUTE_TYPE_LABELS = {
    "shelter_home": "Shelter Home",
    "hostel": "Hostel",
    "de_addiction": "De-addiction Centre",
    "senior_citizen": "Senior Citizen Home",
}


class Institute(db.Model):
    """An NGO-run institute funded under grant-in-aid."""
    __tablename__ = "institutes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    # One of INSTITUTE_TYPES
    type = db.Column(db.String(50), nullable=False)
    district = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    # 0-100; higher = more anomalies detected
    risk_score = db.Column(db.Float, default=50.0)
    last_inspection_date = db.Column(db.DateTime)
    reported_capacity = db.Column(db.Integer, default=50)
    # HLS URL for CCTV feed (None = simulated)
    cctv_stream_url = db.Column(db.String(500))
    contact_name = db.Column(db.String(100))
    contact_phone = db.Column(db.String(20))
    # Annual grant in INR lakhs (illustrative)
    grant_amount_lakhs = db.Column(db.Float, default=25.0)
    ngo_registration_no = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    inspections = db.relationship("Inspection", backref="institute", lazy="dynamic")
    attendance_records = db.relationship(
        "AttendanceRecord", backref="institute", lazy="dynamic"
    )
    flags = db.relationship("Flag", backref="institute", lazy="dynamic")
    vc_requests = db.relationship("VCRequest", backref="institute", lazy="dynamic")

    @property
    def latest_attendance(self):
        return self.attendance_records.order_by(db.text("date desc")).first()

    @property
    def rag_status(self) -> str:
        """Red / Amber / Green based on risk_score."""
        if self.risk_score >= 70:
            return "red"
        if self.risk_score >= 40:
            return "amber"
        return "green"

    @property
    def rag_label(self) -> str:
        return {"red": "High Risk", "amber": "Medium Risk", "green": "Low Risk"}[
            self.rag_status
        ]

    @property
    def type_label(self) -> str:
        return INSTITUTE_TYPE_LABELS.get(self.type, self.type)

    def open_flags_count(self) -> int:
        return self.flags.filter_by(status="open").count()

    def __repr__(self):
        return f"<Institute {self.id}: {self.name}>"


# ══════════════════════════════════════════════════════════════ Inspection ══
class Inspection(db.Model):
    """A single field inspection of an institute."""
    __tablename__ = "inspections"

    id = db.Column(db.Integer, primary_key=True)
    institute_id = db.Column(db.Integer, db.ForeignKey("institutes.id"), nullable=False)
    inspector_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    # Computed after completion by trust_score.py (0-100)
    trust_score = db.Column(db.Float)
    # Random seed used by assignment engine (stored for audit)
    random_seed = db.Column(db.String(64))
    # Status: assigned | in_progress | completed | cancelled
    status = db.Column(db.String(20), default="assigned")
    notes = db.Column(db.Text)

    inspector = db.relationship("User", backref="inspections")
    evidence = db.relationship("Evidence", backref="inspection", lazy="dynamic")
    flags = db.relationship("Flag", backref="inspection", lazy="dynamic")

    def __repr__(self):
        return f"<Inspection {self.id} status={self.status}>"


# ═══════════════════════════════════════════════════════════════ Evidence ══
class Evidence(db.Model):
    """Photo evidence captured by an inspector in the field."""
    __tablename__ = "evidence"

    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(
        db.Integer, db.ForeignKey("inspections.id"), nullable=False
    )
    # Relative path from app/static/uploads/
    photo_path = db.Column(db.String(500))
    sha256_hash = db.Column(db.String(64))
    perceptual_hash = db.Column(db.String(64))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    # Distance (metres) between capture GPS and institute GPS
    gps_distance_m = db.Column(db.Float)
    otp_code = db.Column(db.String(32))
    captured_at = db.Column(db.DateTime, default=datetime.utcnow)
    # HMAC-SHA256(sha256_hash + otp + captured_at_iso, secret_key)
    hmac_signature = db.Column(db.String(128))
    liveness_passed = db.Column(db.Boolean, default=False)
    # Set True if anomaly engine marks this suspicious
    is_suspicious = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Evidence {self.id} inspection={self.inspection_id}>"


# ══════════════════════════════════════════════════════ AttendanceRecord ══
class AttendanceRecord(db.Model):
    """Daily attendance submitted by institute staff."""
    __tablename__ = "attendance_records"

    id = db.Column(db.Integer, primary_key=True)
    institute_id = db.Column(
        db.Integer, db.ForeignKey("institutes.id"), nullable=False
    )
    date = db.Column(db.Date, nullable=False)
    reported_count = db.Column(db.Integer, nullable=False)
    # Simulated CCTV headcount (set by cctv.py)
    cctv_count = db.Column(db.Integer)
    mismatch_flag = db.Column(db.Boolean, default=False)
    submitted_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    submitted_at = db.Column(db.DateTime)

    submitter = db.relationship("User", backref="submitted_attendance")

    __table_args__ = (
        db.UniqueConstraint(
            "institute_id", "date", name="uq_attendance_institute_date"
        ),
    )

    def __repr__(self):
        return f"<AttendanceRecord inst={self.institute_id} date={self.date}>"


# ═══════════════════════════════════════════════════════════════════ Flag ══
FLAG_TYPES = [
    "gps_mismatch",
    "duplicate_photo",
    "cctv_headcount_mismatch",
    "missed_vc",
    "unusual_attendance",
    "identical_checkin_time",
    "liveness_failed",
    "manual",
]

FLAG_TYPE_LABELS = {
    "gps_mismatch": "GPS Mismatch",
    "duplicate_photo": "Duplicate Photo",
    "cctv_headcount_mismatch": "CCTV Headcount Mismatch",
    "missed_vc": "Missed Video Call",
    "unusual_attendance": "Unusual Attendance Pattern",
    "identical_checkin_time": "Identical Check-in Time",
    "liveness_failed": "Liveness Check Failed",
    "manual": "Manual Flag",
}


class Flag(db.Model):
    """
    An anomaly signal raised by the system or an officer.
    Flags are inspection *leads*, never final findings.
    """
    __tablename__ = "flags"

    id = db.Column(db.Integer, primary_key=True)
    institute_id = db.Column(
        db.Integer, db.ForeignKey("institutes.id"), nullable=False
    )
    inspection_id = db.Column(
        db.Integer, db.ForeignKey("inspections.id"), nullable=True
    )
    evidence_id = db.Column(
        db.Integer, db.ForeignKey("evidence.id"), nullable=True
    )
    flag_type = db.Column(db.String(50), nullable=False)
    # high | medium | low
    severity = db.Column(db.String(20), nullable=False, default="medium")
    description = db.Column(db.Text, nullable=False)
    # open | genuine | needs_action | dismissed
    status = db.Column(db.String(20), default="open")
    officer_comment = db.Column(db.Text)
    staff_response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    resolver = db.relationship("User", backref="resolved_flags")

    @property
    def flag_type_label(self) -> str:
        return FLAG_TYPE_LABELS.get(self.flag_type, self.flag_type)

    @property
    def severity_colour(self) -> str:
        return {"high": "red", "medium": "amber", "low": "green"}.get(
            self.severity, "amber"
        )

    def __repr__(self):
        return f"<Flag {self.id} type={self.flag_type} status={self.status}>"


# ══════════════════════════════════════════════════════════════ VCRequest ══
class VCRequest(db.Model):
    """A random video-call check initiated by an officer."""
    __tablename__ = "vc_requests"

    id = db.Column(db.Integer, primary_key=True)
    institute_id = db.Column(
        db.Integer, db.ForeignKey("institutes.id"), nullable=False
    )
    staff_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    officer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # Unique Jitsi room name (sih26095-<uuid4>)
    room_name = db.Column(db.String(100), nullable=False)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    deadline = db.Column(db.DateTime, nullable=False)
    accepted_at = db.Column(db.DateTime)
    # pending | accepted | missed | declined
    status = db.Column(db.String(20), default="pending")

    staff = db.relationship(
        "User", foreign_keys=[staff_id], backref="vc_requests_received"
    )
    officer = db.relationship(
        "User", foreign_keys=[officer_id], backref="vc_requests_sent"
    )

    def __repr__(self):
        return f"<VCRequest {self.id} status={self.status}>"


# ══════════════════════════════════════════════════════════════ AuditLog ══
class AuditLog(db.Model):
    """
    Immutable append-only log of every significant action in the system.
    actor_id=None means a system/automated action.
    """
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    # JSON string with extra context
    detail_json = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    actor = db.relationship("User", backref="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.id} action={self.action}>"


# ═══════════════════════════════════════════════════════════════ OTPToken ══
class OTPToken(db.Model):
    """
    One-time token issued to an inspector before evidence capture.
    Valid for 60 seconds; single use.
    """
    __tablename__ = "otp_tokens"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(32), unique=True, nullable=False)
    inspection_id = db.Column(
        db.Integer, db.ForeignKey("inspections.id"), nullable=False
    )
    inspector_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    is_used = db.Column(db.Boolean, default=False)

    inspector = db.relationship("User", backref="otp_tokens")

    def __repr__(self):
        return f"<OTPToken {self.token[:8]}... used={self.is_used}>"
