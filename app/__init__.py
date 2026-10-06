"""
Flask application factory.
All extensions are initialised here so there are no circular imports.
"""
from flask import Flask, redirect, url_for
from flask_login import current_user

from .extensions import db, login_manager, scheduler


def create_app():
    app = Flask(__name__)

    # ------------------------------------------------------------------ config
    app.config["SECRET_KEY"] = "sih26095-dev-secret-change-in-production"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///monitoring.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SCHEDULER_API_ENABLED"] = False

    # --------------------------------------------------------- init extensions
    db.init_app(app)
    login_manager.init_app(app)

    # ---------------------------------------------------- flask-login settings
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return db.session.get(User, int(user_id))

    # ------------------------------------------------------- register blueprints
    from .blueprints.auth import auth_bp
    from .blueprints.officer import officer_bp
    from .blueprints.inspector import inspector_bp
    from .blueprints.staff import staff_bp
    from .blueprints.api import api_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(officer_bp, url_prefix="/officer")
    app.register_blueprint(inspector_bp, url_prefix="/inspector")
    app.register_blueprint(staff_bp, url_prefix="/staff")
    app.register_blueprint(api_bp, url_prefix="/api")

    # ----------------------------------------------------------- root redirect
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            role_map = {
                "officer": "officer.overview",
                "inspector": "inspector.tasks",
                "staff": "staff.attendance",
            }
            return redirect(url_for(role_map.get(current_user.role, "auth.login")))
        return redirect(url_for("auth.login"))

    # --------------------------------- create tables + seed demo data on startup
    with app.app_context():
        db.create_all()
        from .seed import seed_if_empty
        seed_if_empty()

    # --------------------------------- APScheduler Background Jobs (VC Deadline Monitor)
    def _vc_deadline_job():
        with app.app_context():
            from .services.vc import check_and_expire_pending_vcs
            check_and_expire_pending_vcs()

    # Only add job once and start scheduler
    if not scheduler.running:
        scheduler.add_job(
            id="vc_deadline_checker",
            func=_vc_deadline_job,
            trigger="interval",
            seconds=5,
            replace_existing=True,
        )
        try:
            scheduler.start()
        except Exception as e:
            print("[Scheduler] Notice:", e)

    return app
