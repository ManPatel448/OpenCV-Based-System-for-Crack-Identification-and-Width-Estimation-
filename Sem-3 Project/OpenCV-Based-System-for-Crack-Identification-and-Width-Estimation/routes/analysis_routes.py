from pathlib import Path
from collections import Counter

from flask import Blueprint, current_app, jsonify, render_template, request, send_file

from models.analysis_model import get_analysis, update_analysis, now
from models.image_model import list_images
from models.measurement_model import list_measurements, create_measurements
from services.image_service import load_and_resize
from services.preprocessing_service import preprocess
from services.detection_service import detect_components, filter_crack_components
from services.measurement_service import measure_component
from utils.file_utils import is_within

analysis_bp = Blueprint("analysis", __name__)


def serialize(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items() if k != "_id"}
    if isinstance(value, list):
        return [serialize(v) for v in value]
    return value


def _ensure_measurements(analysis_id, analysis, images):
    """Auto-compute measurements for historical or synced analyses if not in database."""
    all_measurements = []
    cfg = current_app.config["PROCESSING"]
    pixels_per_mm = analysis.get("pixels_per_mm") or current_app.config.get("DEFAULT_PIXELS_PER_MM", 10.0)
    thresholds = analysis.get("severity_thresholds") or cfg["severity_thresholds"]

    for record in images:
        orig_path = record.get("original_path")
        if not orig_path or not Path(orig_path).exists():
            continue
        try:
            image, _ = load_and_resize(orig_path, cfg["resize_max_dimension"])
            stages = preprocess(image, cfg)
            cleaned, mask, components = detect_components(stages["binary"], cfg)
            components = filter_crack_components(components, cfg)
            for idx, component in enumerate(components, 1):
                measurement = measure_component(component, pixels_per_mm, thresholds)
                measurement.pop("skeleton", None)
                measurement.pop("distance_transform", None)
                measurement.pop("width_estimation", None)
                measurement.update({
                    "crack_id": f"{record['image_id'][:8]}-{idx}",
                    "analysis_id": analysis_id,
                    "image_id": record["image_id"],
                    "created_at": now(),
                })
                all_measurements.append(measurement)
        except Exception:
            continue

    if all_measurements:
        create_measurements(all_measurements)
        update_analysis(analysis_id, {"total_detected_regions": len(all_measurements), "status": "Completed"})
    return all_measurements


@analysis_bp.get("/analysis/<analysis_id>")
def analysis_page(analysis_id):
    analysis = get_analysis(analysis_id)
    if not analysis:
        return render_template("analysis_not_found.html", analysis_id=analysis_id), 404
    if not analysis.get("severity_thresholds") or not isinstance(analysis.get("severity_thresholds"), dict) or "good_max_width_px" not in analysis["severity_thresholds"]:
        analysis["severity_thresholds"] = current_app.config["PROCESSING"]["severity_thresholds"]
    if not analysis.get("pixels_per_mm"):
        analysis["pixels_per_mm"] = current_app.config.get("DEFAULT_PIXELS_PER_MM", 10.0)
    images = list_images(analysis_id)
    measurements = list_measurements(analysis_id)
    if not measurements and images:
        measurements = _ensure_measurements(analysis_id, analysis, images)

    counts = Counter(item.get("severity", "Unknown") for item in measurements)
    total = len(measurements)
    summary = {
        "total_cracks": total,
        "total_length_px": sum(item.get("skeleton_length_px", 0) for item in measurements),
        "total_length_mm": sum(item.get("skeleton_length_mm", 0) for item in measurements),
        "average_width_px": sum(item.get("mean_width_px", 0) for item in measurements) / total if total else 0,
        "average_width_mm": sum(item.get("mean_width_mm", 0) for item in measurements) / total if total else 0,
        "maximum_width_px": max((item.get("max_width_px", 0) for item in measurements), default=0),
        "maximum_width_mm": max((item.get("max_width_mm", 0) for item in measurements), default=0),
        "minimum_width_px": min((item.get("mean_width_px", 0) for item in measurements), default=0),
        "minimum_width_mm": min((item.get("mean_width_mm", 0) for item in measurements), default=0),
        "good_count": counts.get("Good", 0),
        "medium_count": counts.get("Medium", 0),
        "heavy_count": counts.get("Heavy", 0),
        "overall_severity": "Heavy" if counts.get("Heavy", 0) else "Medium" if counts.get("Medium", 0) else "Good" if total else "No data",
    }
    for key in ("good_count", "medium_count", "heavy_count"):
        summary[f"{key}_percentage"] = summary[key] / total * 100 if total else 0
    if not total:
        summary["remark"] = "No crack measurements were produced. Upload a clearer crack image for another analysis."
    elif summary["heavy_count"]:
        summary["remark"] = (
            f"Heavy-severity indications were detected in {summary['heavy_count']} of {total} crack region(s). "
            "Review the annotated image and arrange a qualified structural inspection."
        )
    elif summary["medium_count"]:
        summary["remark"] = (
            f"Medium-severity indications were detected in {summary['medium_count']} of {total} crack region(s). "
            "Monitor the affected area and consider a qualified inspection."
        )
    else:
        summary["remark"] = (
            f"All {total} detected crack region(s) are in the Good software category. "
            "Continue routine monitoring because image-based results are not a structural safety assessment."
        )
    return render_template("results.html", analysis=analysis, images=images, measurements=measurements, summary=summary)


@analysis_bp.get("/api/analysis/<analysis_id>")
def analysis_api(analysis_id):
    analysis = get_analysis(analysis_id)
    if not analysis:
        return jsonify({"ok": False, "error": "Analysis not found."}), 404
    images = list_images(analysis_id)
    measurements = list_measurements(analysis_id)
    if not measurements and images:
        measurements = _ensure_measurements(analysis_id, analysis, images)
    return jsonify({"ok": True, "analysis": serialize(analysis), "images": serialize(images), "measurements": serialize(measurements)})


@analysis_bp.get("/files/<analysis_id>/<image_id>/<file_type>")
def file_route(analysis_id, image_id, file_type):
    allowed = {"original": "original_path", "annotated": "annotated_path"}
    images = list_images(analysis_id)
    image = next((item for item in images if item["image_id"] == image_id), None)
    if not image or file_type not in allowed:
        return "File not found", 404
    path = image.get(allowed[file_type])
    if not path or not is_within(Path(current_app.config["STORAGE_DIR"]) / "analyses" / analysis_id, path):
        return "File not found", 404
    return send_file(path)


@analysis_bp.get("/files/<analysis_id>/<image_id>/processed/<stage>")
def processed_file_route(analysis_id, image_id, stage):
    image = next((item for item in list_images(analysis_id) if item["image_id"] == image_id), None)
    path = image.get("processed_paths", {}).get(stage) if image else None
    root = Path(current_app.config["STORAGE_DIR"]) / "analyses" / analysis_id
    if not path or not is_within(root, path):
        return "File not found", 404
    return send_file(path)
