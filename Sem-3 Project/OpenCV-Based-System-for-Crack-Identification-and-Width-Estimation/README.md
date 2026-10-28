# Crack Detaction

Crack Detaction is a Flask/OpenCV research application for identifying candidate crack-like regions in concrete, road, wall, and pavement images. It reports measurements in pixels and optionally converts them to millimeters when a valid pixels-per-millimeter calibration is provided. Its severity labels are configurable software categories, not professional structural safety judgments.

## Prerequisites

- Python 3.10+
- MongoDB Community Server, or a MongoDB Atlas connection string

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with your MongoDB URI and a secret key. The default database is `crack_detection_db`. The app stores image stages and reports under `storage/`; those files are intentionally not stored in MongoDB.

## Run

### Automatic Windows launch

Double-click [`run_crackscope.bat`](./run_crackscope.bat). It will:

1. Create `.venv` if it does not exist.
2. Create `.env` from `.env.example` if needed.
3. Install or update the Python dependencies.
4. Start Flask on `http://127.0.0.1:5000`.
5. Wait until Flask responds and open the upload page in your default browser.

The launcher enables automatic source reload, so Python changes restart the server without manually closing and starting it again. Keep the **Crack Detaction Flask Server** console open while using the application. Close that console to stop Flask.

### Manual launch

```powershell
python app.py
```

Open `http://127.0.0.1:5000`. Use **Upload** to select one or more JPG, JPEG, JFIF, or PNG files. Pixel-to-millimeter calibration is applied automatically using the configured default of 10 pixels/mm. Detection starts automatically; uploads that contain no detected crack are rejected with an error. Results include original, preprocessing stages, segmentation, skeletons, and annotated images. The analysis page provides CSV, PDF, and ZIP downloads.

## Processing workflow

The pipeline resizes while preserving aspect ratio, converts to grayscale, applies Gaussian blur and CLAHE, computes a BlackHat transform, uses adaptive local thresholding to preserve normal crack lines without turning pavement texture into foreground, cleans morphology, filters connected components, preserves multiple sufficiently strong crack networks, skeletonizes each candidate, estimates skeleton length and distance-transform width, and draws annotated results. Width is reported from stable centerline samples: the median is used for mean width and the 95th percentile is used for maximum width, preventing a branch or segmentation blob from dominating the result. Synthetic tests exercise this pipeline; real photographs still require domain validation and suitable calibration.

## Tests

```powershell
pytest -q
```

If MongoDB is unavailable, the Flask process still starts and keeps newly created results available for the current running session. Configure MongoDB for permanent history. When running `python app.py`, source changes automatically restart Flask; set `FLASK_AUTO_RELOAD=0` to disable this behavior.

## Troubleshooting

- Check that MongoDB is running and `MONGO_URI` is correct.
- Ensure the account can create indexes and collections.
- Increase `MAX_CONTENT_LENGTH` for larger images.
- Candidate detection is sensitive to lighting, texture, and the configured BlackHat and minimum-area parameters.
