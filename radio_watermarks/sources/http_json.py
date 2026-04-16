from datetime import datetime
from typing import Any

import httpx

from radio_watermarks.channels import Channel
from radio_watermarks.sources.model import Play


def _dig(obj: Any, path: str | None) -> Any:
    if not path:
        return None
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if part.isdigit() and isinstance(cur, list):
            idx = int(part)
            cur = cur[idx] if idx < len(cur) else None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _parse_ts(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v / 1000 if v > 1e12 else v)
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def fetch_http_json(channel: Channel) -> list[Play]:
    cfg = channel.config
    headers = cfg.get("headers", {})
    r = httpx.get(cfg["url"], timeout=10, headers=headers)
    r.raise_for_status()
    raw = r.text
    data = r.json()
    root = _dig(data, cfg.get("root_path")) if cfg.get("root_path") else data
    items = root if isinstance(root, list) else [root]
    plays: list[Play] = []
    for item in items:
        plays.append(
            Play(
                artist=str(_dig(item, cfg.get("artist_path")) or "").strip(),
                title=str(_dig(item, cfg.get("title_path")) or "").strip(),
                starts_at=_parse_ts(_dig(item, cfg.get("starts_at_path"))),
                ends_at=_parse_ts(_dig(item, cfg.get("ends_at_path"))),
                raw=raw,
            )
        )
    return plays
