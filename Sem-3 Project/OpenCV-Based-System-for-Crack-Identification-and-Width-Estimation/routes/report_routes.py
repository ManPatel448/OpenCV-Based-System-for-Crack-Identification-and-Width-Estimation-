import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, send_file

from models.analysis_model import get_analysis
from models.image_model import list_images
from models.measurement_model import list_measurements
from services.csv_service import create_csv
from services.pdf_service import create_pdf
from services.storage_service import analysis_dir
from services.zip_service import create_manifest, create_zip

report_bp = Blueprint("reports", __name__)


@report_bp.get("/reports")
def reports():
    return render_template("reports.html")


def build_report(analysis_id, report_type):
    analysis = get_analysis(analysis_id)
    if not analysis:
        return None
    images = list_images(analysis_id)
    measurements = list_measurements(analysis_id)
    root = analysis_dir(current_app.config["STORAGE_DIR"], analysis_id)
    report_dir = root / "reports"
    report_dir.mkdir(exist_ok=True)
    if report_type == "csv":
        path = report_dir / f"{analysis_id}.csv"
        return create_csv(analysis, images, measurements, path)
    if report_type == "pdf":
        path = report_dir / f"{analysis_id}.pdf"
        return create_pdf(analysis, images, measurements, path)
    csv_path = build_report(analysis_id, "csv")
    pdf_path = build_report(analysis_id, "pdf")
    manifest_path = create_manifest(analysis, images, measurements, report_dir / f"{analysis_id}_manifest.txt")
    return create_zip(analysis_id, root, [csv_path, pdf_path, manifest_path], report_dir / f"{analysis_id}.zip")


@report_bp.get("/reports/<analysis_id>/<report_type>")
def download_report(analysis_id, report_type):
    if report_type not in {"csv", "pdf", "zip"}:
        return jsonify({"ok": False, "error": "Unknown report type."}), 400
    path = build_report(analysis_id, report_type)
    return send_file(path, as_attachment=True, download_name=Path(path).name) if path else ("Analysis not found", 404)
