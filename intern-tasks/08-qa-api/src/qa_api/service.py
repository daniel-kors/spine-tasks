"""Framework-independent question-answering orchestration."""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .errors import ApplicationError
from .models import AskRequest, AskResponse, DraftAnswer, Subject
from .ports import AnswerComposer, AnswerValidator, Clock, KnowledgeGateway


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True)
class RequestEntry:
    fingerprint: str
    task: asyncio.Task[AskResponse]


class AskQuestion:
    def __init__(
        self,
        gateway: KnowledgeGateway,
        composer: AnswerComposer,
        validator: AnswerValidator,
        clock: Clock,
        logger: Any,
        *,
        composer_timeout_seconds: float,
    ) -> None:
        self.gateway = gateway
        self.composer = composer
        self.validator = validator
        self.clock = clock
        self.logger = logger
        self.composer_timeout_seconds = composer_timeout_seconds
        self._entries: dict[str, RequestEntry] = {}
        self._lock = asyncio.Lock()

    async def execute(self, request: AskRequest) -> AskResponse:
        fingerprint = self._fingerprint(request)
        async with self._lock:
            existing = self._entries.get(request.request_id)
            if existing is not None:
                if existing.fingerprint != fingerprint:
                    raise ApplicationError(
                        code="REQUEST_ID_CONFLICT",
                        message="request_id was already used for another request",
                        trace_id=uuid4(),
                        retryable=False,
                        status_code=409,
                    )
                task = existing.task
            else:
                task = asyncio.create_task(self._execute_once(request))
                self._entries[request.request_id] = RequestEntry(fingerprint, task)
        try:
            return await asyncio.shield(task)
        except Exception:
            async with self._lock:
                current = self._entries.get(request.request_id)
                if current is not None and current.task is task:
                    self._entries.pop(request.request_id, None)
            raise

    async def _execute_once(self, request: AskRequest) -> AskResponse:
        trace_id = uuid4()
        self.logger.info(
            "ask_started",
            trace_id=str(trace_id),
            request_id=request.request_id,
            workspace_id=request.workspace_id,
        )
        subject = Subject(
            workspace_id=request.workspace_id,
            user_id=request.user_id,
            scopes=request.scopes,
        )
        context = await self.gateway.retrieve(subject, request.question)
        if context.chunks:
            try:
                draft = await asyncio.wait_for(
                    self.composer.compose(request.question, context.chunks),
                    timeout=self.composer_timeout_seconds,
                )
            except TimeoutError as exc:
                self.logger.warning("composer_timeout", trace_id=str(trace_id))
                raise ApplicationError(
                    code="COMPOSER_TIMEOUT",
                    message="Answer composition timed out",
                    trace_id=trace_id,
                    retryable=True,
                    status_code=503,
                ) from exc
        else:
            draft = DraftAnswer(claims=(), summary="Недостаточно сведений")
        validated = self.validator.validate(draft, context.chunks)
        response = AskResponse(
            status=validated.status,
            answer=validated.answer_text,
            citations=validated.citations,
            index_version=context.index_version,
            policy_version=context.policy_version,
            trace_id=trace_id,
            as_of=self.clock.now(),
            reasons=validated.reasons,
        )
        self.logger.info(
            "ask_completed",
            trace_id=str(trace_id),
            request_id=request.request_id,
            status=response.status,
        )
        return response

    @staticmethod
    def _fingerprint(request: AskRequest) -> str:
        payload = request.model_dump(mode="json", exclude={"request_id"})
        payload["scopes"] = sorted(payload["scopes"])
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
