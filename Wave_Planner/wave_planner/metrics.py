"""Quality metrics + the naive baseline used to justify the planner."""

from __future__ import annotations

import random
from collections.abc import Mapping

import networkx as nx

from .graph import natural_key


def evaluate_assignment(graph: nx.DiGraph, wave_of: Mapping[str, int]) -> dict[str, int]:
    """Count how dependency edges relate to a wave assignment.

    * ``cross_wave``: dependent and dependency migrate in different waves
      (each one needs temporary cross-environment connectivity).
    * ``unmet``: the dependency migrates in a LATER wave than its dependent,
      i.e. the app moves before something it relies on.
    """
    cross = unmet = 0
    for a, b in graph.edges:
        if wave_of[a] != wave_of[b]:
            cross += 1
            if wave_of[b] > wave_of[a]:
                unmet += 1
    return {"total": graph.number_of_edges(), "cross_wave": cross, "unmet": unmet}


def random_baseline(
    graph: nx.DiGraph, wave_sizes: list[int], trials: int = 30, seed: int = 42
) -> dict[str, float]:
    """Average metrics of random app-to-wave assignments with the SAME wave sizes."""
    nodes = sorted(graph.nodes, key=natural_key)
    if not nodes or trials <= 0:
        return {"cross_wave": 0.0, "unmet": 0.0}
    cross_total = unmet_total = 0.0
    for t in range(trials):
        rng = random.Random(seed + t)
        shuffled = nodes[:]
        rng.shuffle(shuffled)
        wave_of: dict[str, int] = {}
        i = 0
        for number, size in enumerate(wave_sizes, start=1):
            for node in shuffled[i:i + size]:
                wave_of[node] = number
            i += size
        m = evaluate_assignment(graph, wave_of)
        cross_total += m["cross_wave"]
        unmet_total += m["unmet"]
    return {"cross_wave": cross_total / trials, "unmet": unmet_total / trials}


def reduction_pct(planned: float, baseline: float) -> float:
    return round(100.0 * (baseline - planned) / baseline, 1) if baseline else 0.0
