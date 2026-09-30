import os
from pathlib import Path

from dotenv import load_dotenv


def generate_answer(question, retrieved_docs):
    env_file = Path(__file__).resolve().with_name(".env")
    load_dotenv(dotenv_path=env_file, override=False)
    token = os.getenv("HF_TOKEN")
    if not token or token.strip() == "YOUR_HUGGING_FACE_TOKEN":
        raise RuntimeError("HF_TOKEN is not configured for Hugging Face inference.")
    token = token.strip()

    from huggingface_hub import InferenceClient

    context = "\n\n".join(
        f"DOCUMENT CHUNK {index + 1}:\n{document['text']}"
        for index, document in enumerate(retrieved_docs)
    )
    client = InferenceClient(provider="novita", api_key=token)
    response = client.chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI Copilot for cloud migration planning. Answer using the "
                    "provided migration knowledge, do not invent unsupported facts, and say "
                    "when the context is insufficient."
                ),
            },
            {
                "role": "user",
                "content": f"Retrieved migration knowledge:\n\n{context}\n\nQuestion:\n{question}",
            },
        ],
        model="meta-llama/Llama-3.1-8B-Instruct",
        max_tokens=400,
        temperature=0.2,
    )
    return response.choices[0].message.content