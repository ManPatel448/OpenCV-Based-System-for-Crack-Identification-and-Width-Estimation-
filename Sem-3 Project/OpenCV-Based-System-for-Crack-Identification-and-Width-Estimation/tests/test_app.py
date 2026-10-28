from io import BytesIO

import cv2
import numpy as np
from zipfile import ZipFile

from app import create_app
from services.zip_service import create_zip


def test_create_zip_excludes_itself_and_duplicate_reports(tmp_path):
    root = tmp_path / "analysis"
    reports = root / "reports"
    reports.mkdir(parents=True)
    image = root / "processed.png"
    csv_path = reports / "analysis.csv"
    pdf_path = reports / "analysis.pdf"
    zip_path = reports / "analysis.zip"
    image.write_bytes(b"image")
    csv_path.write_bytes(b"csv")
    pdf_path.write_bytes(b"pdf")

    create_zip("analysis", root, [csv_path, pdf_path], zip_path)

    with ZipFile(zip_path) as archive:
        names = archive.namelist()
    assert "Crack_Analysis_Results/reports/analysis.zip" not in names
    assert names.count("Crack_Analysis_Results/reports/analysis.csv") == 1
    assert names.count("Crack_Analysis_Results/reports/analysis.pdf") == 1


def test_upload_rejects_empty_batch(tmp_path):
    class TestConfig:
        TESTING = True
        SECRET_KEY = "test"
        STORAGE_DIR = tmp_path
        MAX_CONTENT_LENGTH = 1024 * 1024
        ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
        MAX_FILES_PER_ANALYSIS = 20
        MAX_IMAGE_DIMENSION = 8000
        MONGO_URI = "mongodb://invalid-host:27017"
        MONGO_DB_NAME = "test"
        PROCESSING = {"resize_max_dimension": 1600, "gaussian_kernel": 5, "clahe_clip_limit": 2,
                      "clahe_tile_grid": 8, "blackhat_kernel": 21, "morphology_kernel": 3,
                      "morphology_iterations": 1, "minimum_region_area": 10}
    client = create_app(TestConfig).test_client()
    response = client.post("/api/analyze", data={})
    assert response.status_code == 400


def test_upload_rejects_invalid_extension(tmp_path):
    class TestConfig:
        TESTING = True
        SECRET_KEY = "test"
        STORAGE_DIR = tmp_path
        MAX_CONTENT_LENGTH = 1024 * 1024
        ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
        MAX_FILES_PER_ANALYSIS = 20
        MAX_IMAGE_DIMENSION = 8000
        MONGO_URI = "mongodb://invalid-host:27017"
        MONGO_DB_NAME = "test"
        PROCESSING = {"resize_max_dimension": 1600, "gaussian_kernel": 5, "clahe_clip_limit": 2,
                      "clahe_tile_grid": 8, "blackhat_kernel": 21, "morphology_kernel": 3,
                      "morphology_iterations": 1, "minimum_region_area": 10}
    client = create_app(TestConfig).test_client()
    response = client.post("/api/analyze", data={"images": (BytesIO(b"not image"), "x.txt")}, content_type="multipart/form-data")
    assert response.status_code == 400
