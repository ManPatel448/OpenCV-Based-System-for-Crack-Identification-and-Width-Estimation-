import cv2
import numpy as np


def preprocess(image, config):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    kernel_size = int(config["gaussian_kernel"])
    blurred = cv2.GaussianBlur(gray, (kernel_size, kernel_size), 0)
    clahe = cv2.createCLAHE(
        clipLimit=float(config["clahe_clip_limit"]),
        tileGridSize=(int(config["clahe_tile_grid"]), int(config["clahe_tile_grid"])),
    )
    enhanced = clahe.apply(blurred)
    k = int(config["blackhat_kernel"])
    blackhat = cv2.morphologyEx(enhanced, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    adaptive_block = config.get("adaptive_threshold_block_size")
    if adaptive_block:
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            int(adaptive_block),
            float(config.get("adaptive_threshold_offset", 8)),
        )
    else:
        percentile = config.get("blackhat_threshold_percentile")
        if percentile is None:
            _, binary = cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            threshold = float(np.percentile(blackhat, float(percentile)))
            binary = cv2.inRange(blackhat, threshold, 255)
    return {"gray": gray, "blurred": blurred, "clahe": enhanced, "blackhat": blackhat, "binary": binary}
