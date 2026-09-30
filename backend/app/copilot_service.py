from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import HTTPException, status

from .models import CopilotResponse

logger = logging.getLogger(__name__)
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def _get_pipeline():
    from copilot.llm import generate_answer
    from copilot.rag import search

    return search, generate_answer


def answer_copilot(question: str) -> CopilotResponse:
    normalized = question.strip()
    try:
        search, generate_answer = _get_pipeline()
        retrieved_docs = search(normalized, top_k=3)
        if not retrieved_docs:
            raise ValueError("Copilot retrieval returned no migration documents.")
        answer = generate_answer(normalized, retrieved_docs)
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

    if not sources:
        sources = ["Migration knowledge base"]
    return CopilotResponse(
        question=normalized,
        answer=answer.strip(),
        sources=sources,
    )
