from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from .config import Config, write_initial
from .models import Message, MessageState
from .storage import MessageStore


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="hfctl")
    result.add_argument("--state-dir", type=Path, default=Path.home() / ".local/state/hf-link")
    sub = result.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create a receive-only station configuration")
    init.add_argument("--callsign", required=True)
    send = sub.add_parser("send", help="queue a text message")
    send.add_argument("--to", required=True)
    send.add_argument("--channel", default="main")
    send.add_argument("body")
    listing = sub.add_parser("list", help="list recent messages")
    listing.add_argument("--state", choices=[state.value for state in MessageState])
    listing.add_argument("--limit", type=int, default=100)
    sub.add_parser("status", help="show station and queue status")
    show = sub.add_parser("show", help="show one message")
    show.add_argument("message_id", type=UUID)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    state_dir: Path = args.state_dir
    config_path = state_dir / "config.toml"
    db_path = state_dir / "messages.sqlite3"
    if args.command == "init":
        write_initial(config_path, args.callsign)
        MessageStore(db_path)
        print(f"initialized receive-only station at {state_dir}")
        return 0
    config = Config.load(config_path)
    store = MessageStore(db_path)
    if args.command == "send":
        message = Message.outgoing(config.callsign, args.to, args.body, args.channel)
        store.put(message)
        print(message.message_id)
    elif args.command == "list":
        state = MessageState(args.state) if args.state else None
        for message in reversed(store.list(state=state, limit=args.limit)):
            print(f"{message.created_at.isoformat()} {message.source}: {message.body} [{message.state}]")
    elif args.command == "show":
        message = store.get(args.message_id)
        if message is None:
            raise SystemExit("message not found")
        print(json.dumps(_as_json(message), indent=2))
    elif args.command == "status":
        queued = len(store.list(state=MessageState.QUEUED, limit=1000))
        print(json.dumps({
            "callsign": config.callsign,
            "radio_armed": config.radio_armed,
            "meshtastic_enabled": config.meshtastic_enabled,
            "queued_messages": queued,
        }, indent=2))
    return 0


def _as_json(message: Message) -> dict[str, str]:
    return {
        "message_id": str(message.message_id), "source": message.source,
        "destination": message.destination, "channel": message.channel,
        "body": message.body, "created_at": message.created_at.isoformat(),
        "state": message.state.value, "direction": message.direction,
    }


if __name__ == "__main__":
    raise SystemExit(main())

