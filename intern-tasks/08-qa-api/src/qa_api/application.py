"""FastAPI assembly, exception mapping, and fake-mode dependencies."""

import json
from pathlib import Path
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .errors import ApplicationError
from .fakes import FakeAnswerComposer, FixtureGateway, StrictAnswerValidator
from .models import ErrorResponse, RetrievedChunk
from .routes import router
from .service import AskQuestion, SystemClock
from .settings import Settings


def create_app(
    service: AskQuestion | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    configured = settings or Settings()
    logger = structlog.get_logger("qa_api")
    app = FastAPI(title="Knowledge Q&A API", version="0.1.0")
    app.state.settings = configured
    app.state.logger = logger
    app.state.ask_service = service or _fake_service(configured, logger)
    app.include_router(router)
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    return app


async def application_error_handler(request: Request, exc: Exception) -> JSONResponse:
    error = exc
    if not isinstance(error, ApplicationError):
        raise error
    body = ErrorResponse(
        code=error.code,
        message=error.message,
        trace_id=error.trace_id,
        retryable=error.retryable,
    )
    request.app.state.logger.warning(
        "application_error",
        trace_id=str(error.trace_id),
        code=error.code,
        retryable=error.retryable,
    )
    return JSONResponse(status_code=error.status_code, content=body.model_dump(mode="json"))


async def validation_error_handler(request: Request, _: RequestValidationError) -> JSONResponse:
    trace_id = uuid4()
    request.app.state.logger.info("request_validation_failed", trace_id=str(trace_id))
    body = ErrorResponse(
        code="INVALID_REQUEST",
        message="Request validation failed",
        trace_id=trace_id,
        retryable=False,
    )
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))


async def unexpected_error_handler(request: Request, _: Exception) -> JSONResponse:
    trace_id = uuid4()
    request.app.state.logger.error("unexpected_error", trace_id=str(trace_id))
    body = ErrorResponse(
        code="INTERNAL_ERROR",
        message="Internal server error",
        trace_id=trace_id,
        retryable=True,
    )
    return JSONResponse(status_code=500, content=body.model_dump(mode="json"))


def _fake_service(settings: Settings, logger: object) -> AskQuestion:
    fixture_path = Path(__file__).parents[2] / "data" / "fixtures" / "fake-context.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    chunks = {
        question: tuple(RetrievedChunk.model_validate(item) for item in items)
        for question, items in payload["answers"].items()
    }
    return AskQuestion(
        FixtureGateway(chunks),
        FakeAnswerComposer(),
        StrictAnswerValidator(),
        SystemClock(),
        logger,
        composer_timeout_seconds=settings.composer_timeout_seconds,
    )
