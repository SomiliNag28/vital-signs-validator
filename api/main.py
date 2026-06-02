# FastAPI inference service for ICU vital signs validation pipeline.
# Visit: http://127.0.0.1:8000/docs

import os
import sys
import json
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator
from collections import defaultdict
import time

# Global metrics store — updated by every request
METRICS = {
    "server_start_time"        : time.time(),
    "total_requests"           : 0,
    "total_validations"        : 0,
    "total_single_validations" : 0,
    "total_critical_issues"    : 0,
    "total_warnings"           : 0,
    "total_anomalies"          : 0,
    "total_passed"             : 0,
    "total_failed"             : 0,
    "total_readings_processed" : 0,
    "recent_validations"       : [],   # last 10 validation summaries
}

def record_validation(summary: dict, is_batch: bool = True) -> None:
    # Update global metrics after every validation run.
    METRICS["total_requests"]            += 1
    METRICS["total_critical_issues"]     += summary.get("critical_count", 0)
    METRICS["total_warnings"]            += summary.get("warning_count", 0)
    METRICS["total_anomalies"]           += summary.get("total_anomalies", 0)
    METRICS["total_readings_processed"]  += summary.get("total_rows", 1)

    if is_batch:
        METRICS["total_validations"] += 1
    else:
        METRICS["total_single_validations"] += 1

    if summary.get("passed", False):
        METRICS["total_passed"] += 1
    else:
        METRICS["total_failed"] += 1

    # Keep last 10 validation records for recent activity feed
    recent_entry = {
        "timestamp"      : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type"           : "batch" if is_batch else "single",
        "rows"           : summary.get("total_rows", 1),
        "critical"       : summary.get("critical_count", 0),
        "warnings"       : summary.get("warning_count", 0),
        "anomalies"      : summary.get("total_anomalies", 0),
        "passed"         : summary.get("passed", False),
    }
    METRICS["recent_validations"].insert(0, recent_entry)
    METRICS["recent_validations"] = METRICS["recent_validations"][:10]


# ── [S5.1] Path setup ─────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
sys.path.insert(0, BASE_DIR)

import pandas as pd
from src.pipeline import run_pipeline


# ── [S5.2] App initialization ─────────────────────────────────────────────────
app = FastAPI(
    title       = "ICU Vital Signs Validation API",
    description = (
        "A feature validation and anomaly detection pipeline for ICU "
        "patient vital signs data. Validates physiological ranges, "
        "detects sensor anomalies, and generates HTML reports."
    ),
    version     = "1.0.0",
)


# ── [S5.3] Pydantic Schemas ───────────────────────────────────────────────────

class VitalReading(BaseModel):
    """Schema for a single patient vital signs reading."""
    patient_id  : str            = Field(
        ..., description="Unique patient identifier",
        examples=["P0001"])
    timestamp   : str            = Field(
        ..., description="ISO format timestamp",
        examples=["2024-01-01 00:00:00"])
    heart_rate  : Optional[float] = Field(
        None, description="Heart rate in bpm",
        examples=[75.0])
    spo2        : Optional[float] = Field(
        None, description="Oxygen saturation in %",
        examples=[97.5])
    temperature : Optional[float] = Field(
        None, description="Body temperature in Celsius",
        examples=[37.0])
    systolic_bp : Optional[float] = Field(
        None, description="Systolic blood pressure in mmHg",
        examples=[120.0])
    diastolic_bp: Optional[float] = Field(
        None, description="Diastolic blood pressure in mmHg",
        examples=[80.0])
    resp_rate   : Optional[float] = Field(
        None, description="Respiratory rate per minute",
        examples=[16.0])

    # [S5.3-A] Validate heart rate is positive if provided
    @field_validator("heart_rate")
    @classmethod
    def heart_rate_positive(cls, v):
        if v is not None and v < 0:
            raise ValueError("heart_rate cannot be negative")
        return v

    # [S5.3-B] Validate SpO2 is within absolute bounds
    @field_validator("spo2")
    @classmethod
    def spo2_bounds(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError("spo2 must be between 0 and 100")
        return v


class BatchValidateRequest(BaseModel):
    """Schema for batch validation request."""
    readings: List[VitalReading] = Field(
        ...,
        min_length=1,
        description="List of vital sign readings to validate",
    )


class ValidationSummaryResponse(BaseModel):
    """Schema for validation pipeline response."""
    status          : str   = Field(description="PASS or FAIL")
    total_rows      : int   = Field(description="Number of readings processed")
    total_issues    : int   = Field(description="Total validation issues found")
    critical_count  : int   = Field(description="Number of critical issues")
    warning_count   : int   = Field(description="Number of warnings")
    total_anomalies : int   = Field(description="Total anomalies detected")
    anomaly_critical: int   = Field(description="Critical anomalies")
    passed          : bool  = Field(description="True if no critical issues")
    report_filename : str   = Field(description="HTML report filename")
    report_url      : str   = Field(description="URL to download HTML report")
    generated_at    : str   = Field(description="Report generation timestamp")


class SingleReadingResponse(BaseModel):
    """Schema for single reading validation response."""
    patient_id      : str
    passed          : bool
    critical_count  : int
    warning_count   : int
    issues          : List[dict]
    anomalies       : List[dict]


class HealthResponse(BaseModel):
    """Schema for health check response."""
    status      : str
    version     : str
    pipeline    : str
    reports_dir : str


# ── [S5.4] Root Endpoint ──────────────────────────────────────────────────────

@app.get("/", summary="Redirect to dashboard")
def root():
    # Redirect root URL to the live monitoring dashboard.
    return RedirectResponse(url="/dashboard")

# ── [S5.5] Health Endpoint ────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check"
)
def health():
    """
    Health check endpoint.
    Verifies pipeline modules are importable and reports dir exists.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    return HealthResponse(
        status      = "ok",
        version     = "1.0.0",
        pipeline    = "ready",
        reports_dir = REPORTS_DIR,
    )


# ── [S5.6] Batch Validation Endpoint ─────────────────────────────────────────

@app.post(
    "/validate",
    response_model = ValidationSummaryResponse,
    summary        = "Validate a batch of vital sign readings"
)
def validate_batch(request: BatchValidateRequest):
    # Run the full validation pipeline on a batch of vital sign readings.
    try:
        # [S5.6-A] Convert readings to DataFrame
        records = [r.model_dump() for r in request.readings]
        df      = pd.DataFrame(records)

        # [S5.6-B] Run full pipeline
        result = run_pipeline(df)
        summary = result["summary"]

        # [S5.6-C] Get report filename for download URL
        report_path     = summary["report_path"]
        report_filename = os.path.basename(report_path)
        report_url      = f"/report/{report_filename}"

        # [M2] Record metrics
        record_validation(summary, is_batch=True)

        return ValidationSummaryResponse(
            status           = "PASS" if summary["passed"] else "FAIL",
            total_rows       = summary["total_rows"],
            total_issues     = summary["total_issues"],
            critical_count   = summary["critical_count"],
            warning_count    = summary["warning_count"],
            total_anomalies  = summary["total_anomalies"],
            anomaly_critical = summary["anomaly_critical"],
            passed           = summary["passed"],
            report_filename  = report_filename,
            report_url       = report_url,
            generated_at     = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline error: {str(e)}"
        )


# ── [S5.7] Single Reading Endpoint ───────────────────────────────────────────

@app.post(
    "/validate/row",
    response_model = SingleReadingResponse,
    summary        = "Validate a single vital signs reading instantly"
)
def validate_single(reading: VitalReading):
    # Validate a single patient reading in real time.
    try:
        # [S5.7-A] Single row DataFrame
        df = pd.DataFrame([reading.model_dump()])

        # [S5.7-B] Run validator only (no report for single row)
        from src.validator import VitalSignsValidator
        from src.anomaly   import AnomalyDetector

        validator = VitalSignsValidator()
        detector  = AnomalyDetector()

        v_results = validator.validate(df)
        a_results = detector.detect(df)

        # [S5.7-C] Serialize issues to plain dicts for JSON response
        issues = [
            {
                "column"   : i.column,
                "value"    : i.value if i.value == i.value else None,
                "severity" : i.severity.value
                             if hasattr(i.severity, 'value')
                             else str(i.severity),
                "rule"     : i.rule,
            }
            for i in v_results["issues"]
        ]

        anomalies = [
            {
                "type"       : a.anomaly_type.value
                               if hasattr(a.anomaly_type, 'value')
                               else str(a.anomaly_type),
                "column"     : a.column,
                "value"      : a.value if a.value == a.value else None,
                "severity"   : a.severity,
                "description": a.description,
            }
            for a in a_results["anomalies"]
        ]

        # [M3] Record metrics for single validation
        single_summary = {
            "total_rows"     : 1,
            "critical_count" : v_results["critical_count"],
            "warning_count"  : v_results["warning_count"],
            "total_anomalies": a_results["total_anomalies"],
            "passed"         : v_results["passed"],
        }
        record_validation(single_summary, is_batch=False)

        return SingleReadingResponse(
            patient_id    = reading.patient_id,
            passed        = v_results["passed"],
            critical_count= v_results["critical_count"],
            warning_count = v_results["warning_count"],
            issues        = issues,
            anomalies     = anomalies,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Validation error: {str(e)}"
        )


# ── [S5.8] Report Download Endpoint ──────────────────────────────────────────

@app.get(
    "/report/{filename}",
    summary="Download a generated HTML validation report"
)
def download_report(filename: str):
    """
    Serve a previously generated HTML validation report.
    """
    # [S5.8-A] Security: prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # [S5.8-B] Only allow .html files
    if not filename.endswith(".html"):
        raise HTTPException(status_code=400, detail="Invalid file type")

    # [S5.8-C] Only allow files matching our naming pattern
    if not filename.startswith("validation_report_"):
        raise HTTPException(status_code=404, detail="Report not found")

    report_path = os.path.join(REPORTS_DIR, filename)

    if not os.path.exists(report_path):
        raise HTTPException(
            status_code=404,
            detail=f"Report '{filename}' not found."
        )

    return FileResponse(
        path       = report_path,
        media_type = "text/html",
        filename   = filename,
    )

# ── [M4] Metrics Endpoint ─────────────────────────────────────────────────────

@app.get("/metrics", summary="Live pipeline metrics")
def get_metrics():
    # Return live metrics for the validation pipeline.
    uptime_seconds = time.time() - METRICS["server_start_time"]
    uptime_minutes = uptime_seconds / 60
    uptime_hours   = uptime_minutes / 60

    total_val = (
        METRICS["total_validations"] +
        METRICS["total_single_validations"]
    )
    pass_rate = (
        (METRICS["total_passed"] / total_val * 100)
        if total_val > 0 else 0
    )

    return {
        "service"                  : "ICU Vital Signs Validation API",
        "version"                  : "1.0.0",
        "uptime"                   : {
            "seconds"              : round(uptime_seconds, 1),
            "minutes"              : round(uptime_minutes, 2),
            "hours"                : round(uptime_hours, 3),
        },
        "requests"                 : {
            "total"                : METRICS["total_requests"],
            "batch_validations"    : METRICS["total_validations"],
            "single_validations"   : METRICS["total_single_validations"],
        },
        "validation_outcomes"      : {
            "total_passed"         : METRICS["total_passed"],
            "total_failed"         : METRICS["total_failed"],
            "pass_rate_percent"    : round(pass_rate, 1),
        },
        "data_quality_stats"       : {
            "total_readings"       : METRICS["total_readings_processed"],
            "total_critical_issues": METRICS["total_critical_issues"],
            "total_warnings"       : METRICS["total_warnings"],
            "total_anomalies"      : METRICS["total_anomalies"],
        },
        "recent_validations"       : METRICS["recent_validations"],
    }


# ── [M5] Monitoring Dashboard Endpoint ───────────────────────────────────────

@app.get("/dashboard", summary="Live monitoring dashboard")
def monitoring_dashboard():
    """  
    Serve the live HTML monitoring dashboard.
    Auto-refreshes every 10 seconds.
    """
    dashboard_path = os.path.join(BASE_DIR, "monitoring", "dashboard.html")
    if not os.path.exists(dashboard_path):
        raise HTTPException(
            status_code=404,
            detail="Dashboard not found. Create monitoring/dashboard.html"
        )
    return FileResponse(dashboard_path, media_type="text/html")


def download_report(filename: str):
    # Serve a previously generated HTML validation report.
    # [S5.8-A] Security: prevent path traversal attacks
    # e.g. filename = "../../etc/passwd"
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename"
        )

    report_path = os.path.join(REPORTS_DIR, filename)

    if not os.path.exists(report_path):
        raise HTTPException(
            status_code=404,
            detail=f"Report '{filename}' not found. "
                   f"Run /validate first to generate a report."
        )

    return FileResponse(
        path         = report_path,
        media_type   = "text/html",
        filename     = filename,
    )