from flask import Blueprint, jsonify

from config import Config
from services.firebase_service import is_available as firebase_is_available

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health", methods=["GET"])
def health():
    """Liveness/readiness probe. Also reports (without secrets) whether
    downstream dependencies are configured, which is useful for quickly
    diagnosing a "why isn't analyze working" report."""
    return (
        jsonify(
            {
                "success": True,
                "status": "ok",
                "gemini_configured": Config.gemini_configured(),
                "firebase_configured": firebase_is_available(),
            }
        ),
        200,
    )
