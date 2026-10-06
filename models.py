"""SQLAlchemy models used by the SIH26095 Step 1 prototype."""
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """A department officer or an inspector who can sign in to the demo."""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # Werkzeug password hash
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'officer' or 'inspector'
    home_district = db.Column(db.String(80), nullable=True)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Institute(db.Model):
    """A fictional institute record for the demo map and officer list."""
    __tablename__ = 'institutes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    type = db.Column(db.String(80), nullable=False)
    district = db.Column(db.String(80), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    risk_score = db.Column(db.Integer, nullable=False, default=50)

    inspections = db.relationship('Inspection', back_populates='institute')


class Inspection(db.Model):
    """Schema foundation for future inspection assignments."""
    __tablename__ = 'inspections'
    id = db.Column(db.Integer, primary_key=True)
    institute_id = db.Column(db.Integer, db.ForeignKey('institutes.id'), nullable=False)
    inspector_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='assigned')
    completed_at = db.Column(db.DateTime, nullable=True)
    assignment_seed = db.Column(db.String(32), nullable=True)
    institute = db.relationship('Institute', back_populates='inspections')
    inspector = db.relationship('User')
    evidences = db.relationship('Evidence', back_populates='inspection')


class AssignmentBatch(db.Model):
    """Audit header for one seeded assignment run."""
    __tablename__ = 'assignment_batches'
    id = db.Column(db.Integer, primary_key=True)
    seed = db.Column(db.String(32), unique=True, nullable=False)
    assigned_count = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class CaptureNonce(db.Model):
    """A server-issued one-time code bound to one inspector and assignment."""
    __tablename__ = 'capture_nonces'
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey('inspections.id'), nullable=False)
    inspector_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    nonce = db.Column(db.String(64), unique=True, nullable=False)
    issued_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)


class Evidence(db.Model):
    """A camera image and the signed location and time record from a visit."""
    __tablename__ = 'evidence'
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey('inspections.id'), nullable=False)
    image_filename = db.Column(db.String(255), nullable=False)
    image_hash = db.Column(db.String(64), nullable=False)
    nonce = db.Column(db.String(64), nullable=False)
    captured_latitude = db.Column(db.Float, nullable=False)
    captured_longitude = db.Column(db.Float, nullable=False)
    distance_meters = db.Column(db.Float, nullable=False)
    server_timestamp = db.Column(db.DateTime, nullable=False)
    hmac_signature = db.Column(db.String(64), nullable=False)
    inspection = db.relationship('Inspection', back_populates='evidences')


class Flag(db.Model):
    """Schema foundation for human-review flags added in a later step."""
    __tablename__ = 'flags'
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey('inspections.id'), nullable=True)
    institute_id = db.Column(db.Integer, db.ForeignKey('institutes.id'), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='open')
    reviewer_comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_at = db.Column(db.DateTime, nullable=True)
