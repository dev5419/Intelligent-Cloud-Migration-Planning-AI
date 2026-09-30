"""Public entry point: ``plan_waves``."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

import networkx as nx

from .clustering import detect_clusters
from .graph import build_dependency_graph, natural_key, undirected_projection
from .metrics import evaluate_assignment, random_baseline, reduction_pct
from .risk import risk_level, score_cluster
from .scheduler import build_cluster_graph, migration_order, schedule_waves
from .types import AppNode, Cluster, Wave, WavePlan

DEFAULT_MAX_WAVE_SIZE = 100  # upper bound for the automatic wave size
MIN_AUTO_WAVES = 4  # the automatic wave size aims for at least this many waves
UNMET_PENALTY_MAX = 20.0  # extra risk points when every outgoing dependency of a wave is unmet


def auto_wave_size(application_count: int) -> int:
    """Default wave capacity: at most 100 apps, but small portfolios still get ~4 waves."""
    return max(1, min(DEFAULT_MAX_WAVE_SIZE, -(-application_count // MIN_AUTO_WAVES)))


def plan_waves(
    apps: Iterable[AppNode],
    *,
    max_wave_size: int | None = None,
    max_cluster_size: int | None = None,
    resolution: float = 1.0,
    seed: int = 42,
    baseline_trials: int = 30,
) -> WavePlan:
    """Plan dependency-aware migration waves.

    1. Build the dependency graph (NetworkX).
    2. Cluster tightly coupled apps with Louvain community detection.
    3. Score every cluster's migration risk (explainable, 0-100).
    4. Order clusters greedily (lowest risk first, dependencies before
       dependents, cycles broken with a min-unmet-dependency rule) and pack them
       into waves of at most ``max_wave_size`` applications.
    5. Compare against a random-assignment baseline.

    ``max_wave_size=None`` picks :func:`auto_wave_size`. Applications inside each
    wave are listed in migration order (dependencies first). The result is
    deterministic for a fixed ``seed``.
    """
    if max_wave_size is not None and max_wave_size < 1:
        raise ValueError("max_wave_size must be >= 1")
    if resolution <= 0:
        raise ValueError("resolution must be > 0")

    apps = list(apps)
    graph, warnings = build_dependency_graph(apps)
    if max_wave_size is None:
        max_wave_size = auto_wave_size(graph.number_of_nodes())
    if graph.number_of_nodes() == 0:
        return WavePlan(waves=[], clusters=[], summary=_empty_summary(max_wave_size), warnings=warnings)

    nodes = {n: graph.nodes[n]["app"] for n in graph.nodes}
    cluster_cap = max_cluster_size or max_wave_size

    # --- 2. clusters -------------------------------------------------------
    groups = detect_clusters(
        undirected_projection(graph), resolution=resolution, max_cluster_size=cluster_cap, seed=seed
    )
    membership: dict[str, str] = {}
    clusters: dict[str, Cluster] = {}
    width = max(2, len(str(len(groups))))
    for index, members in enumerate(groups, start=1):
        cid = f"C{index:0{width}d}"
        clusters[cid] = Cluster(id=cid, apps=members)
        for app_id in members:
            membership[app_id] = cid

    # --- 3. risk -----------------------------------------------------------
    for a, b in graph.edges:
        ca, cb = membership[a], membership[b]
        if ca == cb:
            clusters[ca].internal_edges += 1
        else:
            clusters[ca].external_edges += 1
            clusters[cb].external_edges += 1
    for cluster in clusters.values():
        cluster.risk_score, cluster.risk_factors = score_cluster(
            [nodes[a] for a in cluster.apps], cluster.external_edges, max_wave_size
        )

    # --- 4. order + pack ---------------------------------------------------
    cluster_graph = build_cluster_graph(graph, membership)
    schedule = schedule_waves(cluster_graph, clusters, max_wave_size)

    wave_of: dict[str, int] = {}
    waves: list[Wave] = []
    for number, (cluster_ids, cycle_break) in enumerate(schedule, start=1):
        wave_clusters = [clusters[c] for c in cluster_ids]
        wave_apps = migration_order(graph, [a for c in wave_clusters for a in c.apps])
        for app_id in wave_apps:
            wave_of[app_id] = number
        waves.append(Wave(number=number, clusters=wave_clusters, apps=wave_apps, cycle_break=cycle_break))

    for wave in waves:
        outgoing = unmet = 0
        depends_on: set[int] = set()
        for app_id in wave.apps:
            for dep in graph.successors(app_id):
                outgoing += 1
                dep_wave = wave_of[dep]
                if dep_wave > wave.number:
                    unmet += 1
                elif dep_wave < wave.number:
                    depends_on.add(dep_wave)
        wave.unmet_dependencies = unmet
        wave.depends_on_waves = sorted(depends_on)
        base = sum(c.risk_score * c.size for c in wave.clusters) / len(wave.apps)
        penalty = UNMET_PENALTY_MAX * unmet / outgoing if outgoing else 0.0
        wave.risk_score = round(min(100.0, base + penalty), 2)
        wave.risk = risk_level(wave.risk_score)

    # --- 5. evaluation -----------------------------------------------------
    planned = evaluate_assignment(graph, wave_of)
    baseline = random_baseline(graph, [len(w.apps) for w in waves], baseline_trials, seed)
    summary = {
        "application_count": graph.number_of_nodes(),
        "dependency_count": planned["total"],
        "cluster_count": len(clusters),
        "wave_count": len(waves),
        "max_wave_size": max_wave_size,
        "cycle_breaks": sum(1 for w in waves if w.cycle_break),
        "largest_dependency_cycle": max(
            (len(c) for c in nx.strongly_connected_components(graph)), default=0
        ),
        "intra_cluster_dependency_pct": round(
            100.0 * sum(c.internal_edges for c in clusters.values()) / planned["total"], 1
        ) if planned["total"] else 100.0,
        "risk_distribution": dict(Counter(w.risk for w in waves)),
        "planner": {
            "cross_wave_dependencies": planned["cross_wave"],
            "unmet_dependencies": planned["unmet"],
        },
        "random_baseline": {
            "trials": baseline_trials,
            "cross_wave_dependencies": round(baseline["cross_wave"], 1),
            "unmet_dependencies": round(baseline["unmet"], 1),
        },
        "improvement_vs_random_pct": {
            "cross_wave_dependencies": reduction_pct(planned["cross_wave"], baseline["cross_wave"]),
            "unmet_dependencies": reduction_pct(planned["unmet"], baseline["unmet"]),
        },
        "params": {"resolution": resolution, "max_cluster_size": cluster_cap, "seed": seed},
    }
    return WavePlan(waves=waves, clusters=list(clusters.values()), summary=summary, warnings=warnings)


def _empty_summary(max_wave_size: int) -> dict:
    return {"application_count": 0, "dependency_count": 0, "cluster_count": 0,
            "wave_count": 0, "max_wave_size": max_wave_size}
