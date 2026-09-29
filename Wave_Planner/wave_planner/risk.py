"""Explainable 0-100 risk scoring for clusters and waves.

Every factor is normalised to 0..1 and multiplied by a documented weight. A
factor whose input is missing for *all* applications of a cluster is left out
and the remaining weights are re-normalised, so sparse inputs (like the mock
API data, which has no CPU or age) still produce a meaningful score.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .types import AppNode

# Weights sum to 100.
RISK_WEIGHTS: dict[str, float] = {
    "criticality": 30.0,
    "compliance": 20.0,
    "coupling": 20.0,
    "size": 10.0,
    "age": 10.0,
    "utilization": 10.0,
}

CRITICALITY_VALUE = {"low": 0.0, "medium": 0.5, "high": 1.0}
COUPLING_CAP = 3.0  # external dependencies per application that count as "fully coupled"
AGE_CAP_YEARS = 15.0

# Score thresholds for the Low / Medium / High label used by the API contract.
# Calibrated on the 1,000-app synthetic portfolio (wave scores span ~35-75); tune for real data.
MEDIUM_THRESHOLD = 45.0
HIGH_THRESHOLD = 65.0


def risk_level(score: float) -> str:
    if score >= HIGH_THRESHOLD:
        return "High"
    if score >= MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def score_cluster(
    apps: Sequence[AppNode], external_edges: int, size_reference: int
) -> tuple[float, dict[str, float]]:
    """Return ``(score 0..100, per-factor points)``."""
    n = len(apps)
    crit = [CRITICALITY_VALUE[a.criticality.lower()] for a in apps
            if a.criticality and a.criticality.lower() in CRITICALITY_VALUE]
    comp = [1.0 if a.compliance else 0.0 for a in apps if a.compliance is not None]
    age = [min(a.age_years, AGE_CAP_YEARS) / AGE_CAP_YEARS for a in apps if a.age_years is not None]
    util = [(a.cpu_usage + a.memory_usage) / 2 for a in apps
            if a.cpu_usage is not None and a.memory_usage is not None]

    normalised: dict[str, float | None] = {
        "criticality": _mean(crit),
        "compliance": _mean(comp),
        "coupling": min(1.0, (external_edges / n) / COUPLING_CAP) if n else 0.0,
        "size": min(1.0, math.log1p(n) / math.log1p(max(size_reference, 2))),
        "age": _mean(age),
        "utilization": _mean(util),
    }
    available = {k: v for k, v in normalised.items() if v is not None}
    total_weight = sum(RISK_WEIGHTS[k] for k in available)
    points = {k: round(100.0 * RISK_WEIGHTS[k] * v / total_weight, 2) for k, v in available.items()}
    return round(sum(points.values()), 2), points
