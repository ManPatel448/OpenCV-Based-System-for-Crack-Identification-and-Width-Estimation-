from .database import get_db, get_fallback_store


def create_measurements(documents):
    db = get_db()
    if db is not None and documents:
        db.crack_measurements.insert_many(documents)
    elif documents:
        get_fallback_store()["measurements"].extend(item.copy() for item in documents)


def list_measurements(analysis_id, image_id=None):
    db = get_db()
    if db is None:
        values = [item for item in get_fallback_store()["measurements"] if item["analysis_id"] == analysis_id]
        if image_id:
            values = [item for item in values if item["image_id"] == image_id]
        return sorted(values, key=lambda item: item.get("crack_id", ""))
    query = {"analysis_id": analysis_id}
    if image_id:
        query["image_id"] = image_id
    return list(db.crack_measurements.find(query).sort("crack_id", 1))


def update_measurement_calibration(analysis_id, pixels_per_mm):
    db = get_db()
    measurements = list_measurements(analysis_id)
    for measurement in measurements:
        values = {
            "contour_area_mm2": measurement["contour_area_px"] / (pixels_per_mm * pixels_per_mm),
            "skeleton_length_mm": measurement["skeleton_length_px"] / pixels_per_mm,
            "mean_width_mm": measurement["mean_width_px"] / pixels_per_mm,
            "max_width_mm": measurement["max_width_px"] / pixels_per_mm,
            "calibration_status": "calibrated",
            "measurement_points": [
                {**point, "width_mm": point["width_px"] / pixels_per_mm}
                for point in measurement.get("measurement_points", [])
            ],
        }
        if db is not None:
            db.crack_measurements.update_one({"_id": measurement["_id"]}, {"$set": values})
        else:
            measurement.update(values)
