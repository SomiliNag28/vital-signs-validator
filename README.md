# ICU Vital Signs Validation Pipeline

A production-style feature validation and anomaly detection pipeline
for ICU patient vital signs data. Validates physiological ranges,
detects sensor anomalies, and generates HTML reports via a REST API.

## Project Structure

```
vital_signs_validator/
├── data/                    # Raw dataset
├── reports/                 # Generated HTML reports
├── src/
│   ├── explore.py           # Dataset exploration
│   ├── validator.py         # Validation rules engine
│   ├── anomaly.py           # Anomaly detection
│   ├── reporter.py          # HTML report generator
│   └── pipeline.py          # Master pipeline
├── api/
│   └── main.py              # FastAPI service
├── tests/
│   ├── test_validator.py    # Unit tests
│   └── test_api.py          # Integration tests
├── run_pipeline.py          # CLI entry point
└── requirements.txt
```

## Quickstart

```bash
git clone <your-repo-url>
cd vital_signs_validator
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run_pipeline.py        # CLI — generates HTML report
uvicorn api.main:app --reload # API — visit /docs
pytest tests/ -v              # Tests
```

## Validation Rules

| Vital Sign | Normal Range | Critical Threshold |
|---|---|---|
| Heart Rate | 60–100 bpm | <40 or >150 |
| SpO2 | 95–100% | <90% |
| Temperature | 36.1–37.2°C | <35 or >38.5 |
| Systolic BP | 90–140 mmHg | <70 or >180 |
| Diastolic BP | 60–90 mmHg | <40 or >120 |
| Resp Rate | 12–20 /min | <8 or >30 |

## Anomaly Detection

- Statistical outliers (Z-score > 3σ)
- Stuck sensor (identical values repeated)
- Sudden spikes (delta exceeds threshold)
- Timestamp gaps (missing monitoring periods)
- Flatlines (near-zero variance window)

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| / | GET | Service info |
| /health | GET | Health check |
| /validate | POST | Batch validation + HTML report |
| /validate/row | POST | Single reading instant check |
| /report/{filename} | GET | Download HTML report |

## Tech Stack

Python · Pandas · NumPy · SciPy · FastAPI · Pydantic · Pytest