import csv
import re
from pathlib import Path

from .config import settings
from .models import Application


def normalize_application_id(raw_value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(raw_value or "")).upper()
    match = re.search(r"(\d+)", cleaned)
    if not match:
        return cleaned
    number = match.group(1).zfill(3)
    prefix = cleaned[: match.start(1)] if cleaned[: match.start(1)] else "APP"
    return f"{prefix}{number}"


def _coerce_dependency_list(value: str | None) -> list[str]:
    if value in (None, "", "0", "[]"):
        return []
    if isinstance(value, str):
        raw_items = value.replace(";", ",").split(",")
        normalized = [item.strip() for item in raw_items if item.strip()]
        return [normalize_application_id(item) for item in normalized]
    return []


def _load_dataset() -> list[Application]:
    dataset_path = Path(settings.dataset_path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found at {dataset_path}")

    with dataset_path.open("r", encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        applications: list[Application] = []
        for row in reader:
            app_id = normalize_application_id(row.get("application_id") or row.get("id") or "")
            if not app_id:
                continue
            dependencies = _coerce_dependency_list(row.get("dependency_ids") or row.get("dependencies") or "")
            criticality = str(row.get("criticality") or "Medium").strip().title()
            if criticality not in {"Low", "Medium", "High"}:
                criticality = "Medium"
            app = Application(
                id=app_id,
                application_id=app_id,
                name=(row.get("application_name") or row.get("name") or "Unknown application").strip(),
                application_name=(row.get("application_name") or row.get("name") or "Unknown application").strip(),
                owner=row.get("owner") or "Unknown",
                technology=row.get("technology") or "Unknown",
                criticality=criticality,
                dependencies=dependencies,
                dependency_ids=dependencies,
                dependency_count=int(row.get("dependency_count") or len(dependencies) or 0),
                cpu_usage=float(row.get("cpu_usage") or 0),
                memory_usage=float(row.get("memory_usage") or 0),
                age_years=int(row.get("age_years") or 0),
                compliance_flag=int(row.get("compliance_flag") or 0),
            )
            applications.append(app)

    if not applications:
        raise ValueError("Application dataset is empty")

    return applications


def get_applications() -> list[Application]:
    return _load_dataset()


def get_application_by_id(application_id: str) -> Application:
    normalized_id = normalize_application_id(application_id)
    for application in _load_dataset():
        if application.id == normalized_id or application.application_id == normalized_id:
            return application
    raise KeyError(normalized_id)


def get_application_ids() -> set[str]:
    return {app.id for app in _load_dataset()}
