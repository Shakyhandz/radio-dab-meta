"""Local analysis CLI. Pulls `plays` rows and surfaces char-level anomalies.

Run:
    uv run rwm-analyze              # all channels
    uv run rwm-analyze --group suspect
    uv run rwm-analyze --channel viaplay_star_fm
"""

import argparse
import os
import sys
import unicodedata
from collections import Counter

from azure.data.tables import TableServiceClient

TABLE_NAME = "plays"


def _client() -> TableServiceClient:
    conn = os.environ.get("AzureWebJobsStorage") or os.environ.get("STORAGE_CONNECTION_STRING")
    if not conn:
        sys.exit("set AzureWebJobsStorage or STORAGE_CONNECTION_STRING")
    return TableServiceClient.from_connection_string(conn)


def _iter_entities(group: str | None, channel: str | None):
    table = _client().get_table_client(TABLE_NAME)
    filters = []
    if group:
        filters.append(f"group eq '{group}'")
    if channel:
        filters.append(f"PartitionKey eq '{channel}'")
    q = " and ".join(filters) if filters else None
    return table.query_entities(q) if q else table.list_entities()


def _is_weird(ch: str) -> bool:
    cat = unicodedata.category(ch)
    # Cc = control, Cf = format, Cs = surrogate, Co = private use, Cn = unassigned
    if cat in {"Cc", "Cf", "Cs", "Co", "Cn"}:
        return True
    # Anything above the Basic Multilingual Plane.
    if ord(ch) > 0xFFFF:
        return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", choices=["control", "suspect"])
    ap.add_argument("--channel")
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args()

    per_channel_counts: dict[str, Counter] = {}
    per_channel_rows: Counter = Counter()
    per_channel_weird: dict[str, list[tuple[str, str, str]]] = {}

    for e in _iter_entities(args.group, args.channel):
        ch = e["PartitionKey"]
        per_channel_rows[ch] += 1
        counts = per_channel_counts.setdefault(ch, Counter())
        weird = per_channel_weird.setdefault(ch, [])
        for field in ("artist", "title"):
            text = e.get(field) or ""
            counts.update(text)
            for c in text:
                if _is_weird(c):
                    weird.append((field, text, c))

    print(f"\n=== Row counts ===")
    for ch, n in per_channel_rows.most_common():
        print(f"  {ch:28s} {n}")

    print(f"\n=== Non-ASCII / weird chars by channel ===")
    for ch in sorted(per_channel_counts):
        weird_chars = Counter(c for c, n in per_channel_counts[ch].items() if ord(c) > 127)
        if not weird_chars:
            continue
        print(f"\n  {ch} (top {args.top}):")
        for c, n in weird_chars.most_common(args.top):
            name = unicodedata.name(c, "?")
            print(f"    U+{ord(c):04X}  x{n:4d}  {c!r:8s}  {name}")

    print(f"\n=== Control / format / supplementary-plane occurrences ===")
    any_weird = False
    for ch, items in per_channel_weird.items():
        if not items:
            continue
        any_weird = True
        print(f"\n  {ch}: {len(items)} occurrences")
        for field, text, c in items[:10]:
            print(f"    [{field}] U+{ord(c):04X} in {text!r}")
    if not any_weird:
        print("  (none found)")


if __name__ == "__main__":
    main()
