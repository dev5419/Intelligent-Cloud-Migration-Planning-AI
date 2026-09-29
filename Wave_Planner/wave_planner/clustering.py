"""Community detection: group tightly coupled applications (Louvain)."""

from __future__ import annotations

from collections import deque

import networkx as nx

from .graph import natural_key


def _louvain(graph: nx.Graph, resolution: float, seed: int) -> list[set[str]]:
    if graph.number_of_nodes() == 0:
        return []
    return [set(c) for c in nx.community.louvain_communities(
        graph, weight="weight", resolution=resolution, seed=seed
    )]


def _bfs_chunks(graph: nx.Graph, cap: int) -> list[set[str]]:
    """Deterministic last-resort split: walk the graph breadth-first and cut every ``cap`` nodes."""
    order: list[str] = []
    seen: set[str] = set()
    for start in sorted(graph.nodes, key=natural_key):
        if start in seen:
            continue
        queue = deque([start])
        seen.add(start)
        while queue:
            node = queue.popleft()
            order.append(node)
            for nbr in sorted(graph[node], key=natural_key):
                if nbr not in seen:
                    seen.add(nbr)
                    queue.append(nbr)
    return [set(order[i:i + cap]) for i in range(0, len(order), cap)]


def _split_oversized(nodes: set[str], graph: nx.Graph, cap: int, resolution: float, seed: int) -> list[set[str]]:
    if len(nodes) <= cap:
        return [nodes]
    sub = graph.subgraph(nodes)
    parts: list[set[str]] = [nodes]
    res = resolution
    for _ in range(6):  # raise the resolution until Louvain actually splits the community
        res *= 1.5
        parts = _louvain(sub, res, seed)
        if len(parts) > 1:
            break
    if len(parts) <= 1:
        parts = _bfs_chunks(sub, cap)
    result: list[set[str]] = []
    for part in parts:
        if len(part) < len(nodes):
            result.extend(_split_oversized(part, graph, cap, resolution, seed))
        else:  # no progress possible -> chunk to guarantee termination
            result.extend(_bfs_chunks(graph.subgraph(part), cap))
    return result


def detect_clusters(
    undirected: nx.Graph,
    *,
    resolution: float = 1.0,
    max_cluster_size: int | None = None,
    seed: int = 42,
) -> list[list[str]]:
    """Louvain communities, optionally capped in size.

    Returns clusters as sorted ID lists, ordered by their smallest ID so cluster
    numbering is stable between runs.
    """
    communities = _louvain(undirected, resolution, seed)
    if max_cluster_size:
        capped: list[set[str]] = []
        for community in communities:
            capped.extend(_split_oversized(community, undirected, max_cluster_size, resolution, seed))
        communities = capped
    clusters = [sorted(c, key=natural_key) for c in communities if c]
    clusters.sort(key=lambda c: natural_key(c[0]))
    return clusters
