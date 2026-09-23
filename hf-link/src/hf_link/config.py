from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

from .models import validate_callsign


@dataclass(frozen=True, slots=True)
class Config:
    callsign: str
    mercury_host: str = "127.0.0.1"
    mercury_control_port: int = 8300
    radio_armed: bool = False
    meshtastic_enabled: bool = False

    @classmethod
    def load(cls, path: Path) -> "Config":
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
        station = raw.get("station", {})
        mercury = raw.get("mercury", {})
        return cls(
            callsign=validate_callsign(station["callsign"]),
            mercury_host=str(mercury.get("host", "127.0.0.1")),
            mercury_control_port=int(mercury.get("control_port", 8300)),
            radio_armed=bool(station.get("radio_armed", False)),
            meshtastic_enabled=bool(raw.get("meshtastic", {}).get("enabled", False)),
        )


def write_initial(path: Path, callsign: str) -> None:
    callsign = validate_callsign(callsign)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    path.write_text(
        f'''[station]\ncallsign = "{callsign}"\nradio_armed = false\n\n'''
        '[mercury]\nhost = "127.0.0.1"\ncontrol_port = 8300\n\n'
        '[meshtastic]\nenabled = false\n',
        encoding="utf-8",
    )

