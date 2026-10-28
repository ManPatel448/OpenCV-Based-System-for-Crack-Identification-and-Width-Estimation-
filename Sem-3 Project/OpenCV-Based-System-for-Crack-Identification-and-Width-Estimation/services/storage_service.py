import shutil
from pathlib import Path


def analysis_dir(storage_dir, analysis_id):
    root = Path(storage_dir)
    path = root / "analyses" / analysis_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def remove_analysis(storage_dir, analysis_id):
    path = Path(storage_dir) / "analyses" / analysis_id
    if path.exists():
        shutil.rmtree(path)
