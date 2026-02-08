from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .aggregation import (
    CONSERVATIVE_MINUTES_BY_CATEGORY,
    aggregate_metrics,
    automation_leverage_summary,
)
from .classification import HeuristicClassifier, OpenAIClassifier
from .ingestion import ingest_csv, ingest_imap, ingest_text_batch, limit_items
from .models import ClassifiedItem
from .reporting import (
    generate_html_report_from_metrics,
    generate_markdown_report,
    write_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a one-time Operations Load Diagnostic and generate a static report."
    )
    parser.add_argument("--mode", choices=["csv", "text", "imap"], required=True)
    parser.add_argument("--input", help="Path for csv/text mode.")
    parser.add_argument("--lookback-days", type=int, default=14)
    parser.add_argument("--max-items", type=int, default=200)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--report-name", default="operations_load_diagnostic")
    parser.add_argument("--format", choices=["markdown", "html", "both"], default="both")
    parser.add_argument("--classifier", choices=["heuristic", "openai"], default="heuristic")
    parser.add_argument("--openai-model", default="gpt-4.1-mini")

    parser.add_argument("--imap-host")
    parser.add_argument("--imap-user")
    parser.add_argument("--imap-password")
    parser.add_argument("--imap-folder", default="INBOX")

    return parser


def run(args: argparse.Namespace) -> dict[str, object]:
    if args.mode in {"csv", "text"} and not args.input:
        raise ValueError("--input is required for csv/text mode.")

    if args.mode == "csv":
        inbound = ingest_csv(args.input)
    elif args.mode == "text":
        inbound = ingest_text_batch(args.input)
    else:
        if not all([args.imap_host, args.imap_user, args.imap_password]):
            raise ValueError(
                "IMAP mode requires --imap-host, --imap-user, and --imap-password."
            )
        inbound = ingest_imap(
            host=args.imap_host,
            username=args.imap_user,
            password=args.imap_password,
            folder=args.imap_folder,
            lookback_days=args.lookback_days,
            max_items=args.max_items,
        )

    inbound = limit_items(
        inbound,
        lookback_days=args.lookback_days,
        max_items=args.max_items,
    )

    if args.classifier == "openai":
        classifier = OpenAIClassifier(model=args.openai_model)
    else:
        classifier = HeuristicClassifier()

    classified: list[ClassifiedItem] = [
        ClassifiedItem(item=item, classification=classifier.classify(item)) for item in inbound
    ]

    metrics = aggregate_metrics(classified, fallback_period_days=args.lookback_days)
    leverage = automation_leverage_summary(metrics)

    assumptions = {
        "Diagnostic mode": "Read-only, one-time static snapshot; no workflow changes.",
        "Window cap": f"{args.lookback_days} day lookback and max {args.max_items} items.",
        "Handling time defaults (minutes/category)": ", ".join(
            [f"{k.value}: {v}" for k, v in CONSERVATIVE_MINUTES_BY_CATEGORY.items()]
        ),
        "Classifier": args.classifier,
        "Accuracy expectation": "Directionally correct prioritization, not perfect labeling.",
    }

    output_dir = Path(args.output_dir)
    timestamp_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{args.report_name}_{timestamp_tag}"

    output_files: dict[str, str] = {}
    if args.format in {"markdown", "both"}:
        md_content = generate_markdown_report(metrics, leverage, assumptions)
        md_path = write_report(md_content, output_dir / f"{base_name}.md")
        output_files["markdown"] = str(md_path)
    if args.format in {"html", "both"}:
        html_content = generate_html_report_from_metrics(metrics, leverage, assumptions)
        html_path = write_report(html_content, output_dir / f"{base_name}.html")
        output_files["html"] = str(html_path)

    summary = {
        "items_processed": metrics.total_volume,
        "period_days": metrics.period_days,
        "estimated_hours_per_week": metrics.estimated_hours_per_week,
        "output_files": output_files,
    }
    write_report(
        json.dumps(summary, indent=2),
        output_dir / f"{base_name}.summary.json",
    )
    return summary


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
