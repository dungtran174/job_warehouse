"""Keep source interpretation separate from comparable monetary measures."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Salary:
    status: str
    kind: str = "unknown"
    source_min: Decimal | None = None
    source_max: Decimal | None = None
    currency: str | None = None
    period: str | None = None
    min_inclusive: bool | None = None
    max_inclusive: bool | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    flags: tuple[str, ...] = ()
    reason: str = ""
    component: str = "unspecified"
    fx_rate: Decimal | None = None
    fx_reference: str | None = None
    rounding_quantum: str | None = None
    evidence_column: str | None = None
    evidence_sha256: str | None = None

    @property
    def numeric_eligible(self) -> bool:
        """At least one published VND/month bound; never substitute zero for missing."""
        return self.status == "mapped" and (
            self.salary_min is not None or self.salary_max is not None
        )

    @property
    def midpoint_eligible(self) -> bool:
        """Only two-sided published offers can contribute a midpoint observation."""
        return (
            self.numeric_eligible
            and self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min <= self.salary_max
        )


@dataclass(frozen=True)
class Rate:
    year: int
    vnd_per_usd: Decimal
    period_start: str
    period_end: str
    provisional: bool
    source_url: str
    series: str
    reference: str
