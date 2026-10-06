"""
Automated unit and integration test for Step 1.
Tests database models, demo seeding, authentication, and role-based access.
"""

import unittest
from app import app
from models import db, User, Institute, Inspection

class Step1TestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_database_counts(self):
        """Verify seeded data meets SIH26095 requirements."""
        with app.app_context():
            officer_count = User.query.filter_by(role='officer').count()
            inspector_count = User.query.filter_by(role='inspector').count()
            institute_count = Institute.query.count()

            self.assertEqual(officer_count, 1, "Expected 1 officer")
            self.assertEqual(inspector_count, 5, "Expected 5 inspectors")
            self.assertEqual(institute_count, 15, "Expected 15 institutes")

            # Check that each inspector has a home district
            inspectors = User.query.filter_by(role='inspector').all()
            for insp in inspectors:
                self.assertIsNotNone(insp.home_district)
                self.assertTrue(len(insp.home_district) > 0)

            # Check risk scores are bounded [0, 100]
            institutes = Institute.query.all()
            for inst in institutes:
                self.assertGreaterEqual(inst.risk_score, 0)
                self.assertLessEqual(inst.risk_score, 100)

    def test_unauthenticated_redirect(self):
        """Unauthenticated requests must redirect to /login."""
        response = self.client.get('/', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/login' in response.headers['Location'])

    def test_officer_login_and_access(self):
        """Officer can log in and view the officer dashboard."""
        response = self.client.post('/login', data={
            'username': 'officer1',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Officer Management Dashboard", response.data)
        self.assertIn(b"Sample Shelter 01", response.data)

    def test_inspector_login_and_access(self):
        """Inspector can log in and view their personal inspector portal."""
        response = self.client.post('/login', data={
            'username': 'inspector1',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Inspector Profile", response.data)
        self.assertIn(b"Pune", response.data)

    def test_role_enforcement(self):
        """Inspector attempting to view /officer must be rejected."""
        # Log in as inspector
        self.client.post('/login', data={
            'username': 'inspector1',
            'password': 'password123'
        }, follow_redirects=True)

        # Attempt to access officer dashboard
        response = self.client.get('/officer', follow_redirects=True)
        self.assertIn(b"Access denied", response.data)

if __name__ == '__main__':
    unittest.main()
