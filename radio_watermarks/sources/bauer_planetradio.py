"""Bauer Media's Planet Radio now-playing API.

URL pattern: https://listenapi.planetradio.co.uk/api9.2/nowplaying/<mount>
Response: JSON with `TrackTitle`, `ArtistName`, `EventStart`, `EventFinish`,
`TrackDuration`, `EventService` (numeric station ID).
"""

from datetime import datetime, timezone

import httpx

from radio_watermarks.channels import Channel
from radio_watermarks.sources.model import Play

_URL = "https://listenapi.planetradio.co.uk/api9.2/nowplaying/{mount}"


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def fetch_bauer(channel: Channel) -> list[Play]:
    mount = channel.config["mount"]
    headers = {"User-Agent": "radio-watermarks/0.1 (metadata research)"}
    r = httpx.get(_URL.format(mount=mount), timeout=10, headers=headers)
    r.raise_for_status()
    raw = r.text
    data = r.json()
    artist = (data.get("ArtistName") or "").strip()
    title = (data.get("TrackTitle") or "").strip()
    if not artist and not title:
        return []
    return [
        Play(
            artist=artist,
            title=title,
            starts_at=_parse_ts(data.get("EventStart")),
            ends_at=_parse_ts(data.get("EventFinish")),
            raw=raw,
        )
    ]
