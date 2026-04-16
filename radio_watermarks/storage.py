import hashlib
import json
import os
from datetime import datetime, timezone

from azure.data.tables import TableServiceClient, UpdateMode

from radio_watermarks.channels import Channel
from radio_watermarks.sources.model import Play

TABLE_NAME = "plays"


def _client() -> TableServiceClient:
    conn = os.environ["AzureWebJobsStorage"]
    return TableServiceClient.from_connection_string(conn)


def ensure_table() -> None:
    _client().create_table_if_not_exists(TABLE_NAME)


def _row_key(play: Play) -> str:
    # Stable per (start, artist, title). Falls back to fetched time if no start.
    ts = play.starts_at or datetime.now(timezone.utc)
    ts_part = ts.strftime("%Y%m%dT%H%M%SZ")
    h = hashlib.sha1(f"{play.artist}|{play.title}".encode("utf-8")).hexdigest()[:8]
    return f"{ts_part}_{h}"


def write_plays(channel: Channel, plays: list[Play]) -> int:
    if not plays:
        return 0
    table = _client().get_table_client(TABLE_NAME)
    now = datetime.now(timezone.utc).isoformat()
    written = 0
    for p in plays:
        if not p.artist and not p.title:
            continue
        entity = {
            "PartitionKey": channel.slug,
            "RowKey": _row_key(p),
            "channel_name": channel.name,
            "operator": channel.operator,
            "group": channel.group,
            "source": channel.source,
            "artist": p.artist,
            "title": p.title,
            "starts_at": p.starts_at.isoformat() if p.starts_at else "",
            "ends_at": p.ends_at.isoformat() if p.ends_at else "",
            "fetched_at": now,
            # Char-level forensics — keep the original bytes around.
            "artist_bytes_hex": p.artist.encode("utf-8").hex(),
            "title_bytes_hex": p.title.encode("utf-8").hex(),
            "raw": p.raw[:32000],  # Table Storage string column cap is 32KB
        }
        table.upsert_entity(entity=entity, mode=UpdateMode.REPLACE)
        written += 1
    return written
