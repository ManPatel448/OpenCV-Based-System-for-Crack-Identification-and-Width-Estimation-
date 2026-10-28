from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from models.analysis_model import delete_analysis_records, list_analyses
from models.database import get_db
from services.storage_service import remove_analysis
from flask import current_app

history_bp = Blueprint("history", __name__)


@history_bp.get("/history")
def history():
    return render_template("history.html", analyses=list_analyses(limit=100))


@history_bp.get("/api/history")
def history_api():
    query = {}
    search = request.args.get("q")
    if search:
        query = {"analysis_name": {"$regex": search, "$options": "i"}}
    return jsonify({"ok": True, "analyses": [{k: v for k, v in item.items() if k != "_id"} for item in list_analyses(query, limit=100)]})


@history_bp.delete("/api/analysis/<analysis_id>")
def delete(analysis_id):
    delete_analysis_records(analysis_id)
    remove_analysis(current_app.config["STORAGE_DIR"], analysis_id)
    return jsonify({"ok": True})
