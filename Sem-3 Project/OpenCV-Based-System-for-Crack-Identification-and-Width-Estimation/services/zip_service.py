from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from datetime import datetime, timezone


def create_manifest(analysis, images, measurements, output_path):
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "Crack Detaction complete analysis package",
        f"Analysis ID: {analysis.get('analysis_id', '')}",
        f"Analysis name: {analysis.get('analysis_name', '')}",
        f"Analysis date: {analysis.get('created_at', '')}",
        f"Package generated: {datetime.now(timezone.utc).isoformat()}",
        f"Status: {analysis.get('status', '')}",
        f"Images: {len(images)}",
        f"Detected crack regions: {len(measurements)}",
        "",
        "Package contents:",
        "- Original uploaded images",
        "- All processed image stages and annotated results",
        "- CSV measurement report",
        "- PDF measurement report",
        "- This manifest",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(output)


def create_zip(analysis_id, analysis_dir, report_paths, output_path):
    root = Path(analysis_dir)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    files = []
    seen = set()
    for path in root.rglob("*"):
        if path.is_file() and path.resolve() != output.resolve():
            archive_name = Path("Crack_Analysis_Results") / path.relative_to(root)
            files.append((path, archive_name))
            seen.add(archive_name.as_posix())
    for path in report_paths:
        report_path = Path(path)
        archive_name = Path("Crack_Analysis_Results") / "reports" / report_path.name
        if report_path.exists() and archive_name.as_posix() not in seen:
            files.append((report_path, archive_name))
            seen.add(archive_name.as_posix())
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path, archive_name in files:
            archive.write(path, archive_name)
    return str(output)
