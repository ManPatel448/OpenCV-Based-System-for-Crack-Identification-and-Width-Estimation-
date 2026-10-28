import cv2
import numpy as np

from services.calibration_service import convert_pixels, validate_pixels_per_mm
from services.classification_service import classify
from services.detection_service import detect_components, filter_crack_components, validate_crack_image
from services.measurement_service import measure_component
from services.preprocessing_service import preprocess


CONFIG = {"gaussian_kernel": 5, "clahe_clip_limit": 2, "clahe_tile_grid": 8, "blackhat_kernel": 21,
          "morphology_kernel": 3, "morphology_iterations": 1, "minimum_region_area": 10}


def test_pipeline_detects_synthetic_dark_crack():
    image = np.full((220, 220, 3), 210, dtype=np.uint8)
    cv2.line(image, (25, 30), (190, 180), (20, 20, 20), 5)
    stages = preprocess(image, CONFIG)
    _, _, components = detect_components(stages["binary"], CONFIG)
    assert components
    assert filter_crack_components(components, CONFIG)
    assert validate_crack_image(filter_crack_components(components, CONFIG), image.shape, CONFIG)
    result = measure_component(components[0], 10)
    assert result["skeleton_length_px"] > 0
    assert result["skeleton_length_mm"] is not None


def test_calibration_and_classification():
    assert validate_pixels_per_mm("4") == 4
    assert validate_pixels_per_mm("0") is None
    assert convert_pixels(20, 4) == 5
    assert classify(10, 1) == "Good"
    assert classify(10, 4) == "Medium"
    assert classify(6000, 1) == "Heavy"


def test_validation_rejects_round_non_crack_region():
    image = np.full((220, 220, 3), 210, dtype=np.uint8)
    cv2.circle(image, (110, 110), 35, (20, 20, 20), -1)
    stages = preprocess(image, CONFIG)
    _, _, components = detect_components(stages["binary"], CONFIG)
    assert not filter_crack_components(components, CONFIG)


def test_validation_rejects_text_heavy_image():
    image = np.full((220, 220, 3), 210, dtype=np.uint8)
    for y in range(20, 210, 20):
        cv2.putText(image, "TEXT", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1)
    stages = preprocess(image, CONFIG)
    _, _, components = detect_components(stages["binary"], CONFIG)
    filtered = filter_crack_components(components, CONFIG)
    assert not validate_crack_image(filtered, image.shape, CONFIG)


def test_validation_allows_fragmented_dominant_crack():
    image = np.full((220, 220, 3), 210, dtype=np.uint8)
    for start, end in [((15, 110), (70, 100)), ((75, 98), (130, 80)), ((135, 78), (205, 45))]:
        cv2.line(image, start, end, (20, 20, 20), 4)
    stages = preprocess(image, {**CONFIG, "maximum_crack_components": 1, "maximum_crack_coverage": 0.001})
    _, _, components = detect_components(stages["binary"], {**CONFIG, "maximum_crack_components": 1})
    filtered = filter_crack_components(components, CONFIG)
    assert validate_crack_image(filtered, image.shape, {**CONFIG, "maximum_crack_components": 1, "maximum_crack_coverage": 0.001})


def test_validation_allows_dominant_crack_with_texture_fragments():
    image = np.full((220, 220, 3), 150, dtype=np.uint8)
    cv2.line(image, (20, 112), (200, 92), (80, 80, 80), 4)
    for x, y in ((30, 30), (75, 180), (130, 45), (180, 165)):
        cv2.line(image, (x, y), (x + 8, y + 2), (110, 110, 110), 2)

    stages = preprocess(image, CONFIG)
    _, _, components = detect_components(stages["binary"], CONFIG)
    filtered = filter_crack_components(components, CONFIG)

    assert filtered
    assert validate_crack_image(filtered, image.shape, CONFIG)


def test_filter_keeps_coherent_crack_and_discards_texture_blobs():
    image = np.full((220, 220, 3), 150, dtype=np.uint8)
    for start, end in [((15, 112), (70, 105)), ((74, 104), (130, 94)), ((134, 93), (205, 78))]:
        cv2.line(image, start, end, (80, 80, 80), 5)
    for x, y in ((30, 30), (110, 40), (180, 170), (40, 180), (190, 45)):
        cv2.line(image, (x, y), (x + 7, y + 2), (80, 80, 80), 3)

    stages = preprocess(image, CONFIG)
    _, _, components = detect_components(stages["binary"], CONFIG)
    filtered = filter_crack_components(components, {**CONFIG, "crack_link_distance_px": 18})

    assert 1 <= len(filtered) <= 4
    assert validate_crack_image(filtered, image.shape, CONFIG)


def test_percentile_threshold_limits_road_texture_noise():
    image = np.full((320, 480, 3), 120, dtype=np.uint8)
    noise = np.random.default_rng(7).normal(0, 8, image.shape[:2]).clip(-30, 30).astype(np.int16)
    textured = np.clip(image[:, :, 0].astype(np.int16) + noise, 0, 255).astype(np.uint8)
    image[:] = cv2.cvtColor(textured, cv2.COLOR_GRAY2BGR)
    cv2.polylines(image, [np.array([[10, 190], [100, 170], [190, 205], [300, 185], [470, 195]])], False, (55, 55, 55), 3)

    stages = preprocess(image, {**CONFIG, "blackhat_threshold_percentile": 90})
    _, _, components = detect_components(stages["binary"], CONFIG)
    filtered = filter_crack_components(components, CONFIG)

    assert stages["binary"].mean() < 80
    assert filtered
    assert validate_crack_image(filtered, image.shape, CONFIG)


def test_adaptive_threshold_measures_full_normal_road_crack():
    image = np.full((320, 480, 3), 120, dtype=np.uint8)
    noise = np.random.default_rng(12).normal(0, 6, image.shape[:2]).clip(-25, 25).astype(np.int16)
    textured = np.clip(image[:, :, 0].astype(np.int16) + noise, 0, 255).astype(np.uint8)
    image[:] = cv2.cvtColor(textured, cv2.COLOR_GRAY2BGR)
    cv2.polylines(
        image,
        [np.array([[5, 170], [100, 155], [200, 190], [310, 175], [475, 185]])],
        False,
        (55, 55, 55),
        2,
    )

    config = {**CONFIG, "adaptive_threshold_block_size": 41, "adaptive_threshold_offset": 8}
    stages = preprocess(image, config)
    _, _, components = detect_components(stages["binary"], config)
    filtered = filter_crack_components(components, config)
    measurements = [measure_component(component, 10) for component in filtered]

    assert filtered
    assert max(cv2.boundingRect(component["contour"])[0] + cv2.boundingRect(component["contour"])[2] for component in filtered) > 400
    assert sum(item["skeleton_length_px"] for item in measurements) < 800


def test_width_measurement_uses_stable_centerline_statistics():
    image = np.full((220, 220, 3), 210, dtype=np.uint8)
    cv2.line(image, (25, 110), (195, 110), (20, 20, 20), 4)
    stages = preprocess(image, CONFIG)
    _, _, components = detect_components(stages["binary"], CONFIG)

    measurement = measure_component(components[0], 10)

    assert 5 <= measurement["mean_width_px"] <= 7
    assert measurement["max_width_px"] >= measurement["mean_width_px"]
    assert measurement["max_width_px"] < 8


def test_multiple_separate_crack_networks_are_measured_independently():
    image = np.full((360, 480, 3), 150, dtype=np.uint8)
    cv2.polylines(image, [np.array([[20, 70], [90, 95], [160, 55]])], False, (55, 55, 55), 4)
    cv2.polylines(image, [np.array([[300, 80], [360, 130], [450, 105]])], False, (55, 55, 55), 4)
    cv2.polylines(image, [np.array([[30, 280], [110, 245], [180, 300]])], False, (55, 55, 55), 4)

    config = {**CONFIG, "adaptive_threshold_block_size": 41, "adaptive_threshold_offset": 16}
    stages = preprocess(image, config)
    _, _, components = detect_components(stages["binary"], config)
    filtered = filter_crack_components(components, config)
    measurements = [measure_component(component, 10) for component in filtered]

    assert len(filtered) >= 3
    assert all(item["skeleton_length_px"] > 30 for item in measurements)
    assert validate_crack_image(filtered, image.shape, config)


def test_validation_allows_wide_dominant_road_crack():
    image = np.full((384, 544, 3), 150, dtype=np.uint8)
    cv2.line(image, (80, 310), (160, 280), (80, 80, 80), 8)
    stages = preprocess(image, CONFIG)
    _, _, components = detect_components(stages["binary"], CONFIG)
    filtered = filter_crack_components(components, CONFIG)

    assert validate_crack_image(
        filtered,
        image.shape,
        {
            **CONFIG,
            "minimum_dominant_crack_area_ratio": 0.003,
            "minimum_dominant_crack_aspect_ratio": 2.4,
        },
    )


def test_validation_rejects_dispersed_portrait_like_regions():
    image = np.full((220, 220, 3), 210, dtype=np.uint8)
    for x, y in ((30, 30), (110, 35), (185, 45), (40, 150), (120, 140), (195, 165)):
        cv2.line(image, (x, y), (x + 15, y + 4), (20, 20, 20), 4)
    stages = preprocess(image, CONFIG)
    _, _, components = detect_components(stages["binary"], CONFIG)
    filtered = filter_crack_components(components, CONFIG)
    assert not validate_crack_image(
        filtered,
        image.shape,
        {**CONFIG, "maximum_crack_components": 1, "maximum_crack_coverage": 0.001},
    )


def test_continuous_crack_path_unification():
    image = np.full((320, 480, 3), 150, dtype=np.uint8)
    for start, end in [((10, 100), (100, 120)), ((108, 122), (220, 150)), ((228, 152), (350, 190)), ((356, 192), (470, 220))]:
        cv2.line(image, start, end, (50, 50, 50), 3)
    stages = preprocess(image, {**CONFIG, "adaptive_threshold_block_size": 41, "adaptive_threshold_offset": 16})
    _, _, components = detect_components(stages["binary"], {**CONFIG, "morphology_kernel": 3})
    filtered = filter_crack_components(components, {**CONFIG, "crack_link_distance_px": 25.0})
    assert len(filtered) == 1
    assert filtered[0]["area"] > 500
    measurement = measure_component(filtered[0], 10)
    assert measurement["skeleton_length_px"] > 350
