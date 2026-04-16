from radio_watermarks.channels import Channel
from radio_watermarks.sources.sr import fetch_sr
from radio_watermarks.sources.triton import fetch_triton
from radio_watermarks.sources.http_json import fetch_http_json
from radio_watermarks.sources.model import Play


def fetch(channel: Channel) -> list[Play]:
    if channel.source == "sr":
        return fetch_sr(channel)
    if channel.source == "triton":
        return fetch_triton(channel)
    if channel.source == "http_json":
        return fetch_http_json(channel)
    raise ValueError(f"unknown source: {channel.source}")
