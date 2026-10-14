"""S3 results retain decisions and evidence without expanding the posting grain."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Evidence:
    field: str
    rule_id: str
    value: str
    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class Occupation:
    primary: str | None
    candidates: tuple[str, ...]
    source_candidates: tuple[str, ...]
    domains: tuple[str, ...]
    status: str
    method: str
    flags: tuple[str, ...]
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class AddressLink:
    rule_id: str
    place: str
    partial_start: int
    partial_end: int
    complete_start: int
    complete_end: int


@dataclass(frozen=True, slots=True)
class Location:
    places: tuple[str, ...]
    status: str
    group: str
    remote: bool
    nationwide: bool
    foreign: tuple[str, ...]
    flags: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    address_links: tuple[AddressLink, ...] = ()
