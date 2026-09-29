# Feature 2: Dependency-Aware Migration Wave Planner

Groups tightly coupled applications and orders migration waves so that
dependencies move before the applications that rely on them.

Self-contained module: nothing outside this folder needs to change. It reads the team's `data/processed/application_portfolio_1000.csv` (one level up).

## Pipeline

```
application portfolio (CSV / API)
        |  graph.py        NetworkX DiGraph, edge  A -> B  =  "A depends on B"
        v
dependency graph
        |  clustering.py   Louvain community detection (undirected, mutual deps weigh 2)
        v
clusters (tightly coupled apps that migrate together)
        |  risk.py         explainable 0-100 risk score per cluster
        |  scheduler.py    greedy ordering, packing into waves of <= max_wave_size apps
        v
waves  ->  metrics.py: compare against a random-assignment baseline
```

1. **Graph.** Self-dependencies, duplicates and references to apps outside the
   selected set are dropped and reported in `warnings` (real exports are messy).
2. **Clusters.** `networkx.community.louvain_communities` (seeded, so runs are
   reproducible). Clusters larger than `max_cluster_size` are re-split with a
   higher resolution, with a deterministic BFS chunking fallback.
3. **Risk.** Weighted, explainable score. Weights: criticality 30, compliance
   20, coupling (cross-cluster dependencies per app) 20, size 10, age 10,
   utilisation 10. Factors missing from the input (the mock API data has no
   CPU/age/compliance) are dropped and the rest are re-normalised.
   `risk_factors` in the response shows the points each factor contributed.
   Labels: Low < 45 <= Medium < 65 <= High (constants in `risk.py`).
4. **Ordering (greedy heuristic, no GNN / GA needed).**
   * A cluster is *ready* when everything it depends on is in an **earlier** wave.
   * Ready clusters are taken lowest-risk / least-coupled first until the wave is
     full (`max_wave_size`).
   * If nothing is ready, a **dependency cycle** blocks progress. It is broken with
     the Eades-Lin-Smyth rule: pick the cluster minimising
     `unmet_out - pending_in` (dependencies it strands minus dependents it
     unblocks), then keep filling the wave while that cost stays <= 0.
   * Inside each wave the applications are listed in migration order
     (dependencies first; members of a cycle stay adjacent).
5. **Wave risk** = app-weighted mean of its cluster scores, plus up to 20 points
   depending on the share of the wave's outgoing dependencies that are unmet.

## Metrics reported in `summary`

| Metric | Meaning |
|---|---|
| `cross_wave_dependencies` | dependency edges whose two ends migrate in different waves (need temporary hybrid connectivity) |
| `unmet_dependencies` | subset where the dependency migrates in a **later** wave than its dependent |
| `random_baseline` | mean of 30 random app-to-wave assignments with identical wave sizes |
| `improvement_vs_random_pct` | reduction of the two metrics vs that baseline |
| `intra_cluster_dependency_pct` | share of dependencies kept inside a cluster |
| `largest_dependency_cycle` | size of the biggest strongly connected component |

## Results on the 1,000-app synthetic portfolio (2,533 dependencies)

| Setting | Clusters | Waves | Cross-wave deps (random) | Unmet deps (random) |
|---|---|---|---|---|
| default (auto wave size = 100) | 37 | 12 | 1,232 (2,326), **-47%** | 530 (1,164), **-55%** |
| `max_wave_size=150` | | 8 | 1,155, **-48%** | 510, **-54%** |
| `max_wave_size=50` | | 21 | 1,437, **-41%** | 557, **-54%** |

Runtime is about 0.15 s for 1,000 apps and about 2 s for 5,000.

### Read this before quoting the numbers

* **The synthetic portfolio is unusually cyclic.** Dependencies were generated
  at random, so 712 of the 1,000 apps sit in one dependency cycle. At least one
  dependency per cycle *must* be unmet, so a large share of the 530 unmet
  edges is unavoidable, not a planner defect. Real portfolios are usually more
  layered.
* **Cohesion vs. ordering is a trade-off.** On a layered, acyclic 500-app test
  portfolio, default clustering still leaves 115 unmet dependencies (random:
  358) because a cluster can span tiers and clusters then depend on each
  other. Smaller clusters give the orderer more freedom:

  | `max_cluster_size` | unmet | cross-wave |
  |---|---|---|
  | default | 115 | 285 |
  | 10 | 84 | 378 |
  | 1 (no clustering) | **0** | 808 |

  Choose by what hurts more: co-migrating coupled apps, or running an app before
  its dependency. `max_cluster_size=1` is guaranteed to give zero unmet
  dependencies on acyclic input (covered by a test).
* The greedy ordering is a heuristic, not an optimum. It is a defensible
  baseline for the paper; OR-Tools could replace `schedule_waves` later without
  changing the API.
* Risk weights and Low/Medium/High thresholds are hand-set and were calibrated
  on the synthetic data, not learned from real migrations.

## Usage

Run everything from inside this folder.

```bash
pip install -r requirements-dev.txt
python -m pytest                                   # 42 tests
```

### Command line

```bash
python -m wave_planner                              # 1,000-app portfolio
python -m wave_planner --json sample_apps.json      # the 4 demo apps
python -m wave_planner --csv my_apps.csv --max-wave-size 50 --out plan.json
python -m wave_planner --max-cluster-size 1         # pure dependency order
```

### Python

```python
from wave_planner import load_csv, plan_waves

plan = plan_waves(load_csv("../data/processed/application_portfolio_1000.csv"))
plan.summary["improvement_vs_random_pct"]
[(w.number, w.risk, len(w.apps)) for w in plan.waves]
plan.to_dict()          # JSON-ready
```

Input CSV/JSON accepts the repo's field names (`application_id`/`id`,
`dependency_ids`/`dependencies`, `criticality`, `compliance_flag`, `age_years`,
`cpu_usage`, `memory_usage`); only the ID is required. `0` or an empty value
means "no dependencies".

### Standalone API (optional)

```bash
uvicorn api:app --reload --port 8001
curl -X POST localhost:8001/migration-waves -H "Content-Type: application/json" -d '{"source": "portfolio"}'
```

Request fields (all optional): `source` (`"portfolio"` default, or `"sample"`),
`application_ids`, `max_wave_size`, `max_cluster_size`, `resolution`. Unknown IDs
return 404, a missing dataset 503. Response: `waves[]` (`wave`, `applications`
in migration order, `risk`, `risk_score`, `unmet_dependencies`,
`depends_on_waves`, `cycle_break`, `clusters[]`), `summary`, `warnings`.

### Plugging into the main backend later (for the coordinator)

Copy the `wave_planner/` package into `backend/app/` and replace the body of
`get_migration_waves` in `services.py` with `plan_waves(...)`, then return
`MigrationWavesResponse(**plan.to_dict())`. The extra response fields are all
additive, so the existing `wave` / `applications` / `risk` contract is unchanged.
