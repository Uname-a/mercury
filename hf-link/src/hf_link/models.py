from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4


class MessageState(StrEnum):
    QUEUED = "queued"
    CONNECTING = "connecting"
    TRANSMITTING = "transmitting"
    MODEM_ACKNOWLEDGED = "modem_acknowledged"
    PEER_STORED = "peer_stored"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Message:
    message_id: UUID
    source: str
    destination: str
    channel: str
    body: str
    created_at: datetime
    state: MessageState
    direction: str

    @classmethod
    def outgoing(
        cls, source: str, destination: str, body: str, channel: str = "main"
    ) -> "Message":
        source = validate_callsign(source)
        destination = validate_callsign(destination)
        body_bytes = body.encode("utf-8")
        if not body or len(body_bytes) > 4096:
            raise ValueError("message body must contain 1 to 4096 UTF-8 bytes")
        if not channel or len(channel.encode("utf-8")) > 64:
            raise ValueError("channel must contain 1 to 64 UTF-8 bytes")
        return cls(
            message_id=uuid4(),
            source=source,
            destination=destination,
            channel=channel,
            body=body,
            created_at=datetime.now(timezone.utc),
            state=MessageState.QUEUED,
            direction="out",
        )


def validate_callsign(value: str) -> str:
    value = value.strip().upper()
    if not 3 <= len(value) <= 15:
        raise ValueError("callsign must be 3 to 15 characters")
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/")
    if any(char not in allowed for char in value):
        raise ValueError("callsign contains unsupported characters")
    return value

