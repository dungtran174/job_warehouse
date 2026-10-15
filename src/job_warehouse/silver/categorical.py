"""Reviewed finite source-label mappings, with explicit unknown/partial results."""

import csv
from functools import lru_cache
from importlib.resources import files
from typing import Literal

from job_warehouse.silver.models import Category, JobType, Position
from job_warehouse.silver.text import normalize_text

SOURCE_LABEL_FIELDS = {
    "education_level": "education_label_clean",
    "job_type": "job_type_label_clean",
    "job_position": "position_label_clean",
}


def lookup_key(value: str) -> str:
    return value.casefold()


@lru_cache
def mapping(name: str) -> dict[str, dict[str, str]]:
    resource = files("job_warehouse.silver").joinpath(f"mappings/{name}.csv")
    with resource.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        key = (row["label"] if "label" in row else row["context"]).casefold()
        if key in result:
            raise ValueError(f"Duplicate mapping label: {name}")
        if "display_label" in row and row["display_label"].casefold() != key:
            raise ValueError(f"Display label changes source meaning: {name}")
        result[key] = row
    return result


@lru_cache(maxsize=4096)
def canonical_label(
    field: Literal["education_level", "job_type", "job_position"], value: str | None
) -> str | None:
    """Choose one source-label spelling; never infer or merge different meanings."""
    label = normalize_text(value, short=True).clean
    if label is None:
        return None
    entries = mapping(
        {"education_level": "education", "job_type": "job_type", "job_position": "position"}[field]
    )

    def render(token: str) -> str:
        row = entries.get(token.casefold())
        return (row.get("display_label") or row["label"]) if row else token

    if field == "job_type":
        # Keep the source's order and all labels, including Remote and unknown tokens.
        return ", ".join(render(token.strip()) for token in label.split(","))
    return render(label)


@lru_cache(maxsize=4096)
def education(value: str | None) -> Category:
    label = normalize_text(value, short=True).clean
    if label is None:
        return Category(None, "missing")
    row = mapping("education").get(label.casefold())
    return Category(row["category"] or None, row["status"]) if row else Category(None, "unmapped")


@lru_cache(maxsize=4096)
def job_type(value: str | None) -> JobType:
    label = normalize_text(value, short=True).clean
    if label is None:
        return JobType((), "unknown", None, None, "missing")
    entries = mapping("job_type")
    types: set[str] = set()
    arrangement = None
    shift = None
    unknown: list[str] = []
    statuses: set[str] = set()
    for token in label.split(","):
        token = token.strip()
        row = entries.get(token.casefold())
        if row is None:
            unknown.append(token)
            continue
        statuses.add(row["status"])
        if row["category"]:
            types.add(row["category"])
        if row["work_arrangement"]:
            arrangement = row["work_arrangement"]
        if row["shift_work"] == "true":
            shift = True
    known = bool(types or arrangement or shift)
    status = "partial" if unknown and known else "unmapped" if unknown else "mapped"
    if known and statuses - {"mapped"}:
        status = "partial"
    if not known and not unknown:
        status = next(iter(statuses)) if len(statuses) == 1 else "ambiguous"
    group = "multiple" if len(types) > 1 else next(iter(types)) if types else "unknown"
    return JobType(tuple(sorted(types)), group, arrangement, shift, status, tuple(unknown))


@lru_cache(maxsize=4096)
def position(value: str | None) -> Position:
    label = canonical_label("job_position", value)
    if label is None:
        return Position(None, (), (), (), "missing")
    row = mapping("position").get(label.casefold())
    if row is None:
        return Position(label, (), (), (), "unmapped")
    return Position(
        label,
        tuple(filter(None, row["roles"].split("|"))),
        tuple(filter(None, row["seniorities"].split("|"))),
        tuple(filter(None, row["management"].split("|"))),
        row["status"],
    )
