"""Flask entry point for the SIH26095 Step 3 prototype."""
from functools import wraps
import base64
import binascii
import hashlib
import hmac
import json
import math
import os
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
import imagehash
from PIL import Image, UnidentifiedImageError
import random
import secrets
from flask import Flask, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash
from sqlalchemy import inspect as sqlalchemy_inspect, text
from models import db, AssignmentBatch, CaptureNonce, Evidence, Flag, Inspection, Institute, User
from seed_data import seed_database

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sih26095-step1-demo-secret-change-for-deployment'
# A separate file keeps any database from an earlier prototype untouched.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///step3_monitoring.db'
app.config['EVIDENCE_HMAC_SECRET'] = os.environ.get('EVIDENCE_HMAC_SECRET') or app.config['SECRET_KEY']
app.config['MAX_CONTENT_LENGTH'] = 7 * 1024 * 1024
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)


def role_required(required_role):
    """Restrict a page to a signed-in user with the requested demo role."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if session.get('role') != required_role:
                flash('You do not have access to that page.', 'error')
                return redirect(url_for('index'))
            return view(*args, **kwargs)
        return wrapped
    return decorator


@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session.get('role') == 'officer':
        return redirect(url_for('officer_page'))
    return redirect(url_for('inspector_page'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session.clear()
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('index'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/officer')
@role_required('officer')
def officer_page():
    institutes = Institute.query.order_by(Institute.id).all()
    open_count = Inspection.query.filter_by(status='assigned').count()
    open_flag_counts = dict(
        db.session.query(Flag.institute_id, db.func.count(Flag.id))
        .filter_by(status='open').group_by(Flag.institute_id).all()
    )
    map_institutes = []
    last_inspected_by_id = {}
    for institute in institutes:
        last_visit = Inspection.query.filter_by(
            institute_id=institute.id, status='completed'
        ).order_by(Inspection.completed_at.desc(), Inspection.id.desc()).first()
        last_inspected_by_id[institute.id] = (
            _as_utc(last_visit.completed_at).strftime('%Y-%m-%d')
            if last_visit and last_visit.completed_at else 'Never'
        )
        count = open_flag_counts.get(institute.id, 0)
        status = ('red' if count or institute.risk_score >= 70
                  else 'amber' if institute.risk_score >= 40 else 'green')
        map_institutes.append({
            'id': institute.id,
            'name': institute.name,
            'type': institute.type,
            'district': institute.district,
            'latitude': institute.latitude,
            'longitude': institute.longitude,
            'risk_score': institute.risk_score,
            'open_flags': count,
            'status': status,
            'history_url': url_for('institute_history', institute_id=institute.id),
        })
    open_flags = Flag.query.filter_by(status='open').order_by(
        Flag.created_at.desc(), Flag.id.desc()
    ).all()
    return render_template(
        'officer_dashboard.html', institutes=institutes, open_count=open_count,
        map_institutes=map_institutes, open_flags=open_flags,
        last_inspected_by_id=last_inspected_by_id,
    )


@app.route('/officer/institute/<int:institute_id>')
@role_required('officer')
def institute_history(institute_id):
    institute = Institute.query.get_or_404(institute_id)
    inspections = Inspection.query.filter_by(institute_id=institute.id).order_by(
        Inspection.assigned_at.desc(), Inspection.id.desc()
    ).all()
    flags = Flag.query.filter_by(institute_id=institute.id).order_by(
        Flag.created_at.desc(), Flag.id.desc()
    ).all()
    return render_template(
        'institute_history.html', institute=institute,
        inspections=inspections, flags=flags,
    )


@app.route('/officer/evidence/<int:evidence_id>/image')
@role_required('officer')
def officer_evidence_image(evidence_id):
    evidence = Evidence.query.get_or_404(evidence_id)
    filename = os.path.basename(evidence.image_filename)
    return send_from_directory(
        os.path.join(app.instance_path, 'evidence'), filename, mimetype='image/jpeg'
    )


@app.route('/officer/flag/<int:flag_id>/review', methods=['POST'])
@role_required('officer')
def review_flag(flag_id):
    flag = Flag.query.get_or_404(flag_id)
    decision = request.form.get('decision', '')
    if decision not in {'reviewed_genuine', 'reviewed_needs_action'}:
        flash('Choose genuine or needs action to review this flag.', 'error')
        return redirect(url_for('officer_page') + '#open-flags')
    if flag.status != 'open':
        flash('This flag has already been reviewed.', 'info')
        return redirect(url_for('officer_page') + '#open-flags')
    flag.status = decision
    flag.reviewer_comment = request.form.get('comment', '').strip()[:2000]
    flag.reviewed_at = datetime.now(timezone.utc)
    db.session.commit()
    flash('Flag review saved.', 'success')
    return redirect(url_for('officer_page') + '#open-flags')


@app.route('/inspector/inspection/<int:inspection_id>/capture')
@role_required('inspector')
def capture_page(inspection_id):
    inspection = Inspection.query.filter_by(
        id=inspection_id, inspector_id=session['user_id'], status='assigned'
    ).first_or_404()
    return render_template('capture_evidence.html', inspection=inspection)


@app.route('/inspector/inspection/<int:inspection_id>/nonce', methods=['POST'])
@role_required('inspector')
def issue_capture_nonce(inspection_id):
    # Issue a fresh code that expires after 60 server-clock seconds.
    inspection = Inspection.query.filter_by(
        id=inspection_id, inspector_id=session['user_id'], status='assigned'
    ).first_or_404()
    now = datetime.now(timezone.utc)
    # A newer request invalidates any earlier, unused code for this inspection.
    CaptureNonce.query.filter_by(inspection_id=inspection.id, used_at=None).update(
        {CaptureNonce.expires_at: now}, synchronize_session=False
    )
    nonce = secrets.token_urlsafe(24)
    expires = now + timedelta(seconds=60)
    db.session.add(CaptureNonce(
        inspection_id=inspection.id,
        inspector_id=session['user_id'],
        nonce=nonce,
        issued_at=now,
        expires_at=expires,
    ))
    db.session.commit()
    return jsonify(nonce=nonce, server_time=now.isoformat(), expires_at=expires.isoformat())


@app.route('/inspector/inspection/<int:inspection_id>/evidence', methods=['POST'])
@role_required('inspector')
def submit_evidence(inspection_id):
    # Validate the one-time code and persist a signed camera evidence record.
    inspection = Inspection.query.filter_by(
        id=inspection_id, inspector_id=session['user_id']
    ).first_or_404()
    payload = request.get_json(silent=True) or {}
    nonce_value = payload.get('nonce', '')
    if not isinstance(nonce_value, str) or not nonce_value:
        return jsonify(error='A capture code is required.'), 400
    nonce_record = CaptureNonce.query.filter_by(
        nonce=nonce_value,
        inspection_id=inspection.id,
        inspector_id=session['user_id'],
    ).first()
    if nonce_record is None:
        return jsonify(error='The capture code is not valid for this assignment.'), 400

    now = datetime.now(timezone.utc)
    if nonce_record.used_at is not None:
        return jsonify(error='This capture code has already been used. Request a new one.'), 409
    if inspection.status != 'assigned':
        return jsonify(error='This inspection is no longer active.'), 409
    expires = nonce_record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now:
        return jsonify(error='The capture code expired. Request a new one.'), 410

    # The page sends only the JPEG data URL produced from its live video element.
    image_data = payload.get('image', '')
    prefix = 'data:image/jpeg;base64,'
    if not isinstance(image_data, str) or not image_data.startswith(prefix):
        return jsonify(error='Capture a JPEG frame from the live camera.'), 400
    try:
        image_bytes = base64.b64decode(image_data[len(prefix):], validate=True)
    except (binascii.Error, ValueError):
        return jsonify(error='The captured image data is invalid.'), 400
    if (len(image_bytes) > 5 * 1024 * 1024
            or not image_bytes.startswith(bytes((255, 216, 255)))):
        return jsonify(error='The captured JPEG is invalid or exceeds 5 MB.'), 400
    current_perceptual_hash = _perceptual_hash(image_bytes)
    if current_perceptual_hash is None:
        return jsonify(error='The captured JPEG could not be decoded.'), 400

    try:
        latitude = float(payload.get('latitude'))
        longitude = float(payload.get('longitude'))
    except (TypeError, ValueError):
        return jsonify(error='Browser GPS coordinates are required.'), 400
    if (not math.isfinite(latitude) or not math.isfinite(longitude)
            or not -90 <= latitude <= 90 or not -180 <= longitude <= 180):
        return jsonify(error='Browser GPS coordinates are invalid.'), 400

    distance = _distance_meters(
        latitude, longitude, inspection.institute.latitude, inspection.institute.longitude
    )
    latitude = round(latitude, 7)
    longitude = round(longitude, 7)
    distance = round(distance, 2)
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    server_timestamp = now.isoformat()
    signed_fields = {
        'image_sha256': image_hash,
        'nonce': nonce_value,
        'latitude': latitude,
        'longitude': longitude,
        'distance_meters': distance,
        'server_time': server_timestamp,
    }
    message = json.dumps(signed_fields, sort_keys=True, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(
        app.config['EVIDENCE_HMAC_SECRET'].encode('utf-8'), message, hashlib.sha256
    ).hexdigest()

    # Consume with a conditional update to reject concurrent replay attempts.
    used = CaptureNonce.query.filter_by(id=nonce_record.id, used_at=None).filter(
        CaptureNonce.expires_at > now
    ).update({CaptureNonce.used_at: now}, synchronize_session=False)
    if used != 1:
        db.session.rollback()
        return jsonify(error='The capture code expired or was already used.'), 409

    filename = f'{uuid.uuid4().hex}.jpg'
    evidence_dir = os.path.join(app.instance_path, 'evidence')
    image_path = os.path.join(evidence_dir, filename)
    try:
        os.makedirs(evidence_dir, exist_ok=True)
        with open(image_path, 'wb') as image_file:
            image_file.write(image_bytes)
    except OSError:
        db.session.rollback()
        return jsonify(error='The server could not save the captured image.'), 500

    evidence = Evidence(
        inspection_id=inspection.id,
        image_filename=filename,
        image_hash=image_hash,
        nonce=nonce_value,
        captured_latitude=latitude,
        captured_longitude=longitude,
        distance_meters=distance,
        server_timestamp=now,
        hmac_signature=signature,
    )
    inspection.status = 'completed'
    inspection.completed_at = now
    # Detect anomalies against saved evidence before adding this new row.
    anomaly_reasons = _anomaly_reasons(inspection, current_perceptual_hash, now, distance)
    for reason in anomaly_reasons:
        db.session.add(Flag(
            inspection_id=inspection.id,
            institute_id=inspection.institute_id,
            reason=reason,
            status='open',
        ))
    db.session.add(evidence)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            os.remove(image_path)
        except OSError:
            pass
        raise

    return jsonify(
        message='Evidence captured and saved.',
        image_sha256=image_hash,
        nonce=nonce_value,
        latitude=latitude,
        longitude=longitude,
        distance_meters=distance,
        server_timestamp=server_timestamp,
        record_signature=signature,
        flagged=bool(anomaly_reasons),
        flags=anomaly_reasons,
    ), 201


def _perceptual_hash(image_bytes):
    """Create a 64-bit pHash, rejecting invalid or excessively large images."""
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            width, height = image.size
            if width * height > 20_000_000:
                return None
            image.verify()
        with Image.open(BytesIO(image_bytes)) as image:
            return imagehash.phash(image.convert('RGB'))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None


def _stored_perceptual_hash(evidence):
    """Read a previous private evidence file and calculate its pHash."""
    filename = os.path.basename(evidence.image_filename or '')
    if not filename:
        return None
    path = os.path.join(app.instance_path, 'evidence', filename)
    try:
        with open(path, 'rb') as image_file:
            return _perceptual_hash(image_file.read())
    except OSError:
        return None


def _as_utc(value):
    """SQLite may return naive datetime values; treat stored values as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _anomaly_reasons(inspection, current_hash, server_time, distance):
    """Return review-only reasons for similar images, repeated times, or GPS distance."""
    reasons = []
    if current_hash is not None:
        # Compare globally so a reused photo at a different institute is also noticed.
        for previous in Evidence.query.order_by(Evidence.id).all():
            previous_hash = _stored_perceptual_hash(previous)
            if previous_hash is None:
                continue
            difference = current_hash - previous_hash
            if difference <= 6:  # At least 58 of 64 pHash bits match.
                reasons.append(
                    f'Photo is similar to prior evidence #{previous.id} '
                    f'(perceptual hash distance {difference}/64; threshold 6).'
                )
                break

    same_minute_dates = set()
    checkin_minute = server_time.strftime('%H:%M')
    prior_rows = db.session.query(Evidence, Inspection).join(
        Inspection, Evidence.inspection_id == Inspection.id
    ).filter(Inspection.institute_id == inspection.institute_id).all()
    for previous_evidence, _previous_inspection in prior_rows:
        if previous_evidence.server_timestamp is None:
            continue
        previous_time = _as_utc(previous_evidence.server_timestamp)
        if previous_time.strftime('%H:%M') == checkin_minute:
            same_minute_dates.add(previous_time.date())
    same_minute_dates.add(_as_utc(server_time).date())
    if len(same_minute_dates) >= 3:
        reasons.append(
            f'Check-in time {checkin_minute} UTC repeated at this institute '
            f'on {len(same_minute_dates)} different UTC dates.'
        )

    if distance > 200:
        reasons.append(f'GPS location is {distance:.2f} m from the institute (over 200 m).')
    return reasons


def _distance_meters(lat1, lon1, lat2, lon2):
    # Haversine distance in metres between two latitude/longitude pairs.
    earth_radius = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    term = (math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    term = min(1.0, max(0.0, term))
    return earth_radius * 2 * math.atan2(math.sqrt(term), math.sqrt(1 - term))


@app.route('/inspector')
@role_required('inspector')
def inspector_page():
    current_user = db.session.get(User, session['user_id'])
    assigned_inspections = Inspection.query.filter_by(
        inspector_id=current_user.id, status='assigned'
    ).order_by(Inspection.assigned_at.desc()).all()
    return render_template(
        'inspector_home.html', current_user=current_user,
        assigned_inspections=assigned_inspections,
    )


@app.route('/officer/assign', methods=['POST'])
@role_required('officer')
def assign_inspections():
    """Create a weighted batch and record the seed used for its choices."""
    inspectors = User.query.filter_by(role='inspector').order_by(User.id).all()
    active_ids = {
        row[0] for row in db.session.query(Inspection.institute_id)
        .filter_by(status='assigned').distinct().all()
    }

    eligible_inspectors = {}
    candidates = []
    for institute in Institute.query.order_by(Institute.id).all():
        if institute.id in active_ids:
            continue  # Avoid issuing a second open assignment for the same institute.
        previous = Inspection.query.filter_by(
            institute_id=institute.id, status='completed'
        ).order_by(Inspection.completed_at.desc(), Inspection.id.desc()).first()
        eligible = [
            inspector for inspector in inspectors
            if (inspector.home_district or '').strip().casefold()
               != institute.district.strip().casefold()
            and (previous is None or inspector.id != previous.inspector_id)
        ]
        if eligible:
            eligible_inspectors[institute.id] = eligible
            candidates.append((institute, previous))

    if not candidates:
        flash('No institutes currently have an eligible inspector.', 'info')
        return redirect(url_for('officer_page'))

    seed = f'{secrets.randbits(64):016x}'
    rng = random.Random(int(seed, 16))
    now = datetime.now(timezone.utc)
    pool = list(candidates)
    selected = []
    # Pick at most five institutes per click, weighted and without replacement.
    for _ in range(min(5, len(pool))):
        weights = []
        for institute, previous in pool:
            risk_weight = 1.0 + max(0, min(100, institute.risk_score)) / 100.0
            if previous is None or previous.completed_at is None:
                staleness_weight = 4.0
            else:
                last_time = previous.completed_at
                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=timezone.utc)
                days_old = max(0.0, (now - last_time).total_seconds() / 86400)
                staleness_weight = 1.0 + min(days_old / 90.0, 3.0)
            weights.append(risk_weight * staleness_weight)
        chosen_index = rng.choices(range(len(pool)), weights=weights, k=1)[0]
        selected.append(pool.pop(chosen_index)[0])

    batch = AssignmentBatch(seed=seed, assigned_count=len(selected), created_at=now)
    db.session.add(batch)
    for institute in selected:
        inspector = rng.choice(eligible_inspectors[institute.id])
        db.session.add(Inspection(
            institute_id=institute.id,
            inspector_id=inspector.id,
            assigned_at=now,
            status='assigned',
            assignment_seed=seed,
        ))
    db.session.commit()
    flash(f'{len(selected)} inspections assigned. Seed: {seed}', 'success')
    return redirect(url_for('assignment_audit'))


@app.route('/officer/audit')
@role_required('officer')
def assignment_audit():
    batches = AssignmentBatch.query.order_by(
        AssignmentBatch.created_at.desc(), AssignmentBatch.id.desc()
    ).limit(20).all()
    audit_rows = []
    for batch in batches:
        inspections = Inspection.query.filter_by(
            assignment_seed=batch.seed
        ).order_by(Inspection.id).all()
        audit_rows.append({'batch': batch, 'inspections': inspections})
    return render_template('assignment_audit.html', audit_rows=audit_rows)


def initialize_database():
    """Create the Step 5 tables, migrate flag review time, and seed the local demo rows once."""
    with app.app_context():
        db.create_all()
        # Add the Step 5 review timestamp to an existing Step 4 SQLite database.
        flag_columns = {column['name'] for column in sqlalchemy_inspect(db.engine).get_columns('flags')}
        if 'reviewed_at' not in flag_columns:
            with db.engine.begin() as connection:
                connection.execute(text('ALTER TABLE flags ADD COLUMN reviewed_at DATETIME'))
        seed_database()


if __name__ == '__main__':
    initialize_database()
    app.run(debug=True)
