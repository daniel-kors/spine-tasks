"""Local application service demonstrating idempotent projection operations."""

from dataclasses import dataclass, field

from .models import IndexBatchInput, MarkFailedInput, ProjectionInput, ValidateManifestsInput


@dataclass
class ProjectionState:
    expected_count: int
    indexed_by_key: dict[str, int] = field(default_factory=dict)
    active: bool = False
    failed_reason: str | None = None


class InMemoryProjectionService:
    def __init__(self) -> None:
        self.projections: dict[tuple[str, str], ProjectionState] = {}

    async def validate(self, data: ValidateManifestsInput) -> None:
        if not data.manifest_paths:
            raise ValueError("manifest_paths must not be empty")
        if len(set(data.manifest_paths)) != len(data.manifest_paths):
            raise ValueError("manifest_paths must be unique")
        if any(not path.endswith(".jsonl") for path in data.manifest_paths):
            raise ValueError("every manifest path must end with .jsonl")

    async def create(self, data: ProjectionInput) -> None:
        self.projections.setdefault(
            (data.workspace_id, data.projection_id),
            ProjectionState(expected_count=data.expected_count),
        )

    async def index(self, data: IndexBatchInput) -> int:
        state = self._state(data.workspace_id, data.projection_id)
        previous = state.indexed_by_key.get(data.idempotency_key)
        if previous is not None:
            return previous
        count = len(data.manifest_paths)
        state.indexed_by_key[data.idempotency_key] = count
        return count

    async def verify(self, data: ProjectionInput) -> None:
        state = self._state(data.workspace_id, data.projection_id)
        if sum(state.indexed_by_key.values()) != data.expected_count:
            raise RuntimeError("projection is incomplete")

    async def activate(self, data: ProjectionInput) -> None:
        state = self._state(data.workspace_id, data.projection_id)
        if sum(state.indexed_by_key.values()) != data.expected_count:
            raise RuntimeError("cannot activate an incomplete projection")
        state.active = True

    async def mark_failed(self, data: MarkFailedInput) -> None:
        state = self.projections.setdefault(
            (data.workspace_id, data.projection_id),
            ProjectionState(expected_count=0),
        )
        state.failed_reason = data.reason_code
        state.active = False

    def _state(self, workspace_id: str, projection_id: str) -> ProjectionState:
        try:
            return self.projections[(workspace_id, projection_id)]
        except KeyError as exc:
            raise RuntimeError(
                f"unknown projection: {workspace_id}/{projection_id}"
            ) from exc
