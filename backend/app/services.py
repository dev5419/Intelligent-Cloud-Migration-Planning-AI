from __future__ import annotations

from .data_loader import get_application_by_id, get_applications as load_applications
from .models import (
    Application,
    CopilotResponse,
    CostRiskResponse,
    MigrationWavesResponse,
    RecommendationResponse,
)
from .copilot_service import answer_copilot as _answer_copilot
from .cost_service import get_cost_risk as _get_cost_risk
from .recommendation_service import get_recommendation as _get_recommendation
from .wave_service import get_migration_waves as _get_migration_waves


def get_applications() -> list[Application]:
    return load_applications()


def get_application(application_id: str) -> Application:
    return get_application_by_id(application_id)


def get_recommendation(application_id: str) -> RecommendationResponse:
    return _get_recommendation(application_id)


def get_migration_waves(application_ids: list[str] | None) -> MigrationWavesResponse:
    return _get_migration_waves(application_ids)


def answer_copilot(question: str) -> CopilotResponse:
    return _answer_copilot(question)


def get_cost_risk(application_id: str) -> CostRiskResponse:
    return _get_cost_risk(application_id)
