# Weather Prediction Agent (Enhanced)

This project is an enhanced Streamlit app for weather prediction (temperature regression + rain classification).
It includes:
- Support for loading a real historical CSV (via `data/historical.csv` or upload in the UI)
- Model choices: LightGBM, XGBoost, RandomForest
- Optional Optuna hyperparameter tuning
- SHAP-based explainability saved as an image
- A packaged, ready-to-run Streamlit UI

## Quick start

1. Copy the project to your machine or download the zip provided by the assistant.
2. Create & activate a Python virtual environment:

Linux / macOS:
```bash
python -m venv venv
source venv/bin/activate
```

Windows:
```powershell
python -m venv venv
venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the app:
```bash
streamlit run streamlit_app.py
```

5. In the app:
- (Optional) Upload a historical CSV with the expected columns (see below) or place it at `data/historical.csv`.
- Choose model type and whether to tune.
- Train models and then fetch/predict and explain predictions.

## Historical CSV format (required columns)
The CSV should contain these columns (header names):

- timestamp (ISO datetime string, e.g. 2022-01-01T12:00:00)
- temp_c (temperature in Celsius)
- humidity (percent)
- pressure (hPa)
- wind_speed (m/s or km/h)
- precip_mm (precipitation amount in mm for the interval)

Column names are case-sensitive. If your CSV uses different names, rename them before upload.

## Notes
- The project falls back to a synthetic historical generator only if no CSV is provided.
- Optuna tuning may take time depending on `n_trials` — keep it small (5-30) for quick runs.
- SHAP explainability will be saved as `models/shap_summary.png`.

