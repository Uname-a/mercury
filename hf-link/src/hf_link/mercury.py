from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator


class MercuryError(RuntimeError):
    pass


class MercuryClient:
    """Small async adapter for Mercury's VARA-compatible TCP interface."""

    def __init__(self, host: str = "127.0.0.1", control_port: int = 8300) -> None:
        self.host = host
        self.control_port = control_port
        self._control_reader: asyncio.StreamReader | None = None
        self._control_writer: asyncio.StreamWriter | None = None
        self._data_reader: asyncio.StreamReader | None = None
        self._data_writer: asyncio.StreamWriter | None = None
        self._command_lock = asyncio.Lock()

    async def open(self) -> None:
        self._control_reader, self._control_writer = await asyncio.open_connection(
            self.host, self.control_port
        )
        self._data_reader, self._data_writer = await asyncio.open_connection(
            self.host, self.control_port + 1
        )

    async def close(self) -> None:
        for writer in (self._data_writer, self._control_writer):
            if writer is not None:
                writer.close()
                await writer.wait_closed()

    async def command(self, command: str) -> str:
        if self._control_writer is None or self._control_reader is None:
            raise MercuryError("Mercury connection is not open")
        if "\r" in command or "\n" in command:
            raise ValueError("command must be one line")
        async with self._command_lock:
            self._control_writer.write(command.encode("ascii") + b"\r")
            await self._control_writer.drain()
            response = await self._control_reader.readuntil(b"\r")
        return response[:-1].decode("ascii", errors="strict")

    async def initialize(self, callsign: str) -> None:
        for command in (f"MYCALL {callsign}", "BW500", "LISTEN ON"):
            response = await self.command(command)
            if response != "OK":
                raise MercuryError(f"Mercury rejected {command!r}: {response}")

    async def send_payload(self, payload: bytes) -> None:
        if self._data_writer is None:
            raise MercuryError("Mercury data connection is not open")
        self._data_writer.write(payload)
        await self._data_writer.drain()

    async def receive_payloads(self, size: int = 4096) -> AsyncIterator[bytes]:
        if self._data_reader is None:
            raise MercuryError("Mercury data connection is not open")
        while chunk := await self._data_reader.read(size):
            yield chunk

