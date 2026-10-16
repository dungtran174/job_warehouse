"""Explicit owner exceptions and a local, reviewable exchange-rate registry."""

import csv
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from typing import Any, TypedDict

from job_warehouse.history.identity import file_sha256
from job_warehouse.silver.salary.models import Rate, Salary


class _Evidence(TypedDict):
    flags: tuple[str, ...]
    reason: str
    evidence_column: str | None
    evidence_sha256: str | None


@dataclass(frozen=True)
class Override:
    expected_raw: str
    action: str
    amount: Decimal | None
    maximum: Decimal | None
    currency: str
    flags: tuple[str, ...]
    reference: str
    period: str = "month"
    rounding_quantum: str | None = None
    evidence_column: str | None = None
    evidence_sha256: str | None = None


@lru_cache(maxsize=1)
def owner_overrides() -> dict[int, Override]:
    text = files("job_warehouse.silver.salary").joinpath("owner_overrides.csv").read_text()
    result = {}
    for row in csv.DictReader(text.splitlines()):
        ident = int(row["id"])
        amount = Decimal(row["source_min"]) if row["source_min"] else None
        maximum = Decimal(row["source_max"]) if row["source_max"] else None
        action = row["action"]
        if (
            ident in result
            or action not in {"point", "range", "upper_only", "lower_only", "unresolved"}
            or row["currency"] not in {"VND", "USD"}
            or row["period"] not in {"month", "year"}
            or row["rounding_quantum"] not in {"", "1", "1000000"}
            or (row["period"] == "year" and not row["rounding_quantum"])
            or row["evidence_column"] not in {"", "benefits"}
        ):
            raise ValueError("Invalid salary owner policy")
        if (
            any(x is not None and (not x.is_finite() or x <= 0) for x in (amount, maximum))
            or (action == "unresolved" and (amount is not None or maximum is not None))
            or (action == "upper_only" and (amount is not None or maximum is None))
            or (action == "lower_only" and (amount is None or maximum is not None))
            or (
                action in {"point", "range"}
                and (
                    amount is None
                    or maximum is None
                    or maximum < amount
                    or (action == "point" and amount != maximum)
                )
            )
        ):
            raise ValueError("Invalid owner salary amount")
        result[ident] = Override(
            row["expected_raw"],
            action,
            amount,
            maximum,
            row["currency"],
            tuple(row["flags"].split(";")),
            row["decision_reference"],
            row["period"],
            row["rounding_quantum"] or None,
            row["evidence_column"] or None,
            row["evidence_sha256"] or None,
        )
    return result


def apply_override(ident: int, raw: str | None, *, benefits: str | None = None) -> Salary | None:
    override = owner_overrides().get(ident)
    if override is None:
        return None
    if raw != override.expected_raw:
        raise ValueError(f"Owner salary override raw mismatch for ID {ident}")
    if override.evidence_column == "benefits":
        observed = sha256(benefits.encode()).hexdigest() if benefits is not None else None
        if observed != override.evidence_sha256:
            raise ValueError(f"Owner salary benefits evidence mismatch for ID {ident}")
    common: _Evidence = dict(
        flags=override.flags,
        reason=override.reference,
        evidence_column=override.evidence_column,
        evidence_sha256=override.evidence_sha256,
    )
    if override.action == "unresolved":
        return Salary("owner_unresolved", **common)
    return Salary(
        "mapped",
        override.action,
        override.amount,
        override.maximum,
        override.currency,
        override.period,
        True if override.amount is not None else None,
        True if override.maximum is not None else None,
        rounding_quantum=override.rounding_quantum,
        **common,
    )


def load_rates(path: Path | None) -> tuple[dict[int, Rate], dict[str, Any]]:
    """No network calls or latest-rate fallbacks during a reproducible offline run."""
    if path is None:
        return {}, {"status": "pending_verified_rates", "rates": []}
    document = json.loads(path.read_text())
    if "source_pdf" in document and file_sha256(Path(document["source_pdf"])) != document.get(
        "source_pdf_sha256"
    ):
        raise ValueError("FX source PDF SHA mismatch")
    result: dict[int, Rate] = {}
    for row in document["rates"]:
        year = row["year"]
        start, end = date.fromisoformat(row["period_start"]), date.fromisoformat(row["period_end"])
        value = Decimal(str(row["vnd_per_usd"]))
        if (
            type(year) is not int
            or year in result
            or start != date(year, 1, 1)
            or end.year != year
            or end < start
            or not value.is_finite()
            or value <= 0
            or type(row["provisional"]) is not bool
            or row["provisional"] != (end != date(year, 12, 31))
            or not row["source_url"].startswith("https://")
            or not row["series"]
            or not row["reference"]
            or row.get("approved") is not True
            or (document.get("as_of") is not None and end > date.fromisoformat(document["as_of"]))
        ):
            raise ValueError("Invalid or unapproved salary FX rate")
        result[year] = Rate(
            year,
            value,
            row["period_start"],
            row["period_end"],
            row["provisional"],
            row["source_url"],
            row["series"],
            row["reference"],
        )
    if len({(r.source_url.split("/")[2], r.series) for r in result.values()}) > 1:
        raise ValueError("FX rates must share one source and rate series")
    return result, document
