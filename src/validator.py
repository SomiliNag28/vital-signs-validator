# Feature validation rules engine for ICU vital signs data.

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


# ── [S2.1] Severity Levels ────────────────────────────────────────────────────

class Severity(str, Enum):
    INFO     = "INFO"
    WARNING  = "WARNING"
    CRITICAL = "CRITICAL"


# ── [S2.2] Validation Issue Dataclass ────────────────────────────────────────

@dataclass
class ValidationIssue:
    """
    Represents a single validation failure.

    Attributes:
        column    : Which vital sign column failed
        row_index : Which row (patient reading) failed
        value     : The actual value that failed
        rule      : Human-readable rule that was violated
        severity  : INFO / WARNING / CRITICAL
        patient_id: Patient identifier if available
    """
    column    : str
    row_index : int
    value     : float
    rule      : str
    severity  : Severity
    patient_id: Optional[str] = None


# ── [S2.3] Physiological Range Definitions ───────────────────────────────────
# Based on standard clinical reference ranges.
# Each vital has: impossible_low, critical_low, normal_low,
#                 normal_high, critical_high, impossible_high

VITAL_RANGES = {
    "heart_rate": {
        "impossible_low" : 0,
        "critical_low"   : 40,
        "normal_low"     : 60,
        "normal_high"    : 100,
        "critical_high"  : 150,
        "impossible_high": 300,
        "unit"           : "bpm",
        "full_name"      : "Heart Rate",
    },
    "spo2": {
        "impossible_low" : 0,
        "critical_low"   : 90,
        "normal_low"     : 95,
        "normal_high"    : 100,
        "critical_high"  : 100,   # can't exceed 100%
        "impossible_high": 100,
        "unit"           : "%",
        "full_name"      : "Oxygen Saturation (SpO2)",
    },
    "temperature": {
        "impossible_low" : 25.0,
        "critical_low"   : 35.0,
        "normal_low"     : 36.1,
        "normal_high"    : 37.2,
        "critical_high"  : 38.5,
        "impossible_high": 45.0,
        "unit"           : "C",
        "full_name"      : "Body Temperature",
    },
    "systolic_bp": {
        "impossible_low" : 0,
        "critical_low"   : 70,
        "normal_low"     : 90,
        "normal_high"    : 140,
        "critical_high"  : 180,
        "impossible_high": 300,
        "unit"           : "mmHg",
        "full_name"      : "Systolic Blood Pressure",
    },
    "diastolic_bp": {
        "impossible_low" : 0,
        "critical_low"   : 40,
        "normal_low"     : 60,
        "normal_high"    : 90,
        "critical_high"  : 120,
        "impossible_high": 200,
        "unit"           : "mmHg",
        "full_name"      : "Diastolic Blood Pressure",
    },
    "resp_rate": {
        "impossible_low" : 0,
        "critical_low"   : 8,
        "normal_low"     : 12,
        "normal_high"    : 20,
        "critical_high"  : 30,
        "impossible_high": 60,
        "unit"           : "/min",
        "full_name"      : "Respiratory Rate",
    },
}

# ── [S2.4] Required Columns ───────────────────────────────────────────────────
REQUIRED_COLUMNS = [
    "patient_id",
    "timestamp",
    "heart_rate",
    "spo2",
    "temperature",
    "systolic_bp",
    "diastolic_bp",
    "resp_rate",
]


# ── [S2.5] Main Validator Class ───────────────────────────────────────────────

class VitalSignsValidator:
    """
    Validates ICU vital signs DataFrame against clinical rules.

    Methods:
        validate(df)          -> full validation, returns ValidationReport
        _check_schema(df)     -> column presence and data types
        _check_nulls(df)      -> missing value detection
        _check_ranges(df)     -> physiological range validation
        _check_bp_consistency -> diastolic must be < systolic
    """

    def __init__(self):
        self.vital_ranges    = VITAL_RANGES
        self.required_columns = REQUIRED_COLUMNS

    # ── [S2.6] Schema Validation ──────────────────────────────────────────────
    def _check_schema(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """
        Check that all required columns are present.

        Args:
            df: Raw vital signs DataFrame.

        Returns:
            List of ValidationIssue for missing columns.
        """
        issues = []
        for col in self.required_columns:
            if col not in df.columns:
                issues.append(ValidationIssue(
                    column    = col,
                    row_index = -1,
                    value     = float("nan"),
                    rule      = f"Required column '{col}' is missing from dataset",
                    severity  = Severity.CRITICAL,
                ))
        return issues

    # ── [S2.7] Null Validation ────────────────────────────────────────────────
    def _check_nulls(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """
        Detect missing values in all vital sign columns.

        Args:
            df: Raw vital signs DataFrame.

        Returns:
            List of ValidationIssue for each null value found.
        """
        issues  = []
        vitals  = [c for c in self.vital_ranges.keys() if c in df.columns]
        pid_col = "patient_id" if "patient_id" in df.columns else None

        for col in vitals:
            null_rows = df[df[col].isnull()].index.tolist()
            for idx in null_rows:
                pid = str(df.loc[idx, pid_col]) if pid_col else None
                issues.append(ValidationIssue(
                    column     = col,
                    row_index  = int(idx),
                    value      = float("nan"),
                    rule       = f"Missing value in '{col}' — sensor may be disconnected",
                    severity   = Severity.WARNING,
                    patient_id = pid,
                ))
        return issues

    # ── [S2.8] Range Validation ───────────────────────────────────────────────
    def _check_ranges(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """
        Validate each vital sign against physiological ranges.

        Three tiers:
            CRITICAL — value is physiologically impossible
            CRITICAL — value is life-threatening
            WARNING  — value is outside normal but not critical

        Args:
            df: Raw vital signs DataFrame.

        Returns:
            List of ValidationIssue for each out-of-range value.
        """
        issues  = []
        pid_col = "patient_id" if "patient_id" in df.columns else None

        for col, ranges in self.vital_ranges.items():
            if col not in df.columns:
                continue

            col_data = df[col].dropna()
            unit     = ranges["unit"]
            name     = ranges["full_name"]

            for idx, value in col_data.items():
                pid = str(df.loc[idx, pid_col]) if pid_col else None

                # [S2.8-A] Impossible values — physically cannot exist
                if (value <= ranges["impossible_low"] or
                        value > ranges["impossible_high"]):
                    issues.append(ValidationIssue(
                        column     = col,
                        row_index  = int(idx),
                        value      = float(value),
                        rule       = (
                            f"{name} value {value}{unit} is physiologically "
                            f"impossible. Valid range: "
                            f"{ranges['impossible_low']}-"
                            f"{ranges['impossible_high']}{unit}"
                        ),
                        severity   = Severity.CRITICAL,
                        patient_id = pid,
                    ))

                # [S2.8-B] Life-threatening values
                elif (value < ranges["critical_low"] or
                        value > ranges["critical_high"]):
                    issues.append(ValidationIssue(
                        column     = col,
                        row_index  = int(idx),
                        value      = float(value),
                        rule       = (
                            f"{name} value {value}{unit} is life-threatening. "
                            f"Critical range: "
                            f"{ranges['critical_low']}-"
                            f"{ranges['critical_high']}{unit}"
                        ),
                        severity   = Severity.CRITICAL,
                        patient_id = pid,
                    ))

                # [S2.8-C] Outside normal range — warning only
                elif (value < ranges["normal_low"] or
                        value > ranges["normal_high"]):
                    issues.append(ValidationIssue(
                        column     = col,
                        row_index  = int(idx),
                        value      = float(value),
                        rule       = (
                            f"{name} value {value}{unit} is outside normal range "
                            f"{ranges['normal_low']}-"
                            f"{ranges['normal_high']}{unit}"
                        ),
                        severity   = Severity.WARNING,
                        patient_id = pid,
                    ))

        return issues

    # ── [S2.9] BP Consistency Check ───────────────────────────────────────────
    def _check_bp_consistency(
            self, df: pd.DataFrame) -> List[ValidationIssue]:
        """
        Diastolic BP must always be lower than Systolic BP.
        If diastolic >= systolic, the readings are physically impossible
        or the columns are swapped.

        Args:
            df: Raw vital signs DataFrame.

        Returns:
            List of ValidationIssue for inconsistent BP pairs.
        """
        issues  = []
        pid_col = "patient_id" if "patient_id" in df.columns else None

        if "systolic_bp" not in df.columns or "diastolic_bp" not in df.columns:
            return issues

        bp_data = df[["systolic_bp", "diastolic_bp"]].dropna()

        for idx, row in bp_data.iterrows():
            sbp = row["systolic_bp"]
            dbp = row["diastolic_bp"]
            pid = str(df.loc[idx, pid_col]) if pid_col else None

            if dbp >= sbp:
                issues.append(ValidationIssue(
                    column     = "diastolic_bp",
                    row_index  = int(idx),
                    value      = float(dbp),
                    rule       = (
                        f"Diastolic BP ({dbp}mmHg) >= Systolic BP ({sbp}mmHg). "
                        f"Physiologically impossible — readings may be swapped "
                        f"or sensor malfunction."
                    ),
                    severity   = Severity.CRITICAL,
                    patient_id = pid,
                ))

        return issues

    # ── [S2.10] Main Validate Method ─────────────────────────────────────────
    def validate(self, df: pd.DataFrame) -> Dict:
        """
        Run all validation checks and return structured report dict.

        Runs in order:
            1. Schema check
            2. Null check
            3. Range check
            4. BP consistency check

        Args:
            df: Raw vital signs DataFrame.

        Returns:
            Dict with keys:
                total_rows       : int
                total_issues     : int
                critical_count   : int
                warning_count    : int
                issues           : List[ValidationIssue]
                column_summary   : Dict[str, Dict]
                passed           : bool
        """
        print("[Validator] Running schema check...")
        schema_issues = self._check_schema(df)

        # Stop early if schema is broken
        if any(i.severity == Severity.CRITICAL for i in schema_issues):
            print("[Validator] [ERROR] Schema validation failed. Stopping.")
            return {
                "total_rows"     : len(df),
                "total_issues"   : len(schema_issues),
                "critical_count" : len(schema_issues),
                "warning_count"  : 0,
                "issues"         : schema_issues,
                "column_summary" : {},
                "passed"         : False,
            }

        print("[Validator] Running null check...")
        null_issues = self._check_nulls(df)

        print("[Validator] Running range check...")
        range_issues = self._check_ranges(df)

        print("[Validator] Running BP consistency check...")
        bp_issues = self._check_bp_consistency(df)

        # Combine all issues
        all_issues = schema_issues + null_issues + range_issues + bp_issues

        # Build per-column summary
        column_summary = {}
        for col in self.vital_ranges.keys():
            col_issues = [i for i in all_issues if i.column == col]
            column_summary[col] = {
                "total_issues"   : len(col_issues),
                "critical_count" : sum(
                    1 for i in col_issues if i.severity == Severity.CRITICAL),
                "warning_count"  : sum(
                    1 for i in col_issues if i.severity == Severity.WARNING),
                "null_count"     : sum(
                    1 for i in col_issues
                    if "Missing value" in i.rule),
            }

        critical_count = sum(
            1 for i in all_issues if i.severity == Severity.CRITICAL)
        warning_count  = sum(
            1 for i in all_issues if i.severity == Severity.WARNING)

        print(f"[Validator] Complete.")
        print(f"            Total issues   : {len(all_issues)}")
        print(f"            Critical       : {critical_count}")
        print(f"            Warnings       : {warning_count}")

        return {
            "total_rows"     : len(df),
            "total_issues"   : len(all_issues),
            "critical_count" : critical_count,
            "warning_count"  : warning_count,
            "issues"         : all_issues,
            "column_summary" : column_summary,
            "passed"         : critical_count == 0,
        }