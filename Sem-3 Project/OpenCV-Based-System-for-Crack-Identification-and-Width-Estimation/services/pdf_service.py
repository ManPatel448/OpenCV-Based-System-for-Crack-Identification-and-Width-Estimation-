from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.lib.utils import ImageReader


WORKFLOW_STEPS = [
    ("1", "Upload and validate", "Check file type, size, and image readability.", "Validated source image"),
    ("2", "Resize image", "Fit the image to the configured processing dimension.", "Resized image"),
    ("3", "Preprocess", "Create grayscale, blur, CLAHE, and BlackHat images.", "Preprocessing images"),
    ("4", "Segment crack candidates", "Apply thresholding, morphology, and connected components.", "Binary and segmentation masks"),
    ("5", "Measure cracks", "Skeletonize regions and estimate area, length, and width.", "Skeleton, distance transform, width estimates"),
    ("6", "Calibrate and classify", "Convert pixels to millimeters and assign severity.", "px/mm measurements and severity"),
    ("7", "Annotate and export", "Draw measurement lines and prepare report files.", "Annotated image, CSV, PDF, ZIP"),
]


def _text(value):
    return escape(str(value if value is not None else ""))


def _number(value, unit=""):
    if value is None:
        return "Not calibrated" if unit == "mm" else "-"
    return f"{float(value):.2f} {unit}".strip()


def _date_time(value):
    if hasattr(value, "astimezone"):
        local_value = value.astimezone()
        return local_value.strftime("%Y-%m-%d %H:%M:%S %z")
    if value:
        return str(value)
    return "Not available"


def _image(path, max_width=6.4 * inch, max_height=3.8 * inch):
    """Create an aspect-preserving ReportLab image."""
    reader = ImageReader(str(path))
    width, height = reader.getSize()
    scale = min(max_width / width, max_height / height)
    image = Image(str(path), width=width * scale, height=height * scale)
    image.hAlign = "LEFT"
    return image


def _table(rows, widths, header=True, font_size=8):
    style = [
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#94a3b8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        style.extend([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#172033")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])
    return Table(rows, colWidths=widths, repeatRows=1 if header else 0, style=TableStyle(style))


def _footer(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
    canvas.line(36, 28, A4[0] - 36, 28)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(36, 16, "Crack Detaction - image-based crack measurement report")
    canvas.drawRightString(A4[0] - 36, 16, f"Page {document.page}")
    canvas.restoreState()


def create_pdf(analysis, images, measurements, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=42,
        bottomMargin=42,
        title=f"Crack Detaction report - {analysis.get('analysis_name', '')}",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], alignment=TA_CENTER, fontSize=20, leading=24, spaceAfter=10, textColor=colors.HexColor("#123b66")))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10, spaceAfter=6, textColor=colors.HexColor("#475569")))
    styles.add(ParagraphStyle(name="Step", parent=styles["BodyText"], fontSize=9, leading=12, spaceAfter=3))
    styles["Heading2"].spaceBefore = 12
    styles["Heading2"].spaceAfter = 8
    styles["Heading3"].spaceBefore = 10
    styles["Heading3"].spaceAfter = 6
    generated_at = datetime.now(timezone.utc)
    story = [
        Paragraph("Crack Detaction Measurement Report", styles["ReportTitle"]),
        Spacer(1, 6),
        Paragraph(f"<b>Analysis:</b> {_text(analysis.get('analysis_name', 'Untitled analysis'))}", styles["Heading2"]),
        Paragraph(f"<b>Analysis ID:</b> {_text(analysis.get('analysis_id', ''))} &nbsp;&nbsp; <b>Status:</b> {_text(analysis.get('status', ''))}", styles["Small"]),
        Paragraph(f"<b>Analysis date and time:</b> {_text(_date_time(analysis.get('created_at')))}", styles["Small"]),
        Paragraph(f"<b>Report generated date and time:</b> {_text(_date_time(generated_at))}", styles["Small"]),
        Paragraph("This report contains automated image-processing results. It is not a certified structural safety assessment.", styles["Small"]),
        Spacer(1, 14),
    ]

    counts = Counter(item.get("severity", "Unknown") for item in measurements)
    total = len(measurements)
    calibrated = bool(analysis.get("calibration_enabled") and analysis.get("pixels_per_mm"))
    pixels_per_mm = analysis.get("pixels_per_mm")
    total_length_px = sum(item.get("skeleton_length_px", 0) for item in measurements)
    total_length_mm = sum(item.get("skeleton_length_mm") or 0 for item in measurements) if calibrated else None
    average_width_px = sum(item.get("mean_width_px", 0) for item in measurements) / total if total else 0
    average_width_mm = sum(item.get("mean_width_mm") or 0 for item in measurements) / total if total and calibrated else None
    maximum_width_px = max((item.get("max_width_px", 0) for item in measurements), default=0)
    maximum_width_mm = max((item.get("max_width_mm") or 0 for item in measurements), default=0) if calibrated else None
    overall = "Heavy" if counts["Heavy"] else "Medium" if counts["Medium"] else "Good" if total else "No data"

    summary_rows = [
        ["Report item", "Result"],
        ["Images processed", str(len(images))],
        ["Detected crack regions", str(total)],
        ["Total crack length", f"{_number(total_length_px, 'px')} / {_number(total_length_mm, 'mm')}"],
        ["Average crack width", f"{_number(average_width_px, 'px')} / {_number(average_width_mm, 'mm')}"],
        ["Maximum crack width", f"{_number(maximum_width_px, 'px')} / {_number(maximum_width_mm, 'mm')}"],
        ["Overall severity", f"{overall} (Good {counts['Good']}, Medium {counts['Medium']}, Heavy {counts['Heavy']})"],
        ["Calibration", f"{_number(pixels_per_mm, 'pixels/mm')}" if calibrated else "Pixel-only; millimeters not calibrated"],
    ]
    story.extend([
        KeepTogether([
            Paragraph("1. Crack analysis summary", styles["Heading2"]),
            Paragraph("This section provides the key results before the detailed workflow and evidence.", styles["Small"]),
            Spacer(1, 10),
            _table(summary_rows, [2.3 * inch, 4.0 * inch]),
        ]),
        Spacer(1, 14),
    ])

    thresholds = analysis.get("severity_thresholds", {"good_max_width_px": 3, "medium_max_width_px": 8, "heavy_min_area_px": 5000})
    threshold_rows = [["Category", "Pixel rule", "Millimeter rule"]]
    if calibrated:
        threshold_rows.extend([
            ["Good", f"Mean width <= {thresholds['good_max_width_px']} px", f"Mean width <= {thresholds['good_max_width_px'] / pixels_per_mm:.3f} mm"],
            ["Medium", f"> {thresholds['good_max_width_px']} and <= {thresholds['medium_max_width_px']} px", f"> {thresholds['good_max_width_px'] / pixels_per_mm:.3f} and <= {thresholds['medium_max_width_px'] / pixels_per_mm:.3f} mm"],
            ["Heavy", f"> {thresholds['medium_max_width_px']} px or area >= {thresholds['heavy_min_area_px']} px^2", f"> {thresholds['medium_max_width_px'] / pixels_per_mm:.3f} mm or area >= {thresholds['heavy_min_area_px'] / pixels_per_mm**2:.3f} mm^2"],
        ])
    else:
        threshold_rows.extend([
            ["Good", f"Mean width <= {thresholds['good_max_width_px']} px", "Not calibrated"],
            ["Medium", f"> {thresholds['good_max_width_px']} and <= {thresholds['medium_max_width_px']} px", "Not calibrated"],
            ["Heavy", f"> {thresholds['medium_max_width_px']} px or area >= {thresholds['heavy_min_area_px']} px^2", "Not calibrated"],
        ])
    story.extend([
        KeepTogether([
            Paragraph("2. Calibration and severity thresholds", styles["Heading2"]),
            Spacer(1, 10),
            _table(threshold_rows, [1.0 * inch, 2.8 * inch, 2.5 * inch]),
        ]),
        Spacer(1, 14),
        PageBreak(),
    ])

    workflow_rows = [["Step", "Stage", "Action", "Output"]]
    workflow_rows.extend([
        [number, Paragraph(f"<b>{_text(title)}</b>", styles["Step"]), Paragraph(_text(description), styles["Step"]), Paragraph(_text(output), styles["Step"])]
        for number, title, description, output in WORKFLOW_STEPS
    ])
    story.extend([
        KeepTogether([
            Paragraph("3. Processing workflow - step by step", styles["Heading2"]),
            Paragraph("The following numbered stages are executed in order for every uploaded image. The output column identifies the evidence included later in this report.", styles["Small"]),
            Spacer(1, 10),
        ]),
        _table(workflow_rows, [.45 * inch, 1.45 * inch, 2.55 * inch, 1.95 * inch], font_size=8),
        Spacer(1, 12),
    ])
    timing_rows = [["Image", "Stage", "Time (s)"]]
    for image in images:
        for stage, seconds in image.get("workflow_times", {}).items():
            timing_rows.append([_text(image.get("original_filename", "")), stage.replace("_", " ").title(), f"{float(seconds):.4f}"])
    story.append(Paragraph("Workflow timings", styles["Heading3"]))
    story.append(Paragraph("Times are measured by the application and are reported separately for each uploaded image.", styles["Small"]))
    if len(timing_rows) > 1:
        story.extend([Spacer(1, 8), _table(timing_rows, [2.8 * inch, 2.3 * inch, 1.2 * inch])])
    story.append(PageBreak())
    story.append(KeepTogether([
        Paragraph("4. Crack measurements", styles["Heading2"]),
        Paragraph("Every value is shown as pixels and millimeters where calibration is available.", styles["Small"]),
        Spacer(1, 10),
    ]))
    measurement_rows = [["Image / crack", "Area px^2", "Area mm^2", "Length px", "Length mm", "Severity"]]
    for item in measurements:
        measurement_rows.append([
            f"{_text(item.get('image_id', ''))[:12]} / {_text(item.get('crack_id', ''))}",
            _number(item.get("contour_area_px"), "px^2"),
            _number(item.get("contour_area_mm2"), "mm^2"),
            _number(item.get("skeleton_length_px"), "px"),
            _number(item.get("skeleton_length_mm"), "mm"),
            _text(item.get("severity", "")),
        ])
    if len(measurement_rows) == 1:
        measurement_rows.append(["No candidate crack regions", "-", "-", "-", "-", "-"])
    story.append(_table(measurement_rows, [1.55 * inch, .85 * inch, .85 * inch, .85 * inch, .85 * inch, .95 * inch], font_size=7))
    story.append(Spacer(1, 10))
    width_rows = [["Crack", "Mean width px", "Mean width mm", "Max width px", "Max width mm", "Samples"]]
    for item in measurements:
        width_rows.append([
            _text(item.get("crack_id", "")),
            _number(item.get("mean_width_px"), "px"),
            _number(item.get("mean_width_mm"), "mm"),
            _number(item.get("max_width_px"), "px"),
            _number(item.get("max_width_mm"), "mm"),
            str(item.get("width_sample_count", 0)),
        ])
    if len(width_rows) == 1:
        width_rows.append(["No measurements", "-", "-", "-", "-", "-"])
    story.extend([Spacer(1, 10), _table(width_rows, [1.55 * inch, 1.05 * inch, 1.05 * inch, 1.05 * inch, 1.05 * inch, .65 * inch], font_size=7)])
    story.append(PageBreak())
    story.append(KeepTogether([
        Paragraph("5. Image-processing evidence", styles["Heading2"]),
        Paragraph("Each processing stage is shown in a readable flow below. The stage name and source file are kept with its image so the evidence remains understandable when printed or extracted from the ZIP package.", styles["Small"]),
    ]))
    for image_index, image in enumerate(images, 1):
        story.append(Paragraph(_text(image.get("original_filename", "Image")), styles["Heading3"]))
        stage_order = [
            ("resized", "Resized input"),
            ("gray", "Grayscale"),
            ("blurred", "Gaussian blur"),
            ("clahe", "CLAHE"),
            ("blackhat", "BlackHat"),
            ("binary", "Otsu threshold"),
            ("cleaned_mask", "Morphological cleanup"),
            ("segmentation_mask", "Segmentation mask"),
        ]
        stage_order.extend(
            (stage, stage.replace("_", " ").title())
            for stage in image.get("processed_paths", {})
            if stage.startswith(("distance_transform_", "width_estimation_", "skeleton_"))
        )
        evidence_rows = []
        for stage_index, (stage, title) in enumerate(stage_order, 1):
            path = image.get("processed_paths", {}).get(stage)
            if path and Path(path).exists():
                if stage_index > 1 or image_index > 1:
                    story.append(PageBreak())
                story.extend([
                    Paragraph(f"Evidence {image_index}.{stage_index}: {_text(title)}", styles["Heading3"]),
                    Paragraph(f"<font color='#64748b'>File: {_text(Path(path).name)}</font>", styles["Small"]),
                    Spacer(1, 6),
                    _image(path, 6.4 * inch, 5.0 * inch),
                    Spacer(1, 14),
                ])
        annotated = image.get("annotated_path")
        if annotated and Path(annotated).exists():
            story.extend([Spacer(1, 10), Paragraph("Annotated result with measurement lines", styles["Heading3"]), _image(annotated)])
        story.append(PageBreak())

    story.append(Paragraph("6. Assessment notes", styles["Heading2"]))
    if counts["Heavy"]:
        remark = f"Heavy-severity indications were detected in {counts['Heavy']} of {total} crack region(s). Review the annotated evidence and arrange a qualified structural inspection."
    elif counts["Medium"]:
        remark = f"Medium-severity indications were detected in {counts['Medium']} of {total} crack region(s). Monitor the affected area and consider a qualified inspection."
    elif total:
        remark = f"All {total} detected crack region(s) are in the Good software category. Continue routine monitoring."
    else:
        remark = "No crack measurements were produced. Upload a clearer crack image for another analysis."
    story.extend([
        Paragraph(remark, styles["BodyText"]),
        Spacer(1, 8),
        Paragraph("The results depend on lighting, image resolution, texture, resizing, segmentation thresholds, and calibration accuracy. Use this report as an inspection aid, not as a standalone engineering conclusion.", styles["BodyText"]),
    ])
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output_path
