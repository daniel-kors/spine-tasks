"""FastAPI dependency accessors."""

from fastapi import Request

from .service import AskQuestion


def get_ask_service(request: Request) -> AskQuestion:
    return request.app.state.ask_service
