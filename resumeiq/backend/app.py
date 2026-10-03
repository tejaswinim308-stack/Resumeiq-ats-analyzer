"""
ResumeIQ Flask application entrypoint.

Run locally with:   python app.py
Run in production with:   gunicorn -b 0.0.0.0:$PORT app:app
"""
import logging
import os
from dotenv import load_dotenv

load_dotenv()  # no-op in Cloud Run (no .env file there); loads local .env for dev

from flask import Flask, jsonify, make_response, request, send_from_directory

from config import Config
from utils.errors import AppError

logging.basicConfig(level=logging.INFO if not Config.DEBUG else logging.DEBUG)
logger = logging.getLogger("resumeiq")


def _is_origin_allowed(origin: str, allowed: set) -> bool:
    if not allowed or origin in allowed:
        return True
    if Config.DEBUG and origin:
        if origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:"):
            return True
    return False


def _configure_cors(app: Flask) -> None:
    """Minimal, dependency-free CORS handling: only the origins listed in
    ALLOWED_ORIGINS (or local dev origins in debug mode) may call /api/*.
    Credentials are not used (auth is a Bearer token, not a cookie), so
    we never echo back Access-Control-Allow-Credentials.
    """
    allowed = set(Config.ALLOWED_ORIGINS)

    @app.before_request
    def _handle_preflight():
        if request.method == "OPTIONS" and request.path.startswith("/api/"):
            # Create a clean empty 200 OK response for OPTIONS preflight
            resp = make_response("", 200)
            origin = request.headers.get("Origin", "")
            if _is_origin_allowed(origin, allowed):
                resp.headers["Access-Control-Allow-Origin"] = origin or "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            resp.headers["Access-Control-Max-Age"] = "3600"
            return resp

    @app.after_request
    def _add_cors_headers(response):
        if request.path.startswith("/api/"):
            origin = request.headers.get("Origin", "")
            if _is_origin_allowed(origin, allowed):
                response.headers["Access-Control-Allow-Origin"] = origin or "*"
                response.headers.setdefault("Vary", "Origin")
        return response


def create_app() -> Flask:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.abspath(os.path.join(base_dir, "..", "frontend"))
    if not os.path.exists(frontend_dir):
        frontend_dir = os.path.abspath(os.path.join(base_dir, "frontend"))

    app = Flask(
        __name__,
        static_folder=frontend_dir if os.path.exists(frontend_dir) else None,
        static_url_path="",
    )
    app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024  # hard cap slightly above 10MB limit

    _configure_cors(app)

    from routes.health import health_bp
    from routes.analyze import analyze_bp
    from routes.auth import auth_bp
    from routes.history import history_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(analyze_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(history_bp)

    if os.path.exists(frontend_dir):
        @app.route("/", methods=["GET"])
        def serve_index():
            return send_from_directory(frontend_dir, "index.html")

        @app.route("/<path:filename>", methods=["GET"])
        def serve_static(filename):
            if filename.startswith("api/"):
                return (
                    jsonify({"success": False, "error": {"code": "not_found", "message": "The requested resource was not found."}}),
                    404,
                )
            file_path = os.path.join(frontend_dir, filename)
            if os.path.exists(file_path) and not os.path.isdir(file_path):
                return send_from_directory(frontend_dir, filename)
            return send_from_directory(frontend_dir, "index.html")

    @app.errorhandler(AppError)
    def handle_app_error(err: AppError):
        if err.status_code >= 500:
            logger.exception("Application error: %s", err.message)
        else:
            logger.info("Client error [%s]: %s", err.error_code, err.message)
        return jsonify(err.to_dict()), err.status_code

    @app.errorhandler(413)
    def handle_too_large(_err):
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "file_too_large",
                        "message": "Upload is too large. Maximum allowed size is 10 MB.",
                    },
                }
            ),
            413,
        )

    @app.errorhandler(404)
    def handle_not_found(_err):
        return (
            jsonify({"success": False, "error": {"code": "not_found", "message": "The requested resource was not found."}}),
            404,
        )

    @app.errorhandler(405)
    def handle_method_not_allowed(_err):
        return (
            jsonify({"success": False, "error": {"code": "method_not_allowed", "message": "Method not allowed on this endpoint."}}),
            405,
        )

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        logger.exception("Unhandled exception: %s", str(err))
        error_message = str(err) if Config.DEBUG else "Something went wrong on our end. Please try again shortly."
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "internal_error",
                        "message": error_message,
                    },
                }
            ),
            500,
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)