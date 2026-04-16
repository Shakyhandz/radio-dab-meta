from dataclasses import dataclass
from datetime import datetime


@dataclass
class Play:
    artist: str
    title: str
    starts_at: datetime | None
    ends_at: datetime | None
    raw: str  # original response body for later forensic analysis
