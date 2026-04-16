from dataclasses import dataclass


@dataclass(frozen=True)
class Channel:
    slug: str
    name: str
    operator: str
    group: str  # "control" | "suspect"
    source: str  # "sr" | "triton" | "http_json"
    config: dict


CHANNELS: list[Channel] = [
    # --- Sveriges Radio (control) ---
    Channel("sr_p1", "P1", "sr", "control", "sr", {"channel_id": 132}),
    Channel("sr_p2", "P2", "sr", "control", "sr", {"channel_id": 163}),
    Channel("sr_p3", "P3", "sr", "control", "sr", {"channel_id": 164}),
    Channel("sr_p4_sthlm", "P4 Stockholm", "sr", "control", "sr", {"channel_id": 701}),
    Channel("sr_p4_gbg", "P4 Göteborg", "sr", "control", "sr", {"channel_id": 212}),
    Channel("sr_p4_malmohus", "P4 Malmöhus", "sr", "control", "sr", {"channel_id": 210}),

    # Commercial stations (Bauer + Viaplay) are captured via the khz.se
    # Socket.IO stream (see function_app.py `collect_khz` + sources/khz_socketio.py).
    # Channel IDs are numeric; confirmed so far: 94 = Star FM (Viaplay).
]
