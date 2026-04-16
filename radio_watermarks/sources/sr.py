import re
from datetime import datetime, timezone

import httpx

from radio_watermarks.channels import Channel
from radio_watermarks.sources.model import Play

_DOT_NET_DATE = re.compile(r"/Date\((\d+)[^)]*\)/")


def _parse_dotnet_date(s: str | None) -> datetime | None:
    if not s:
        return None
    m = _DOT_NET_DATE.match(s)
    if not m:
        return None
    return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc)


def fetch_sr(channel: Channel) -> list[Play]:
    cid = channel.config["channel_id"]
    url = f"https://api.sr.se/api/v2/playlists/rightnow?channelid={cid}&format=json"
    r = httpx.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    plays: list[Play] = []
    raw = r.text
    for key in ("previoussong", "song", "nextsong"):
        s = data.get("playlist", {}).get(key)
        if not s:
            continue
        plays.append(
            Play(
                artist=(s.get("artist") or "").strip(),
                title=(s.get("title") or "").strip(),
                starts_at=_parse_dotnet_date(s.get("starttimeutc")),
                ends_at=_parse_dotnet_date(s.get("stoptimeutc")),
                raw=raw,
            )
        )
    return plays
