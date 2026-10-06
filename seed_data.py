"""Create fake Step 1 users, institutes, and Step 2 inspection history in an empty database."""
from datetime import datetime, timedelta, timezone
from models import db, Institute, Inspection, User
from werkzeug.security import generate_password_hash


def seed_database():
    """Seed only an empty database; never replace existing rows."""
    if User.query.first() or Institute.query.first():
        return

    db.session.add(User(
        username='officer1', password=generate_password_hash('password123'),
        full_name='Demo Officer', role='officer',
    ))

    # These names are labels for sample data, not real NGOs or facilities.
    inspector_rows = [
        ('inspector1', 'Pune'), ('inspector2', 'Nagpur'),
        ('inspector3', 'Nashik'), ('inspector4', 'Thane'),
        ('inspector5', 'Aurangabad'),
    ]
    for username, district in inspector_rows:
        db.session.add(User(
            username=username, password=generate_password_hash('password123'),
            full_name=f'Demo Inspector {username[-1]}', role='inspector',
            home_district=district,
        ))

    # Approximate district coordinates are illustrative and do not identify institutes.
    institute_rows = [
        ('Sample Shelter 01', 'Shelter Home', 'Pune', 18.5204, 73.8567, 88),
        ('Sample Recovery Centre 02', 'De-addiction Centre', 'Pune', 18.5312, 73.8445, 62),
        ('Sample Hostel 03', 'Hostel', 'Pune', 18.5089, 73.8299, 25),
        ('Sample Shelter 04', 'Shelter Home', 'Nagpur', 21.1458, 79.0882, 92),
        ('Sample Recovery Centre 05', 'De-addiction Centre', 'Nagpur', 21.1307, 79.0621, 74),
        ('Sample Hostel 06', 'Hostel', 'Nagpur', 21.1610, 79.1023, 40),
        ('Sample Shelter 07', 'Shelter Home', 'Nashik', 19.9975, 73.7898, 81),
        ('Sample Recovery Centre 08', 'De-addiction Centre', 'Nashik', 20.0112, 73.7741, 55),
        ('Sample Hostel 09', 'Hostel', 'Nashik', 19.9823, 73.8012, 18),
        ('Sample Shelter 10', 'Shelter Home', 'Thane', 19.2183, 72.9781, 79),
        ('Sample Recovery Centre 11', 'De-addiction Centre', 'Thane', 19.2014, 72.9642, 68),
        ('Sample Hostel 12', 'Hostel', 'Thane', 19.2291, 72.9899, 32),
        ('Sample Shelter 13', 'Shelter Home', 'Aurangabad', 19.8762, 75.3433, 85),
        ('Sample Recovery Centre 14', 'De-addiction Centre', 'Aurangabad', 19.8621, 75.3289, 48),
        ('Sample Hostel 15', 'Hostel', 'Aurangabad', 19.8890, 75.3567, 15),
    ]
    for name, institute_type, district, latitude, longitude, risk_score in institute_rows:
        db.session.add(Institute(
            name=name, type=institute_type, district=district,
            latitude=latitude, longitude=longitude, risk_score=risk_score,
        ))
    db.session.commit()

    # Fake completed visits provide last-inspected dates and a prior inspector.
    # Sample Shelter 04 and Sample Shelter 10 are deliberately never inspected.
    never_inspected = {4, 10}
    inspectors = User.query.filter_by(role='inspector').order_by(User.id).all()
    now = datetime.now(timezone.utc)
    for index, institute in enumerate(Institute.query.order_by(Institute.id).all(), start=1):
        if index in never_inspected:
            continue
        visit_time = now - timedelta(days=15 + index * 17)
        db.session.add(Inspection(
            institute_id=institute.id,
            inspector_id=inspectors[(index - 1) % len(inspectors)].id,
            assigned_at=visit_time,
            completed_at=visit_time,
            status='completed',
        ))
    db.session.commit()
