# CLI entry point for the validation pipeline.

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.explore  import load_dataset
from src.pipeline import run_pipeline

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "vital_signs.csv")

if __name__ == "__main__":
    df     = load_dataset(DATA_PATH)
    result = run_pipeline(df)
    print(f"Open your report at:")
    print(f"  {result['report_path']}")