import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .models import (
    Application,
    CopilotRequest,
    CopilotResponse,
    CostRiskRequest,
    CostRiskResponse,
    MigrationWavesRequest,
    MigrationWavesResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from .services import (
    answer_copilot,
    get_applications,
    get_application,
    get_cost_risk,
    get_migration_waves,
    get_recommendation,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

app = FastAPI(
    title="Intelligent Cloud Migration Planning API",
    version="0.2.0",
    description="Local FastAPI integration layer for the cloud migration planning platform.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Request validation failed for %s: %s", request.url.path, exc.errors())
    serializable_errors = []
    for error in exc.errors():
        clean_error = dict(error)
        if "ctx" in clean_error and clean_error["ctx"] is not None:
            clean_error["ctx"] = {key: str(value) for key, value in clean_error["ctx"].items()}
        serializable_errors.append(clean_error)
    return JSONResponse(status_code=422, content={"detail": "Validation error", "errors": serializable_errors})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception for %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/applications", response_model=list[Application])
def applications() -> list[Application]:
    return get_applications()


@app.get("/applications/{app_id}", response_model=Application)
def application_by_id(app_id: str) -> Application:
    try:
        return get_application(app_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Application not found: {app_id}",
        ) from exc


@app.post("/recommendation", response_model=RecommendationResponse)
def recommendation(request: RecommendationRequest) -> RecommendationResponse:
    return get_recommendation(request.app_id or request.application_id)


@app.post("/migration-waves", response_model=MigrationWavesResponse)
def migration_waves(request: MigrationWavesRequest) -> MigrationWavesResponse:
    return get_migration_waves(request.application_ids)


@app.post("/copilot", response_model=CopilotResponse)
def copilot(request: CopilotRequest) -> CopilotResponse:
    return answer_copilot(request.question)


@app.post("/cost-risk", response_model=CostRiskResponse)
def cost_risk(request: CostRiskRequest) -> CostRiskResponse:
    return get_cost_risk(request.app_id or request.application_id)
