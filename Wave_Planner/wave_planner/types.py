"""Plain data structures shared by the wave planner modules.

The planner is deliberately independent from FastAPI/Pydantic so it can be
reused from the CLI, notebooks, tests, or an AWS Lambda handler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RISK_LEVELS = ("Low", "Medium", "High")


@dataclass(frozen=True)
class AppNode:
    """One application as seen by the planner.

    ``dependencies`` lists the IDs this application *depends on*, i.e. the
    applications that should already be running in the cloud when this one
    moves. Only ``id`` is mandatory; every other field is optional and simply
    excluded from the risk score when it is missing.
    """

    id: str
    name: str = ""
    dependencies: tuple[str, ...] = ()
    criticality: str | None = None  # "Low" | "Medium" | "High"
    compliance: bool | None = None
    age_years: float | None = None
    cpu_usage: float | None = None  # 0..1
    memory_usage: float | None = None  # 0..1


@dataclass
class Cluster:
    """A group of tightly coupled applications that migrate together."""

    id: str
    apps: list[str]
    internal_edges: int = 0  # dependencies fully inside the cluster
    external_edges: int = 0  # dependencies crossing the cluster boundary (in + out)
    risk_score: float = 0.0
    risk_factors: dict[str, float] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.apps)


@dataclass
class Wave:
    number: int
    clusters: list[Cluster]
    apps: list[str]
    risk_score: float = 0.0
    risk: str = "Low"
    # Dependency edges leaving this wave towards applications that only migrate
    # in a LATER wave. They need temporary hybrid connectivity.
    unmet_dependencies: int = 0
    # Earlier waves this wave depends on (all satisfied before it starts).
    depends_on_waves: list[int] = field(default_factory=list)
    # True when clusters depending on each other (a cycle) were broken up or
    # co-scheduled to build this wave.
    cycle_break: bool = False


@dataclass
class WavePlan:
    waves: list[Wave]
    clusters: list[Cluster]
    summary: dict[str, Any]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "waves": [
                {
                    "wave": w.number,
                    "applications": w.apps,
                    "risk": w.risk,
                    "risk_score": w.risk_score,
                    "application_count": len(w.apps),
                    "unmet_dependencies": w.unmet_dependencies,
                    "depends_on_waves": w.depends_on_waves,
                    "cycle_break": w.cycle_break,
                    "clusters": [
                        {
                            "cluster_id": c.id,
                            "applications": c.apps,
                            "size": c.size,
                            "internal_dependencies": c.internal_edges,
                            "external_dependencies": c.external_edges,
                            "risk_score": c.risk_score,
                            "risk_factors": c.risk_factors,
                        }
                        for c in w.clusters
                    ],
                }
                for w in self.waves
            ],
            "summary": self.summary,
            "warnings": self.warnings,
        }
