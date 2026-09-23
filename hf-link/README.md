# Mercury HF Link

Mercury HF Link is a persistent messaging layer for two HF stations running
[Mercury](https://github.com/Rhizomatica/mercury). It will provide an IRC-style
conversation view, mailbox behavior, resumable small files, Hamlib-controlled
channel selection, and an optional Meshtastic bridge.

This first development slice provides:

- a versioned `HFML/1` binary envelope with incremental stream decoding;
- a durable SQLite outbox/inbox with message deduplication;
- `hfctl` commands to initialize a station, queue text, inspect the mailbox,
  and report status;
- a Mercury TNC client for the documented control and data sockets; and
- unit tests for framing, partial reads, malformed lengths, persistence, and
  duplicate reception.

RF transmission is disabled by default. The Raspberry Pi + (tr)uSDX +
CM108/CM119 and Windows + FTDX10 paths must pass the hardware acceptance gate
before unattended transmission is enabled.

## Development

```sh
cd hf-link
python -m venv .venv
. .venv/bin/activate              # Windows: .venv\Scripts\activate
python -m pip install -e .
python -m unittest discover -s tests -v
hfctl --state-dir ./state init --callsign YOURCALL
hfctl --state-dir ./state send --to PEERCALL "test message"
hfctl --state-dir ./state list
```

Run the daemon in receive-only mode:

```sh
hf-linkd --state-dir ./state
```

The daemon will refuse to connect to Mercury until `radio_armed = true` is set
deliberately in `config.toml`. This switch is only an application interlock;
operators remain responsible for lawful operation, correct band privileges,
station identification, and interference avoidance.

## Layout

- `src/hf_link/protocol.py` — wire framing and compact canonical codec
- `src/hf_link/storage.py` — transactional SQLite message repository
- `src/hf_link/mercury.py` — asynchronous Mercury TCP adapter
- `src/hf_link/service.py` — continuously running service entry point
- `src/hf_link/cli.py` — local command-line client
- `docs/PROJECT_PLAN.md` — complete architecture and implementation plan

