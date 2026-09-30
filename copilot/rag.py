from pathlib import Path
from functools import lru_cache

import faiss
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).parent
VECTORSTORE_DIR = BASE_DIR / "vectorstore"

MODEL_NAME = "all-MiniLM-L6-v2"


def load_chunks():
    chunks_file = VECTORSTORE_DIR / "chunks.txt"
    text = chunks_file.read_text(encoding="utf-8")

    return [
        chunk.strip()
        for chunk in text.split("---CHUNK---")
        if chunk.strip()
    ]


@lru_cache(maxsize=1)
def _load_resources():
    index = faiss.read_index(
        str(VECTORSTORE_DIR / "migration.index")
    )

    chunks = load_chunks()
    model = SentenceTransformer(MODEL_NAME)
    if index.ntotal == 0 or not chunks:
        raise ValueError("Copilot knowledge base is empty.")
    if index.ntotal != len(chunks):
        raise ValueError("Copilot FAISS index and document chunks are out of sync.")
    return index, chunks, model


def search(question, top_k=3):
    index, chunks, model = _load_resources()

    question_embedding = model.encode(
        [question],
        convert_to_numpy=True
    )

    distances, indices = index.search(
        question_embedding,
        min(top_k, len(chunks))
    )

    results = []

    for distance, index_id in zip(distances[0], indices[0]):
        if index_id < len(chunks):
            results.append({
                "distance": float(distance),
                "text": chunks[index_id]
            })

    return results


if __name__ == "__main__":
    question = input("Ask a migration question: ")

    results = search(question)

    print("\n===== RETRIEVED KNOWLEDGE =====\n")

    for i, result in enumerate(results, 1):
        print(f"--- Result {i} ---")
        print(result["text"])
        print(f"\nDistance: {result['distance']}\n")