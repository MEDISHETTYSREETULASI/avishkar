from flask import Blueprint
staff_bp = Blueprint("staff", __name__, template_folder="../../templates/staff")
from . import routes  # noqa: F401, E402
