from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime

from .models import ClassifiedItem, RiskFlag, WorkCategory, WorkNature


CONSERVATIVE_MINUTES_BY_CATEGORY: dict[WorkCategory, int] = {
    WorkCategory.TRACKING_ETA: 4,
    WorkCategory.EXCEPTION_DELAY: 12,
    WorkCategory.DOCUMENTATION: 7,
    WorkCategory.RATE_PRICING: 8,
    WorkCategory.INTERNAL_COORDINATION: 6,
    WorkCategory.OTHER: 5,
}


@dataclass(slots=True)
class DiagnosticMetrics:
    total_volume: int
    period_days: int
    category_counts: dict[str, int]
    category_percentages: dict[str, float]
    nature_counts: dict[str, int]
    nature_percentages: dict[str, float]
    risk_counts: dict[str, int]
    risk_percentages: dict[str, float]
    estimated_minutes_by_category: dict[str, int]
    estimated_total_minutes: int
    estimated_hours_per_week: float
    sla_clusters: list[dict[str, object]]


def _safe_pct(count: int, total: int) -> float:
    return round((count / total) * 100, 1) if total else 0.0


def aggregate_metrics(
    items: list[ClassifiedItem],
    fallback_period_days: int = 14,
) -> DiagnosticMetrics:
    total = len(items)
    if total == 0:
        return DiagnosticMetrics(
            total_volume=0,
            period_days=fallback_period_days,
            category_counts={},
            category_percentages={},
            nature_counts={},
            nature_percentages={},
            risk_counts={},
            risk_percentages={},
            estimated_minutes_by_category={},
            estimated_total_minutes=0,
            estimated_hours_per_week=0.0,
            sla_clusters=[],
        )

    timestamps = [x.item.timestamp for x in items if x.item.timestamp is not None]
    if timestamps:
        min_ts = min(timestamps)
        max_ts = max(timestamps)
        period_days = max(1, (max_ts - min_ts).days + 1)
    else:
        period_days = fallback_period_days

    cat_counter = Counter([x.classification.category.value for x in items])
    nature_counter = Counter([x.classification.nature.value for x in items])
    risk_counter = Counter([x.classification.risk.value for x in items])

    estimated_by_category: dict[str, int] = {}
    for cat_name, count in cat_counter.items():
        cat_enum = WorkCategory(cat_name)
        estimated_by_category[cat_name] = count * CONSERVATIVE_MINUTES_BY_CATEGORY[cat_enum]
    total_minutes = sum(estimated_by_category.values())
    weekly_hours = round((total_minutes / 60.0) * (7.0 / period_days), 1)

    sla_by_category: defaultdict[str, int] = defaultdict(int)
    for x in items:
        if x.classification.risk == RiskFlag.SLA_SENSITIVE:
            sla_by_category[x.classification.category.value] += 1

    sla_clusters = sorted(
        [
            {
                "category": category,
                "count": count,
                "share_of_sla": _safe_pct(count, sum(sla_by_category.values())),
            }
            for category, count in sla_by_category.items()
        ],
        key=lambda x: x["count"],
        reverse=True,
    )

    return DiagnosticMetrics(
        total_volume=total,
        period_days=period_days,
        category_counts=dict(cat_counter),
        category_percentages={k: _safe_pct(v, total) for k, v in cat_counter.items()},
        nature_counts=dict(nature_counter),
        nature_percentages={k: _safe_pct(v, total) for k, v in nature_counter.items()},
        risk_counts=dict(risk_counter),
        risk_percentages={k: _safe_pct(v, total) for k, v in risk_counter.items()},
        estimated_minutes_by_category=estimated_by_category,
        estimated_total_minutes=total_minutes,
        estimated_hours_per_week=weekly_hours,
        sla_clusters=sla_clusters,
    )


def automation_leverage_summary(metrics: DiagnosticMetrics) -> list[str]:
    summary: list[str] = []
    if metrics.total_volume == 0:
        return ["No inbound data in selected window; unable to estimate automation leverage."]

    repetitive_pct = metrics.nature_percentages.get(WorkNature.REPETITIVE.value, 0.0)
    exception_pct = metrics.nature_percentages.get(WorkNature.EXCEPTION_DRIVEN.value, 0.0)

    if repetitive_pct >= 50:
        summary.append(
            f"{repetitive_pct}% of inbound work appears repetitive and is a candidate for templated AI assistance."
        )
    else:
        summary.append(
            f"Repetitive work is {repetitive_pct}%; prioritize exception triage before broad automation."
        )

    top_categories = sorted(
        metrics.category_counts.items(), key=lambda x: x[1], reverse=True
    )[:2]
    if top_categories:
        cats = ", ".join([f"{name} ({count})" for name, count in top_categories])
        summary.append(f"Highest-load categories: {cats}. Start pilot scope here.")

    sla_sensitive_pct = metrics.risk_percentages.get(RiskFlag.SLA_SENSITIVE.value, 0.0)
    if sla_sensitive_pct > 0:
        summary.append(
            f"SLA-sensitive traffic is {sla_sensitive_pct}%; keep human-in-the-loop controls for these flows."
        )
    else:
        summary.append("No SLA-sensitive cluster detected in this sample window.")

    weekly = metrics.estimated_hours_per_week
    if weekly >= 10:
        summary.append(
            f"Estimated operational load is {weekly} hours/week, indicating meaningful automation ROI potential."
        )
    else:
        summary.append(
            f"Estimated load is {weekly} hours/week; use this as a baseline before committing to heavier automation."
        )

    return summary
