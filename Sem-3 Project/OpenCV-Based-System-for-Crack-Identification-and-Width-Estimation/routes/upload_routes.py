import time
import uuid
from pathlib import Path

import cv2
from flask import Blueprint, current_app, jsonify, render_template, request
import numpy as np

from models.analysis_model import create_analysis, delete_analysis_records, get_analysis, now, update_analysis
from models.image_model import create_image, list_images, update_image
from models.measurement_model import create_measurements
from services.detection_service import detect_components, filter_crack_components, validate_crack_image
from services.image_service import load_and_resize, write_image
from services.measurement_service import annotate, measure_component
from services.preprocessing_service import preprocess
from services.storage_service import analysis_dir, remove_analysis
from utils.file_utils import safe_filename
from utils.validators import validate_upload

upload_bp = Blueprint("upload", __name__)


@upload_bp.get("/upload")
def upload_page():
    return render_template("upload.html")


def _validate_files(files):
    if not files:
        return "Select at least one image."
    if len(files) > current_app.config["MAX_FILES_PER_ANALYSIS"]:
        return "Too many images in one analysis."
    for file in files:
        error = validate_upload(file, current_app.config)
        if error:
            return f"{file.filename}: {error}"
    return None


def _create_uploaded_analysis(files):
    analysis_id = uuid.uuid4().hex
    pixels_per_mm = current_app.config.get("DEFAULT_PIXELS_PER_MM", 10.0)
    analysis = {
        "analysis_id": analysis_id,
        "analysis_name": "Crack image analysis",
        "notes": "",
        "created_at": now(), "updated_at": now(), "status": "Uploaded",
        "total_images": len(files), "total_detected_regions": 0,
        "calibration_enabled": bool(pixels_per_mm), "pixels_per_mm": pixels_per_mm,
        "processing_configuration": current_app.config["PROCESSING"],
        "severity_thresholds": current_app.config["PROCESSING"]["severity_thresholds"],
        "error_summary": [],
    }
    create_analysis(analysis)
    root = analysis_dir(current_app.config["STORAGE_DIR"], analysis_id)
    for file in files:
        image_id = uuid.uuid4().hex
        original_path = root / "original_images" / f"{image_id}_{safe_filename(file.filename)}"
        original_path.parent.mkdir(parents=True, exist_ok=True)
        file.save(original_path)
        create_image({
            "image_id": image_id, "analysis_id": analysis_id,
            "original_filename": file.filename, "stored_filename": original_path.name,
            "original_path": str(original_path), "uploaded_at": now(),
            "processing_status": "Uploaded", "workflow_times": {},
        })
    return analysis_id


def _process_analysis(analysis_id):
    analysis = get_analysis(analysis_id)
    if not analysis:
        return None, "Analysis not found."
    update_analysis(analysis_id, {"status": "Processing", "updated_at": now()})
    all_measurements = []
    images_without_cracks = []
    processing_errors = []
    for record in list_images(analysis_id):
        timings = {}
        try:
            started = time.perf_counter()
            image, scale = load_and_resize(record["original_path"], current_app.config["PROCESSING"]["resize_max_dimension"])
            timings["resize"] = round(time.perf_counter() - started, 4)
            started = time.perf_counter()
            stages = preprocess(image, current_app.config["PROCESSING"])
            timings.update(stages.pop("_timings", {}))
            timings["preprocessing"] = round(time.perf_counter() - started, 4)
            started = time.perf_counter()
            cleaned, mask, components = detect_components(stages["binary"], current_app.config["PROCESSING"])
            components = filter_crack_components(components, current_app.config["PROCESSING"])
            timings["detection"] = round(time.perf_counter() - started, 4)
            if not validate_crack_image(components, image.shape, current_app.config["PROCESSING"]):
                images_without_cracks.append(record["original_filename"])
            processed_dir = analysis_dir(current_app.config["STORAGE_DIR"], analysis_id) / "processed_images"
            final_mask = np.zeros_like(cleaned)
            for component in components:
                final_mask = cv2.bitwise_or(final_mask, component["mask"])
            paths = {}
            for name, stage in {"resized": image, **stages, "cleaned_mask": cleaned, "segmentation_mask": final_mask}.items():
                path = processed_dir / f"{record['image_id']}_{name}.png"
                write_image(path, stage)
                paths[name] = str(path)
            started = time.perf_counter()
            measurements = []
            for index, component in enumerate(components, 1):
                measurement = measure_component(component, analysis.get("pixels_per_mm"), analysis.get("severity_thresholds"))
                measurement.update({"crack_id": f"{record['image_id'][:8]}-{index}", "analysis_id": analysis_id, "image_id": record["image_id"], "created_at": now()})
                all_measurements.append(measurement)
                measurements.append(measurement)
                skeleton_path = processed_dir / f"{record['image_id']}_skeleton_{index}.png"
                write_image(skeleton_path, measurement.pop("skeleton"))
                paths[f"skeleton_{index}"] = str(skeleton_path)
                distance_path = processed_dir / f"{record['image_id']}_distance_transform_{index}.png"
                distance_image = measurement.pop("distance_transform")
                write_image(distance_path, distance_image)
                paths[f"distance_transform_{index}"] = str(distance_path)
                width_path = processed_dir / f"{record['image_id']}_width_estimation_{index}.png"
                width_image = measurement.pop("width_estimation")
                write_image(width_path, width_image)
                paths[f"width_estimation_{index}"] = str(width_path)
            timings["measurement"] = round(time.perf_counter() - started, 4)
            started = time.perf_counter()
            annotated_path = analysis_dir(current_app.config["STORAGE_DIR"], analysis_id) / "annotated_images" / f"{record['image_id']}_annotated.png"
            write_image(annotated_path, annotate(image, components, measurements))
            timings["annotation"] = round(time.perf_counter() - started, 4)
            update_image(record["image_id"], {
                "image_width": int(image.shape[1]), "image_height": int(image.shape[0]),
                "resize_scale": scale, "processed_paths": paths,
                "annotated_path": str(annotated_path), "workflow_times": timings,
                "processing_status": "Completed",
            })
        except Exception as exc:
            processing_errors.append(f"{record['original_filename']}: {exc}")
            update_image(record["image_id"], {"processing_status": "Failed", "error_message": str(exc), "workflow_times": timings})
    if images_without_cracks or processing_errors:
        rejected_files = images_without_cracks + processing_errors
        delete_analysis_records(analysis_id)
        remove_analysis(current_app.config["STORAGE_DIR"], analysis_id)
        if images_without_cracks:
            return None, (
                "Only images containing detectable cracks are allowed. "
                f"No crack was detected in: {', '.join(images_without_cracks)}."
            )
        return None, f"Unable to process the uploaded image(s): {'; '.join(rejected_files)}"
    create_measurements(all_measurements)
    update_analysis(analysis_id, {"status": "Completed", "total_detected_regions": len(all_measurements), "updated_at": now()})
    return analysis_id, None


@upload_bp.post("/api/upload")
def upload():
    files = request.files.getlist("images")
    error = _validate_files(files)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    analysis_id = _create_uploaded_analysis(files)
    result, process_error = _process_analysis(analysis_id)
    if process_error:
        return jsonify({"ok": False, "error": process_error}), 422
    return jsonify({"ok": True, "analysis_id": result, "status": "Completed", "images": len(files)})


@upload_bp.post("/api/analyze")
def analyze():
    files = request.files.getlist("images")
    error = _validate_files(files)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    analysis_id = _create_uploaded_analysis(files)
    result, error = _process_analysis(analysis_id)
    if error:
        return jsonify({"ok": False, "error": error}), 422
    return jsonify({"ok": True, "analysis_id": result, "status": "Completed",
                    "images": len(list_images(result)), "regions": len(__import__("models.measurement_model", fromlist=["list_measurements"]).list_measurements(result))})
