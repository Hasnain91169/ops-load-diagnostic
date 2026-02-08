from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .models import Classification, InboundItem, RiskFlag, WorkCategory, WorkNature


def _contains_any(text: str, phrases: Iterable[str]) -> bool:
    text_lower = text.lower()
    return any(p in text_lower for p in phrases)


@dataclass(slots=True)
class RuleSet:
    category_keywords: dict[WorkCategory, list[str]]
    exception_keywords: list[str]
    sla_keywords: list[str]


DEFAULT_RULESET = RuleSet(
    category_keywords={
        WorkCategory.EXCEPTION_DELAY: [
            "delay",
            "late",
            "missed",
            "issue",
            "problem",
            "stuck",
            "hold",
            "damaged",
            "shortage",
            "escalat",
            "failed delivery",
            "cancelled",
            "detention",
            "demurrage",
        ],
        WorkCategory.TRACKING_ETA: [
            "eta",
            "track",
            "tracking",
            "status update",
            "where is",
            "arrival time",
            "delivery time",
            "in transit",
        ],
        WorkCategory.DOCUMENTATION: [
            "invoice",
            "pod",
            "bill of lading",
            "bol",
            "awb",
            "packing list",
            "customs",
            "document",
            "paperwork",
            "declaration",
            "certificate",
            "forms",
        ],
        WorkCategory.RATE_PRICING: [
            "rate",
            "pricing",
            "quote",
            "quotation",
            "cost",
            "charge",
            "tariff",
            "spot rate",
        ],
        WorkCategory.INTERNAL_COORDINATION: [
            "please coordinate",
            "warehouse",
            "dispatch",
            "driver",
            "pickup schedule",
            "handover",
            "internal",
            "team",
            "ops",
            "arrange pickup",
        ],
    },
    exception_keywords=[
        "urgent",
        "escalat",
        "problem",
        "failed",
        "delay",
        "late",
        "stuck",
        "damage",
        "asap",
        "critical",
    ],
    sla_keywords=[
        "urgent",
        "asap",
        "today",
        "immediately",
        "deadline",
        "cutoff",
        "cut-off",
        "demurrage",
        "detention",
        "customer waiting",
        "sla",
        "missed",
    ],
)


class BaseClassifier(ABC):
    @abstractmethod
    def classify(self, item: InboundItem) -> Classification:
        raise NotImplementedError


class HeuristicClassifier(BaseClassifier):
    def __init__(self, ruleset: RuleSet | None = None):
        self.ruleset = ruleset or DEFAULT_RULESET

    def classify(self, item: InboundItem) -> Classification:
        text = f"{item.subject}\n{item.body}".lower()
        scores: dict[WorkCategory, int] = defaultdict(int)
        reasons: list[str] = []

        for category, keywords in self.ruleset.category_keywords.items():
            for kw in keywords:
                if kw in text:
                    scores[category] += 1

        if scores:
            category = max(scores.items(), key=lambda x: x[1])[0]
            reasons.append(f"Matched keywords for {category.value}")
        else:
            category = WorkCategory.OTHER
            reasons.append("No category-specific keyword match; fallback to Other")

        is_exception = category == WorkCategory.EXCEPTION_DELAY or _contains_any(
            text, self.ruleset.exception_keywords
        )
        nature = WorkNature.EXCEPTION_DRIVEN if is_exception else WorkNature.REPETITIVE

        sla_sensitive = _contains_any(text, self.ruleset.sla_keywords) or (
            category == WorkCategory.EXCEPTION_DELAY and "urgent" in text
        )
        risk = RiskFlag.SLA_SENSITIVE if sla_sensitive else RiskFlag.NOT_SLA_SENSITIVE

        confidence = 0.5
        if category != WorkCategory.OTHER:
            confidence = min(0.95, 0.55 + (scores.get(category, 0) * 0.1))
        if nature == WorkNature.EXCEPTION_DRIVEN:
            reasons.append("Exception indicators present")
        else:
            reasons.append("Routine request pattern")
        if risk == RiskFlag.SLA_SENSITIVE:
            reasons.append("SLA-sensitive language detected")

        return Classification(
            category=category,
            nature=nature,
            risk=risk,
            confidence=round(confidence, 2),
            reasons=reasons,
        )


class OpenAIClassifier(BaseClassifier):
    """
    Optional LLM-backed classifier. Falls back to heuristic behavior if output is invalid.
    """

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        api_key_env: str = "OPENAI_API_KEY",
        fallback: BaseClassifier | None = None,
    ):
        self.model = model
        self.fallback = fallback or HeuristicClassifier()
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(f"Environment variable {api_key_env} is required for OpenAI mode.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "Install openai package to use OpenAI classification: pip install openai"
            ) from exc
        self.client = OpenAI(api_key=api_key)

    def classify(self, item: InboundItem) -> Classification:
        prompt = {
            "task": "Classify one inbound logistics operations message.",
            "labels": {
                "category": [c.value for c in WorkCategory],
                "nature": [n.value for n in WorkNature],
                "risk": [r.value for r in RiskFlag],
            },
            "input": {
                "subject": item.subject,
                "body": item.body[:4000],
            },
            "requirements": [
                "Return strict JSON only.",
                "Use conservative judgments.",
                "Keep reasons concise.",
            ],
            "schema": {
                "category": "string",
                "nature": "string",
                "risk": "string",
                "confidence": "number between 0 and 1",
                "reasons": "array of short strings",
            },
        }

        response = self.client.responses.create(
            model=self.model,
            input=[{"role": "user", "content": json.dumps(prompt)}],
            temperature=0,
        )
        text = response.output_text.strip()
        try:
            parsed = json.loads(text)
            category = WorkCategory(parsed["category"])
            nature = WorkNature(parsed["nature"])
            risk = RiskFlag(parsed["risk"])
            confidence = float(parsed.get("confidence", 0.7))
            reasons = parsed.get("reasons", []) or []
            return Classification(
                category=category,
                nature=nature,
                risk=risk,
                confidence=max(0.0, min(1.0, confidence)),
                reasons=[str(r) for r in reasons][:3],
            )
        except Exception:
            return self.fallback.classify(item)
