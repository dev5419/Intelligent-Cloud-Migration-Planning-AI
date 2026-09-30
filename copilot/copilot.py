from pathlib import Path
import os

import faiss
from sentence_transformers import SentenceTransformer
from huggingface_hub import InferenceClient
from dotenv import load_dotenv


# =============================
# CONFIGURATION
# =============================

BASE_DIR = Path(__file__).parent
VECTORSTORE_DIR = BASE_DIR / "vectorstore"

MODEL_NAME = "all-MiniLM-L6-v2"
LLM_MODEL = "meta-llama/Llama-3.1-8B-Instruct"


# =============================
# LOAD ENVIRONMENT
# =============================

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    raise ValueError(
        "HF_TOKEN not found. Set your Hugging Face token first."
    )


# =============================
# LOAD EMBEDDING MODEL
# =============================

print("Loading embedding model...")

embedding_model = SentenceTransformer(MODEL_NAME)


# =============================
# LOAD FAISS INDEX
# =============================

print("Loading FAISS knowledge base...")

index = faiss.read_index(
    str(VECTORSTORE_DIR / "migration.index")
)


# =============================
# LOAD DOCUMENT CHUNKS
# =============================

def load_chunks():

    chunks_file = VECTORSTORE_DIR / "chunks.txt"

    text = chunks_file.read_text(
        encoding="utf-8"
    )

    return [
        chunk.strip()
        for chunk in text.split("---CHUNK---")
        if chunk.strip()
    ]


chunks = load_chunks()


# =============================
# HUGGING FACE CLIENT
# =============================

client = InferenceClient(
    provider="novita",
    api_key=HF_TOKEN
)


# =============================
# RETRIEVAL
# =============================

def retrieve(question, top_k=3):

    question_embedding = embedding_model.encode(
        [question],
        convert_to_numpy=True
    )

    distances, indices = index.search(
        question_embedding,
        min(top_k, len(chunks))
    )

    results = []

    for distance, index_id in zip(
        distances[0],
        indices[0]
    ):

        if index_id < len(chunks):

            results.append({
                "distance": float(distance),
                "text": chunks[index_id]
            })

    return results


# =============================
# LLM GENERATION
# =============================

def generate_answer(question, retrieved_docs):

    context = "\n\n".join(
        [
            f"DOCUMENT CHUNK {i + 1}:\n{doc['text']}"
            for i, doc in enumerate(retrieved_docs)
        ]
    )

    messages = [

        {
            "role": "system",
            "content": """
You are an AI Copilot for cloud migration planning.

Answer the user's question using the provided migration knowledge.

Rules:
- Use the provided context as the primary source.
- Do not invent facts that are not supported by the context.
- If the context does not contain enough information, clearly say so.
- Give a concise and useful answer.
- Explain migration concepts in simple technical language.
"""
        },

        {
            "role": "user",
            "content": f"""
Retrieved migration knowledge:

{context}

User question:

{question}

Answer:
"""
        }

    ]

    response = client.chat_completion(
        messages=messages,
        model=LLM_MODEL,
        max_tokens=400,
        temperature=0.2
    )

    return response.choices[0].message.content


# =============================
# COMPLETE RAG PIPELINE
# =============================

def answer_question(question):

    retrieved_docs = retrieve(
        question,
        top_k=3
    )

    answer = generate_answer(
        question,
        retrieved_docs
    )

    return answer, retrieved_docs


# =============================
# MAIN
# =============================

if __name__ == "__main__":

    question = input(
        "Ask a migration question: "
    )

    print("\nSearching migration knowledge...")

    answer, sources = answer_question(
        question
    )

    print("\n================================")
    print("GENAI COPILOT ANSWER")
    print("================================\n")

    print(answer)

    print("\n================================")
    print("RETRIEVED SOURCES")
    print("================================\n")

    for i, source in enumerate(
        sources,
        1
    ):

        print(
            f"Source {i} "
            f"(distance: {source['distance']:.4f})"
        )

        print(
            source["text"][:500]
        )

        print()