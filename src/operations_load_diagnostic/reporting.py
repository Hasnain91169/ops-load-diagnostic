from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .aggregation import DiagnosticMetrics


def _markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    if not rows:
        return "_No data_"
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    row_lines = ["| " + " | ".join(str(x) for x in row) + " |" for row in rows]
    return "\n".join([header_line, sep_line, *row_lines])


def generate_markdown_report(
    metrics: DiagnosticMetrics,
    leverage_summary: list[str],
    assumptions: dict[str, object],
) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    category_rows = sorted(
        [
            [
                category,
                count,
                f"{metrics.category_percentages.get(category, 0.0)}%",
                metrics.estimated_minutes_by_category.get(category, 0),
            ]
            for category, count in metrics.category_counts.items()
        ],
        key=lambda x: x[1],
        reverse=True,
    )

    nature_rows = [
        [name, count, f"{metrics.nature_percentages.get(name, 0.0)}%"]
        for name, count in metrics.nature_counts.items()
    ]

    sla_rows = [
        [row["category"], row["count"], f'{row["share_of_sla"]}%']
        for row in metrics.sla_clusters
    ]

    summary_lines = "\n".join([f"- {x}" for x in leverage_summary]) or "- _No summary generated_"

    assumption_lines = "\n".join([f"- **{k}**: {v}" for k, v in assumptions.items()])

    md = f"""# Operations Load Diagnostic Report

Generated: {timestamp}

## 1. Inbound Volume Snapshot
- Total inbound items analyzed: **{metrics.total_volume}**
- Observation window: **{metrics.period_days} day(s)**

## 2. Work Category Breakdown
{_markdown_table(
    ["Work Category", "Volume", "% of Inbound", "Estimated Minutes"],
    category_rows,
)}

## 3. Repetitive vs Exception Work
{_markdown_table(
    ["Work Nature", "Volume", "% of Inbound"],
    nature_rows,
)}

## 4. Estimated Operational Load (hours/week)
- Estimated total handling time in sample window: **{metrics.estimated_total_minutes} minutes**
- Estimated weekly operational load: **{metrics.estimated_hours_per_week} hours/week**

### SLA-sensitive Work Clusters
{_markdown_table(
    ["Category", "SLA-sensitive Volume", "Share of SLA-sensitive"],
    sla_rows,
)}

## 5. Automation Leverage Summary
{summary_lines}

## Conservative Assumptions Used
{assumption_lines}
"""
    return md


def generate_html_report_from_metrics(
    metrics: DiagnosticMetrics,
    leverage_summary: list[str],
    assumptions: dict[str, object],
) -> str:
    def rows_to_html(rows: list[list[object]]) -> str:
        if not rows:
            return "<tr><td colspan='4'>No data</td></tr>"
        return "\n".join(
            [
                "<tr>" + "".join([f"<td>{str(cell)}</td>" for cell in row]) + "</tr>"
                for row in rows
            ]
        )

    category_rows = sorted(
        [
            [
                category,
                count,
                f"{metrics.category_percentages.get(category, 0.0)}%",
                metrics.estimated_minutes_by_category.get(category, 0),
            ]
            for category, count in metrics.category_counts.items()
        ],
        key=lambda x: x[1],
        reverse=True,
    )
    nature_rows = [
        [name, count, f"{metrics.nature_percentages.get(name, 0.0)}%"]
        for name, count in metrics.nature_counts.items()
    ]
    sla_rows = [
        [row["category"], row["count"], f'{row["share_of_sla"]}%']
        for row in metrics.sla_clusters
    ]

    summary_list = "".join([f"<li>{x}</li>" for x in leverage_summary]) or "<li>No summary generated</li>"
    assumption_list = "".join([f"<li><strong>{k}</strong>: {v}</li>" for k, v in assumptions.items()])

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Operations Load Diagnostic Report</title>
  <style>
    body {{
      font-family: "Segoe UI", Tahoma, sans-serif;
      margin: 32px;
      color: #111;
      line-height: 1.45;
    }}
    h1, h2, h3 {{ margin-top: 24px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0 18px 0;
    }}
    th, td {{
      border: 1px solid #d4d4d4;
      padding: 8px;
      text-align: left;
    }}
    th {{ background: #f5f5f5; }}
    .kpi {{
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      padding: 12px;
      margin: 8px 0;
    }}
  </style>
</head>
<body>
  <h1>Operations Load Diagnostic Report</h1>
  <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>

  <h2>1. Inbound Volume Snapshot</h2>
  <div class="kpi">Total inbound items analyzed: <strong>{metrics.total_volume}</strong></div>
  <div class="kpi">Observation window: <strong>{metrics.period_days} day(s)</strong></div>

  <h2>2. Work Category Breakdown</h2>
  <table>
    <thead><tr><th>Work Category</th><th>Volume</th><th>% of Inbound</th><th>Estimated Minutes</th></tr></thead>
    <tbody>{rows_to_html(category_rows)}</tbody>
  </table>

  <h2>3. Repetitive vs Exception Work</h2>
  <table>
    <thead><tr><th>Work Nature</th><th>Volume</th><th>% of Inbound</th></tr></thead>
    <tbody>{rows_to_html(nature_rows)}</tbody>
  </table>

  <h2>4. Estimated Operational Load (hours/week)</h2>
  <div class="kpi">Sample handling time: <strong>{metrics.estimated_total_minutes} minutes</strong></div>
  <div class="kpi">Estimated weekly load: <strong>{metrics.estimated_hours_per_week} hours/week</strong></div>

  <h3>SLA-sensitive Work Clusters</h3>
  <table>
    <thead><tr><th>Category</th><th>SLA-sensitive Volume</th><th>Share of SLA-sensitive</th></tr></thead>
    <tbody>{rows_to_html(sla_rows)}</tbody>
  </table>

  <h2>5. Automation Leverage Summary</h2>
  <ul>{summary_list}</ul>

  <h2>Conservative Assumptions Used</h2>
  <ul>{assumption_list}</ul>
</body>
</html>"""
    return html


def write_report(content: str, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target
