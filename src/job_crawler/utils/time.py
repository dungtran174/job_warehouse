from __future__ import annotations

import re
import unicodedata
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(UTC)


def local_snapshot_date(now: datetime, timezone: str) -> date:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(ZoneInfo(timezone)).date()


def parse_source_date(value: str | None) -> date | None:
    if not value:
        return None
    cleaned = value.strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(cleaned[:10], pattern).date()
        except ValueError:
            continue
    return None


def _ascii_lower(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def estimate_relative_posted(raw: str | None, now: datetime) -> tuple[datetime | None, str]:
    if not raw:
        return None, "unknown"
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    value = _ascii_lower(raw).strip()
    if "hom nay" in value or "vua xong" in value:
        return now, "estimated_day"
    match = re.search(r"(\d+)\s*(gio|hour)", value)
    if match:
        return now - timedelta(hours=int(match.group(1))), "estimated_hour"
    match = re.search(r"(\d+)\s*(ngay|day)", value)
    if match:
        return now - timedelta(days=int(match.group(1))), "estimated_day"
    match = re.search(r"(\d+)\s*(tuan|week)", value)
    if match:
        return now - timedelta(weeks=int(match.group(1))), "estimated_day"
    return None, "unknown"
