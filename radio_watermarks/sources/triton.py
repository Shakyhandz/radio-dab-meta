from datetime import datetime, timezone

import httpx
from defusedxml import ElementTree as ET

from radio_watermarks.channels import Channel
from radio_watermarks.sources.model import Play


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_triton(channel: Channel) -> list[Play]:
    mount = channel.config["mount"]
    url = (
        "https://np.tritondigital.com/public/nowplaying"
        f"?mountName={mount}&numberToFetch=1&eventType=track"
    )
    r = httpx.get(url, timeout=10)
    r.raise_for_status()
    raw = r.text
    root = ET.fromstring(raw)
    plays: list[Play] = []
    for info in root.findall("nowplaying-info"):
        props = {p.get("name"): (p.text or "").strip() for p in info.findall("property")}
        start = _parse_ts(props.get("cue_time_start"))
        duration_ms = int(props.get("cue_time_duration") or 0)
        end = None
        if start and duration_ms:
            end = datetime.fromtimestamp(start.timestamp() + duration_ms / 1000, tz=timezone.utc)
        plays.append(
            Play(
                artist=props.get("track_artist_name", ""),
                title=props.get("cue_title", ""),
                starts_at=start,
                ends_at=end,
                raw=raw,
            )
        )
    return plays
