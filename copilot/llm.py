import os
from pathlib import Path

from dotenv import load_dotenv


_HF_TOKEN = None


def _get_hf_token():
    global _HF_TOKEN

    if _HF_TOKEN:
        return _HF_TOKEN

    # Local development: use copilot/.env
    env_file = Path(__file__).resolve().with_name(".env")
    load_dotenv(dotenv_path=env_file, override=False)

    local_token = os.getenv("HF_TOKEN")

    if local_token and local_token.strip() != "YOUR_HUGGING_FACE_TOKEN":
        _HF_TOKEN = local_token.strip()
        return _HF_TOKEN

    # AWS Lambda: retrieve token from Secrets Manager
    secret_name = os.getenv(
        "HF_SECRET_NAME",
        "migration-planning/huggingface-token"
    )

    try:
        import boto3

        secrets_client = boto3.client(
            "secretsmanager",
            region_name=os.getenv("AWS_REGION", "ap-south-1"),
        )

        response = secrets_client.get_secret_value(
            SecretId=secret_name
        )

        token = response.get("SecretString")

        if not token:
            raise RuntimeError("Hugging Face secret has no SecretString value.")

        _HF_TOKEN = token.strip()
        return _HF_TOKEN

    except Exception as exc:
        raise RuntimeError(
            "Unable to retrieve the Hugging Face token from Secrets Manager."
        ) from exc


def generate_answer(question, retrieved_docs):
    token = _get_hf_token()

    from huggingface_hub import InferenceClient

    context = "\n\n".join(
        f"DOCUMENT CHUNK {index + 1}:\n{document['text']}"
        for index, document in enumerate(retrieved_docs)
    )

    client = InferenceClient(
        provider="novita",
        api_key=token,
    )

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
                "content": (
                    f"Retrieved migration knowledge:\n\n{context}\n\n"
                    f"Question:\n{question}"
                ),
            },
        ],
        model="meta-llama/Llama-3.1-8B-Instruct",
        max_tokens=400,
        temperature=0.2,
    )

    return response.choices[0].message.content