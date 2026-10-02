# Copilot Lambda

This package deploys only the Copilot `POST /copilot` endpoint. It does not change or include the Core Lambda deployment. The function runs outside a VPC and calls Hugging Face for embeddings and hosted generation.

## Build

From the repository root, using the project Python environment with FAISS installed for offline conversion:

```powershell
python aws-lambda/copilot/build_package.py
```

The builder reconstructs the document vectors directly from `copilot/vectorstore/migration.index`, stages the selected runtime files and demo PDF, and installs Python 3.12 x86_64 Linux wheels. It does not build a container. Generated package files and the ZIP are written under the ignored `aws-lambda/copilot/build/` directory.

## Deploy

Create a Secrets Manager secret whose plaintext value is the Hugging Face token. Do not put the token value in the repository or deployment artifacts. From the repository root, run:

```powershell
sam deploy --guided --template-file aws-lambda/copilot/template.yaml
```

Provide the secret ARN for `HuggingFaceTokenSecretArn` when prompted. The template resolves the secret into the Lambda environment at deployment time. The deployment identity needs permission to read that secret. The function has no VPC configuration; no EFS, NAT Gateway, or Docker image is used.

## Local Checks

With the token supplied through the local environment or the ignored `copilot/.env` file, run:

```powershell
python aws-lambda/copilot/smoke_test.py
```

The smoke test checks the Lambda handler import graph, hosted query embeddings and generation, NumPy retrieval and source metadata, then exercises both the lightweight Lambda app and the existing local FastAPI app. Local Uvicorn startup remains `uvicorn app.main:app --reload` from the `backend` directory and continues to use FAISS/Sentence Transformers by default.