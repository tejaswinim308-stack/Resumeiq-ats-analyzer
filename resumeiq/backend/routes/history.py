from flask import Blueprint, jsonify, request

from services import firebase_service
from utils.auth import get_uid_from_request

history_bp = Blueprint("history", __name__)


@history_bp.route("/api/history", methods=["GET"])
def list_history():
    uid = get_uid_from_request()
    limit = request.args.get("limit", default=25, type=int)
    limit = max(1, min(limit or 25, 100))
    results = firebase_service.list_history(uid, limit=limit)
    return jsonify({"success": True, "history": results}), 200


@history_bp.route("/api/history/<analysis_id>", methods=["GET"])
def get_history_item(analysis_id):
    uid = get_uid_from_request()
    analysis = firebase_service.get_analysis(uid, analysis_id)
    return jsonify({"success": True, "analysis": analysis}), 200


@history_bp.route("/api/history/<analysis_id>", methods=["DELETE"])
def delete_history_item(analysis_id):
    uid = get_uid_from_request()
    firebase_service.delete_analysis(uid, analysis_id)
    return jsonify({"success": True, "deleted": analysis_id}), 200
