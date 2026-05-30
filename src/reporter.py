# HTML report generator for vital signs validation and anomaly results.

import os
from datetime import datetime
from typing import Dict
from src.validator import Severity
from src.anomaly import AnomalyType

# ── [S4.1] Path Setup ─────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")


# ── [S4.2] HTML Template ──────────────────────────────────────────────────────
# Written as a Python string — no external template files needed.
# Jinja2-style but rendered manually for zero extra dependencies.

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vital Signs Validation Report</title>
    <style>
        /* [S4.2-A] Base styles */
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont,
                         'Segoe UI', Roboto, sans-serif;
            background: #f0f2f5;
            color: #1a1a2e;
            font-size: 14px;
        }}

        /* [S4.2-B] Header */
        .header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 32px 40px;
            border-bottom: 4px solid #0f3460;
        }}
        .header h1 {{
            font-size: 26px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}
        .header .subtitle {{
            color: #a0aec0;
            margin-top: 6px;
            font-size: 13px;
        }}
        .header .meta {{
            margin-top: 16px;
            display: flex;
            gap: 24px;
            flex-wrap: wrap;
        }}
        .header .meta span {{
            color: #e2e8f0;
            font-size: 12px;
            background: rgba(255,255,255,0.08);
            padding: 4px 12px;
            border-radius: 20px;
        }}

        /* [S4.2-C] Status banner */
        .status-banner {{
            padding: 16px 40px;
            font-size: 15px;
            font-weight: 600;
            letter-spacing: 0.3px;
        }}
        .status-pass {{
            background: #d4edda;
            color: #155724;
            border-left: 5px solid #28a745;
        }}
        .status-fail {{
            background: #f8d7da;
            color: #721c24;
            border-left: 5px solid #dc3545;
        }}

        /* [S4.2-D] Main container */
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 32px 24px;
        }}

        /* [S4.2-E] Summary cards */
        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
            border-top: 4px solid #e2e8f0;
        }}
        .card.critical {{ border-top-color: #dc3545; }}
        .card.warning  {{ border-top-color: #ffc107; }}
        .card.info     {{ border-top-color: #17a2b8; }}
        .card.total    {{ border-top-color: #6c757d; }}
        .card.anomaly  {{ border-top-color: #6f42c1; }}
        .card .number {{
            font-size: 36px;
            font-weight: 700;
            line-height: 1;
        }}
        .card.critical .number {{ color: #dc3545; }}
        .card.warning  .number {{ color: #e6a817; }}
        .card.info     .number {{ color: #17a2b8; }}
        .card.total    .number {{ color: #6c757d; }}
        .card.anomaly  .number {{ color: #6f42c1; }}
        .card .label {{
            font-size: 12px;
            color: #6c757d;
            margin-top: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        /* [S4.2-F] Section headers */
        .section {{
            background: white;
            border-radius: 10px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        }}
        .section h2 {{
            font-size: 16px;
            font-weight: 700;
            color: #1a1a2e;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 2px solid #f0f2f5;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .section h2 .dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
        }}
        .dot-red    {{ background: #dc3545; }}
        .dot-yellow {{ background: #ffc107; }}
        .dot-blue   {{ background: #17a2b8; }}
        .dot-purple {{ background: #6f42c1; }}

        /* [S4.2-G] Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th {{
            background: #f8f9fa;
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
            color: #495057;
            border-bottom: 2px solid #dee2e6;
            white-space: nowrap;
        }}
        td {{
            padding: 9px 12px;
            border-bottom: 1px solid #f0f2f5;
            vertical-align: top;
        }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover td {{ background: #f8f9fa; }}

        /* [S4.2-H] Severity badges */
        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}
        .badge-critical {{
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }}
        .badge-warning {{
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeeba;
        }}
        .badge-info {{
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }}

        /* [S4.2-I] Anomaly type badges */
        .type-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
            background: #e9ecef;
            color: #495057;
            white-space: nowrap;
        }}

        /* [S4.2-J] Column summary grid */
        .col-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 12px;
            margin-top: 8px;
        }}
        .col-card {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 14px;
            border-left: 4px solid #dee2e6;
        }}
        .col-card.has-critical {{ border-left-color: #dc3545; }}
        .col-card.has-warning  {{ border-left-color: #ffc107; }}
        .col-card.clean        {{ border-left-color: #28a745; }}
        .col-card .col-name {{
            font-weight: 600;
            font-size: 12px;
            color: #1a1a2e;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}
        .col-card .col-stat {{
            font-size: 11px;
            color: #6c757d;
            margin-top: 2px;
        }}
        .col-card .col-stat span {{
            font-weight: 600;
        }}
        .col-stat .crit  {{ color: #dc3545; }}
        .col-stat .warn  {{ color: #e6a817; }}
        .col-stat .clean {{ color: #28a745; }}

        /* [S4.2-K] Anomaly type summary */
        .type-summary {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 8px;
        }}
        .type-pill {{
            background: #f0f2f5;
            border-radius: 20px;
            padding: 6px 16px;
            font-size: 12px;
            font-weight: 600;
            color: #495057;
            border: 1px solid #dee2e6;
        }}
        .type-pill .count {{
            color: #6f42c1;
            font-size: 14px;
        }}

        /* [S4.2-L] Footer */
        .footer {{
            text-align: center;
            padding: 24px;
            color: #adb5bd;
            font-size: 12px;
        }}

        /* [S4.2-M] Scrollable table wrapper */
        .table-wrap {{
            overflow-x: auto;
            max-height: 420px;
            overflow-y: auto;
            border: 1px solid #dee2e6;
            border-radius: 6px;
        }}
        .table-wrap thead th {{
            position: sticky;
            top: 0;
            z-index: 1;
        }}

        /* [S4.2-N] Count limit note */
        .limit-note {{
            font-size: 12px;
            color: #6c757d;
            margin-top: 8px;
            font-style: italic;
        }}
    </style>
</head>
<body>

<!-- [S4.3] Header -->
<div class="header">
    <h1>ICU Vital Signs — Validation Report</h1>
    <p class="subtitle">
        Automated feature validation and anomaly detection pipeline
    </p>
    <div class="meta">
        <span>Generated: {generated_at}</span>
        <span>Total Readings: {total_rows}</span>
        <span>Pipeline Version: 1.0.0</span>
    </div>
</div>

<!-- [S4.4] Status Banner -->
<div class="status-banner {status_class}">
    {status_icon}  Overall Status: {status_text}
    &nbsp;&mdash;&nbsp; {critical_count} critical issues,
    {warning_count} warnings across {total_rows} readings
</div>

<!-- [S4.5] Container -->
<div class="container">

    <!-- [S4.6] Summary Cards -->
    <div class="cards">
        <div class="card total">
            <div class="number">{total_rows}</div>
            <div class="label">Total Readings</div>
        </div>
        <div class="card critical">
            <div class="number">{critical_count}</div>
            <div class="label">Critical Issues</div>
        </div>
        <div class="card warning">
            <div class="number">{warning_count}</div>
            <div class="label">Warnings</div>
        </div>
        <div class="card anomaly">
            <div class="number">{total_anomalies}</div>
            <div class="label">Anomalies Detected</div>
        </div>
        <div class="card info">
            <div class="number">{null_count}</div>
            <div class="label">Missing Values</div>
        </div>
    </div>

    <!-- [S4.7] Column Summary -->
    <div class="section">
        <h2>
            <span class="dot dot-blue"></span>
            Vital Sign Column Summary
        </h2>
        <div class="col-grid">
            {column_cards}
        </div>
    </div>

    <!-- [S4.8] Anomaly Type Summary -->
    <div class="section">
        <h2>
            <span class="dot dot-purple"></span>
            Anomaly Detection Summary
        </h2>
        <div class="type-summary">
            {type_pills}
        </div>
    </div>

    <!-- [S4.9] Validation Issues Table -->
    <div class="section">
        <h2>
            <span class="dot dot-red"></span>
            Validation Issues
            ({total_issues} total)
        </h2>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Row</th>
                        <th>Patient ID</th>
                        <th>Column</th>
                        <th>Value</th>
                        <th>Severity</th>
                        <th>Rule Violated</th>
                    </tr>
                </thead>
                <tbody>
                    {validation_rows}
                </tbody>
            </table>
        </div>
        {validation_limit_note}
    </div>

    <!-- [S4.10] Anomaly Table -->
    <div class="section">
        <h2>
            <span class="dot dot-purple"></span>
            Anomaly Detection Results
            ({total_anomalies} total)
        </h2>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Row</th>
                        <th>Patient ID</th>
                        <th>Column</th>
                        <th>Type</th>
                        <th>Value</th>
                        <th>Severity</th>
                        <th>Description</th>
                        <th>Context</th>
                    </tr>
                </thead>
                <tbody>
                    {anomaly_rows}
                </tbody>
            </table>
        </div>
        {anomaly_limit_note}
    </div>

</div>

<!-- [S4.11] Footer -->
<div class="footer">
    Vital Signs Validation Pipeline v1.0.0 &nbsp;|&nbsp;
    Generated {generated_at} &nbsp;|&nbsp;
    Built with Python, Pandas, FastAPI
</div>

</body>
</html>"""


# ── [S4.12] Report Generator Class ───────────────────────────────────────────

class ReportGenerator:
    """
    Generates HTML validation report from validator and anomaly results.

    Methods:
        generate(validation_results, anomaly_results, df) -> str (file path)
        _build_column_cards(validation_results)           -> str (HTML)
        _build_type_pills(anomaly_results)                -> str (HTML)
        _build_validation_rows(issues, limit)             -> str (HTML)
        _build_anomaly_rows(anomalies, limit)             -> str (HTML)
    """

    MAX_TABLE_ROWS = 200   # Cap table rows for browser performance

    # ── [S4.13] Column Summary Cards ─────────────────────────────────────────
    def _build_column_cards(
            self, validation_results: Dict) -> str:
        """
        Build per-column summary cards showing issue counts.

        Args:
            validation_results: Dict from VitalSignsValidator.validate()

        Returns:
            HTML string of column card divs.
        """
        cards = []
        summary = validation_results.get("column_summary", {})

        vital_labels = {
            "heart_rate"  : "Heart Rate",
            "spo2"        : "SpO2",
            "temperature" : "Temperature",
            "systolic_bp" : "Systolic BP",
            "diastolic_bp": "Diastolic BP",
            "resp_rate"   : "Resp Rate",
        }

        for col, label in vital_labels.items():
            stats = summary.get(col, {
                "total_issues": 0,
                "critical_count": 0,
                "warning_count": 0,
                "null_count": 0,
            })

            crit  = stats.get("critical_count", 0)
            warn  = stats.get("warning_count", 0)
            nulls = stats.get("null_count", 0)

            if crit > 0:
                css_class = "has-critical"
            elif warn > 0:
                css_class = "has-warning"
            else:
                css_class = "clean"

            crit_class  = "crit"  if crit > 0  else "clean"
            warn_class  = "warn"  if warn > 0  else "clean"
            null_class  = "crit"  if nulls > 0 else "clean"

            cards.append(f"""
            <div class="col-card {css_class}">
                <div class="col-name">{label}</div>
                <div class="col-stat">
                    Critical:
                    <span class="{crit_class}">{crit}</span>
                </div>
                <div class="col-stat">
                    Warnings:
                    <span class="{warn_class}">{warn}</span>
                </div>
                <div class="col-stat">
                    Nulls:
                    <span class="{null_class}">{nulls}</span>
                </div>
            </div>""")

        return "\n".join(cards)

    # ── [S4.14] Anomaly Type Pills ────────────────────────────────────────────
    def _build_type_pills(self, anomaly_results: Dict) -> str:
        """
        Build anomaly type summary pills.

        Args:
            anomaly_results: Dict from AnomalyDetector.detect()

        Returns:
            HTML string of pill spans.
        """
        pills = []
        by_type = anomaly_results.get("by_type", {})

        type_labels = {
            "STATISTICAL_OUTLIER" : "Statistical Outliers",
            "STUCK_SENSOR"        : "Stuck Sensor",
            "SUDDEN_SPIKE"        : "Sudden Spikes",
            "TIMESTAMP_GAP"       : "Timestamp Gaps",
            "FLATLINE"            : "Flatlines",
        }

        for type_key, label in type_labels.items():
            count = by_type.get(type_key, 0)
            pills.append(
                f'<div class="type-pill">'
                f'{label}: <span class="count">{count}</span>'
                f'</div>'
            )

        return "\n".join(pills)

    # ── [S4.15] Validation Issue Rows ─────────────────────────────────────────
    def _build_validation_rows(
            self, issues, limit: int) -> str:
        """
        Build HTML table rows for validation issues.

        Args:
            issues: List of ValidationIssue from validator
            limit:  Max rows to render

        Returns:
            HTML string of <tr> elements.
        """
        rows    = []
        display = issues[:limit]

        for issue in display:
            severity = issue.severity.value \
                if hasattr(issue.severity, 'value') else str(issue.severity)
            badge_class = f"badge-{severity.lower()}"

            val_display = (f"{issue.value:.2f}"
                           if issue.value == issue.value  # NaN check
                           else "NULL")

            pid = issue.patient_id or "—"

            rows.append(f"""
                <tr>
                    <td>{issue.row_index}</td>
                    <td>{pid}</td>
                    <td><code>{issue.column}</code></td>
                    <td>{val_display}</td>
                    <td>
                        <span class="badge {badge_class}">
                            {severity}
                        </span>
                    </td>
                    <td>{issue.rule}</td>
                </tr>""")

        return "\n".join(rows)

    # ── [S4.16] Anomaly Rows ──────────────────────────────────────────────────
    def _build_anomaly_rows(
            self, anomalies, limit: int) -> str:
        """
        Build HTML table rows for anomaly results.

        Args:
            anomalies: List of Anomaly from detector
            limit:     Max rows to render

        Returns:
            HTML string of <tr> elements.
        """
        rows    = []
        display = anomalies[:limit]

        for anomaly in display:
            badge_class = f"badge-{anomaly.severity.lower()}"
            type_label  = anomaly.anomaly_type.value \
                if hasattr(anomaly.anomaly_type, 'value') \
                else str(anomaly.anomaly_type)

            val_display = (f"{anomaly.value:.2f}"
                           if anomaly.value == anomaly.value
                           else "NULL")

            pid     = anomaly.patient_id or "—"
            context = anomaly.context    or "—"

            rows.append(f"""
                <tr>
                    <td>{anomaly.row_index}</td>
                    <td>{pid}</td>
                    <td><code>{anomaly.column}</code></td>
                    <td>
                        <span class="type-badge">{type_label}</span>
                    </td>
                    <td>{val_display}</td>
                    <td>
                        <span class="badge {badge_class}">
                            {anomaly.severity}
                        </span>
                    </td>
                    <td>{anomaly.description}</td>
                    <td><small>{context}</small></td>
                </tr>""")

        return "\n".join(rows)

    # ── [S4.17] Main Generate Method ──────────────────────────────────────────
    def generate(
        self,
        validation_results : Dict,
        anomaly_results    : Dict,
        df,
        output_path        : str = None,
    ) -> str:
        """
        Generate full HTML report and write to reports/ directory.

        Args:
            validation_results : Dict from VitalSignsValidator.validate()
            anomaly_results    : Dict from AnomalyDetector.detect()
            df                 : Original DataFrame (for row count)
            output_path        : Optional custom output path

        Returns:
            Absolute path to the generated HTML file.
        """
        print("[Reporter] Building HTML report...")

        # [S4.17-A] Resolve output path
        os.makedirs(REPORTS_DIR, exist_ok=True)
        if output_path is None:
            timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(
                REPORTS_DIR,
                f"validation_report_{timestamp}.html"
            )

        # [S4.17-B] Computed values
        total_rows     = validation_results.get("total_rows", len(df))
        total_issues   = validation_results.get("total_issues", 0)
        critical_count = validation_results.get("critical_count", 0)
        warning_count  = validation_results.get("warning_count", 0)
        total_anomalies= anomaly_results.get("total_anomalies", 0)
        passed         = validation_results.get("passed", False)
        issues         = validation_results.get("issues", [])
        anomalies      = anomaly_results.get("anomalies", [])

        # Count nulls specifically
        null_count = sum(
            1 for i in issues
            if "Missing value" in i.rule
        )

        # [S4.17-C] Status
        status_class = "status-pass" if passed else "status-fail"
        status_icon  = "[PASS]"      if passed else "[FAIL]"
        status_text  = "VALIDATION PASSED" \
                       if passed else "VALIDATION FAILED"

        # [S4.17-D] Build table rows with cap
        limit = self.MAX_TABLE_ROWS
        validation_rows = self._build_validation_rows(issues, limit)
        anomaly_rows    = self._build_anomaly_rows(anomalies, limit)

        v_note = (
            f'<p class="limit-note">Showing first {limit} of '
            f'{total_issues} issues.</p>'
            if total_issues > limit else ""
        )
        a_note = (
            f'<p class="limit-note">Showing first {limit} of '
            f'{total_anomalies} anomalies.</p>'
            if total_anomalies > limit else ""
        )

        # [S4.17-E] Build component HTML
        column_cards = self._build_column_cards(validation_results)
        type_pills   = self._build_type_pills(anomaly_results)

        # [S4.17-F] Render template
        html = HTML_TEMPLATE.format(
            generated_at          = datetime.now().strftime(
                                    "%Y-%m-%d %H:%M:%S"),
            total_rows            = total_rows,
            total_issues          = total_issues,
            critical_count        = critical_count,
            warning_count         = warning_count,
            total_anomalies       = total_anomalies,
            null_count            = null_count,
            status_class          = status_class,
            status_icon           = status_icon,
            status_text           = status_text,
            column_cards          = column_cards,
            type_pills            = type_pills,
            validation_rows       = validation_rows,
            anomaly_rows          = anomaly_rows,
            validation_limit_note = v_note,
            anomaly_limit_note    = a_note,
        )

        # [S4.17-G] Write file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        file_size = os.path.getsize(output_path) / 1024
        print(f"[Reporter] Report written to: {output_path}")
        print(f"[Reporter] File size: {file_size:.1f} KB")

        return output_path