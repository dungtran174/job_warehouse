from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

CONTENT_HASH_FIELDS = (
    "job_title",
    "company_name",
    "salary_raw",
    "location_raw",
    "job_description",
    "candidate_requirements",
    "benefits",
    "application_deadline_raw",
)


def normalize_for_hash(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    if isinstance(value, Mapping):
        return {str(key): normalize_for_hash(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [normalize_for_hash(item) for item in value]
    return value


def stable_hash(payload: Mapping[str, Any]) -> str:
    normalized = normalize_for_hash(payload)
    serialized = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def job_content_hash(payload: Mapping[str, Any]) -> str:
    return stable_hash({field: payload.get(field) for field in CONTENT_HASH_FIELDS})
