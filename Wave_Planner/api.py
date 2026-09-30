"""Optional standalone API for the wave planner (does not touch the main backend).

    uvicorn api:app --reload --port 8001

Same request/response shape as the ``POST /migration-waves`` contract, so the
coordinator can later copy ``plan_waves`` into ``backend/app/services.py``.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from wave_planner import AppNode, load_csv, load_json, plan_waves

ROOT = Path(__file__).resolve().parent
PORTFOLIO_CSV = ROOT.parent / "data" / "processed" / "application_portfolio_1000.csv"
SAMPLE_JSON = ROOT / "sample_apps.json"

app = FastAPI(title="Migration Wave Planner", version="1.0.0")


class WavesRequest(BaseModel):
    application_ids: list[str] | None = None
    source: Literal["portfolio", "sample"] = "portfolio"
    max_wave_size: int | None = Field(default=None, ge=1, le=5000)
    max_cluster_size: int | None = Field(default=None, ge=1, le=5000)
    resolution: float = Field(default=1.0, gt=0, le=10)


class WaveCluster(BaseModel):
    cluster_id: str
    applications: list[str]
    size: int
    internal_dependencies: int
    external_dependencies: int
    risk_score: float
    risk_factors: dict[str, float]


class Wave(BaseModel):
    wave: int = Field(ge=1)
    applications: list[str]  # in migration order (dependencies first)
    risk: Literal["Low", "Medium", "High"]
    risk_score: float
    application_count: int
    unmet_dependencies: int
    depends_on_waves: list[int]
    cycle_break: bool
    clusters: list[WaveCluster]


class WavesResponse(BaseModel):
    waves: list[Wave]
    summary: dict[str, Any]
    warnings: list[str]


@lru_cache(maxsize=2)
def _load(source: str) -> tuple[AppNode, ...]:
    if source == "sample":
        return tuple(load_json(SAMPLE_JSON))
    path = Path(os.environ.get("PORTFOLIO_CSV", PORTFOLIO_CSV))
    if not path.is_file():
        raise HTTPException(503, f"Portfolio dataset not found at {path}")
    return tuple(load_csv(path))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/migration-waves", response_model=WavesResponse)
def migration_waves(request: WavesRequest) -> WavesResponse:
    apps = list(_load(request.source))
    known = {a.id for a in apps}
    selected = set(request.application_ids or known)
    if selected - known:
        raise HTTPException(404, f"Applications not found: {sorted(selected - known)}")
    plan = plan_waves(
        [a for a in apps if a.id in selected],
        max_wave_size=request.max_wave_size,
        max_cluster_size=request.max_cluster_size,
        resolution=request.resolution,
    )
    return WavesResponse(**plan.to_dict())
