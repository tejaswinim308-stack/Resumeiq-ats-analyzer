"""
Firebase Authentication + Firestore persistence.

Design notes:
- We NEVER store the raw uploaded PDF -- only the structured analysis
  result (per the security requirements). Nothing binary ever reaches
  Firestore.
- All Firestore access here is scoped by the caller's verified Firebase
  UID; routes never accept a client-supplied user id.
- If Firebase isn't configured (no FIREBASE_PROJECT_ID / credentials),
  every function here raises a controlled FirebaseError instead of
  crashing the process, so the analyze flow can still run without
  history/auth in local development.
"""

import datetime
import uuid

from config import Config
from utils.errors import AuthenticationError, FirebaseError, NotFoundError

_firebase_app = None
_firestore_client = None
_initialization_attempted = False


def _init():
    global _firebase_app, _firestore_client, _initialization_attempted
    if _initialization_attempted:
        return
    _initialization_attempted = True

    if not Config.firebase_configured():
        return

    # In local development without credentials, skip ApplicationDefault probe
    # to avoid blocking on the unreachable GCE metadata server (169.254.169.254).
    import os
    if not Config.GOOGLE_APPLICATION_CREDENTIALS and not os.environ.get("K_SERVICE"):
        return

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if Config.GOOGLE_APPLICATION_CREDENTIALS:
            cred = credentials.Certificate(Config.GOOGLE_APPLICATION_CREDENTIALS)
            _firebase_app = firebase_admin.initialize_app(cred, {"projectId": Config.FIREBASE_PROJECT_ID})
        else:
            # Application Default Credentials (recommended on Cloud Run:
            # grant the Cloud Run service account Firestore/Firebase roles).
            cred = credentials.ApplicationDefault()
            _firebase_app = firebase_admin.initialize_app(cred, {"projectId": Config.FIREBASE_PROJECT_ID})
        _firestore_client = firestore.client()
    except Exception:  # noqa: BLE001 - any init failure -> treated as "not configured"
        _firebase_app = None
        _firestore_client = None


def is_available() -> bool:
    _init()
    return _firestore_client is not None


def verify_id_token(id_token: str) -> str:
    """Verify a Firebase Auth ID token and return the caller's UID.

    Raises AuthenticationError on any failure (missing token, expired,
    malformed, Firebase not configured) -- never leaks the underlying
    exception detail to the client.
    """
    _init()
    if not id_token:
        raise AuthenticationError("Missing authentication token.")
    if _firebase_app is None:
        raise FirebaseError("Authentication is not available right now. Please try again later.")

    try:
        from firebase_admin import auth as firebase_auth

        decoded = firebase_auth.verify_id_token(id_token)
        return decoded["uid"]
    except Exception as exc:  # noqa: BLE001
        raise AuthenticationError("Invalid or expired authentication token.") from exc


def upsert_profile(uid: str, profile_data: dict) -> dict:
    _init()
    if _firestore_client is None:
        raise FirebaseError("Profile storage is not available right now. Please try again later.")

    doc_ref = _firestore_client.collection("users").document(uid)
    payload = {
        "displayName": profile_data.get("displayName", ""),
        "email": profile_data.get("email", ""),
        "updatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    doc_ref.set(payload, merge=True)
    snapshot = doc_ref.get()
    return snapshot.to_dict() or {}


def save_analysis(uid: str, analysis: dict) -> str:
    """Persist a completed analysis result under the user's history.
    Never receives or stores the raw PDF bytes -- only the already
    structured/scored JSON. Returns the generated analysis_id."""
    _init()
    analysis_id = analysis.get("analysis_id") or str(uuid.uuid4())

    if _firestore_client is None:
        # History persistence is best-effort: the analysis itself has
        # already succeeded and been returned to the user, so we don't
        # fail the whole request just because Firestore is unavailable.
        return analysis_id

    try:
        doc_ref = (
            _firestore_client.collection("users").document(uid).collection("history").document(analysis_id)
        )
        record = dict(analysis)
        record["analysis_id"] = analysis_id
        record["user_id"] = uid
        record["createdAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        doc_ref.set(record)
    except Exception:  # noqa: BLE001 - never fail the analyze request over a persistence hiccup
        pass

    return analysis_id


def list_history(uid: str, limit: int = 25) -> list:
    _init()
    if _firestore_client is None:
        raise FirebaseError("History is not available right now. Please try again later.")

    try:
        docs = (
            _firestore_client.collection("users")
            .document(uid)
            .collection("history")
            .order_by("createdAt", direction="DESCENDING")
            .limit(limit)
            .stream()
        )
        results = []
        for d in docs:
            data = d.to_dict()
            results.append(
                {
                    "analysis_id": d.id,
                    "createdAt": data.get("createdAt"),
                    "job": {"title": (data.get("job") or {}).get("title", "")},
                    "score": (data.get("score") or {}).get("overall", 0),
                }
            )
        return results
    except Exception as exc:  # noqa: BLE001
        raise FirebaseError("Could not load history right now.") from exc


def get_analysis(uid: str, analysis_id: str) -> dict:
    _init()
    if _firestore_client is None:
        raise FirebaseError("History is not available right now. Please try again later.")

    doc_ref = _firestore_client.collection("users").document(uid).collection("history").document(analysis_id)
    snapshot = doc_ref.get()
    if not snapshot.exists:
        raise NotFoundError("Analysis not found.")
    return snapshot.to_dict()


def delete_analysis(uid: str, analysis_id: str) -> None:
    _init()
    if _firestore_client is None:
        raise FirebaseError("History is not available right now. Please try again later.")

    doc_ref = _firestore_client.collection("users").document(uid).collection("history").document(analysis_id)
    snapshot = doc_ref.get()
    if not snapshot.exists:
        raise NotFoundError("Analysis not found.")
    doc_ref.delete()
