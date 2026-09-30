from __future__ import annotations

import sys
from pathlib import Path

from fastapi import HTTPException, status

from .data_loader import get_applications
from .models import MigrationWavesResponse

WAVE_PLANNER_DIR = Path(__file__).resolve().parents[2] / "Wave_Planner"
if str(WAVE_PLANNER_DIR) not in sys.path:
    sys.path.insert(0, str(WAVE_PLANNER_DIR))

from wave_planner import from_objects, plan_waves


def get_migration_waves(application_ids: list[str] | None) -> MigrationWavesResponse:
    try:
        applications = get_applications()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Application dataset is missing or unreadable.",
        ) from exc

    if application_ids is None:
        selected_ids = {application.id for application in applications}
    else:
        selected_ids = {str(item).strip() for item in application_ids if str(item).strip()}

    valid_ids = {application.id for application in applications}
    unknown_ids = sorted(selected_ids - valid_ids)
    if unknown_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Applications not found: {unknown_ids}",
        )

    selected_applications = [application for application in applications if application.id in selected_ids]
    try:
        plan = plan_waves(from_objects(selected_applications))
        response = plan.to_dict()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Migration wave planning failed: {exc}",
        ) from exc

    return MigrationWavesResponse(**response)
