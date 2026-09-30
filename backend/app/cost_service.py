from __future__ import annotations

import sys
from pathlib import Path

from fastapi import HTTPException, status

from .data_loader import get_application_by_id
from .models import CostRiskResponse

COST_MODULE_DIR = Path(__file__).resolve().parents[2] / "Cost and Risk"
if str(COST_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(COST_MODULE_DIR))

try:
    from cost import analyze_application
except ModuleNotFoundError as exc:  # pragma: no cover - handled at runtime
    analyze_application = None
    import_error = exc
else:
    import_error = None


def _build_cost_input(application) -> dict[str, object]:
    cpu_usage = float(application.cpu_usage or 0.0)
    memory_usage = float(application.memory_usage or 0.0)
    age_years = int(application.age_years or 0)
    dependency_count = int(application.dependency_count or 0)
    compliance_flag = int(application.compliance_flag or 0)

    if cpu_usage >= 0.85 and memory_usage >= 0.75:
        recommended_instance = "m5.2xlarge"
    elif cpu_usage >= 0.6 or memory_usage >= 0.6:
        recommended_instance = "m5.large"
    elif cpu_usage >= 0.35 or memory_usage >= 0.35:
        recommended_instance = "t3.large"
    else:
        recommended_instance = "t3.medium"

    storage_gb = max(20.0, (memory_usage * 200.0) + (dependency_count * 18.0) + (age_years * 2.5))

    criticality = str(application.criticality or "Medium").lower()
    if criticality in {"mission-critical", "critical"}:
        normalized_criticality = "mission-critical"
    elif criticality == "business-critical":
        normalized_criticality = "business-critical"
    else:
        normalized_criticality = "low" if criticality == "low" else "business-critical"

    return {
        "app_id": application.id,
        "app_name": application.name,
        "recommended_instance": recommended_instance,
        "storage_gb": round(storage_gb, 2),
        "app_age_years": age_years,
        "dependency_count": dependency_count,
        "has_compliance_data": bool(compliance_flag == 1),
        "compliance_frameworks": ["PCI"] if compliance_flag == 1 else [],
        "is_deprecated_tech": age_years >= 10 or "legacy" in (application.technology or "").lower(),
        "tech_stack": application.technology or "Unknown",
        "criticality": normalized_criticality,
    }


def get_cost_risk(application_id: str) -> CostRiskResponse:
    try:
        application = get_application_by_id(application_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application not found: {application_id}",
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Application dataset is missing or unreadable.",
        ) from exc

    if analyze_application is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cost-risk implementation could not be imported: {import_error}",
        )

    try:
        app_data = _build_cost_input(application)
        result = analyze_application(app_data, iterations=2000)
        cost_block = result["cost_simulation_monthly"]
        risk_block = result["risk_assessment"]
    except Exception as exc:  # pragma: no cover - surfaced via HTTP error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cost-risk simulation failed: {exc}",
        ) from exc

    return CostRiskResponse(
        app_id=application.id,
        application_id=application.id,
        monthly_aws_cost=float(cost_block["expected_mean_usd"]),
        cost_range={
            "lower": float(cost_block["low_5th_percentile_usd"]),
            "upper": float(cost_block["high_95th_percentile_usd"]),
        },
        risk_score=float(risk_block["risk_score"]),
    )
