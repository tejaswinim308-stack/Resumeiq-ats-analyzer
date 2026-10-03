"""Shared helper for reading a Firebase ID token out of the Authorization
header and verifying it. Used by any route that needs to know who the
caller is (profile, history)."""
from flask import request

from services.firebase_service import verify_id_token
from utils.errors import AuthenticationError


def get_uid_from_request() -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise AuthenticationError("Missing or malformed Authorization header. Expected 'Bearer <token>'.")
    token = header[len("Bearer "):].strip()
    return verify_id_token(token)
