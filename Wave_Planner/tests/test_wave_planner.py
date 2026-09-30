"""Unit tests for Feature 2: the dependency-aware wave planner."""

from pathlib import Path

import networkx as nx
import pytest

from wave_planner import AppNode, parse_dependencies, plan_waves, load_csv
from wave_planner.clustering import detect_clusters
from wave_planner.graph import build_dependency_graph, natural_key, undirected_projection
from wave_planner.scheduler import migration_order

PORTFOLIO_CSV = Path(__file__).resolve().parents[2] / "data" / "processed" / "application_portfolio_1000.csv"


def app(app_id, *deps, **kw):
    return AppNode(id=app_id, dependencies=tuple(deps), **kw)


def wave_of(plan):
    return {a: w.number for w in plan.waves for a in w.apps}


# ---------------------------------------------------------------- parsing
@pytest.mark.parametrize("raw,expected", [
    ("0", ()), ("", ()), (None, ()), ("none", ()),
    ("APP1", ("APP1",)),
    ("APP1,APP2", ("APP1", "APP2")),
    (" APP1 ; APP2 |APP3", ("APP1", "APP2", "APP3")),
    (["a", "b"], ("a", "b")),
])
def test_parse_dependencies(raw, expected):
    assert parse_dependencies(raw) == expected


def test_natural_key_orders_numbers_numerically():
    assert sorted(["APP10", "APP2", "APP1"], key=natural_key) == ["APP1", "APP2", "APP10"]


# ------------------------------------------------------------------ graph
def test_graph_edges_point_from_dependent_to_dependency():
    graph, warnings = build_dependency_graph([app("A", "B"), app("B")])
    assert list(graph.edges) == [("A", "B")]
    assert warnings == []


def test_graph_drops_and_reports_bad_dependencies():
    graph, warnings = build_dependency_graph([app("A", "A", "B", "B", "ghost"), app("B")])
    assert list(graph.edges) == [("A", "B")]
    text = " ".join(warnings)
    assert "self-dependencies" in text and "duplicate" in text and "outside" in text


def test_graph_rejects_duplicate_ids():
    with pytest.raises(ValueError, match="Duplicate"):
        build_dependency_graph([app("A"), app("A")])


# ------------------------------------------------------------- clustering
def _two_cliques():
    apps = []
    for prefix in ("X", "Y"):
        ids = [f"{prefix}{i}" for i in range(6)]
        apps += [app(i, *[j for j in ids if j != i]) for i in ids]
    apps[0] = app("X0", *[f"X{i}" for i in range(1, 6)], "Y0")  # one weak bridge
    return apps


def test_louvain_separates_tight_groups():
    graph, _ = build_dependency_graph(_two_cliques())
    clusters = detect_clusters(undirected_projection(graph))
    assert sorted(map(sorted, clusters)) == [[f"X{i}" for i in range(6)], [f"Y{i}" for i in range(6)]]


def test_oversized_clusters_are_split_to_the_cap():
    ids = [f"N{i}" for i in range(30)]
    graph, _ = build_dependency_graph([app(i, *[j for j in ids if j != i]) for i in ids])
    clusters = detect_clusters(undirected_projection(graph), max_cluster_size=10)
    assert all(len(c) <= 10 for c in clusters)
    assert sorted(a for c in clusters for a in c) == sorted(ids)


# --------------------------------------------------------------- planning
def test_empty_portfolio():
    plan = plan_waves([])
    assert plan.waves == [] and plan.summary["wave_count"] == 0


def test_chain_migrates_dependencies_first():
    plan = plan_waves([app("A", "B"), app("B", "C"), app("C")], max_wave_size=1)
    assert [w.apps for w in plan.waves] == [["C"], ["B"], ["A"]]
    assert plan.summary["planner"]["unmet_dependencies"] == 0
    assert [w.depends_on_waves for w in plan.waves] == [[], [1], [2]]
    assert not any(w.cycle_break for w in plan.waves)


def test_every_app_lands_in_exactly_one_wave():
    plan = plan_waves(_two_cliques() + [app("Z1"), app("Z2", "Z1")], max_wave_size=8)
    placed = [a for w in plan.waves for a in w.apps]
    assert sorted(placed) == sorted({a.id for a in _two_cliques()} | {"Z1", "Z2"})
    assert len(placed) == len(set(placed))


def test_wave_capacity_is_respected():
    apps = [app(f"A{i}") for i in range(25)]
    plan = plan_waves(apps, max_wave_size=10)
    assert all(len(w.apps) <= 10 for w in plan.waves)
    assert len(plan.waves) == 3


def test_independent_apps_share_a_wave_lowest_risk_first():
    apps = [app("hi", criticality="High"), app("lo", criticality="Low"), app("mid", criticality="Medium")]
    plan = plan_waves(apps, max_wave_size=1)
    assert [w.apps[0] for w in plan.waves] == ["lo", "mid", "hi"]
    assert [w.risk_score for w in plan.waves] == sorted(w.risk_score for w in plan.waves)


def test_cycle_is_broken_and_reported():
    plan = plan_waves([app("A", "B"), app("B", "A")], max_wave_size=1)
    assert len(plan.waves) == 2
    assert plan.summary["planner"]["unmet_dependencies"] == 1
    assert plan.waves[0].cycle_break and plan.waves[0].unmet_dependencies == 1
    assert plan.waves[1].unmet_dependencies == 0
    assert plan.summary["largest_dependency_cycle"] == 2


def test_three_cycle_costs_exactly_one_unmet_dependency():
    # Any order of A->B->C->A leaves at least one back-edge; the greedy rule must find that minimum.
    plan = plan_waves([app("A", "B"), app("B", "C"), app("C", "A")], max_wave_size=1)
    assert plan.summary["planner"]["unmet_dependencies"] == 1
    assert sum(w.unmet_dependencies for w in plan.waves) == 1


def test_tightly_coupled_cluster_moves_in_one_wave():
    plan = plan_waves(_two_cliques(), max_wave_size=6)
    waves = wave_of(plan)
    assert len({waves[f"X{i}"] for i in range(6)}) == 1
    assert len({waves[f"Y{i}"] for i in range(6)}) == 1


def test_apps_inside_a_wave_are_listed_dependencies_first():
    graph, _ = build_dependency_graph([app("A", "B"), app("B", "C"), app("C"), app("D")])
    assert migration_order(graph, ["A", "B", "C", "D"]) == ["C", "B", "A", "D"]


def test_cycle_members_stay_contiguous_in_migration_order():
    graph, _ = build_dependency_graph([app("A", "B"), app("B", "A"), app("C", "A"), app("D")])
    order = migration_order(graph, ["A", "B", "C", "D"])
    assert order.index("C") > max(order.index("A"), order.index("B"))
    assert abs(order.index("A") - order.index("B")) == 1


def test_selected_subset_ignores_outside_dependencies():
    plan = plan_waves([app("A", "B"), app("C", "A")][:1])  # B is outside the set
    assert [a for w in plan.waves for a in w.apps] == ["A"]
    assert any("outside" in w for w in plan.warnings)


def test_plan_is_deterministic():
    apps = _two_cliques()
    assert plan_waves(apps).to_dict() == plan_waves(apps).to_dict()


def test_risk_uses_only_available_factors():
    plan = plan_waves([app("A", criticality="High")], max_wave_size=1)
    factors = plan.clusters[0].risk_factors
    assert set(factors) == {"criticality", "coupling", "size"}
    assert 0 <= plan.waves[0].risk_score <= 100


def test_unmet_dependencies_raise_wave_risk():
    calm = plan_waves([app("A", "B"), app("B")], max_wave_size=1).waves
    cyc = plan_waves([app("A", "B"), app("B", "A")], max_wave_size=1).waves
    assert cyc[0].risk_score > calm[0].risk_score


@pytest.mark.parametrize("kwargs", [{"max_wave_size": 0}, {"resolution": 0}])
def test_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        plan_waves([app("A")], **kwargs)


def test_summary_metrics_are_consistent():
    plan = plan_waves(_two_cliques(), max_wave_size=6)
    s = plan.summary
    assert s["application_count"] == 12 and s["wave_count"] == len(plan.waves)
    assert s["planner"]["unmet_dependencies"] <= s["planner"]["cross_wave_dependencies"] <= s["dependency_count"]


def test_acyclic_portfolio_without_clustering_has_zero_unmet_dependencies():
    import random
    rng = random.Random(3)
    tiers = [[f"T{t}_{i}" for i in range(n)] for t, n in enumerate([15, 20, 25, 20, 10])]
    apps = []
    for t, ids in enumerate(tiers):
        lower = [x for tier in tiers[:t] for x in tier]
        for i in ids:
            deps = tuple(rng.sample(lower, min(len(lower), rng.randint(0, 4)))) if lower else ()
            apps.append(app(i, *deps))
    plan = plan_waves(apps, max_cluster_size=1)
    assert plan.summary["largest_dependency_cycle"] == 1
    assert plan.summary["planner"]["unmet_dependencies"] == 0
    order = wave_of(plan)
    graph, _ = build_dependency_graph(apps)
    assert all(order[a] > order[b] or order[a] == order[b] for a, b in graph.edges)


# ------------------------------------------------------- real 1,000-app data
@pytest.mark.skipif(not PORTFOLIO_CSV.exists(), reason="portfolio CSV not present")
def test_full_portfolio_plan():
    apps = load_csv(PORTFOLIO_CSV)
    plan = plan_waves(apps)
    s = plan.summary
    assert s["application_count"] == 1000 and s["dependency_count"] == 2533
    placed = [a for w in plan.waves for a in w.apps]
    assert sorted(placed) == sorted(a.id for a in apps)
    assert all(len(w.apps) <= s["max_wave_size"] for w in plan.waves)
    # The planner must clearly beat a random assignment with identical wave sizes.
    assert s["improvement_vs_random_pct"]["cross_wave_dependencies"] > 30
    assert s["improvement_vs_random_pct"]["unmet_dependencies"] > 30
    assert set(s["risk_distribution"]) <= {"Low", "Medium", "High"}
