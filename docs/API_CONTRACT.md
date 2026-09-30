# Local API Contract

Base URL: `http://127.0.0.1:8000`

This contract remains stable for the frontend while the backend delegates real implementation details to service adapters. The local code does not use AWS services.

## `GET /health`

Returns:

```json
{
  "status": "ok"
}
```

## `GET /applications`

Returns the application portfolio loaded from the repository dataset.

## `GET /applications/{app_id}`

Example: `/applications/APP001`

Returns the single application record.

## `POST /recommendation`

Request examples:

```json
{ "application_id": "APP001" }
```

```json
{ "app_id": "APP001" }
```

Response fields:

- `app_id`
- `application_id`
- `recommendation` (`Rehost`, `Replatform`, `Repurchase`, `Refactor`, `Retire`, `Retain`)
- `confidence` (0 to 1)
- `explanation` (object or string, with model details when available)

## `POST /migration-waves`

Request example:

```json
{ "application_ids": ["APP001", "APP002"] }
```

The field is optional; if omitted, all applications are planned.
The backend uses the dependency-aware planner in `Wave_Planner/wave_planner/`.

Response example:

```json
{
  "waves": [
    {
      "wave": 1,
      "applications": ["APP002"],
      "risk": "Low",
      "risk_score": 22.4,
      "application_count": 1,
      "unmet_dependencies": 0,
      "depends_on_waves": [],
      "cycle_break": false,
      "clusters": []
    }
  ],
  "summary": { "application_count": 1, "dependency_count": 0 },
  "warnings": []
}
```

The original `wave`, `applications`, and `risk` fields are preserved. Additional planner details include cluster membership, scores, dependency metrics, summary, and warnings.

## `POST /copilot`

Request example:

```json
{ "question": "How should we sequence migration waves?" }
```

Response fields:

- `question`
- `answer`
- `sources`

The endpoint uses the checked-in PDF-derived FAISS knowledge base, Sentence Transformers embeddings, and Hugging Face inference. It returns HTTP 503 when the knowledge base or `HF_TOKEN` is unavailable, and HTTP 502 when inference fails. Set `HF_TOKEN` in the backend process environment to enable generated answers.

## `POST /cost-risk`

Request examples:

```json
{ "application_id": "APP001" }
```

```json
{ "app_id": "APP001" }
```

Response fields:

- `app_id`
- `application_id`
- `monthly_aws_cost`
- `cost_range` (`lower` and `upper`)
- `risk_score` (0 to 100)

## Validation and errors

- Missing or malformed request fields return HTTP 422.
- Unknown application IDs return HTTP 404.
- Data-loading and internal service failures return HTTP 500 with a JSON detail message.
- Copilot knowledge-base or configuration failures return HTTP 503; upstream inference failures return HTTP 502.
- Cost estimates use the existing local simulator; its pricing resolver may query public AWS pricing sources when network access is available and falls back locally. No AWS account infrastructure is provisioned.

## Local test flow

1. Install `backend/requirements.txt` in the project's Python environment.
2. Run `uvicorn app.main:app --reload` from the `backend` directory.
3. Use the examples above or load the Swagger docs at `/docs`.
4. Run `pytest -q` from the repository root with `backend` on `PYTHONPATH` (or from the `backend` directory for backend-only tests).

The default portfolio is `data/processed/application_portfolio_1000.csv`; its application records are synthetic. The processed workload trace is a separate dataset.
