"""SQLite adapter for idempotent command results."""

from pathlib import Path
from typing import Protocol

import aiosqlite

from .models import IngestionReceipt


class IdempotencyStore(Protocol):
    async def initialize(self) -> None: ...

    async def get(self, workspace_id: str, idempotency_key: str) -> IngestionReceipt | None: ...

    async def complete(
        self, workspace_id: str, idempotency_key: str, receipt: IngestionReceipt
    ) -> None: ...


class SqliteIdempotencyStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as database:
            await database.executescript(
                """
                CREATE TABLE IF NOT EXISTS run_reports (
                    run_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    receipt_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS command_results (
                    workspace_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    PRIMARY KEY (workspace_id, idempotency_key)
                );
                """
            )
            await database.commit()

    async def get(self, workspace_id: str, idempotency_key: str) -> IngestionReceipt | None:
        async with aiosqlite.connect(self.path) as database:
            cursor = await database.execute(
                """
                SELECT receipt_json
                FROM command_results
                WHERE workspace_id = ? AND idempotency_key = ?
                """,
                (workspace_id, idempotency_key),
            )
            row = await cursor.fetchone()
        return IngestionReceipt.model_validate_json(row[0]) if row else None

    async def complete(
        self, workspace_id: str, idempotency_key: str, receipt: IngestionReceipt
    ) -> None:
        payload = receipt.model_dump_json()
        async with aiosqlite.connect(self.path) as database:
            await database.execute("BEGIN IMMEDIATE")
            try:
                await database.execute(
                    """
                    INSERT INTO run_reports (run_id, workspace_id, receipt_json)
                    VALUES (?, ?, ?)
                    """,
                    (str(receipt.run_id), workspace_id, payload),
                )
                await database.execute(
                    """
                    INSERT INTO command_results (workspace_id, idempotency_key, receipt_json)
                    VALUES (?, ?, ?)
                    """,
                    (workspace_id, idempotency_key, payload),
                )
                await database.commit()
            except Exception:
                await database.rollback()
                raise
