from flask import Blueprint, jsonify, request

from services import firebase_service
from utils.auth import get_uid_from_request
from utils.validators import sanitize_text_input

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/profile", methods=["POST"])
def upsert_profile():
    """Create/update the caller's profile document. Requires a valid
    Firebase ID token in the Authorization header."""
    uid = get_uid_from_request()

    body = request.get_json(silent=True) or {}
    profile_data = {
        "displayName": sanitize_text_input(body.get("displayName", ""), max_length=200),
        "email": sanitize_text_input(body.get("email", ""), max_length=200),
    }

    saved = firebase_service.upsert_profile(uid, profile_data)
    return jsonify({"success": True, "profile": saved}), 200
