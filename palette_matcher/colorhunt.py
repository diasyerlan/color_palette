"""Collector for Color Hunt's public palette feed."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

FEED_URL = "https://colorhunt.co/php/feed.php"
ALL_TIME_DAYS = 4000  # value used by Color Hunt's "All time" control


def split_code(code: str) -> list[str]:
    """Turn Color Hunt's 24-character code into four #RRGGBB strings."""
    code = code.strip().lower()
    if len(code) != 24 or any(c not in "0123456789abcdef" for c in code):
        raise ValueError(f"Invalid Color Hunt palette code: {code!r}")
    return [f"#{code[i:i + 6].upper()}" for i in range(0, 24, 6)]


def fetch_popular(count: int = 100, timeframe_days: int = ALL_TIME_DAYS) -> list[dict]:
    """Fetch the first *count* entries from Color Hunt's popularity feed."""
    if count < 1:
        raise ValueError("count must be positive")

    records: list[dict] = []
    seen: set[str] = set()
    step = 0
    while len(records) < count:
        payload = urlencode(
            {"step": step, "sort": "popular", "tags": "", "timeframe": timeframe_days}
        ).encode("ascii")
        request = Request(
            FEED_URL,
            data=payload,
            headers={
                "User-Agent": "color-palette-analysis/1.0 (academic project)",
                "Accept": "application/json, text/plain, */*",
            },
        )
        with urlopen(request, timeout=30) as response:
            page = json.loads(response.read().decode("utf-8"))
        if not page:
            break

        for item in page:
            code = item["code"].lower()
            split_code(code)  # validate before retaining external data
            if code not in seen:
                seen.add(code)
                records.append(
                    {"code": code, "likes": int(item["likes"]), "age": item["date"]}
                )
                if len(records) == count:
                    break
        step += 1

    if len(records) < count:
        raise RuntimeError(f"Color Hunt returned only {len(records)} unique palettes")
    return records


def write_csv(
    records: Iterable[dict],
    output: str | Path,
    timeframe_days: int = ALL_TIME_DAYS,
    scraped_at: str | None = None,
) -> Path:
    """Write feed records as an analysis-ready, reproducible CSV snapshot."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    timestamp = scraped_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    fields = [
        "rank", "code", "color1", "color2", "color3", "color4", "likes", "age",
        "source_url", "sort", "timeframe_days", "scraped_at_utc",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for rank, record in enumerate(records, start=1):
            colors = split_code(record["code"])
            writer.writerow(
                {
                    "rank": rank,
                    "code": record["code"],
                    "color1": colors[0],
                    "color2": colors[1],
                    "color3": colors[2],
                    "color4": colors[3],
                    "likes": int(record["likes"]),
                    "age": record["age"],
                    "source_url": f"https://colorhunt.co/palette/{record['code']}",
                    "sort": "popular",
                    "timeframe_days": timeframe_days,
                    "scraped_at_utc": timestamp,
                }
            )
    return output


def collect(output: str | Path, count: int = 100) -> Path:
    return write_csv(fetch_popular(count=count), output)
