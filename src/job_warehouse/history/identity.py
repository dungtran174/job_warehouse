"""Stable physical-row identity and exact-content fingerprints."""

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

from job_warehouse.history.contract import CONTENT_COLUMNS

Value = str | int | None
HistoryRow = Mapping[str, Value]


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def record_key(file_hash: str, row_index: int) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", file_hash) or row_index < 0:
        raise ValueError("record_key requires a lowercase SHA256 and nonnegative row_index")
    return hashlib.sha256(f"{file_hash}:{row_index}".encode()).hexdigest()


def content_fingerprint(row: HistoryRow) -> str:
    """Hash the 13 original non-ID values, including year, in contract order.

    No trimming, Unicode normalization, null replacement or fuzzy comparison.
    Fingerprints identify candidates, not proven unique vacancies.
    """
    payload = json.dumps(
        [row[column] for column in CONTENT_COLUMNS],
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
