"""Engine.IO v3 / Socket.IO v2 client for wss://beat.khz.se.

The server pushes `42["message",{"type":"song",...}]` frames for all channels.
No snapshot on connect — we must hold the socket open.

Run once per timer invocation, listen for `duration_s`, then close.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

import httpx
import websockets

HOST = "beat.khz.se"
POLLING_URL = f"https://{HOST}/socket.io/?EIO=3&transport=polling"
WS_URL_FMT = f"wss://{HOST}/socket.io/?EIO=3&transport=websocket&sid={{sid}}"

# Known mapping. Expand as stations are identified by listening.
# (slug, display_name, operator, group)
KHZ_CHANNEL_META: dict[str, tuple[str, str, str, str]] = {
    "94": ("khz_star_fm", "Star FM", "viaplay", "suspect"),
}


def channel_meta(channel_id: str) -> tuple[str, str, str, str]:
    if channel_id in KHZ_CHANNEL_META:
        return KHZ_CHANNEL_META[channel_id]
    return (f"khz_{channel_id}", f"khz Ch {channel_id}", "viaplay", "suspect")


async def _handshake() -> tuple[str, float]:
    async with httpx.AsyncClient(timeout=10) as hc:
        r = await hc.get(POLLING_URL)
        r.raise_for_status()
    # Engine.IO v3 polling response: "<len>:<packet>..." — first packet starts
    # with '0' then a JSON blob with sid/pingInterval/pingTimeout.
    body = r.text
    m = re.search(r"\{.*?\}", body)
    if not m:
        raise RuntimeError(f"no JSON in handshake body: {body!r}")
    hs = json.loads(m.group(0))
    return hs["sid"], hs["pingInterval"] / 1000.0


async def collect(duration_s: int, on_song) -> int:
    """Connect, listen, call `on_song(channel_id, payload_dict, raw_frame)` for
    each 'song' event. Returns the number of events seen.
    """
    sid, ping_interval = await _handshake()
    url = WS_URL_FMT.format(sid=sid)
    count = 0
    async with websockets.connect(url, max_size=2**20) as ws:
        # Probe + upgrade the transport.
        await ws.send("2probe")
        probe = await ws.recv()
        if probe != "3probe":
            raise RuntimeError(f"bad probe response: {probe!r}")
        await ws.send("5")

        loop = asyncio.get_event_loop()
        deadline = loop.time() + duration_s

        async def heartbeat() -> None:
            while loop.time() < deadline:
                await asyncio.sleep(ping_interval)
                try:
                    await ws.send("2")
                except Exception:
                    return

        async def reader() -> None:
            nonlocal count
            while loop.time() < deadline:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    return
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    return
                except websockets.ConnectionClosed:
                    return
                if not isinstance(msg, str):
                    continue
                if msg.startswith("42"):
                    try:
                        envelope = json.loads(msg[2:])
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(envelope, list) or len(envelope) < 2:
                        continue
                    event, payload = envelope[0], envelope[1]
                    if event != "message" or not isinstance(payload, dict):
                        continue
                    if payload.get("type") != "song":
                        continue
                    try:
                        on_song(payload.get("channel", ""), payload, msg)
                        count += 1
                    except Exception:
                        logging.exception("on_song handler failed")
                # "3" (pong), "40" (connect), "41" (disconnect) — ignore

        await asyncio.gather(heartbeat(), reader(), return_exceptions=True)
    return count


def parse_published_at(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
