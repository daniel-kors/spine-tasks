"""Thin HTTP routes over the application service."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from .dependencies import get_ask_service
from .models import AskRequest, AskResponse
from .service import AskQuestion

router = APIRouter()


@router.post("/api/v1/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    service: Annotated[AskQuestion, Depends(get_ask_service)],
) -> AskResponse:
    return await service.execute(request)


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request) -> dict[str, str]:
    mode = request.app.state.settings.qa_mode
    return {"status": "ready", "mode": mode}
