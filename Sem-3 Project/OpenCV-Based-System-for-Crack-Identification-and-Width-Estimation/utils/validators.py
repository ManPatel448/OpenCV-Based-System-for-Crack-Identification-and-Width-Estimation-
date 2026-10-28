from pathlib import Path

import cv2


def validate_upload(file, config):
    if not file or not file.filename:
        return "A file was not selected."
    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in config["ALLOWED_EXTENSIONS"]:
        return "Only JPG, JPEG, JFIF, and PNG images are supported."
    data = file.read()
    file.seek(0)
    if not data:
        return "The uploaded file is empty."
    image = cv2.imdecode(__import__("numpy").frombuffer(data, dtype="uint8"), cv2.IMREAD_COLOR)
    if image is None:
        return "The file is not a valid decodable image."
    height, width = image.shape[:2]
    if width < 2 or height < 2 or max(width, height) > config["MAX_IMAGE_DIMENSION"]:
        return "Image dimensions are outside the supported range."
    return None
