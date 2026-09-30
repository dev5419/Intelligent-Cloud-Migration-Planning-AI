"""Command line interface.

    python -m wave_planner                       # plan the 1,000-app portfolio
    python -m wave_planner --csv my_apps.csv --max-wave-size 50
    python -m wave_planner --json sample_apps.json --out plan.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .loaders import load_csv, load_json
from .planner import plan_waves

DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data" / "processed" / "application_portfolio_1000.csv"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m wave_planner", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group()
    src.add_argument("--csv", type=Path, help=f"portfolio CSV (default: {DEFAULT_CSV.name})")
    src.add_argument("--json", type=Path, help="JSON list of apps, or {'applications': [...]}")
    p.add_argument("--max-wave-size", type=int, default=None, help="max apps per wave (default: auto, <=100)")
    p.add_argument("--max-cluster-size", type=int, default=None, help="max apps per cluster (default: wave size; 1 = no clustering)")
    p.add_argument("--resolution", type=float, default=1.0, help="Louvain resolution (higher = smaller clusters)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, help="write the full plan as JSON to this file")
    p.add_argument("--print-json", action="store_true", help="print the full plan JSON instead of the table")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.json:
        apps = load_json(args.json)
    else:
        csv_path = args.csv or DEFAULT_CSV
        if not csv_path.is_file():
            print(f"error: portfolio CSV not found at {csv_path}\n"
                  "Pass --csv <file> or --json <file>.", file=sys.stderr)
            return 2
        apps = load_csv(csv_path)

    plan = plan_waves(apps, max_wave_size=args.max_wave_size, max_cluster_size=args.max_cluster_size,
                      resolution=args.resolution, seed=args.seed)
    data = plan.to_dict()
    if args.out:
        args.out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if args.print_json:
        print(json.dumps(data, indent=2))
        return 0

    s = plan.summary
    print(f"{s['application_count']} apps, {s['dependency_count']} dependencies -> "
          f"{s['cluster_count']} clusters -> {s['wave_count']} waves "
          f"(max {s['max_wave_size']} apps/wave, largest dependency cycle: {s.get('largest_dependency_cycle', 0)})")
    print(f"{'Wave':>4}  {'Apps':>5}  {'Clusters':>8}  {'Risk':<7} {'Score':>6}  {'Unmet deps':>10}  Depends on")
    for w in plan.waves:
        deps = ",".join(map(str, w.depends_on_waves)) or "-"
        flag = "  (cycle broken)" if w.cycle_break else ""
        print(f"{w.number:>4}  {len(w.apps):>5}  {len(w.clusters):>8}  {w.risk:<7} {w.risk_score:>6.1f}  "
              f"{w.unmet_dependencies:>10}  {deps}{flag}")
    if "planner" in s:
        base, imp = s["random_baseline"], s["improvement_vs_random_pct"]
        print(f"\nCross-wave dependencies: {s['planner']['cross_wave_dependencies']} "
              f"(random: {base['cross_wave_dependencies']}, -{imp['cross_wave_dependencies']}%)")
        print(f"Unmet dependencies:      {s['planner']['unmet_dependencies']} "
              f"(random: {base['unmet_dependencies']}, -{imp['unmet_dependencies']}%)")
    for warning in plan.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if args.out:
        print(f"\nFull plan written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
