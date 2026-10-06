from flask import Blueprint
officer_bp = Blueprint("officer", __name__, template_folder="../../templates/officer")
from . import routes  # noqa: F401, E402
