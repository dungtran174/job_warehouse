"""Typed, immutable normalization results; no database or crawler dependencies."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class TextResult:
    clean: str | None
    status: str
    flags: tuple[str, ...] = ()
    decode_depth: int = 0


@dataclass(frozen=True, slots=True)
class Category:
    category: str | None
    status: str


@dataclass(frozen=True, slots=True)
class JobType:
    employment_types: tuple[str, ...]
    group: str
    work_arrangement: str | None
    shift_work: bool | None
    status: str
    unmapped: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Position:
    label: str | None
    roles: tuple[str, ...]
    seniorities: tuple[str, ...]
    management: tuple[str, ...]
    status: str


@dataclass(frozen=True, slots=True)
class Experience:
    # Months retain exact decimal source amounts; year display may be rounded.
    min_months: Decimal | None = None
    max_months: Decimal | None = None
    min_inclusive: bool | None = None
    max_inclusive: bool | None = None
    kind: str = "unknown"
    group: str = "unknown"
    status: str = "unmapped"
    source_unit: str | None = None
    source_min: str | None = None
    source_max: str | None = None

    def years(self, value: Decimal | None) -> Decimal | None:
        return None if value is None else (value / 12).quantize(Decimal("0.000001"))


@dataclass(frozen=True, slots=True)
class Claim:
    attribute: str
    start: int
    end: int
    context_start: int
    context_end: int
    context: str
    rule_id: str
    options: tuple[str, ...] = ()
    relation: str | None = None
    qualification: str | None = None
    experience: Experience | None = None
    scope: str | None = None
    scope_text: str | None = None
    confidence: str = "high"
    status: str = "accepted"
    reasons: tuple[str, ...] = ("explicit_phrase",)
    logic: str = "single"


@dataclass(frozen=True, slots=True)
class Inference:
    education_options: tuple[str, ...] = ()
    education_relation: str | None = None
    education_status: str = "not_mentioned"
    experience: Experience | None = None
    experience_status: str = "not_mentioned"
    claims: tuple[Claim, ...] = ()
