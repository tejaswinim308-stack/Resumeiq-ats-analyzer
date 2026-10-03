"""Application configuration, loaded from environment variables.

Never hard-code secrets here. In local development, values come from a
.env file (loaded via python-dotenv in app.py) copied from .env.example.
In Cloud Run, they come from the environment / Secret Manager.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()


class Config:
    # --- Server ---
    PORT = int(os.environ.get("PORT", 8080))
    HOST = "0.0.0.0"
    FLASK_ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = FLASK_ENV == "development"

    # --- CORS ---
    # Comma-separated list of allowed origins. Defaults to permissive for
    # local dev; set explicitly in production.
    ALLOWED_ORIGINS = [
        o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500").split(",") if o.strip()
    ]

    # --- Gemini ---
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_TIMEOUT_SECONDS = int(os.environ.get("GEMINI_TIMEOUT_SECONDS", 45))

    # --- Firebase ---
    FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "")
    # Path to a service account JSON file. In Cloud Run, prefer Application
    # Default Credentials (leave this unset) with the Cloud Run service
    # account granted Firestore/Firebase Admin access instead.
    GOOGLE_APPLICATION_CREDENTIALS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

    @classmethod
    def gemini_configured(cls) -> bool:
        return bool(cls.GEMINI_API_KEY)

    @classmethod
    def firebase_configured(cls) -> bool:
        return bool(cls.FIREBASE_PROJECT_ID)
