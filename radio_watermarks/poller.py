import logging

from radio_watermarks.channels import CHANNELS
from radio_watermarks.sources import fetch
from radio_watermarks.storage import ensure_table, write_plays


def poll_all() -> dict:
    ensure_table()
    totals = {"channels": 0, "fetched": 0, "written": 0, "errors": 0}
    for ch in CHANNELS:
        totals["channels"] += 1
        try:
            plays = fetch(ch)
            totals["fetched"] += len(plays)
            totals["written"] += write_plays(ch, plays)
        except Exception:
            totals["errors"] += 1
            logging.exception("poll failed for %s", ch.slug)
    return totals
