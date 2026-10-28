import re
from pathlib import Path


def safe_filename(name):
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name)
    return stem.strip("._") or "image"


def is_within(base, candidate):
    try:
        Path(candidate).resolve().relative_to(Path(base).resolve())
        return True
    except ValueError:
        return False
