"""One-shot: export `plays` table to blob storage, then optionally delete the table rows.

Outputs to the `aggregation` container under two prefixes:
  - aggregations/{yyyy-mm-dd}.csv  -- channel,artist,title,plays   (one row per unique track per day)
  - raw/{yyyy-mm-dd}.jsonl.gz      -- full row dump (preserves *_bytes_hex, raw payload, timestamps)

Day key: starts_at in Europe/Stockholm; falls back to fetched_at when starts_at is empty.

Run:
    python -m radio_watermarks.export_and_clear                 # dump + verify only
    python -m radio_watermarks.export_and_clear --delete        # dump, verify, then delete table rows
"""

import argparse
import csv
import gzip
import io
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from azure.data.tables import TableServiceClient, TransactionOperation
from azure.storage.blob import BlobServiceClient, ContentSettings

TABLE_NAME = "plays"
CONTAINER = "aggregation"
STOCKHOLM = ZoneInfo("Europe/Stockholm")


def _conn() -> str:
    c = os.environ.get("AzureWebJobsStorage") or os.environ.get("STORAGE_CONNECTION_STRING")
    if not c:
        sys.exit("set AzureWebJobsStorage or STORAGE_CONNECTION_STRING")
    return c


def _date_key(entity: dict) -> str:
    raw = entity.get("starts_at") or entity.get("fetched_at") or ""
    if not raw:
        return "unknown"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(STOCKHOLM).date().isoformat()


def _entity_to_jsonable(e: dict) -> dict:
    out = {}
    for k, v in e.items():
        if k.startswith("odata.") or k in {"Timestamp", "etag"}:
            continue
        if isinstance(v, datetime):
            v = v.isoformat()
        out[k] = v
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", action="store_true", help="Delete table rows after a successful export.")
    args = ap.parse_args()

    conn = _conn()
    table = TableServiceClient.from_connection_string(conn).get_table_client(TABLE_NAME)
    blob_svc = BlobServiceClient.from_connection_string(conn)
    container = blob_svc.get_container_client(CONTAINER)
    try:
        container.create_container()
        print(f"created container '{CONTAINER}'")
    except Exception:
        pass  # already exists

    # Aggregation buckets: (channel, artist, title) -> count, keyed by date.
    agg: dict[str, Counter] = defaultdict(Counter)
    rows_per_date: Counter = Counter()
    delete_keys: list[tuple[str, str]] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        gz_files: dict[str, gzip.GzipFile] = {}

        total = 0
        for e in table.list_entities():
            total += 1
            day = _date_key(e)
            channel = e.get("PartitionKey", "")
            artist = e.get("artist", "") or ""
            title = e.get("title", "") or ""
            agg[day][(channel, artist, title)] += 1
            rows_per_date[day] += 1
            delete_keys.append((channel, e["RowKey"]))

            gz = gz_files.get(day)
            if gz is None:
                gz = gzip.open(tmp_path / f"{day}.jsonl.gz", "wt", encoding="utf-8")
                gz_files[day] = gz
            gz.write(json.dumps(_entity_to_jsonable(e), ensure_ascii=False))
            gz.write("\n")

            if total % 5000 == 0:
                print(f"  scanned {total} rows...")

        for gz in gz_files.values():
            gz.close()

        print(f"scanned {total} rows across {len(rows_per_date)} dates")

        # Upload per-date CSV + JSONL.gz.
        for day in sorted(agg):
            buf = io.StringIO()
            w = csv.writer(buf, lineterminator="\n")
            w.writerow(["channel", "artist", "title", "plays"])
            for (channel, artist, title), n in sorted(agg[day].items()):
                w.writerow([channel, artist, title, n])
            csv_bytes = buf.getvalue().encode("utf-8")
            container.get_blob_client(f"aggregations/{day}.csv").upload_blob(
                csv_bytes,
                overwrite=True,
                content_settings=ContentSettings(content_type="text/csv; charset=utf-8"),
            )

            gz_path = tmp_path / f"{day}.jsonl.gz"
            with gz_path.open("rb") as fh:
                container.get_blob_client(f"raw/{day}.jsonl.gz").upload_blob(
                    fh,
                    overwrite=True,
                    content_settings=ContentSettings(content_type="application/gzip"),
                )
            print(f"  uploaded {day}: {rows_per_date[day]} rows, {len(agg[day])} unique tracks")

    # Verify by reading back the raw blobs and counting lines.
    verified = 0
    for day in sorted(rows_per_date):
        blob = container.get_blob_client(f"raw/{day}.jsonl.gz")
        data = blob.download_blob().readall()
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
            n = sum(1 for _ in gz)
        if n != rows_per_date[day]:
            sys.exit(f"VERIFY FAIL {day}: scanned {rows_per_date[day]} but blob has {n}")
        verified += n
    print(f"verified: {verified} rows in blob match {total} scanned")

    if not args.delete:
        print("dump complete. re-run with --delete to remove table rows.")
        return

    # Delete in batches of 100 per partition.
    by_partition: dict[str, list[str]] = defaultdict(list)
    for pk, rk in delete_keys:
        by_partition[pk].append(rk)

    deleted = 0
    for pk, rks in by_partition.items():
        for i in range(0, len(rks), 100):
            chunk = rks[i:i + 100]
            ops = [(TransactionOperation.DELETE, {"PartitionKey": pk, "RowKey": rk}) for rk in chunk]
            table.submit_transaction(ops)
            deleted += len(chunk)
        print(f"  deleted {len(rks)} from partition {pk}")
    print(f"deleted {deleted} rows from table '{TABLE_NAME}'")


if __name__ == "__main__":
    main()
