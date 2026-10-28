import cv2
import numpy as np


def detect_components(binary, config):
    k = int(config["morphology_kernel"])
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    iterations = int(config.get("morphology_iterations", 1))
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=iterations)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, 8)
    minimum = int(config["minimum_region_area"])
    mask = np.zeros_like(cleaned)
    components = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < minimum:
            continue
        component_mask = np.where(labels == label, 255, 0).astype(np.uint8)
        contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        components.append({"label": label, "area": area, "mask": component_mask, "contour": max(contours, key=cv2.contourArea)})
        mask[labels == label] = 255
    return cleaned, mask, components


def filter_crack_components(components, config):
    """Keep thin, elongated regions and reject generic blobs from ordinary photos."""
    minimum_aspect = float(config.get("minimum_crack_aspect_ratio", 3.0))
    crack_components = []
    for component in components:
        _, (width, height), _ = cv2.minAreaRect(component["contour"])
        short_side = min(width, height)
        aspect_ratio = max(width, height) / max(short_side, 1.0)
        points = np.argwhere(component["mask"] > 0)
        if len(points) < 2:
            continue
        _, singular_values, _ = np.linalg.svd(points - points.mean(axis=0), full_matrices=False)
        principal_ratio = float(singular_values[0] / max(singular_values[1], 1e-6))
        if aspect_ratio >= minimum_aspect or principal_ratio >= minimum_aspect:
            crack_components.append(component)
    return _select_coherent_path(crack_components, config)


def _merge_component_group(group, components, link_distance):
    """Merge fragmented components belonging to the same continuous crack path."""
    if len(group) == 1:
        return components[list(group)[0]]

    merged_mask = np.zeros_like(components[0]["mask"])
    for index in group:
        merged_mask = cv2.bitwise_or(merged_mask, components[index]["mask"])

    member_contours = [components[index]["contour"] for index in group]
    for i in range(len(member_contours)):
        for j in range(i + 1, len(member_contours)):
            pts_i = member_contours[i][:, 0, :]
            pts_j = member_contours[j][:, 0, :]
            dists = np.linalg.norm(pts_i[:, None, :] - pts_j[None, :, :], axis=2)
            min_idx = np.unravel_index(np.argmin(dists), dists.shape)
            if dists[min_idx] <= link_distance + 2.0:
                p1 = tuple(pts_i[min_idx[0]])
                p2 = tuple(pts_j[min_idx[1]])
                cv2.line(merged_mask, p1, p2, 255, 2)

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    merged_mask = cv2.morphologyEx(merged_mask, cv2.MORPH_CLOSE, k)

    contours, _ = cv2.findContours(merged_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    main_contour = max(contours, key=cv2.contourArea)
    area = int(np.count_nonzero(merged_mask))
    first_index = min(group)
    return {
        "label": components[first_index]["label"],
        "area": area,
        "mask": merged_mask,
        "contour": main_contour,
    }


def _select_coherent_path(components, config):
    """Discard isolated texture blobs while preserving and uniting separate crack networks."""
    if len(components) <= 1:
        return components
    link_distance = float(config.get("crack_link_distance_px", 18.0))
    groups = []
    remaining = set(range(len(components)))
    while remaining:
        group = {remaining.pop()}
        changed = True
        while changed:
            changed = False
            for index in tuple(remaining):
                if any(_component_gap(components[index], components[member]) <= link_distance for member in group):
                    group.add(index)
                    remaining.remove(index)
                    changed = True
        groups.append(group)

    group_areas = [
        sum(components[index]["area"] for index in group)
        for group in groups
    ]
    largest_area = max(group_areas)
    minimum_group_area = float(config.get("minimum_crack_group_area", 80.0))
    retained_groups = [
        group for group, area in zip(groups, group_areas)
        if area >= minimum_group_area and (
            area >= largest_area * float(config.get("minimum_crack_group_ratio", 0.08))
            or (len(group) >= 2 and area >= minimum_group_area * 2)
        )
    ]
    if not retained_groups:
        retained_groups = [groups[group_areas.index(largest_area)]]
    return [
        _merge_component_group(group, components, link_distance)
        for group in retained_groups
    ]


def _component_gap(first, second):
    first_x, first_y, first_width, first_height = cv2.boundingRect(first["contour"])
    second_x, second_y, second_width, second_height = cv2.boundingRect(second["contour"])
    horizontal_gap = max(first_x - (second_x + second_width), second_x - (first_x + first_width), 0)
    vertical_gap = max(first_y - (second_y + second_height), second_y - (first_y + first_height), 0)
    return float(np.hypot(horizontal_gap, vertical_gap))


def validate_crack_image(components, image_shape, config):
    """Reject unrelated images while allowing fragmented, dominant crack paths."""
    if not components:
        return False
    max_components = int(config.get("maximum_crack_components", 60))
    max_coverage = float(config.get("maximum_crack_coverage", 0.08))
    image_area = max(1, image_shape[0] * image_shape[1])
    coverage = sum(component["area"] for component in components) / image_area
    alignment_ratio = _component_alignment_ratio(components)
    dispersed_limit = int(config.get("maximum_dispersed_components", 8))
    if len(components) <= max_components and coverage <= max_coverage and (
        len(components) <= dispersed_limit
        or alignment_ratio >= float(config.get("minimum_crack_path_alignment", 3.0))
    ):
        return True

    dominant = max(components, key=lambda component: component["area"])
    _, (width, height), _ = cv2.minAreaRect(dominant["contour"])
    short_side = min(width, height)
    dominant_aspect = max(width, height) / max(short_side, 1.0)
    dominant_area_ratio = dominant["area"] / image_area
    return (
        dominant_area_ratio >= float(config.get("minimum_dominant_crack_area_ratio", 0.002))
        and dominant_aspect >= float(config.get("minimum_dominant_crack_aspect_ratio", 4.5))
        and coverage <= float(config.get("maximum_fragmented_crack_coverage", 0.15))
    )


def _component_alignment_ratio(components):
    centers = []
    for component in components:
        ys, xs = np.where(component["mask"] > 0)
        if len(xs):
            centers.append((float(xs.mean()), float(ys.mean())))
    if len(centers) <= 3:
        return float("inf")
    _, values, _ = np.linalg.svd(np.asarray(centers) - np.mean(centers, axis=0), full_matrices=False)
    return float(values[0] / max(values[1], 1e-6))
