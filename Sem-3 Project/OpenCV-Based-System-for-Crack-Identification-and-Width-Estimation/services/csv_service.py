from pathlib import Path

import pandas as pd
from collections import Counter


def create_csv(analysis, images, measurements, output_path):
    rows = []
    counts = Counter(item.get("severity", "Unknown") for item in measurements)
    total = len(measurements)
    summary = {
        "Total_Detected_Cracks": total,
        "Total_Length_Pixels": sum(item.get("skeleton_length_px", 0) for item in measurements),
        "Total_Length_MM": sum(item.get("skeleton_length_mm", 0) for item in measurements),
        "Average_Width_Pixels": sum(item.get("mean_width_px", 0) for item in measurements) / total if total else 0,
        "Average_Width_MM": sum(item.get("mean_width_mm", 0) for item in measurements) / total if total else 0,
        "Maximum_Width_Pixels": max((item.get("max_width_px", 0) for item in measurements), default=0),
        "Maximum_Width_MM": max((item.get("max_width_mm", 0) for item in measurements), default=0),
        "Minimum_Width_Pixels": min((item.get("mean_width_px", 0) for item in measurements), default=0),
        "Minimum_Width_MM": min((item.get("mean_width_mm", 0) for item in measurements), default=0),
        "GOOD_Count": counts.get("Good", 0), "MEDIUM_Count": counts.get("Medium", 0), "HEAVY_Count": counts.get("Heavy", 0),
        "Overall_Severity": "Heavy" if counts.get("Heavy", 0) else "Medium" if counts.get("Medium", 0) else "Good" if total else "No data",
        "Remark": (
            f"Heavy-severity indications were detected in {counts.get('Heavy', 0)} of {total} crack region(s). "
            "Review the annotated image and arrange a qualified structural inspection."
            if counts.get("Heavy", 0) else
            f"Medium-severity indications were detected in {counts.get('Medium', 0)} of {total} crack region(s). "
            "Monitor the affected area and consider a qualified inspection."
            if counts.get("Medium", 0) else
            f"All {total} detected crack region(s) are in the Good software category. Continue routine monitoring."
            if total else "No crack measurements were produced. Upload a clearer crack image for another analysis."
        ),
    }
    by_image = {}
    for item in measurements:
        by_image.setdefault(item["image_id"], []).append(item)
    for image in images:
        records = by_image.get(image["image_id"], [])
        if not records:
            records = [{}]
        for index, measurement in enumerate(records, 1):
            rows.append({
                "Analysis_ID": analysis["analysis_id"], "Analysis_Name": analysis.get("analysis_name", ""),
                "Analysis_Date": analysis.get("created_at", ""), "Image_ID": image["image_id"],
                "Image_Name": image["original_filename"], "Crack_ID": measurement.get("crack_id", f"none-{index}"),
                "Image_Width": image.get("image_width"), "Image_Height": image.get("image_height"),
                "Crack_Area_Pixels": measurement.get("contour_area_px"), "Crack_Area_MM2": measurement.get("contour_area_mm2"), "Crack_Length_Pixels": measurement.get("skeleton_length_px"),
                "Crack_Length_MM": measurement.get("skeleton_length_mm"), "Mean_Width_Pixels": measurement.get("mean_width_px"),
                "Max_Width_Pixels": measurement.get("max_width_px"), "Mean_Width_MM": measurement.get("mean_width_mm"),
                "Max_Width_MM": measurement.get("max_width_mm"), "Calibration_Status": measurement.get("calibration_status"),
                "Pixels_Per_MM": analysis.get("pixels_per_mm"), "Severity": measurement.get("severity"),
                "Processing_Status": image.get("processing_status"),
                **summary,
            })
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output_path, index=False, float_format="%.3f")
    return output_path
