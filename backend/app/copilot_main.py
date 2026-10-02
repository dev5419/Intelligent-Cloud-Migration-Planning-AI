import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum

from .config import settings
from .copilot_service import answer_copilot
from .models import CopilotRequest, CopilotResponse

logger = logging.getLogger(__name__)
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

app = FastAPI(
    title="Intelligent Cloud Migration Planning API",
    version="0.2.0",
    description="Copilot API for the cloud migration planning platform.",
)

handler = Mangum(app)

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


@app.post("/copilot", response_model=CopilotResponse)
def copilot(request: CopilotRequest) -> CopilotResponse:
    return answer_copilot(request.question)