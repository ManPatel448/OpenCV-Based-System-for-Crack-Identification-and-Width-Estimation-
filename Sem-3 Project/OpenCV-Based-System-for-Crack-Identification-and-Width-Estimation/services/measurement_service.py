import cv2
import numpy as np
from skimage.morphology import skeletonize

from .calibration_service import convert_pixels
from .classification_service import classify


def _skeleton_length(skeleton):
    points = np.argwhere(skeleton)
    point_set = set(map(tuple, points))
    length = 0.0
    for y, x in points:
        for dy, dx, distance in ((0, 1, 1.0), (1, 0, 1.0), (1, 1, 2 ** 0.5), (1, -1, 2 ** 0.5)):
            if (y + dy, x + dx) in point_set:
                length += distance
    return length


def _robust_widths(distance, skeleton_points):
    """Return centerline widths while ignoring junction and mask-edge outliers."""
    if not len(skeleton_points):
        return np.array([], dtype=float)

    points = []
    for y, x in skeleton_points:
        neighbors = skeleton_points[
            np.sum((skeleton_points - np.array([y, x])) ** 2, axis=1) <= 2
        ]
        if len(neighbors) <= 3:
            points.append((y, x))

    sample_points = points or [tuple(point) for point in skeleton_points]
    return np.array([distance[y, x] * 2 for y, x in sample_points], dtype=float)


def measure_component(component, pixels_per_mm=None, thresholds=None):
    mask = component["mask"] > 0
    skeleton = skeletonize(mask)
    distance = cv2.distanceTransform(component["mask"], cv2.DIST_L2, 5)
    skeleton_points = np.argwhere(skeleton)
    sample_points = [
        tuple(point)
        for point in skeleton_points
        if skeleton[max(0, point[0] - 1):point[0] + 2, max(0, point[1] - 1):point[1] + 2].sum() - 1 == 2
    ] or [tuple(point) for point in skeleton_points]
    widths = _robust_widths(distance, skeleton_points)
    if widths.size:
        # Median and P95 are stable when a crack joins another region or ends
        # in a widened segmentation blob.
        mean_width = float(np.median(widths))
        max_width = float(np.percentile(widths, 95))
    else:
        mean_width = max_width = 0.0
    length = _skeleton_length(skeleton)
    step = max(1, len(sample_points) // 20)
    points = []
    for y, x in sample_points[::step]:
        nearby = skeleton_points[np.sum((skeleton_points - np.array([y, x])) ** 2, axis=1).argsort()[:9]]
        if len(nearby) > 2:
            _, _, vectors = np.linalg.svd(nearby - nearby.mean(axis=0), full_matrices=False)
            tangent_y, tangent_x = vectors[0]
            angle = float(np.arctan2(tangent_y, tangent_x) + np.pi / 2)
        else:
            angle = 0.0
        points.append({
            "x": int(x), "y": int(y),
            "width_px": round(float(distance[y, x] * 2), 3),
            "width_mm": convert_pixels(float(distance[y, x] * 2), pixels_per_mm),
            "angle": angle,
        })
    distance_visual = cv2.normalize(distance, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    distance_visual = cv2.applyColorMap(distance_visual, cv2.COLORMAP_TURBO)
    cv2.putText(
        distance_visual,
        "Distance transform: radius px; width = 2 x radius",
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        distance_visual,
        "Mean width: %.2f px / %s mm" % (
            mean_width,
            "%.2f" % (mean_width / pixels_per_mm) if pixels_per_mm else "Not calibrated",
        ),
        (12, 52),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    width_visual = cv2.cvtColor((mask > 0).astype(np.uint8) * 35, cv2.COLOR_GRAY2BGR)
    width_visual[skeleton] = (0, 0, 255)
    for point in points:
        px, py = point["x"], point["y"]
        radius = max(2, int(round(point["width_px"] / 2)))
        dx = int(round(np.cos(point["angle"]) * radius))
        dy = int(round(np.sin(point["angle"]) * radius))
        cv2.line(width_visual, (px - dx, py - dy), (px + dx, py + dy), (0, 255, 0), 1)
    cv2.putText(
        width_visual,
        "Width estimation: green samples / red skeleton",
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        width_visual,
        "Mean: %.2f px / %s mm | Max: %.2f px / %s mm" % (
            mean_width,
            "%.2f" % (mean_width / pixels_per_mm) if pixels_per_mm else "Not calibrated",
            max_width,
            "%.2f" % (max_width / pixels_per_mm) if pixels_per_mm else "Not calibrated",
        ),
        (12, 52),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return {
        "contour_area_px": float(component["area"]),
        "contour_area_mm2": convert_pixels(float(component["area"]), pixels_per_mm ** 2 if pixels_per_mm else None),
        "skeleton_length_px": round(length, 3),
        "skeleton_length_mm": convert_pixels(length, pixels_per_mm),
        "mean_width_px": round(mean_width, 3),
        "max_width_px": round(max_width, 3),
        "mean_width_mm": convert_pixels(mean_width, pixels_per_mm),
        "max_width_mm": convert_pixels(max_width, pixels_per_mm),
        "calibration_status": "calibrated" if pixels_per_mm else "pixel-only",
        "severity": classify(component["area"], mean_width, thresholds),
        "measurement_points": points,
        "width_sample_count": len(sample_points),
        "skeleton": (skeleton * 255).astype(np.uint8),
        "distance_transform": distance_visual,
        "width_estimation": width_visual,
    }


def annotate(image, components, measurements):
    output = image.copy()
    for index, component in enumerate(components, 1):
        cv2.drawContours(output, [component["contour"]], -1, (0, 0, 255), 2)
        ys, xs = np.where(component["mask"] > 0)
        if len(xs):
            x, y = int(xs.mean()), int(ys.mean())
            cv2.putText(output, f"C{index}", (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        for point in measurements[index - 1].get("measurement_points", []):
            px, py = point["x"], point["y"]
            radius = max(2, int(round(point["width_px"] / 2)))
            dx = int(round(np.cos(point.get("angle", 0)) * radius))
            dy = int(round(np.sin(point.get("angle", 0)) * radius))
            cv2.line(output, (px - dx, py - dy), (px + dx, py + dy), (0, 255, 255), 1)
            cv2.circle(output, (px, py), 2, (0, 255, 255), -1)
    return output
