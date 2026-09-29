"""Greedy wave ordering over the cluster-level dependency graph.

Rules
-----
1. A cluster is *ready* when every cluster it depends on already sits in an
   EARLIER wave (dependencies land in the cloud first).
2. Ready clusters are added to the current wave lowest-risk / least-coupled
   first, until the wave's application capacity is reached.
3. Real portfolios contain dependency cycles between clusters, so sometimes
   nothing is ready. Then the scheduler breaks the cycle with the
   Eades-Lin-Smyth greedy rule: pick the cluster whose migration strands the
   fewest dependencies relative to how many waiting dependents it unblocks
   (``cost = unmet_out - pending_in``). The wave keeps filling with further
   clusters while their cost stays <= 0 (they resolve at least as much as they
   strand) and they fit the capacity. Unmet dependencies are counted and
   reported so the team knows where temporary hybrid connectivity is needed.
"""

from __future__ import annotations

import networkx as nx

from .graph import natural_key
from .types import Cluster


def build_cluster_graph(graph: nx.DiGraph, membership: dict[str, str]) -> nx.DiGraph:
    """Directed graph between clusters; edge weight = number of app-level dependencies."""
    cluster_graph = nx.DiGraph()
    cluster_graph.add_nodes_from(set(membership.values()))
    for a, b in graph.edges:
        ca, cb = membership[a], membership[b]
        if ca == cb:
            continue
        if cluster_graph.has_edge(ca, cb):
            cluster_graph[ca][cb]["weight"] += 1
        else:
            cluster_graph.add_edge(ca, cb, weight=1)
    return cluster_graph


def schedule_waves(
    cluster_graph: nx.DiGraph,
    clusters: dict[str, Cluster],
    max_wave_size: int,
) -> list[tuple[list[str], bool]]:
    """Return ``[(cluster_ids, cycle_break)]`` in migration order."""
    remaining = set(clusters)
    done: set[str] = set()  # clusters placed in earlier (closed) waves
    waves: list[tuple[list[str], bool]] = []

    def priority(cid: str):
        c = clusters[cid]
        return (c.risk_score, c.external_edges, natural_key(cid))

    def cycle_cost(cid: str):
        unmet_out = sum(cluster_graph[cid][d]["weight"]
                        for d in cluster_graph.successors(cid) if d in remaining)
        pending_in = sum(cluster_graph[p][cid]["weight"]
                         for p in cluster_graph.predecessors(cid) if p in remaining)
        return (unmet_out - pending_in, *priority(cid))

    while remaining:
        wave: list[str] = []
        size = 0
        cycle_break = False

        def fits(cid: str) -> bool:
            # An oversized cluster is allowed, but only alone in its wave.
            return not wave or size + clusters[cid].size <= max_wave_size

        while True:
            # Readiness is judged against strictly earlier waves (`done`); members
            # of the open wave never unblock each other.
            ready = [cid for cid in remaining
                     if all(dep in done for dep in cluster_graph.successors(cid))]
            fitting = [cid for cid in ready if fits(cid)]
            if fitting:
                pick = min(fitting, key=priority)
            elif ready:  # ready clusters exist but the wave is full
                break
            else:  # everything left is blocked by a cycle
                candidates = [cid for cid in remaining if fits(cid)]
                if not candidates:
                    break
                pick = min(candidates, key=cycle_cost)
                # The first pick is forced; extra picks must not strand more than they resolve.
                if wave and cycle_cost(pick)[0] > 0:
                    break
                cycle_break = True
            wave.append(pick)
            size += clusters[pick].size
            remaining.discard(pick)

        done.update(wave)
        waves.append((wave, cycle_break))
    return waves


def migration_order(graph: nx.DiGraph, app_ids: list[str]) -> list[str]:
    """Order the applications of ONE wave so dependencies come before dependents.

    Applications in a dependency cycle cannot be ordered against each other
    (they must cut over together), so each strongly connected component is kept
    contiguous and sorted by ID. Ties between independent items are broken by ID
    for reproducibility.
    """
    sub = graph.subgraph(app_ids)
    condensed = nx.condensation(sub)
    members = {n: sorted(condensed.nodes[n]["members"], key=natural_key) for n in condensed.nodes}
    # Edges point dependent -> dependency, so walk the reversed DAG to visit dependencies first.
    order = nx.lexicographical_topological_sort(
        condensed.reverse(copy=False), key=lambda n: natural_key(members[n][0])
    )
    return [app for node in order for app in members[node]]
