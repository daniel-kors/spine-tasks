"""Application service joining composition with independent validation."""

from .compose import AnswerComposer
from .models import DraftAnswer, RetrievedChunk, ValidatedAnswer
from .validate import validate_answer


class AnswerService:
    def __init__(self, composer: AnswerComposer) -> None:
        self.composer = composer

    async def answer(
        self, question: str, chunks: tuple[RetrievedChunk, ...]
    ) -> ValidatedAnswer:
        if not chunks:
            empty = DraftAnswer(claims=(), summary="Недостаточно данных")
            return validate_answer(empty, chunks)
        draft = await self.composer.compose(question, chunks)
        return validate_answer(draft, chunks)
