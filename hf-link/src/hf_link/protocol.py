"""HFML/1 framing and a deliberately small canonical CBOR implementation.

The codec accepts only the data types used by HFML envelopes. This keeps the
initial service dependency-free while producing deterministic CBOR. It rejects
indefinite-length values, floats, tags, duplicate map keys, and excessive
nesting.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Any

MAGIC = b"HFML"
VERSION = 1
HEADER = struct.Struct(">4sBI")
MAX_FRAME_BYTES = 256 * 1024
MAX_NESTING = 16


class ProtocolError(ValueError):
    pass


def encode_frame(envelope: dict[str, Any]) -> bytes:
    body = _encode(envelope, 0)
    if len(body) > MAX_FRAME_BYTES:
        raise ProtocolError("frame exceeds maximum size")
    return HEADER.pack(MAGIC, VERSION, len(body)) + body


@dataclass(slots=True)
class FrameDecoder:
    _buffer: bytearray

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[dict[str, Any]]:
        self._buffer.extend(data)
        frames: list[dict[str, Any]] = []
        while len(self._buffer) >= HEADER.size:
            magic, version, length = HEADER.unpack_from(self._buffer)
            if magic != MAGIC:
                raise ProtocolError("invalid frame magic")
            if version != VERSION:
                raise ProtocolError(f"unsupported protocol version {version}")
            if length > MAX_FRAME_BYTES:
                raise ProtocolError("announced frame length exceeds maximum")
            total = HEADER.size + length
            if len(self._buffer) < total:
                break
            body = bytes(self._buffer[HEADER.size:total])
            del self._buffer[:total]
            value, offset = _decode(body, 0, 0)
            if offset != len(body) or not isinstance(value, dict):
                raise ProtocolError("frame body must be one CBOR map")
            frames.append(value)
        return frames


def _head(major: int, value: int) -> bytes:
    if value < 0:
        raise ProtocolError("negative length")
    prefix = major << 5
    if value < 24:
        return bytes((prefix | value,))
    if value <= 0xFF:
        return bytes((prefix | 24, value))
    if value <= 0xFFFF:
        return bytes((prefix | 25,)) + struct.pack(">H", value)
    if value <= 0xFFFFFFFF:
        return bytes((prefix | 26,)) + struct.pack(">I", value)
    if value <= 0xFFFFFFFFFFFFFFFF:
        return bytes((prefix | 27,)) + struct.pack(">Q", value)
    raise ProtocolError("integer too large")


def _encode(value: Any, depth: int) -> bytes:
    if depth > MAX_NESTING:
        raise ProtocolError("maximum nesting exceeded")
    if value is None:
        return b"\xf6"
    if value is False:
        return b"\xf4"
    if value is True:
        return b"\xf5"
    if isinstance(value, int):
        return _head(0, value) if value >= 0 else _head(1, -1 - value)
    if isinstance(value, bytes):
        return _head(2, len(value)) + value
    if isinstance(value, str):
        encoded = value.encode("utf-8")
        return _head(3, len(encoded)) + encoded
    if isinstance(value, (list, tuple)):
        return _head(4, len(value)) + b"".join(_encode(v, depth + 1) for v in value)
    if isinstance(value, dict):
        pairs: list[tuple[bytes, bytes]] = []
        for key, item in value.items():
            encoded_key = _encode(key, depth + 1)
            pairs.append((encoded_key, _encode(item, depth + 1)))
        pairs.sort(key=lambda pair: (len(pair[0]), pair[0]))
        return _head(5, len(pairs)) + b"".join(k + v for k, v in pairs)
    raise ProtocolError(f"unsupported CBOR type: {type(value).__name__}")


def _argument(data: bytes, offset: int, additional: int) -> tuple[int, int]:
    sizes = {24: 1, 25: 2, 26: 4, 27: 8}
    if additional < 24:
        return additional, offset
    size = sizes.get(additional)
    if size is None or offset + size > len(data):
        raise ProtocolError("invalid or truncated CBOR argument")
    return int.from_bytes(data[offset:offset + size], "big"), offset + size


def _decode(data: bytes, offset: int, depth: int) -> tuple[Any, int]:
    if depth > MAX_NESTING or offset >= len(data):
        raise ProtocolError("truncated or excessively nested CBOR")
    initial = data[offset]
    offset += 1
    major, additional = initial >> 5, initial & 0x1F
    if major == 7:
        simple = {20: False, 21: True, 22: None}
        if additional in simple:
            return simple[additional], offset
        raise ProtocolError("unsupported CBOR simple value")
    value, offset = _argument(data, offset, additional)
    if major == 0:
        return value, offset
    if major == 1:
        return -1 - value, offset
    if major in (2, 3):
        end = offset + value
        if end > len(data):
            raise ProtocolError("truncated CBOR string")
        raw = data[offset:end]
        if major == 2:
            return raw, end
        try:
            return raw.decode("utf-8"), end
        except UnicodeDecodeError as exc:
            raise ProtocolError("invalid UTF-8 text") from exc
    if major == 4:
        items = []
        for _ in range(value):
            item, offset = _decode(data, offset, depth + 1)
            items.append(item)
        return items, offset
    if major == 5:
        result: dict[Any, Any] = {}
        for _ in range(value):
            key, offset = _decode(data, offset, depth + 1)
            if key in result:
                raise ProtocolError("duplicate CBOR map key")
            item, offset = _decode(data, offset, depth + 1)
            result[key] = item
        return result, offset
    raise ProtocolError(f"unsupported CBOR major type {major}")

