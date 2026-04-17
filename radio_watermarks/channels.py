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

    # --- Bauer Media Sweden (secondary control) ---
    # Polled via Bauer's Planet Radio API. Mount codes found by probing;
    # extend the list when more codes are confirmed from browser devtools.
    Channel("bauer_rokklassiker", "Rockklassiker",    "bauer", "control", "bauer", {"mount": "rok"}),
    Channel("bauer_nrj",          "NRJ",              "bauer", "control", "bauer", {"mount": "nrj"}),
    Channel("bauer_vinyl_fm",     "Vinyl FM",         "bauer", "control", "bauer", {"mount": "vin"}),
    Channel("bauer_svensk_pop",   "Svensk Pop",       "bauer", "control", "bauer", {"mount": "svp"}),
    Channel("bauer_gold_fm",      "Gold FM",          "bauer", "control", "bauer", {"mount": "gfm"}),
    Channel("bauer_nostalgi",     "Nostalgi",         "bauer", "control", "bauer", {"mount": "nos"}),
    Channel("bauer_mix_80tal",    "Mix Megapol 80-tal","bauer","control", "bauer", {"mount": "m80"}),
    Channel("bauer_mix_megapol",  "Mix Megapol",      "bauer", "control", "bauer", {"mount": "mgp"}),
    Channel("bauer_mix_megapol_p","Mix Megapol (p)",  "bauer", "control", "bauer", {"mount": "mmp"}),
    Channel("bauer_lugna_klassiker","Lugna Klassiker","bauer", "control", "bauer", {"mount": "lug"}),

    # Viaplay commercial stations (all of beat.khz.se) are captured via the
    # Socket.IO stream in function_app.py `collect_khz` + sources/khz_socketio.py.
]
