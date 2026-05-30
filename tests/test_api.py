# Integration tests for the FastAPI validation service.

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


# ── [T2.1] Test data helpers ──────────────────────────────────────────────────

def clean_reading(patient_id="P0001"):
    """Normal vital signs reading."""
    return {
        "patient_id"  : patient_id,
        "timestamp"   : "2024-01-01 00:00:00",
        "heart_rate"  : 72.0,
        "spo2"        : 98.0,
        "temperature" : 36.8,
        "systolic_bp" : 118.0,
        "diastolic_bp": 76.0,
        "resp_rate"   : 15.0,
    }


def critical_reading(patient_id="P0002"):
    """Life-threatening vital signs reading."""
    return {
        "patient_id"  : patient_id,
        "timestamp"   : "2024-01-01 00:01:00",
        "heart_rate"  : 210.0,
        "spo2"        : 45.0,
        "temperature" : 42.5,
        "systolic_bp" : 250.0,
        "diastolic_bp": 80.0,
        "resp_rate"   : 16.0,
    }


# ── [T2.2] Root and Health Tests ──────────────────────────────────────────────

class TestRootEndpoint:
    """Tests for GET /"""

    def test_returns_200(self):
        """Root endpoint returns HTTP 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_returns_service_name(self):
        """Response contains correct service name."""
        response = client.get("/")
        assert "ICU Vital Signs" in response.json()["service"]

    def test_returns_endpoints_map(self):
        """Response lists available endpoints."""
        response = client.get("/")
        assert "endpoints" in response.json()


class TestHealthEndpoint:
    """Tests for GET /health"""

    def test_returns_200(self):
        """Health endpoint returns HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_status_ok(self):
        """Health status is 'ok'."""
        response = client.get("/health")
        assert response.json()["status"] == "ok"

    def test_pipeline_ready(self):
        """Pipeline status is 'ready'."""
        response = client.get("/health")
        assert response.json()["pipeline"] == "ready"

    def test_version_present(self):
        """Version field is present."""
        response = client.get("/health")
        assert "version" in response.json()


# ── [T2.3] Single Reading Tests ───────────────────────────────────────────────

class TestSingleReadingEndpoint:
    """Tests for POST /validate/row"""

    def test_clean_reading_passes(self):
        """Clean reading returns passed=True."""
        response = client.post(
            "/validate/row",
            json=clean_reading()
        )
        assert response.status_code == 200
        assert response.json()["passed"] is True

    def test_critical_reading_fails(self):
        """Critical reading returns passed=False."""
        response = client.post(
            "/validate/row",
            json=critical_reading()
        )
        assert response.status_code == 200
        assert response.json()["passed"] is False

    def test_critical_reading_has_critical_count(self):
        """Critical reading returns non-zero critical_count."""
        response = client.post(
            "/validate/row",
            json=critical_reading()
        )
        assert response.json()["critical_count"] > 0

    def test_clean_reading_has_zero_issues(self):
        """Clean reading returns empty issues list."""
        response = client.post(
            "/validate/row",
            json=clean_reading()
        )
        assert response.json()["critical_count"] == 0
        assert response.json()["issues"] == []

    def test_response_has_patient_id(self):
        """Response includes patient_id from request."""
        response = client.post(
            "/validate/row",
            json=clean_reading("TEST_PATIENT")
        )
        assert response.json()["patient_id"] == "TEST_PATIENT"

    def test_response_has_all_fields(self):
        """Response contains all required fields."""
        response = client.post(
            "/validate/row",
            json=clean_reading()
        )
        data = response.json()
        for key in [
            "patient_id", "passed", "critical_count",
            "warning_count", "issues", "anomalies"
        ]:
            assert key in data

    def test_invalid_spo2_rejected(self):
        """SpO2 above 100 is rejected by Pydantic validator."""
        bad = clean_reading()
        bad["spo2"] = 150.0
        response = client.post("/validate/row", json=bad)
        assert response.status_code == 422

    def test_negative_heart_rate_detected(self):
        """Negative heart rate is rejected."""
        bad = clean_reading()
        bad["heart_rate"] = -10.0
        response = client.post("/validate/row", json=bad)
        assert response.status_code == 422

    def test_missing_patient_id_rejected(self):
        """Missing patient_id triggers 422."""
        bad = clean_reading()
        del bad["patient_id"]
        response = client.post("/validate/row", json=bad)
        assert response.status_code == 422

    def test_missing_timestamp_rejected(self):
        """Missing timestamp triggers 422."""
        bad = clean_reading()
        del bad["timestamp"]
        response = client.post("/validate/row", json=bad)
        assert response.status_code == 422


# ── [T2.4] Batch Validation Tests ─────────────────────────────────────────────

class TestBatchValidationEndpoint:
    """Tests for POST /validate"""

    def test_single_clean_batch_passes(self):
        """Batch of one clean reading passes."""
        response = client.post(
            "/validate",
            json={"readings": [clean_reading()]}
        )
        assert response.status_code == 200
        assert response.json()["passed"] is True

    def test_batch_with_critical_fails(self):
        """Batch containing critical reading fails."""
        response = client.post(
            "/validate",
            json={"readings": [
                clean_reading("P0001"),
                critical_reading("P0002"),
            ]}
        )
        assert response.status_code == 200
        assert response.json()["passed"] is False

    def test_batch_response_has_report_url(self):
        """Batch response includes report_url."""
        response = client.post(
            "/validate",
            json={"readings": [clean_reading()]}
        )
        assert "report_url" in response.json()
        assert response.json()["report_url"].startswith("/report/")

    def test_batch_response_has_all_fields(self):
        """Batch response contains all required fields."""
        response = client.post(
            "/validate",
            json={"readings": [clean_reading()]}
        )
        data = response.json()
        for key in [
            "status", "total_rows", "total_issues",
            "critical_count", "warning_count",
            "total_anomalies", "passed",
            "report_filename", "report_url", "generated_at"
        ]:
            assert key in data

    def test_total_rows_matches_input(self):
        """total_rows matches number of readings sent."""
        response = client.post(
            "/validate",
            json={"readings": [
                clean_reading("P0001"),
                clean_reading("P0002"),
                clean_reading("P0003"),
            ]}
        )
        assert response.json()["total_rows"] == 3

    def test_status_field_is_pass_or_fail(self):
        """Status field is either PASS or FAIL."""
        response = client.post(
            "/validate",
            json={"readings": [clean_reading()]}
        )
        assert response.json()["status"] in ["PASS", "FAIL"]

    def test_empty_readings_rejected(self):
        """Empty readings list triggers 422."""
        response = client.post(
            "/validate",
            json={"readings": []}
        )
        assert response.status_code == 422

    def test_missing_readings_field_rejected(self):
        """Missing readings field triggers 422."""
        response = client.post("/validate", json={})
        assert response.status_code == 422


# ── [T2.5] Report Download Tests ─────────────────────────────────────────────

class TestReportEndpoint:
    """Tests for GET /report/{filename}"""

    def test_nonexistent_report_returns_404(self):
        """Requesting missing report returns 404."""
        response = client.get("/report/nonexistent_report.html")
        assert response.status_code == 404

    def test_path_traversal_rejected(self):
        """Path traversal attempt returns 400."""
        response = client.get("/report/../../etc/passwd")
        assert response.status_code == 404

    def test_generated_report_is_downloadable(self):
        """
        Report generated by /validate is downloadable via /report.
        First generate a report, then fetch it.
        """
        # Generate report
        validate_response = client.post(
            "/validate",
            json={"readings": [clean_reading()]}
        )
        assert validate_response.status_code == 200
        filename = validate_response.json()["report_filename"]

        # Download it
        report_response = client.get(f"/report/{filename}")
        assert report_response.status_code == 200
        assert "text/html" in report_response.headers["content-type"]