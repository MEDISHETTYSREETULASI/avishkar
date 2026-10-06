from flask import Blueprint
inspector_bp = Blueprint("inspector", __name__, template_folder="../../templates/inspector")
from . import routes  # noqa: F401, E402
