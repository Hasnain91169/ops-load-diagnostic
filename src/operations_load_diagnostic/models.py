from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class WorkCategory(str, Enum):
    TRACKING_ETA = "Tracking / ETA"
    EXCEPTION_DELAY = "Exception / Delay"
    DOCUMENTATION = "Documentation"
    RATE_PRICING = "Rate / Pricing"
    INTERNAL_COORDINATION = "Internal Coordination"
    OTHER = "Other"


class WorkNature(str, Enum):
    REPETITIVE = "Repetitive"
    EXCEPTION_DRIVEN = "Exception-driven"


class RiskFlag(str, Enum):
    SLA_SENSITIVE = "SLA-sensitive"
    NOT_SLA_SENSITIVE = "Not SLA-sensitive"


@dataclass(slots=True)
class InboundItem:
    item_id: str
    timestamp: Optional[datetime]
    sender: Optional[str]
    subject: str
    body: str
    source: str = "unknown"


@dataclass(slots=True)
class Classification:
    category: WorkCategory
    nature: WorkNature
    risk: RiskFlag
    confidence: float
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ClassifiedItem:
    item: InboundItem
    classification: Classification

