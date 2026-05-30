# Statistical anomaly detection for ICU vital signs time-series data.

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum


# ── [S3.1] Anomaly Types ─────────────────────────────────────────────────────

class AnomalyType(str, Enum):
    OUTLIER        = "STATISTICAL_OUTLIER"
    STUCK_SENSOR   = "STUCK_SENSOR"
    SUDDEN_SPIKE   = "SUDDEN_SPIKE"
    TIMESTAMP_GAP  = "TIMESTAMP_GAP"
    FLATLINE       = "FLATLINE"


# ── [S3.2] Anomaly Dataclass ──────────────────────────────────────────────────

@dataclass
class Anomaly:
    """
    Represents a single detected anomaly.

    Attributes:
        anomaly_type : Type of anomaly detected
        column       : Which vital sign column
        row_index    : Starting row of anomaly
        value        : The anomalous value
        description  : Human-readable explanation
        severity     : WARNING or CRITICAL
        patient_id   : Patient identifier if available
        context      : Additional context (e.g. z-score value)
    """
    anomaly_type : AnomalyType
    column       : str
    row_index    : int
    value        : float
    description  : str
    severity     : str
    patient_id   : Optional[str] = None
    context      : Optional[str] = None


# ── [S3.3] Detector Configuration ────────────────────────────────────────────
# These thresholds are tunable — in a real system they'd be
# configurable per hospital unit and patient profile.

CONFIG = {
    # Z-score threshold beyond which a value is an outlier
    "zscore_threshold"    : 3.0,

    # How many consecutive identical readings = stuck sensor
    "stuck_sensor_window" : 5,

    # Max allowed change between consecutive readings per vital
    "spike_thresholds"    : {
        "heart_rate"  : 40,    # bpm change in one reading
        "spo2"        : 10,    # % drop in one reading
        "temperature" : 1.5,   # degrees change in one reading
        "systolic_bp" : 50,    # mmHg change in one reading
        "diastolic_bp": 40,    # mmHg change in one reading
        "resp_rate"   : 10,    # /min change in one reading
    },

    # Flatline: std dev below this = flatline in window
    "flatline_std_threshold" : 0.01,

    # Window size for flatline detection (number of readings)
    "flatline_window"        : 10,

    # Max allowed gap in minutes between consecutive timestamps
    "max_timestamp_gap_mins" : 5,
}

# Vital sign columns to analyze
VITAL_COLUMNS = [
    "heart_rate", "spo2", "temperature",
    "systolic_bp", "diastolic_bp", "resp_rate"
]


# ── [S3.4] Main Anomaly Detector Class ───────────────────────────────────────

class AnomalyDetector:
    """
    Detects statistical and pattern-based anomalies in vital signs data.

    Methods:
        detect(df)                -> runs all detectors, returns report dict
        _detect_outliers(df)      -> z-score based outlier detection
        _detect_stuck_sensor(df)  -> consecutive identical value detection
        _detect_sudden_spikes(df) -> consecutive reading delta detection
        _detect_timestamp_gaps(df)-> missing time period detection
        _detect_flatlines(df)     -> rolling window variance detection
    """

    def __init__(self, config: Dict = None):
        self.config = config or CONFIG

    # ── [S3.5] Z-Score Outlier Detection ─────────────────────────────────────
    def _detect_outliers(
            self, df: pd.DataFrame) -> List[Anomaly]:
        """
        Flag values beyond Z standard deviations from the mean.

        Z-score = (value - mean) / std
        A z-score > 3 means the value is more than 3 standard
        deviations from the mean — statistically very unusual.

        Args:
            df: Vital signs DataFrame.

        Returns:
            List of Anomaly for each outlier found.
        """
        anomalies = []
        pid_col   = "patient_id" if "patient_id" in df.columns else None
        threshold = self.config["zscore_threshold"]

        for col in VITAL_COLUMNS:
            if col not in df.columns:
                continue

            col_data = df[col].dropna()
            if len(col_data) < 10:
                continue

            mean = col_data.mean()
            std  = col_data.std()

            if std == 0:
                continue

            for idx, value in col_data.items():
                zscore = abs((value - mean) / std)

                if zscore > threshold:
                    pid = str(df.loc[idx, pid_col]) if pid_col else None
                    severity = (
                        "CRITICAL" if zscore > 5
                        else "WARNING"
                    )
                    anomalies.append(Anomaly(
                        anomaly_type = AnomalyType.OUTLIER,
                        column       = col,
                        row_index    = int(idx),
                        value        = float(value),
                        description  = (
                            f"{col} value {value:.2f} is {zscore:.1f} "
                            f"standard deviations from mean ({mean:.2f}). "
                            f"Possible sensor error or genuine emergency."
                        ),
                        severity     = severity,
                        patient_id   = pid,
                        context      = f"z-score={zscore:.2f}, "
                                       f"mean={mean:.2f}, std={std:.2f}",
                    ))

        return anomalies

    # ── [S3.6] Stuck Sensor Detection ────────────────────────────────────────
    def _detect_stuck_sensor(
            self, df: pd.DataFrame) -> List[Anomaly]:
        """
        Detect consecutive identical readings — sign of a frozen sensor.

        In real ICUs, a sensor physically cannot give exactly the same
        reading N times in a row for continuous vitals like heart rate.
        If it does, the sensor is disconnected or malfunctioning.

        Args:
            df: Vital signs DataFrame.

        Returns:
            List of Anomaly for each stuck sensor window found.
        """
        anomalies = []
        pid_col   = "patient_id" if "patient_id" in df.columns else None
        window    = self.config["stuck_sensor_window"]

        for col in VITAL_COLUMNS:
            if col not in df.columns:
                continue

            col_data  = df[col].dropna().reset_index()
            col_data.columns = ["original_idx", "value"]

            if len(col_data) < window:
                continue

            # [S3.6-A] Rolling window — check if all values in window are equal
            i = 0
            while i <= len(col_data) - window:
                window_vals = col_data["value"].iloc[i:i+window]

                # All values identical = stuck sensor
                if window_vals.nunique() == 1:
                    stuck_value = window_vals.iloc[0]
                    start_idx   = int(col_data["original_idx"].iloc[i])
                    pid         = (str(df.loc[start_idx, pid_col])
                                   if pid_col else None)

                    anomalies.append(Anomaly(
                        anomaly_type = AnomalyType.STUCK_SENSOR,
                        column       = col,
                        row_index    = start_idx,
                        value        = float(stuck_value),
                        description  = (
                            f"{col} stuck at {stuck_value:.2f} for "
                            f"{window}+ consecutive readings. "
                            f"Possible sensor disconnect or malfunction."
                        ),
                        severity     = "CRITICAL",
                        patient_id   = pid,
                        context      = f"window={window}, "
                                       f"stuck_value={stuck_value:.2f}",
                    ))
                    # Skip past this stuck window
                    i += window
                else:
                    i += 1

        return anomalies

    # ── [S3.7] Sudden Spike Detection ────────────────────────────────────────
    def _detect_sudden_spikes(
            self, df: pd.DataFrame) -> List[Anomaly]:
        """
        Detect abnormally large changes between consecutive readings.

        A heart rate jumping from 72 to 210 bpm in one reading interval
        is physiologically impossible — it's either a sensor artifact
        or data corruption.

        Args:
            df: Vital signs DataFrame.

        Returns:
            List of Anomaly for each spike detected.
        """
        anomalies  = []
        pid_col    = "patient_id" if "patient_id" in df.columns else None
        thresholds = self.config["spike_thresholds"]

        for col in VITAL_COLUMNS:
            if col not in df.columns:
                continue
            if col not in thresholds:
                continue

            threshold = thresholds[col]
            col_data  = df[col].dropna()

            if len(col_data) < 2:
                continue

            # [S3.7-A] Calculate absolute difference between consecutive rows
            prev_vals = col_data.shift(1).dropna()
            curr_vals = col_data.loc[prev_vals.index]
            deltas    = (curr_vals - prev_vals).abs()

            spike_indices = deltas[deltas > threshold].index

            for idx in spike_indices:
                prev_val = float(df.loc[idx-1, col]) if idx > 0 else float("nan")
                curr_val = float(df.loc[idx, col])
                delta    = abs(curr_val - prev_val)
                pid      = str(df.loc[idx, pid_col]) if pid_col else None

                anomalies.append(Anomaly(
                    anomaly_type = AnomalyType.SUDDEN_SPIKE,
                    column       = col,
                    row_index    = int(idx),
                    value        = curr_val,
                    description  = (
                        f"{col} changed by {delta:.2f} in one reading "
                        f"({prev_val:.2f} -> {curr_val:.2f}). "
                        f"Threshold: {threshold}. Possible spike artifact."
                    ),
                    severity     = "CRITICAL",
                    patient_id   = pid,
                    context      = f"delta={delta:.2f}, "
                                   f"threshold={threshold}",
                ))

        return anomalies

    # ── [S3.8] Timestamp Gap Detection ───────────────────────────────────────
    def _detect_timestamp_gaps(
            self, df: pd.DataFrame) -> List[Anomaly]:
        """
        Detect missing time periods in continuous monitoring stream.

        ICU monitors record continuously. A gap in timestamps means
        either the monitor was disconnected or data was lost.

        Args:
            df: Vital signs DataFrame with 'timestamp' column.

        Returns:
            List of Anomaly for each gap exceeding threshold.
        """
        anomalies = []

        if "timestamp" not in df.columns:
            return anomalies

        try:
            # [S3.8-A] Parse timestamps
            timestamps = pd.to_datetime(df["timestamp"], errors="coerce")
            timestamps = timestamps.dropna().sort_values()

            if len(timestamps) < 2:
                return anomalies

            max_gap = pd.Timedelta(
                minutes=self.config["max_timestamp_gap_mins"])

            # [S3.8-B] Calculate gaps between consecutive timestamps
            gaps = timestamps.diff().dropna()
            large_gaps = gaps[gaps > max_gap]

            for idx, gap in large_gaps.items():
                gap_minutes = gap.total_seconds() / 60
                anomalies.append(Anomaly(
                    anomaly_type = AnomalyType.TIMESTAMP_GAP,
                    column       = "timestamp",
                    row_index    = int(idx),
                    value        = float(gap_minutes),
                    description  = (
                        f"Monitoring gap of {gap_minutes:.1f} minutes "
                        f"detected at row {idx}. "
                        f"Maximum allowed: "
                        f"{self.config['max_timestamp_gap_mins']} minutes. "
                        f"Possible monitor disconnect."
                    ),
                    severity     = (
                        "CRITICAL" if gap_minutes > 30
                        else "WARNING"
                    ),
                    context      = f"gap={gap_minutes:.1f} mins",
                ))

        except Exception as e:
            print(f"  [WARN]  Timestamp parsing failed: {e}")

        return anomalies

    # ── [S3.9] Flatline Detection ─────────────────────────────────────────────
    def _detect_flatlines(
            self, df: pd.DataFrame) -> List[Anomaly]:
        """
        Detect near-zero variance over a rolling window.

        Different from stuck sensor — stuck sensor checks for exact
        identical values. Flatline checks for near-zero variation,
        which catches cases where a sensor is returning slightly
        noisy but essentially constant readings.

        Args:
            df: Vital signs DataFrame.

        Returns:
            List of Anomaly for each flatline window.
        """
        anomalies  = []
        pid_col    = "patient_id" if "patient_id" in df.columns else None
        window     = self.config["flatline_window"]
        std_thresh = self.config["flatline_std_threshold"]

        for col in VITAL_COLUMNS:
            if col not in df.columns:
                continue

            col_data = df[col].dropna()
            if len(col_data) < window:
                continue

            # [S3.9-A] Rolling standard deviation
            rolling_std = col_data.rolling(window=window).std()

            # Find windows with near-zero std (after burn-in period)
            flatline_idx = rolling_std[
                (rolling_std < std_thresh) &
                (rolling_std.index >= window)
            ].index

            # Deduplicate — only report start of each flatline region
            reported_windows = set()
            for idx in flatline_idx:
                window_start = idx - window + 1
                if window_start not in reported_windows:
                    reported_windows.add(window_start)
                    val = float(col_data.loc[idx])
                    pid = (str(df.loc[idx, pid_col])
                           if pid_col else None)

                    anomalies.append(Anomaly(
                        anomaly_type = AnomalyType.FLATLINE,
                        column       = col,
                        row_index    = int(window_start),
                        value        = val,
                        description  = (
                            f"{col} shows near-zero variance "
                            f"(std < {std_thresh}) over {window} "
                            f"consecutive readings around row {idx}. "
                            f"Possible sensor malfunction or patient issue."
                        ),
                        severity     = "CRITICAL",
                        patient_id   = pid,
                        context      = (
                            f"rolling_std={rolling_std.loc[idx]:.4f}, "
                            f"window={window}"
                        ),
                    ))

        return anomalies

    # ── [S3.10] Main Detect Method ────────────────────────────────────────────
    def detect(self, df: pd.DataFrame) -> Dict:
        """
        Run all anomaly detectors and return structured results.

        Args:
            df: Raw vital signs DataFrame.

        Returns:
            Dict with keys:
                total_anomalies   : int
                by_type           : Dict[str, int]
                by_column         : Dict[str, int]
                critical_count    : int
                warning_count     : int
                anomalies         : List[Anomaly]
        """
        print("[Anomaly] Running outlier detection...")
        outliers = self._detect_outliers(df)

        print("[Anomaly] Running stuck sensor detection...")
        stuck = self._detect_stuck_sensor(df)

        print("[Anomaly] Running sudden spike detection...")
        spikes = self._detect_sudden_spikes(df)

        print("[Anomaly] Running timestamp gap detection...")
        gaps = self._detect_timestamp_gaps(df)

        print("[Anomaly] Running flatline detection...")
        flatlines = self._detect_flatlines(df)

        all_anomalies = outliers + stuck + spikes + gaps + flatlines

        # [S3.10-A] Count by type
        by_type = {t.value: 0 for t in AnomalyType}
        for a in all_anomalies:
            by_type[a.anomaly_type.value] += 1

        # [S3.10-B] Count by column
        by_column = {col: 0 for col in VITAL_COLUMNS + ["timestamp"]}
        for a in all_anomalies:
            if a.column in by_column:
                by_column[a.column] += 1

        critical_count = sum(
            1 for a in all_anomalies if a.severity == "CRITICAL")
        warning_count  = sum(
            1 for a in all_anomalies if a.severity == "WARNING")

        print(f"[Anomaly] Complete.")
        print(f"          Total anomalies : {len(all_anomalies)}")
        print(f"          Critical        : {critical_count}")
        print(f"          Warnings        : {warning_count}")
        print(f"          By type:")
        for t, count in by_type.items():
            if count > 0:
                print(f"            {t:<25} : {count}")

        return {
            "total_anomalies" : len(all_anomalies),
            "by_type"         : by_type,
            "by_column"       : by_column,
            "critical_count"  : critical_count,
            "warning_count"   : warning_count,
            "anomalies"       : all_anomalies,
        }