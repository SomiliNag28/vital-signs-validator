# Unit tests for the validation rules engine.

import sys
import os
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.validator import VitalSignsValidator, Severity


# ── [T1.1] Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def validator():
    """Fresh validator instance for each test."""
    return VitalSignsValidator()


@pytest.fixture
def clean_df():
    """
    A perfectly clean single-row DataFrame.
    All values within normal physiological ranges.
    """
    return pd.DataFrame([{
        "patient_id"  : "P0001",
        "timestamp"   : "2024-01-01 00:00:00",
        "heart_rate"  : 75.0,
        "spo2"        : 98.0,
        "temperature" : 36.8,
        "systolic_bp" : 120.0,
        "diastolic_bp": 80.0,
        "resp_rate"   : 16.0,
    }])


@pytest.fixture
def critical_df():
    """
    DataFrame with one row containing life-threatening values.
    """
    return pd.DataFrame([{
        "patient_id"  : "P0002",
        "timestamp"   : "2024-01-01 00:01:00",
        "heart_rate"  : 210.0,   # life-threatening
        "spo2"        : 45.0,    # life-threatening
        "temperature" : 42.5,    # life-threatening
        "systolic_bp" : 250.0,   # life-threatening
        "diastolic_bp": 80.0,
        "resp_rate"   : 16.0,
    }])


@pytest.fixture
def null_df():
    """DataFrame with missing vital sign values."""
    return pd.DataFrame([{
        "patient_id"  : "P0003",
        "timestamp"   : "2024-01-01 00:02:00",
        "heart_rate"  : None,
        "spo2"        : None,
        "temperature" : 36.8,
        "systolic_bp" : 120.0,
        "diastolic_bp": 80.0,
        "resp_rate"   : 16.0,
    }])


@pytest.fixture
def bp_inconsistent_df():
    """DataFrame where diastolic >= systolic — impossible."""
    return pd.DataFrame([{
        "patient_id"  : "P0004",
        "timestamp"   : "2024-01-01 00:03:00",
        "heart_rate"  : 75.0,
        "spo2"        : 98.0,
        "temperature" : 36.8,
        "systolic_bp" : 80.0,    # lower than diastolic
        "diastolic_bp": 120.0,   # higher than systolic — impossible
        "resp_rate"   : 16.0,
    }])


# ── [T1.2] Schema Tests ───────────────────────────────────────────────────────

class TestSchemaValidation:
    """Tests for required column presence checks."""

    def test_clean_data_passes_schema(self, validator, clean_df):
        """Clean DataFrame with all columns passes schema."""
        issues = validator._check_schema(clean_df)
        assert len(issues) == 0

    def test_missing_column_raises_critical(self, validator, clean_df):
        """Dropping a required column triggers CRITICAL issue."""
        df = clean_df.drop(columns=["heart_rate"])
        issues = validator._check_schema(df)
        assert len(issues) == 1
        assert issues[0].severity == Severity.CRITICAL
        assert "heart_rate" in issues[0].rule

    def test_multiple_missing_columns(self, validator, clean_df):
        """Multiple missing columns each trigger their own issue."""
        df = clean_df.drop(columns=["heart_rate", "spo2"])
        issues = validator._check_schema(df)
        assert len(issues) == 2


# ── [T1.3] Null Tests ─────────────────────────────────────────────────────────

class TestNullValidation:
    """Tests for missing value detection."""

    def test_clean_data_has_no_nulls(self, validator, clean_df):
        """Clean DataFrame produces no null issues."""
        issues = validator._check_nulls(clean_df)
        assert len(issues) == 0

    def test_null_heart_rate_detected(self, validator, null_df):
        """Null heart_rate produces WARNING issue."""
        issues = validator._check_nulls(null_df)
        hr_issues = [i for i in issues if i.column == "heart_rate"]
        assert len(hr_issues) == 1
        assert hr_issues[0].severity == Severity.WARNING

    def test_null_spo2_detected(self, validator, null_df):
        """Null spo2 produces WARNING issue."""
        issues = validator._check_nulls(null_df)
        spo2_issues = [i for i in issues if i.column == "spo2"]
        assert len(spo2_issues) == 1

    def test_two_nulls_produce_two_issues(self, validator, null_df):
        """Two null columns produce exactly two null issues."""
        issues = validator._check_nulls(null_df)
        assert len(issues) == 2


# ── [T1.4] Range Tests ────────────────────────────────────────────────────────

class TestRangeValidation:
    """Tests for physiological range checks."""

    def test_clean_data_no_range_issues(self, validator, clean_df):
        """All normal values produce no range issues."""
        issues = validator._check_ranges(clean_df)
        assert len(issues) == 0

    def test_heart_rate_210_is_critical(self, validator, critical_df):
        """Heart rate 210bpm triggers CRITICAL issue."""
        issues = validator._check_ranges(critical_df)
        hr_issues = [
            i for i in issues
            if i.column == "heart_rate" and i.severity == Severity.CRITICAL
        ]
        assert len(hr_issues) > 0

    def test_spo2_45_is_critical(self, validator, critical_df):
        """SpO2 45% triggers CRITICAL issue."""
        issues = validator._check_ranges(critical_df)
        spo2_issues = [
            i for i in issues
            if i.column == "spo2" and i.severity == Severity.CRITICAL
        ]
        assert len(spo2_issues) > 0

    def test_temperature_42_is_critical(self, validator, critical_df):
        """Temperature 42.5C triggers CRITICAL issue."""
        issues = validator._check_ranges(critical_df)
        temp_issues = [
            i for i in issues
            if i.column == "temperature" and i.severity == Severity.CRITICAL
        ]
        assert len(temp_issues) > 0

    def test_warning_for_slightly_high_hr(self, validator):
        """Heart rate 105bpm triggers WARNING not CRITICAL."""
        df = pd.DataFrame([{
            "patient_id": "P0005", "timestamp": "2024-01-01",
            "heart_rate": 105.0, "spo2": 98.0,
            "temperature": 36.8, "systolic_bp": 120.0,
            "diastolic_bp": 80.0, "resp_rate": 16.0,
        }])
        issues = validator._check_ranges(df)
        hr_issues = [i for i in issues if i.column == "heart_rate"]
        assert len(hr_issues) == 1
        assert hr_issues[0].severity == Severity.WARNING

    def test_impossible_negative_heart_rate(self, validator):
        """Negative heart rate triggers CRITICAL impossible value."""
        df = pd.DataFrame([{
            "patient_id": "P0006", "timestamp": "2024-01-01",
            "heart_rate": -10.0, "spo2": 98.0,
            "temperature": 36.8, "systolic_bp": 120.0,
            "diastolic_bp": 80.0, "resp_rate": 16.0,
        }])
        issues = validator._check_ranges(df)
        hr_issues = [
            i for i in issues
            if i.column == "heart_rate" and i.severity == Severity.CRITICAL
        ]
        assert len(hr_issues) > 0


# ── [T1.5] BP Consistency Tests ───────────────────────────────────────────────

class TestBPConsistency:
    """Tests for blood pressure consistency checks."""

    def test_normal_bp_passes(self, validator, clean_df):
        """Normal BP (120/80) passes consistency check."""
        issues = validator._check_bp_consistency(clean_df)
        assert len(issues) == 0

    def test_inverted_bp_is_critical(self, validator, bp_inconsistent_df):
        """Diastolic > Systolic triggers CRITICAL issue."""
        issues = validator._check_bp_consistency(bp_inconsistent_df)
        assert len(issues) == 1
        assert issues[0].severity == Severity.CRITICAL

    def test_equal_bp_is_critical(self, validator):
        """Equal systolic and diastolic triggers CRITICAL issue."""
        df = pd.DataFrame([{
            "patient_id": "P0007", "timestamp": "2024-01-01",
            "heart_rate": 75.0, "spo2": 98.0,
            "temperature": 36.8, "systolic_bp": 80.0,
            "diastolic_bp": 80.0, "resp_rate": 16.0,
        }])
        issues = validator._check_bp_consistency(df)
        assert len(issues) == 1


# ── [T1.6] Full Validate Tests ────────────────────────────────────────────────

class TestFullValidation:
    """Tests for the main validate() method."""

    def test_clean_data_passes(self, validator, clean_df):
        """Perfectly clean data returns passed=True."""
        result = validator.validate(clean_df)
        assert result["passed"] is True
        assert result["critical_count"] == 0

    def test_critical_data_fails(self, validator, critical_df):
        """Data with critical values returns passed=False."""
        result = validator.validate(critical_df)
        assert result["passed"] is False
        assert result["critical_count"] > 0

    def test_result_has_all_keys(self, validator, clean_df):
        """Validation result contains all required keys."""
        result = validator.validate(clean_df)
        required_keys = [
            "total_rows", "total_issues", "critical_count",
            "warning_count", "issues", "column_summary", "passed"
        ]
        for key in required_keys:
            assert key in result

    def test_total_rows_correct(self, validator, clean_df):
        """total_rows matches DataFrame length."""
        result = validator.validate(clean_df)
        assert result["total_rows"] == len(clean_df)