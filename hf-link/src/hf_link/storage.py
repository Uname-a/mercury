from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import UUID

from .models import Message, MessageState


SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    destination TEXT NOT NULL,
    channel TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    state TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('in', 'out'))
);
CREATE INDEX IF NOT EXISTS messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS messages_state ON messages(state);
"""

ALLOWED_TRANSITIONS = {
    MessageState.QUEUED: {MessageState.CONNECTING, MessageState.FAILED},
    MessageState.CONNECTING: {MessageState.TRANSMITTING, MessageState.QUEUED, MessageState.FAILED},
    MessageState.TRANSMITTING: {MessageState.MODEM_ACKNOWLEDGED, MessageState.QUEUED, MessageState.FAILED},
    MessageState.MODEM_ACKNOWLEDGED: {MessageState.PEER_STORED, MessageState.QUEUED, MessageState.FAILED},
    MessageState.PEER_STORED: set(),
    MessageState.FAILED: {MessageState.QUEUED},
}


class MessageStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def put(self, message: Message) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO messages
                (message_id, source, destination, channel, body, created_at, state, direction)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(message.message_id), message.source, message.destination,
                    message.channel, message.body, message.created_at.isoformat(),
                    message.state.value, message.direction,
                ),
            )
            return cursor.rowcount == 1

    def get(self, message_id: UUID) -> Message | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM messages WHERE message_id = ?", (str(message_id),)
            ).fetchone()
        return self._from_row(row) if row else None

    def list(self, *, state: MessageState | None = None, limit: int = 100) -> list[Message]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        sql = "SELECT * FROM messages"
        params: tuple[object, ...] = ()
        if state is not None:
            sql += " WHERE state = ?"
            params = (state.value,)
        sql += " ORDER BY created_at DESC LIMIT ?"
        with self._connect() as connection:
            rows = connection.execute(sql, (*params, limit)).fetchall()
        return [self._from_row(row) for row in rows]

    def transition(self, message_id: UUID, new_state: MessageState) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state FROM messages WHERE message_id = ?", (str(message_id),)
            ).fetchone()
            if row is None:
                raise KeyError(str(message_id))
            old_state = MessageState(row["state"])
            if new_state not in ALLOWED_TRANSITIONS[old_state]:
                raise ValueError(f"invalid transition {old_state.value} -> {new_state.value}")
            connection.execute(
                "UPDATE messages SET state = ? WHERE message_id = ?",
                (new_state.value, str(message_id)),
            )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Message:
        return Message(
            message_id=UUID(row["message_id"]), source=row["source"],
            destination=row["destination"], channel=row["channel"],
            body=row["body"], created_at=datetime.fromisoformat(row["created_at"]),
            state=MessageState(row["state"]), direction=row["direction"],
        )

