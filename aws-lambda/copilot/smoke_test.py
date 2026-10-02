from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv
from fastapi.testclient import TestClient


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_VECTORSTORE = Path(__file__).resolve().parent / "build/package/copilot/vectorstore"
QUESTION = "What should I consider before rehosting an application?"


def verify_lambda_imports() -> None:
    code = f"""
import fastapi
import huggingface_hub
import mangum
import numpy
import pydantic
from pathlib import Path
import os
import sys
from fastapi.testclient import TestClient
sys.path.insert(0, {str(PACKAGE_VECTORSTORE.parents[1])!r})
from backend.app.copilot_service import _get_pipeline
search, _ = _get_pipeline()
from backend.app import copilot_main
from copilot.lambda_rag import _load_resources
vectors, chunks = _load_resources()
assert callable(copilot_main.handler)
assert Path(copilot_main.__file__).resolve().is_relative_to(Path({str(PACKAGE_VECTORSTORE.parents[1])!r}))
assert search.__module__ == 'copilot.lambda_rag'
assert vectors.shape == (3, 384) and len(chunks) == 3
response = TestClient(copilot_main.app).post('/copilot', json={{'question': {QUESTION!r}}})
payload = response.json()
assert response.status_code == 200
assert payload['answer'].strip()
assert 'demo_migration_knowledge.pdf' in payload['sources']
assert os.environ['HF_TOKEN'] not in response.text
assert not set(('faiss', 'torch', 'sentence_transformers')).intersection(sys.modules)
"""
    environment = os.environ.copy()
    environment["COPILOT_RETRIEVAL_BACKEND"] = "numpy"
    environment["COPILOT_VECTORSTORE_DIR"] = str(PACKAGE_VECTORSTORE)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def check_response(response, token: str) -> dict[str, object]:
    if response.status_code != 200:
        raise RuntimeError("Copilot smoke request did not return HTTP 200.")
    payload = response.json()
    if not payload.get("answer", "").strip():
        raise RuntimeError("Copilot smoke request returned an empty answer.")
    sources = payload.get("sources", [])
    if not sources or "demo_migration_knowledge.pdf" not in sources:
        raise RuntimeError("Copilot smoke request did not preserve demo PDF source metadata.")
    if token in json.dumps(payload, ensure_ascii=True):
        raise RuntimeError("Copilot response unexpectedly contained the configured token.")
    return payload


def main() -> int:
    if not PACKAGE_VECTORSTORE.joinpath("migration_vectors.npy").is_file():
        raise RuntimeError("Run build_package.py before the local smoke test.")

    load_dotenv(REPOSITORY_ROOT / "copilot/.env", override=False)
    token = os.getenv("HF_TOKEN", "").strip()
    if not token or token == "YOUR_HUGGING_FACE_TOKEN":
        raise RuntimeError("Configure the runtime token in the environment or ignored copilot/.env file.")

    verify_lambda_imports()

    sys.path.insert(0, str(REPOSITORY_ROOT))
    os.environ["COPILOT_RETRIEVAL_BACKEND"] = "numpy"
    os.environ["COPILOT_VECTORSTORE_DIR"] = str(PACKAGE_VECTORSTORE)

    from copilot.lambda_rag import search
    retrieved = search(QUESTION, top_k=3)
    if not retrieved or "demo_migration_knowledge.pdf" not in retrieved[0]["text"]:
        raise RuntimeError("Hosted embedding or NumPy retrieval did not return demo knowledge.")

    os.environ["COPILOT_RETRIEVAL_BACKEND"] = "faiss"
    os.environ.pop("COPILOT_VECTORSTORE_DIR", None)
    from backend.app.main import app as local_app

    local_payload = check_response(TestClient(local_app).post("/copilot", json={"question": QUESTION}), token)

    print("Staged Lambda POST /copilot: HTTP 200; non-empty answer; source metadata present")
    print("Hosted query embedding and NumPy retrieval: passed")
    print("Local FAISS POST /copilot: HTTP 200; non-empty answer; source metadata present")
    print("HF_TOKEN response check: passed")
    print("Local sources:", ", ".join(local_payload["sources"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())