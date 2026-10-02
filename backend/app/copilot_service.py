from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException, status

from .models import CopilotResponse

logger = logging.getLogger(__name__)
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

APPLICATION_ID_PATTERN = re.compile(r"\b(APP\d+)\b", re.IGNORECASE)
SIX_R_STRATEGIES = {"Rehost", "Replatform", "Repurchase", "Refactor", "Retire", "Retain"}


class LiveDataUnavailable(Exception):
    pass


def _get_pipeline():
    from copilot.llm import generate_answer

    if os.getenv("COPILOT_RETRIEVAL_BACKEND", "numpy").strip().lower() == "numpy":
        from copilot.lambda_rag import search
    else:
        from copilot.rag import search

    return search, generate_answer


def _classify_live_intent(question: str) -> str | None:
    normalized = question.casefold()
    if re.search(r"\b(first|earliest)\b", normalized) and re.search(
        r"\b(?:applications?|app\d+|migrat\w*|run|start)\b", normalized
    ):
        return "migration_order"
    if re.search(r"\b(depend\w*|dependencies|dependency)\b", normalized):
        return "dependencies"
    if re.search(r"\b(recommendation|recommend|6r)\b", normalized) or (
        re.search(r"\bshould\b", normalized)
        and re.search(r"\buse\b", normalized)
        and re.search(r"\bmigrat\w*\b", normalized)
    ):
        return "recommendation"
    if re.search(r"\b(cost|risk|expense|pricing)\b", normalized):
        return "cost_risk"
    return None


def _extract_application_id(question: str) -> str | None:
    match = APPLICATION_ID_PATTERN.search(question)
    return match.group(1).upper() if match else None


def _request_core_api(method: str, path: str, payload: dict | None = None) -> dict | list:
    base_url = os.getenv("COPILOT_DATA_API_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        raise LiveDataUnavailable

    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{base_url}{path}",
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError:
        raise LiveDataUnavailable from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise LiveDataUnavailable from None

    if not isinstance(result, (dict, list)):
        raise LiveDataUnavailable
    return result


def _application_records() -> list[dict]:
    result = _request_core_api("GET", "/applications")
    if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
        raise LiveDataUnavailable
    return result


def _application_record(applications: list[dict], application_id: str) -> dict | None:
    requested_digits = application_id[3:].lstrip("0") or "0"
    normalized_id = f"APP{requested_digits.zfill(3)}"
    for result in applications:
        canonical_id = result.get("application_id") or result.get("id")
        if isinstance(canonical_id, str) and canonical_id.upper() in {application_id, normalized_id}:
            return result
    return None


def _canonical_application_id(application: dict) -> str:
    canonical_id = application.get("application_id") or application.get("id")
    if not isinstance(canonical_id, str) or not APPLICATION_ID_PATTERN.fullmatch(canonical_id):
        raise LiveDataUnavailable
    return canonical_id


def _live_response(question: str, answer: str, sources: list[str]) -> CopilotResponse:
    return CopilotResponse(question=question, answer=answer, sources=sources)


def _answer_live_question(
    question: str,
    intent: str,
    application_id: str | None,
    application: dict | None,
    applications: list[dict] | None,
) -> CopilotResponse:
    canonical_id = _canonical_application_id(application) if application is not None else None

    if intent == "migration_order":
        result = _request_core_api("POST", "/migration-waves", {"application_ids": None})
        waves = result.get("waves") if isinstance(result, dict) else None
        if not isinstance(waves, list):
            raise LiveDataUnavailable
        if not waves:
            return _live_response(question, "The current migration plan contains no applications.", ["/migration-waves"])

        first_wave = waves[0]
        ordered_apps = first_wave.get("applications") if isinstance(first_wave, dict) else None
        if not isinstance(ordered_apps, list) or not ordered_apps:
            raise LiveDataUnavailable
        wave_number = first_wave.get("wave", 1)
        listed_apps = ", ".join(str(item) for item in ordered_apps[:10])
        answer = f"According to the current dependency-aware plan, Wave {wave_number} runs first. Its first applications are: {listed_apps}."
        sources = ["/migration-waves"]
        if canonical_id:
            assigned_wave = next(
                (
                    wave.get("wave")
                    for wave in waves
                    if isinstance(wave, dict) and canonical_id in wave.get("applications", [])
                ),
                None,
            )
            if assigned_wave is not None:
                answer += f" {canonical_id} is assigned to Wave {assigned_wave}."
            sources.insert(0, "/applications")
        return _live_response(question, answer, sources)

    if not canonical_id or not application:
        raise LiveDataUnavailable

    application_source = "/applications"
    if intent == "recommendation":
        result = _request_core_api("POST", "/recommendation", {"application_id": canonical_id})
        recommendation = result.get("recommendation") if isinstance(result, dict) else None
        confidence = result.get("confidence") if isinstance(result, dict) else None
        if recommendation not in SIX_R_STRATEGIES or not isinstance(confidence, (int, float)):
            raise LiveDataUnavailable
        answer = f"The current 6R recommendation for {canonical_id} is {recommendation} (confidence {confidence:.0%})."
        return _live_response(question, answer, [application_source, "/recommendation"])

    if intent == "cost_risk":
        result = _request_core_api("POST", "/cost-risk", {"application_id": canonical_id})
        cost_range = result.get("cost_range") if isinstance(result, dict) else None
        monthly_cost = result.get("monthly_aws_cost") if isinstance(result, dict) else None
        risk_score = result.get("risk_score") if isinstance(result, dict) else None
        if (
            not isinstance(cost_range, dict)
            or not all(isinstance(value, (int, float)) for value in (monthly_cost, cost_range.get("lower"), cost_range.get("upper"), risk_score))
        ):
            raise LiveDataUnavailable
        answer = (
            f"The current estimate for {canonical_id} is ${monthly_cost:,.2f} per month, "
            f"with a range of ${cost_range['lower']:,.2f} to ${cost_range['upper']:,.2f} "
            f"and a risk score of {risk_score}/100."
        )
        return _live_response(question, answer, [application_source, "/cost-risk"])

    if intent == "dependencies":
        asks_dependents = bool(re.search(r"\b(depends on|dependents|dependent on)\b", question, re.IGNORECASE))
        if asks_dependents:
            if applications is None:
                raise LiveDataUnavailable
            dependents = [
                str(item.get("application_id") or item.get("id"))
                for item in applications
                if isinstance(item, dict)
                and canonical_id in (item.get("dependencies") or item.get("dependency_ids") or [])
            ]
            answer = (
                f"Applications that depend on {canonical_id}: {', '.join(dependents)}."
                if dependents
                else f"No applications in the current dataset list {canonical_id} as a dependency."
            )
            return _live_response(question, answer, ["/applications"])

        dependencies = application.get("dependencies") or application.get("dependency_ids") or []
        if not isinstance(dependencies, list):
            raise LiveDataUnavailable
        answer = (
            f"{canonical_id} lists these dependencies: {', '.join(str(item) for item in dependencies)}."
            if dependencies
            else f"{canonical_id} has no listed dependencies."
        )
        return _live_response(question, answer, [application_source])

    raise LiveDataUnavailable


def _answer_with_rag(question: str) -> CopilotResponse:
    search, generate_answer = _get_pipeline()
    retrieved_docs = search(question, top_k=3)
    if not retrieved_docs:
        raise ValueError("Copilot retrieval returned no migration documents.")
    answer = generate_answer(question, retrieved_docs)
    sources = list(
        dict.fromkeys(
            line.partition(":")[2].strip()
            for document in retrieved_docs
            for line in document["text"].splitlines()
            if line.startswith("SOURCE:") and line.partition(":")[2].strip()
        )
    )
    if not answer or not answer.strip():
        raise RuntimeError("Hugging Face returned an empty answer.")
    if not sources:
        sources = ["Migration knowledge base"]
    return CopilotResponse(question=question, answer=answer.strip(), sources=sources)


def answer_copilot(question: str) -> CopilotResponse:
    normalized = question.strip()
    intent = _classify_live_intent(normalized)
    application_id = _extract_application_id(normalized)

    if intent is None and application_id is None:
        return _answer_rag_with_http_errors(normalized)

    if intent in {"recommendation", "cost_risk", "dependencies"} and not application_id:
        return _live_response(
            normalized,
            "Please include an application ID, such as APP001, so I can look up current migration data.",
            [],
        )

    try:
        applications = _application_records() if application_id else None
        application = _application_record(applications, application_id) if applications is not None and application_id else None
        if application_id and application is None:
            return _live_response(
                normalized,
                f"I could not find {application_id} in the current application data.",
                ["/applications"],
            )
        if intent is None:
            canonical_id = _canonical_application_id(application)
            return _live_response(
                normalized,
                f"I verified {canonical_id} exists, but this question does not match a supported live-data lookup.",
                ["/applications"],
            )
        return _answer_live_question(normalized, intent, application_id, application, applications)
    except LiveDataUnavailable:
        logger.warning("Copilot live-data lookup is unavailable")
        return _live_response(
            normalized,
            "Live application data is currently unavailable, so I cannot provide a current migration value.",
            ["Core API (unavailable)"],
        )
    except Exception as exc:
        logger.warning("Copilot live-data lookup failed (%s)", type(exc).__name__)
        return _live_response(
            normalized,
            "Live application data is currently unavailable, so I cannot provide a current migration value.",
            ["Core API (unavailable)"],
        )


def _answer_rag_with_http_errors(question: str) -> CopilotResponse:
    try:
        return _answer_with_rag(question)
    except (ImportError, FileNotFoundError, ValueError) as exc:
        logger.exception("Copilot knowledge base is unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Copilot knowledge base is unavailable: {exc}",
        ) from exc
    except RuntimeError as exc:
        logger.warning("Copilot generation is unavailable (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Copilot generation unavailable. Verify HF_TOKEN and Hugging Face provider/model access.",
        ) from exc
    except Exception as exc:
        logger.error("Copilot inference request failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Copilot inference failed. Verify HF_TOKEN and Hugging Face provider/model access.",
        ) from exc
