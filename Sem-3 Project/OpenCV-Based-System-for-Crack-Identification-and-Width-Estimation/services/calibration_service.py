def validate_pixels_per_mm(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def convert_pixels(value, pixels_per_mm):
    return value / pixels_per_mm if pixels_per_mm else None
