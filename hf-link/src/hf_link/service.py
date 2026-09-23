from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .config import Config
from .mercury import MercuryClient
from .storage import MessageStore


async def run(state_dir: Path) -> None:
    config = Config.load(state_dir / "config.toml")
    MessageStore(state_dir / "messages.sqlite3")
    if not config.radio_armed:
        print(f"hf-linkd ready for {config.callsign}; RF is inhibited")
        await asyncio.Event().wait()
    client = MercuryClient(config.mercury_host, config.mercury_control_port)
    await client.open()
    try:
        await client.initialize(config.callsign)
        print(f"hf-linkd listening through Mercury as {config.callsign}")
        await asyncio.Event().wait()
    finally:
        await client.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hf-linkd")
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".local/state/hf-link")
    args = parser.parse_args(argv)
    try:
        asyncio.run(run(args.state_dir))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

