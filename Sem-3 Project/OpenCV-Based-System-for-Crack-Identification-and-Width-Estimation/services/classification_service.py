def classify(area_px, mean_width_px, thresholds=None):
    thresholds = thresholds or {"good_max_width_px": 3.0, "medium_max_width_px": 8.0, "heavy_min_area_px": 5000}
    if area_px >= thresholds["heavy_min_area_px"] or mean_width_px > thresholds["medium_max_width_px"]:
        return "Heavy"
    if mean_width_px > thresholds["good_max_width_px"]:
        return "Medium"
    return "Good"


def threshold_description(thresholds=None):
    thresholds = thresholds or {"good_max_width_px": 3.0, "medium_max_width_px": 8.0, "heavy_min_area_px": 5000}
    return {
        "Good": f"mean width <= {thresholds['good_max_width_px']:.2f} px",
        "Medium": f"mean width > {thresholds['good_max_width_px']:.2f} px and <= {thresholds['medium_max_width_px']:.2f} px",
        "Heavy": f"mean width > {thresholds['medium_max_width_px']:.2f} px or area >= {thresholds['heavy_min_area_px']:.0f} px²",
    }
