"""
Demo data seeder for SIH26095 – Smart Monitoring & Inspection App.

Seeds:
  - 1 officer
  - 5 inspectors (different states from the institutes they inspect)
  - 15 institutes (mix of types, states, risk levels)
  - 20 staff (1-2 per institute)
  - 30 days of attendance records
  - 8 completed inspections with evidence
  - Scripted anomalies:
      * GPS mismatch on inspection #3
      * Duplicate photo hash on inspection #5 & #6
      * CCTV headcount mismatch on institute #1
      * Missed VC on institute #8

All data is FICTIONAL - no real people, NGOs, or institutes.
"""
import random
import json
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash
from .extensions import db
from .models import (
    User, Institute, Inspection, Evidence,
    AttendanceRecord, Flag, VCRequest, AuditLog
)


INSTITUTE_DATA = [
    # (name, type, district, state, lat, lng, capacity, risk_score, grant)
    ("Naya Savera Shelter Home", "shelter_home", "New Delhi", "Delhi", 28.6139, 77.2090, 60, 82.0, 35.0),
    ("Udaan Girls Hostel", "hostel", "Mumbai", "Maharashtra", 19.0760, 72.8777, 80, 55.0, 28.0),
    ("Prabhat De-addiction Centre", "de_addiction", "Pune", "Maharashtra", 18.5204, 73.8567, 40, 73.0, 20.0),
    ("Vatsalya Senior Citizen Home", "senior_citizen", "Kolkata", "West Bengal", 22.5726, 88.3639, 50, 32.0, 22.0),
    ("Asha Kiran Shelter", "shelter_home", "Chennai", "Tamil Nadu", 13.0827, 80.2707, 55, 68.0, 30.0),
    ("Nirmala Women\'s Hostel", "hostel", "Bengaluru", "Karnataka", 12.9716, 77.5946, 70, 28.0, 32.0),
    ("Jeevan Jyoti De-addiction", "de_addiction", "Hyderabad", "Telangana", 17.3850, 78.4867, 35, 78.0, 18.0),
    ("Mamta Bal Griha", "shelter_home", "Ahmedabad", "Gujarat", 23.0225, 72.5714, 45, 60.0, 25.0),
    ("Suraksha Shelter Home", "shelter_home", "Jaipur", "Rajasthan", 26.9124, 75.7873, 50, 45.0, 27.0),
    ("Swabhiman Senior Home", "senior_citizen", "Lucknow", "Uttar Pradesh", 26.8467, 80.9462, 60, 38.0, 24.0),
    ("Pragati Girls Hostel", "hostel", "Chandigarh", "Punjab", 30.7333, 76.7794, 65, 22.0, 29.0),
    ("Prerna De-addiction Centre", "de_addiction", "Bhopal", "Madhya Pradesh", 23.2599, 77.4126, 30, 50.0, 16.0),
    ("Aadhar Shelter Home", "shelter_home", "Patna", "Bihar", 25.5941, 85.1376, 55, 65.0, 26.0),
    ("Sahara Women\'s Hostel", "hostel", "Indore", "Madhya Pradesh", 22.7196, 75.8577, 75, 35.0, 31.0),
    ("Navodaya Senior Citizen Home", "senior_citizen", "Nagpur", "Maharashtra", 21.1458, 79.0882, 45, 42.0, 21.0),
]

INSPECTOR_DATA = [
    # (name, email, district, state)
    ("Rajan Mehta", "inspector1@demo.in", "Surat", "Gujarat"),
    ("Priya Sharma", "inspector2@demo.in", "Agra", "Uttar Pradesh"),
    ("Amit Verma", "inspector3@demo.in", "Nashik", "Maharashtra"),
    ("Sunita Rao", "inspector4@demo.in", "Coimbatore", "Tamil Nadu"),
    ("Vinod Kumar", "inspector5@demo.in", "Amritsar", "Punjab"),
]

STAFF_NAMES = [
    "Kavita Patel", "Suresh Babu", "Anita Joshi", "Mohan Lal",
    "Rekha Singh", "Dinesh Yadav", "Meena Kumari", "Rajesh Gupta",
    "Sanjay Nair", "Pooja Iyer", "Harish Chandra", "Usha Devi",
    "Arun Mishra", "Deepa Menon", "Ganesh Patil", "Lata Sharma",
    "Vijay Kumar", "Savita Reddy", "Bharat Jain", "Neha Thakur",
]


def seed_if_empty():
    """Only seed if the database is empty (first run)."""
    if User.query.count() > 0:
        return
    print("[SEED] Seeding demo data...")
    _seed_all()
    print("[SEED] Done.")


def _seed_all():
    today = date.today()

    # ---------------------------------------------------------------- Officer
    officer = User(
        name="Aditya Kapoor",
        email="officer@demo.in",
        role="officer",
        district="New Delhi",
        state="Delhi",
        phone="9800000001",
    )
    officer.set_password("demo123")
    db.session.add(officer)

    # -------------------------------------------------------------- Inspectors
    inspectors = []
    for name, email, district, state in INSPECTOR_DATA:
        u = User(name=name, email=email, role="inspector",
                 district=district, state=state)
        u.set_password("demo123")
        db.session.add(u)
        inspectors.append(u)

    # --------------------------------------------------------------- Institutes
    institutes = []
    for idx, row in enumerate(INSTITUTE_DATA):
        name, itype, district, state, lat, lng, cap, risk, grant = row
        inst = Institute(
            name=name, type=itype, district=district, state=state,
            lat=lat, lng=lng, reported_capacity=cap,
            risk_score=risk, grant_amount_lakhs=grant,
            contact_name=f"Manager {idx+1}",
            contact_phone=f"98{idx:08d}",
            ngo_registration_no=f"NGO-2019-{1000+idx}",
            address=f"{idx+1}, Main Road, {district}",
            last_inspection_date=datetime.utcnow() - timedelta(days=random.randint(10, 90)),
        )
        db.session.add(inst)
        institutes.append(inst)

    db.session.flush()  # get IDs

    # ------------------------------------------------------------------ Staff
    staff_users = []
    # Assign ~1-2 staff per institute (20 staff, 15 institutes)
    staff_assignments = []
    for i in range(15):
        staff_assignments.append(i)           # at least one per institute
    for i in range(5):
        staff_assignments.append(i % 15)      # 5 institutes get a second staff

    for idx, (name, inst_idx) in enumerate(zip(STAFF_NAMES, staff_assignments)):
        email = f"staff{idx+1:02d}@demo.in"
        u = User(
            name=name,
            email=email,
            role="staff",
            district=institutes[inst_idx].district,
            state=institutes[inst_idx].state,
            institute_id=institutes[inst_idx].id,
        )
        u.set_password("demo123")
        db.session.add(u)
        staff_users.append(u)

    db.session.flush()

    # --------------------------------------------------------- Attendance records (30 days)
    rng = random.Random(42)  # fixed seed for reproducibility
    for inst in institutes:
        for day_offset in range(30):
            rec_date = today - timedelta(days=30 - day_offset)
            reported = int(inst.reported_capacity * rng.uniform(0.7, 1.0))
            # Simulated CCTV count: mostly close to reported
            cctv = int(reported * rng.uniform(0.92, 1.08))
            mismatch = abs(cctv - reported) / max(reported, 1) > 0.10

            # Scripted: institute[0] (Naya Savera) has a headcount mismatch on latest day
            if inst is institutes[0] and day_offset == 29:
                reported = 48
                cctv = 29       # big mismatch
                mismatch = True

            ar = AttendanceRecord(
                institute_id=inst.id,
                date=rec_date,
                reported_count=reported,
                cctv_count=cctv,
                mismatch_flag=mismatch,
            )
            db.session.add(ar)

    # ------------------------------------------------------------ Inspections & Evidence
    # We create 8 completed inspections with pre-seeded flags
    inspection_data = [
        # (inst_idx, inspector_idx, days_ago, trust_score)
        (3,  0, 25, 92.0),  # clean inspection
        (5,  1, 20, 88.0),  # clean
        (2,  2, 15, 55.0),  # GPS mismatch → flag raised
        (9,  3, 12, 90.0),  # clean
        (6,  4, 10, 45.0),  # duplicate photo → flag
        (6,  0,  8, 48.0),  # duplicate photo (same phash as #5) → flag
        (0,  1,  5, 60.0),  # CCTV mismatch already flagged separately
        (12, 2,  3, 85.0),  # clean
    ]
    inspections = []
    FAKE_PHASH = "aabbccddeeff0011"  # shared perceptual hash for duplicate scenario

    for i_idx, (inst_i, insp_i, days_ago, trust) in enumerate(inspection_data):
        seed_val = f"SEED-{rng.randint(100000,999999)}"
        comp_dt = datetime.utcnow() - timedelta(days=days_ago)
        insp = Inspection(
            institute_id=institutes[inst_i].id,
            inspector_id=inspectors[insp_i].id,
            assigned_at=comp_dt - timedelta(hours=3),
            started_at=comp_dt - timedelta(hours=2),
            completed_at=comp_dt,
            trust_score=trust,
            random_seed=seed_val,
            status="completed",
            notes=f"Routine inspection #{i_idx+1}",
        )
        db.session.add(insp)
        inspections.append(insp)

    db.session.flush()

    # Evidence records (one per inspection)
    for i_idx, insp in enumerate(inspections):
        inst = institutes[inspection_data[i_idx][0]]
        # Normal GPS = institute coordinates + tiny offset
        ev_lat = inst.lat + rng.uniform(-0.0005, 0.0005)
        ev_lng = inst.lng + rng.uniform(-0.0005, 0.0005)
        gps_dist = rng.uniform(10, 80)   # within tolerance

        phash = f"{rng.getrandbits(64):016x}"  # unique hash
        sha = f"{rng.getrandbits(256):064x}"
        suspicious = False

        # Scripted GPS mismatch: inspection index 2
        if i_idx == 2:
            ev_lat = inst.lat + 0.005  # ~555 m away
            ev_lng = inst.lng + 0.005
            gps_dist = 620.0
            suspicious = True

        # Scripted duplicate photo: inspections index 4 & 5 share a phash
        if i_idx in (4, 5):
            phash = FAKE_PHASH
            suspicious = True

        ev = Evidence(
            inspection_id=insp.id,
            photo_path=f"uploads/demo_evidence_{i_idx+1}.jpg",
            sha256_hash=sha,
            perceptual_hash=phash,
            lat=ev_lat,
            lng=ev_lng,
            gps_distance_m=gps_dist,
            otp_code=f"OTP-{rng.randint(100000,999999)}",
            captured_at=insp.completed_at,
            hmac_signature=f"{rng.getrandbits(128):032x}",
            liveness_passed=True,
            is_suspicious=suspicious,
        )
        db.session.add(ev)

    db.session.flush()

    # ------------------------------------------------------------------ Flags
    # 1. GPS mismatch flag (inspection index 2 = inspections[2])
    f1 = Flag(
        institute_id=institutes[2].id,
        inspection_id=inspections[2].id,
        flag_type="gps_mismatch",
        severity="high",
        description=(
            "Inspector GPS location was 620 m from the institute during evidence capture. "
            "Threshold: 200 m. Requires officer review."
        ),
        status="open",
    )
    db.session.add(f1)

    # 2. Duplicate photo flag (inspection index 4)
    f2 = Flag(
        institute_id=institutes[6].id,
        inspection_id=inspections[4].id,
        flag_type="duplicate_photo",
        severity="high",
        description=(
            "Perceptual hash of captured photo matches evidence from a previous inspection "
            "(Inspection #6). Possible reuse of photo."
        ),
        status="open",
    )
    db.session.add(f2)

    # 3. CCTV headcount mismatch flag (institute[0])
    f3 = Flag(
        institute_id=institutes[0].id,
        inspection_id=inspections[6].id,
        flag_type="cctv_headcount_mismatch",
        severity="high",
        description=(
            "Naya Savera Shelter Home: Staff reported 48 residents but CCTV headcount "
            "detected only 29. Discrepancy: 39.6% (threshold: 10%)."
        ),
        status="open",
    )
    db.session.add(f3)

    # 4. Unusual attendance flag (institute[12])
    f4 = Flag(
        institute_id=institutes[12].id,
        flag_type="unusual_attendance",
        severity="medium",
        description=(
            "Aadhar Shelter Home attendance has remained exactly at 54 for 7 consecutive days. "
            "Statistical anomaly detected."
        ),
        status="open",
    )
    db.session.add(f4)

    # 5. Missed VC flag (institute[7])
    f5 = Flag(
        institute_id=institutes[7].id,
        flag_type="missed_vc",
        severity="medium",
        description=(
            "Staff at Mamta Bal Griha did not respond to random video-call check within "
            "60-second deadline. Call marked as missed."
        ),
        status="open",
    )
    db.session.add(f5)

    # 6. A resolved flag (for variety)
    f6 = Flag(
        institute_id=institutes[3].id,
        flag_type="unusual_attendance",
        severity="low",
        description="Minor attendance dip detected. Verified as a public holiday.",
        status="dismissed",
        officer_comment="Verified with institute - state public holiday on that date.",
        staff_response="25 Oct was Dussehra holiday, residents were on leave.",
        resolved_at=datetime.utcnow() - timedelta(days=5),
    )
    db.session.add(f6)

    # ----------------------------------------------------------- Missed VC request
    # Find a staff member at institute[7]
    staff_at_7 = next(
        (s for s in staff_users if s.institute_id == institutes[7].id), staff_users[7]
    )
    vc = VCRequest(
        institute_id=institutes[7].id,
        staff_id=staff_at_7.id,
        officer_id=officer.id,
        room_name="sih26095-scripted-missed-vc-001",
        requested_at=datetime.utcnow() - timedelta(days=3),
        deadline=datetime.utcnow() - timedelta(days=3, seconds=-60),
        status="missed",
    )
    db.session.add(vc)

    # ----------------------------------------------------------- Audit log entries
    audit_entries = [
        (None, "system_start", "system", None,
         json.dumps({"message": "Application started, seed data loaded."})),
        (None, "inspection_assigned", "Inspection", 1,
         json.dumps({"seed": inspections[0].random_seed, "institute": institutes[3].name})),
        (None, "flag_raised", "Flag", 1,
         json.dumps({"type": "gps_mismatch", "institute": institutes[2].name})),
        (None, "vc_missed", "VCRequest", 1,
         json.dumps({"institute": institutes[7].name, "staff": staff_at_7.name})),
    ]
    for actor_id, action, etype, eid, detail in audit_entries:
        log = AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=etype,
            entity_id=eid,
            detail_json=detail,
        )
        db.session.add(log)

    db.session.commit()
    print(f"[SEED] Created: 1 officer, {len(inspectors)} inspectors, "
          f"{len(staff_users)} staff, {len(institutes)} institutes, "
          f"{len(inspections)} inspections, 5 open flags.")
