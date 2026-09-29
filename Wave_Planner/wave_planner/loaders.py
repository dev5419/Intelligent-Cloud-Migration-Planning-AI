"""Turn CSV / JSON / backend objects into ``AppNode`` lists."""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .types import AppNode

_SPLIT = re.compile(r"[,;|\s]+")
_EMPTY = {"", "0", "none", "null", "nan", "[]"}


def parse_dependencies(raw: Any) -> tuple[str, ...]:
    """Accept ``"APP1,APP2"``, ``"0"``/``""`` (none), or a list of IDs."""
    if raw is None:
        return ()
    if isinstance(raw, (list, tuple, set)):
        items = [str(x).strip() for x in raw]
    else:
        text = str(raw).strip()
        if text.lower() in _EMPTY:
            return ()
        items = _SPLIT.split(text)
    return tuple(i for i in items if i and i.lower() not in _EMPTY)


def _criticality(raw: Any) -> str | None:
    if raw is None or str(raw).strip() == "":
        return None
    value = str(raw).strip().capitalize()
    return value if value in {"Low", "Medium", "High"} else None


def _float(raw: Any) -> float | None:
    try:
        return None if raw is None or str(raw).strip() == "" else float(raw)
    except ValueError:
        return None


def _bool(raw: Any) -> bool | None:
    if raw is None or str(raw).strip() == "":
        return None
    return str(raw).strip().lower() in {"1", "true", "yes", "y"}


def _first(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def app_from_mapping(row: Mapping[str, Any]) -> AppNode:
    """Build an ``AppNode`` from a dict using the repo's field-name variants."""
    app_id = _first(row, "id", "application_id", "app_id")
    if app_id is None or str(app_id).strip() == "":
        raise ValueError(f"Row without an application id: {dict(row)}")
    return AppNode(
        id=str(app_id).strip(),
        name=str(_first(row, "name", "application_name", "app_name") or ""),
        dependencies=parse_dependencies(_first(row, "dependencies", "dependency_ids")),
        criticality=_criticality(row.get("criticality")),
        compliance=_bool(_first(row, "compliance_flag", "compliance")),
        age_years=_float(_first(row, "age_years", "app_age_years")),
        cpu_usage=_float(row.get("cpu_usage")),
        memory_usage=_float(row.get("memory_usage")),
    )


def load_csv(path: str | Path) -> list[AppNode]:
    with open(path, newline="", encoding="utf-8") as handle:
        return [app_from_mapping(row) for row in csv.DictReader(handle)]


def load_json(path: str | Path) -> list[AppNode]:
    """A list of app objects, or ``{"applications": [...]}``."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    rows = data["applications"] if isinstance(data, dict) else data
    return [app_from_mapping(row) for row in rows]


def from_objects(objects: Iterable[Any]) -> list[AppNode]:
    """Adapt Pydantic models (e.g. the backend ``Application``) or any object with the same attributes."""
    apps = []
    for obj in objects:
        row = obj.model_dump() if hasattr(obj, "model_dump") else dict(vars(obj))
        apps.append(app_from_mapping(row))
    return apps
