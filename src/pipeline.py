# Master pipeline that runs validation + anomaly detection + reporting.

import pandas as pd
from src.validator import VitalSignsValidator
from src.anomaly   import AnomalyDetector
from src.reporter  import ReportGenerator


def run_pipeline(df: pd.DataFrame, output_path: str = None) -> dict:
    """
    Run the complete validation pipeline on a vital signs DataFrame.

    Steps:
        1. Validate features against clinical rules
        2. Detect statistical and pattern anomalies
        3. Generate HTML report

    Args:
        df          : Vital signs DataFrame with standard columns
        output_path : Optional custom report output path

    Returns:
        Dict with keys:
            validation  : Full validation results dict
            anomaly     : Full anomaly results dict
            report_path : Path to generated HTML report
            summary     : High-level summary dict
    """
    print("\n" + "=" * 55)
    print("  VITAL SIGNS VALIDATION PIPELINE")
    print("=" * 55)

    # [S4-P1] Validate
    validator          = VitalSignsValidator()
    validation_results = validator.validate(df)

    # [S4-P2] Detect anomalies
    detector        = AnomalyDetector()
    anomaly_results = detector.detect(df)

    # [S4-P3] Generate report
    generator   = ReportGenerator()
    report_path = generator.generate(
        validation_results,
        anomaly_results,
        df,
        output_path=output_path,
    )

    # [S4-P4] Build summary
    summary = {
        "total_rows"      : validation_results["total_rows"],
        "total_issues"    : validation_results["total_issues"],
        "critical_count"  : validation_results["critical_count"],
        "warning_count"   : validation_results["warning_count"],
        "total_anomalies" : anomaly_results["total_anomalies"],
        "anomaly_critical": anomaly_results["critical_count"],
        "passed"          : validation_results["passed"],
        "report_path"     : report_path,
    }

    print("\n" + "=" * 55)
    print("  PIPELINE COMPLETE")
    print(f"  Status   : {'PASS' if summary['passed'] else 'FAIL'}")
    print(f"  Issues   : {summary['total_issues']}")
    print(f"  Anomalies: {summary['total_anomalies']}")
    print(f"  Report   : {report_path}")
    print("=" * 55 + "\n")

    return {
        "validation" : validation_results,
        "anomaly"    : anomaly_results,
        "report_path": report_path,
        "summary"    : summary,
    }