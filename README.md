# Intelligent Cloud Migration Planning using AI

This project models an end-to-end cloud migration planning system. The current goal is to complete the local backend integration first, keep AWS out of the implementation until the final phase, and preserve stable API contracts for future frontend and ML integration.

## Local architecture

The working local structure is:

```text
Local FastAPI backend
    |
    v
    HTTP endpoints (/health, /applications, /recommendation, /migration-waves, /copilot, /cost-risk)
    |
    v
    Data loader -> application_portfolio_1000.csv
    |
    v
    Service adapters for recommendation, waves, genAI, and cost/risk
    |
    v
    Future ML / AI modules (Random Forest + SHAP, NetworkX, LangChain + FAISS)
```

The AWS architecture is intentionally kept out of the local code path and is planned only for the final stage:

```text
Local FastAPI
    |
    v
API Gateway
    |
    v
Lambda
    |
    v
DynamoDB / S3 / CloudWatch
```

## Python virtual environment

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the FastAPI app locally

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Then open:

- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/openapi.json

## Run tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -q
```

## API endpoints

### GET /health
Returns the server health status.

### GET /applications
Returns the catalog of applications loaded from the real local dataset.

### GET /applications/{app_id}
Returns the application record for the requested app ID.

### POST /recommendation
Request example:

```json
{
  "application_id": "APP001"
}
```

Response example:

```json
{
  "app_id": "APP001",
  "application_id": "APP001",
  "recommendation": "Rehost",
  "confidence": 0.87,
  "explanation": {
    "model": "local_adapter",
    "source": "fallback_heuristic",
    "top_features": ["criticality", "dependency_count", "cpu_usage", "age_years"],
    "shap": {
      "available": false,
      "note": "No SHAP values were loaded from the model yet."
    }
  }
}
```

### POST /migration-waves
Request example:

```json
{
  "application_ids": ["APP001", "APP002"]
}
```

### POST /copilot
Request example:

```json
{
  "question": "How should we sequence migration waves?"
}
```

### POST /cost-risk
Request example:

```json
{
  "application_id": "APP001"
}
```

## Data source

The application portfolio is loaded from the repo’s local dataset:

- [data/processed/application_portfolio_1000.csv](data/processed/application_portfolio_1000.csv)

This avoids hard-coding portfolio data in the API layer. The backend reads the CSV and normalizes IDs to the stable `APP###` format.

## Current module status

- Recommendation service: adapter boundary ready for the real Member 3 6R model. A local fallback is active until the ML model is placed in the project.
- Migration waves: service interface ready for NetworkX / community detection / greedy wave planning.
- GenAI copilot: interface ready for LangChain + FAISS + Hugging Face.
- Cost/risk: local simulator interface remains in place and is not tied to AWS services yet.

## Notes

- No AWS services are used in the local implementation.
- There are no secrets, keys, or credentials in the codebase.
- The API contract remains frontend-friendly and stable for future integration.

## Contribution

This repository is structured so the backend can be tested and refined locally before the final AWS deployment phase.
