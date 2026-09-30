"""Dependency graph construction (NetworkX)."""

from __future__ import annotations

import re
from collections.abc import Iterable

import networkx as nx

from .types import AppNode

_NUM = re.compile(r"(\d+)")


def natural_key(value: str) -> list:
    """Sort key so that APP2 < APP10 (and results are deterministic)."""
    return [int(p) if p.isdigit() else p for p in _NUM.split(value)]


def build_dependency_graph(apps: Iterable[AppNode]) -> tuple[nx.DiGraph, list[str]]:
    """Return ``(graph, warnings)``.

    Edge ``a -> b`` means "*a depends on b*", so ``b`` should migrate first.
    Self-dependencies, duplicates and references to applications outside the
    given set are dropped and reported as warnings rather than raising, because
    real portfolio exports are messy.
    """
    apps = sorted(apps, key=lambda a: natural_key(a.id))
    ids = [a.id for a in apps]
    if len(ids) != len(set(ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1}, key=natural_key)
        raise ValueError(f"Duplicate application ids: {dupes}")

    graph = nx.DiGraph()
    for app in apps:
        graph.add_node(app.id, app=app)

    known = set(ids)
    self_deps = outside = duplicates = 0
    for app in apps:
        for dep in app.dependencies:
            if dep == app.id:
                self_deps += 1
            elif dep not in known:
                outside += 1
            elif graph.has_edge(app.id, dep):
                duplicates += 1
            else:
                graph.add_edge(app.id, dep)

    warnings: list[str] = []
    if self_deps:
        warnings.append(f"Ignored {self_deps} self-dependencies.")
    if duplicates:
        warnings.append(f"Ignored {duplicates} duplicate dependency entries.")
    if outside:
        warnings.append(
            f"Ignored {outside} dependencies on applications outside the selected set "
            "(assumed already migrated or out of scope)."
        )
    return graph, warnings


def undirected_projection(graph: nx.DiGraph) -> nx.Graph:
    """Weighted undirected view used for community detection.

    A mutual dependency (a<->b) is a stronger coupling than a one-way one, so it
    gets weight 2. Nodes are inserted in natural order for reproducible runs.
    """
    undirected = nx.Graph()
    undirected.add_nodes_from(sorted(graph.nodes, key=natural_key))
    for a, b in graph.edges:
        weight = 2 if graph.has_edge(b, a) else 1
        undirected.add_edge(a, b, weight=weight)
    return undirected
