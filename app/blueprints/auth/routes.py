from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from . import auth_bp
from ...extensions import db
from ...models import User, AuditLog


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        user = User.query.filter(db.func.lower(User.email) == email).first()

        if user and user.check_password(password) and user.is_active_account:
            login_user(user, remember=True)
            log = AuditLog(
                actor_id=user.id,
                action="login",
                entity_type="User",
                entity_id=user.id,
                ip_address=request.remote_addr,
            )
            db.session.add(log)
            db.session.commit()
            next_url = request.args.get("next")
            return redirect(next_url or url_for("index"))
        else:
            error = "Invalid email or password. Please try 'officer@demo.in' and 'demo123' or use 1-Click Quick Login below."

    return render_template("auth/login.html", error=error)


@auth_bp.route("/quick-login/<role>")
def quick_login(role):
    """Instant 1-click login for demo roles."""
    role_email_map = {
        "officer": "officer@demo.in",
        "inspector": "inspector1@demo.in",
        "staff": "staff01@demo.in",
    }
    target_email = role_email_map.get(role, "officer@demo.in")
    user = User.query.filter(db.func.lower(User.email) == target_email).first()

    if not user:
        user = User.query.filter_by(role=role).first()

    if user:
        login_user(user, remember=True)
        log = AuditLog(
            actor_id=user.id,
            action="quick_login",
            entity_type="User",
            entity_id=user.id,
            ip_address=request.remote_addr,
        )
        db.session.add(log)
        db.session.commit()
        return redirect(url_for("index"))

    flash("User account not found. Please re-seed.", "error")
    return redirect(url_for("auth.login"))


@auth_bp.route("/logout")
@login_required
def logout():
    log = AuditLog(
        actor_id=current_user.id,
        action="logout",
        entity_type="User",
        entity_id=current_user.id,
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()
    logout_user()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("auth.login"))
