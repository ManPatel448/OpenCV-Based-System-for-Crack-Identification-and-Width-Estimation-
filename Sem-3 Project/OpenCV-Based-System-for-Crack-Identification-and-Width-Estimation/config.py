import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "development-only-key")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "crack_detection_db")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(16 * 1024 * 1024)))
    STORAGE_DIR = Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "storage")))
    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "jfif", "png"}
    MAX_FILES_PER_ANALYSIS = 20
    MAX_IMAGE_DIMENSION = 8000
    AUTO_RELOAD = os.getenv("FLASK_AUTO_RELOAD", "1").strip().lower() in {"1", "true", "yes", "on"}
    DEFAULT_PIXELS_PER_MM = 10.0
    PROCESSING = {
        "resize_max_dimension": 1600,
        "gaussian_kernel": 5,
        "clahe_clip_limit": 2.0,
        "clahe_tile_grid": 8,
        "blackhat_kernel": 21,
        "adaptive_threshold_block_size": 41,
        "adaptive_threshold_offset": 16,
        "morphology_kernel": 3,
        "morphology_iterations": 1,
        "minimum_region_area": 30,
        "minimum_crack_aspect_ratio": 3.0,
        "crack_link_distance_px": 25.0,
        "maximum_crack_components": 60,
        "maximum_crack_coverage": 0.12,
        "maximum_dispersed_components": 12,
        "minimum_crack_path_alignment": 3.0,
        "minimum_dominant_crack_area_ratio": 0.003,
        "minimum_dominant_crack_aspect_ratio": 2.4,
        "minimum_fragmented_crack_alignment": 3.0,
        "maximum_fragmented_crack_coverage": 0.15,
        "severity_thresholds": {
            "good_max_width_px": 3.0,
            "medium_max_width_px": 8.0,
            "heavy_min_area_px": 5000,
        },
    }
