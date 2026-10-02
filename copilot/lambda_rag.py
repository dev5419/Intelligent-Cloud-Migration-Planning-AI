from functools import lru_cache
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from huggingface_hub import InferenceClient


BASE_DIR = Path(__file__).parent
VECTORSTORE_DIR = Path(os.getenv("COPILOT_VECTORSTORE_DIR", str(BASE_DIR / "vectorstore")))
MODEL_NAME = os.getenv("COPILOT_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)


def load_chunks() -> list[str]:
    chunks_file = VECTORSTORE_DIR / "chunks.txt"
    return [
        chunk.strip()
        for chunk in chunks_file.read_text(encoding="utf-8").split("---CHUNK---")
        if chunk.strip()
    ]


@lru_cache(maxsize=1)
def _load_resources() -> tuple[np.ndarray, list[str]]:
    vectors = np.load(VECTORSTORE_DIR / "migration_vectors.npy", allow_pickle=False)
    chunks = load_chunks()
    if vectors.ndim != 2 or vectors.dtype != np.float32:
        raise ValueError("Copilot document vectors must be a two-dimensional float32 array.")
    if vectors.shape[0] == 0 or not chunks:
        raise ValueError("Copilot knowledge base is empty.")
    if vectors.shape[0] != len(chunks):
        raise ValueError("Copilot vectors and document chunks are out of sync.")
    return vectors, chunks


def _embed_question(question: str) -> np.ndarray:
    from copilot.llm import _get_hf_token

    token = _get_hf_token()

    client = InferenceClient(
        model=MODEL_NAME,
        provider="hf-inference",
        token=token,
    )

    embedding = np.asarray(
        client.feature_extraction(question),
        dtype=np.float32,
    )

    if embedding.ndim == 2 and embedding.shape[0] == 1:
        embedding = embedding[0]

    if embedding.ndim != 1:
        raise ValueError("Hugging Face returned an invalid query embedding shape.")

    return embedding


def search(question: str, top_k: int = 3) -> list[dict[str, str | float]]:
    vectors, chunks = _load_resources()
    query_vector = _embed_question(question)
    if query_vector.shape[0] != vectors.shape[1]:
        raise ValueError("Query embedding and Copilot document vectors have different dimensions.")

    squared_distances = np.sum((vectors - query_vector) ** 2, axis=1, dtype=np.float32)
    result_count = max(0, min(int(top_k), len(chunks)))
    indices = np.argsort(squared_distances, kind="stable")[:result_count]
    return [
        {"distance": float(squared_distances[index]), "text": chunks[index]}
        for index in indices
    ]