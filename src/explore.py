# Dataset exploration for ICU vital signs data.

import os
import sys
import pandas as pd
import numpy as np

# ── [S1.1-A] Path setup ───────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "vital_signs.csv")


def load_dataset(path: str) -> pd.DataFrame:
    # [S1.1-B] Check file exists
    if not os.path.exists(path):
        print(f"  [ERROR]  File not found: {path}")
        print("           Place vital_signs.csv inside the data/ folder.")
        sys.exit(1)

    # [S1.1-C] Try loading with different delimiters
    for sep in [",", ";", "\t"]:
        try:
            df = pd.read_csv(path, sep=sep, encoding="utf-8", nrows=5)
            if df.shape[1] > 1:
                # Found the right delimiter — load full file
                df = pd.read_csv(path, sep=sep, encoding="utf-8")
                print(f"  [OK]  Delimiter detected: {repr(sep)}")
                print(f"  [OK]  Loaded {len(df)} rows, {df.shape[1]} columns")
                return df
        except Exception:
            continue

    # [S1.1-D] Fallback — try latin-1 encoding
    try:
        df = pd.read_csv(path, encoding="latin-1")
        print(f"  [OK]  Loaded with latin-1 encoding")
        print(f"  [OK]  Loaded {len(df)} rows, {df.shape[1]} columns")
        return df
    except Exception as e:
        print(f"  [ERROR]  Could not load file: {e}")
        sys.exit(1)


def explore(df: pd.DataFrame) -> None:
    """
    Print full structured exploration report.

    Args:
        df: Raw DataFrame from load_dataset()
    """

    # ── [S1.2] Section 1: Column names ───────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SECTION 1 - Column Names")
    print("=" * 60)
    print(f"  Total columns: {len(df.columns)}")
    for i, col in enumerate(df.columns):
        print(f"  [{i:02d}]  {col}")

    # ── [S1.3] Section 2: Shape ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SECTION 2 - Dataset Shape")
    print("=" * 60)
    print(f"  Rows    : {df.shape[0]}")
    print(f"  Columns : {df.shape[1]}")

    # ── [S1.4] Section 3: Data types ─────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SECTION 3 - Data Types")
    print("=" * 60)
    for col in df.columns:
        print(f"  {col:<35} {str(df[col].dtype):<15}")

    # ── [S1.5] Section 4: Missing values ─────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SECTION 4 - Missing Values")
    print("=" * 60)
    null_counts = df.isnull().sum()
    total_nulls = null_counts.sum()
    for col, count in null_counts.items():
        pct    = (count / len(df)) * 100
        status = "[WARN]" if count > 0 else "[OK]  "
        print(f"  {status}  {col:<35} {count:>6} nulls  ({pct:.1f}%)")
    print(f"\n  Total missing values: {total_nulls}")

    # ── [S1.6] Section 5: Statistical summary ────────────────────────────────
    print("\n" + "=" * 60)
    print("  SECTION 5 - Statistical Summary (Numeric Columns)")
    print("=" * 60)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) == 0:
        print("  [WARN]  No numeric columns found.")
    else:
        for col in numeric_cols:
            col_data = df[col].dropna()
            if len(col_data) == 0:
                continue
            print(f"\n  {col}")
            print(f"    min    : {col_data.min():.4f}")
            print(f"    max    : {col_data.max():.4f}")
            print(f"    mean   : {col_data.mean():.4f}")
            print(f"    median : {col_data.median():.4f}")
            print(f"    std    : {col_data.std():.4f}")

    # ── [S1.7] Section 6: First 5 rows ───────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SECTION 6 - First 5 Rows")
    print("=" * 60)
    print(df.head().to_string())

    # ── [S1.8] Section 7: Unique values for categorical columns ──────────────
    print("\n" + "=" * 60)
    print("  SECTION 7 - Categorical Column Unique Values")
    print("=" * 60)
    cat_cols = df.select_dtypes(include=["object"]).columns
    if len(cat_cols) == 0:
        print("  No categorical columns found.")
    else:
        for col in cat_cols:
            unique_vals = df[col].unique()[:10]  # show max 10
            print(f"\n  {col} ({df[col].nunique()} unique values)")
            print(f"    Sample: {list(unique_vals)}")

    # ── [S1.9] Section 8: Outlier preview ────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SECTION 8 - Outlier Preview (values beyond 3 std devs)")
    print("=" * 60)
    for col in numeric_cols:
        col_data = df[col].dropna()
        if len(col_data) < 10:
            continue
        mean = col_data.mean()
        std  = col_data.std()
        if std == 0:
            print(f"  {col:<35} [WARN] std=0, possible stuck sensor")
            continue
        outliers = col_data[np.abs(col_data - mean) > 3 * std]
        if len(outliers) > 0:
            print(f"  {col:<35} {len(outliers):>5} outliers  "
                  f"(range: {outliers.min():.2f} to {outliers.max():.2f})")
        else:
            print(f"  {col:<35} [OK]  no outliers beyond 3 std")

    # ── [S1.10] Section 9: Recommended vital sign columns ────────────────────
    print("\n" + "=" * 60)
    print("  SECTION 9 - Vital Sign Column Detection")
    print("=" * 60)

    # Keywords we expect in a vital signs dataset
    vital_keywords = {
        "heart_rate"  : ["heart", "hr", "pulse", "bpm"],
        "spo2"        : ["spo2", "oxygen", "o2", "sat"],
        "temperature" : ["temp", "temperature", "body"],
        "systolic_bp" : ["systolic", "sbp", "sys"],
        "diastolic_bp": ["diastolic", "dbp", "dia"],
        "resp_rate"   : ["resp", "rr", "respiratory", "breath"],
    }

    detected = {}
    for vital, keywords in vital_keywords.items():
        for col in df.columns:
            col_lower = col.lower()
            if any(kw in col_lower for kw in keywords):
                detected[vital] = col
                break

    if detected:
        print("  Detected vital sign columns:")
        for vital, col in detected.items():
            print(f"    {vital:<20} -> '{col}'")
    else:
        print("  [WARN]  No standard vital sign columns auto-detected.")
        print("          Column names may be non-standard.")
        print("          Check Section 1 and map manually.")

    print("\n" + "=" * 60)
    print("  [OK]  Exploration complete.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    print("\n  Loading dataset...\n")
    df = load_dataset(DATA_PATH)
    explore(df)