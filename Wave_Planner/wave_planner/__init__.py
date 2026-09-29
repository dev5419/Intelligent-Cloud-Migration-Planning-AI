"""Feature 2: Dependency-Aware Migration Wave Planner.

NetworkX dependency graph -> Louvain clustering -> greedy wave ordering.
See ``docs/WAVE_PLANNER.md``.
"""

from .loaders import from_objects, load_csv, load_json, parse_dependencies
from .planner import DEFAULT_MAX_WAVE_SIZE, auto_wave_size, plan_waves
from .types import AppNode, Cluster, Wave, WavePlan

__all__ = [
    "AppNode", "Cluster", "Wave", "WavePlan",
    "plan_waves", "auto_wave_size", "DEFAULT_MAX_WAVE_SIZE",
    "load_csv", "load_json", "from_objects", "parse_dependencies",
]
