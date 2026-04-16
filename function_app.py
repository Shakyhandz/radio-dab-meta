import asyncio
import logging
from datetime import timedelta

import azure.functions as func

from radio_watermarks.channels import Channel
from radio_watermarks.poller import poll_all
from radio_watermarks.sources import khz_socketio
from radio_watermarks.sources.model import Play
from radio_watermarks.storage import ensure_table, write_plays

app = func.FunctionApp()


@app.timer_trigger(
    schedule="0 */1 * * * *",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=False,
)
def poll_channels(timer: func.TimerRequest) -> None:
    result = poll_all()
    logging.info("poll summary: %s", result)


@app.timer_trigger(
    schedule="0 */10 * * * *",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=False,
)
def collect_khz(timer: func.TimerRequest) -> None:
    ensure_table()
    stats = {"events": 0, "written": 0}

    def on_song(channel_id: str, payload: dict, raw_frame: str) -> None:
        slug, name, operator, group = khz_socketio.channel_meta(str(channel_id))
        ch = Channel(slug, name, operator, group, "khz_socketio", {"channel_id": channel_id})
        data = payload.get("data") or {}
        song = data.get("song") or {}
        starts_at = khz_socketio.parse_published_at(data.get("published_at"))
        try:
            run_length = int(data.get("run_length") or 0)
        except (TypeError, ValueError):
            run_length = 0
        ends_at = starts_at + timedelta(seconds=run_length) if (starts_at and run_length) else None
        play = Play(
            artist=(song.get("artist_name") or "").strip(),
            title=(song.get("title") or "").strip(),
            starts_at=starts_at,
            ends_at=ends_at,
            raw=raw_frame,
        )
        stats["written"] += write_plays(ch, [play])
        stats["events"] += 1

    try:
        asyncio.run(khz_socketio.collect(duration_s=560, on_song=on_song))
    except Exception:
        logging.exception("khz socket listener crashed")
    logging.info("khz summary: %s", stats)
