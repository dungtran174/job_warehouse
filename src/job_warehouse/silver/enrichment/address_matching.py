"""Bounded source-address identity checks; no geocoding or persisted addresses."""

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AddressKey:
    house: str
    street: str
    units: tuple[tuple[str, str], ...]
    qualifiers: tuple[str, ...]
    normalized: str


ABBREVIATIONS = [
    (re.compile(r"(?<!\w)p(?:\.|\s+|(?=\d))", re.I), "phường "),
    (re.compile(r"(?<!\w)q(?:\.|\s+|(?=\d))", re.I), "quận "),
    (re.compile(r"(?<!\w)ql(?:\.|\s+|(?=\d))", re.I), "quốc lộ "),
    (re.compile(r"(?<!\w)số nhà(?!\w)", re.I), "số"),
]
NUMBER = re.compile(r"(?<!\w)(?:số\s*)?(\d+[a-z]?(?:[/\-]\d+[a-z]?)*)(?!\w)", re.I)
NON_HOUSE_PREFIX = re.compile(
    r"(?:tầng|lầu|floor|phường|quận|xã|huyện|ấp|thôn|tòa|toà|lô|khu phố|"
    r"ngõ|hẻm|quốc lộ|đường số)\s*$",
    re.I,
)
ROAD_PREFIX = re.compile(r"^(?:đường(?: số)?|phố|ngõ|hẻm|quốc lộ|street)\s*", re.I)
FIELD_BOUNDARY = re.compile(r",|\s+[-–—]\s+|(?<!\w)(?:phường|quận|xã|huyện|ấp|thôn)(?!\w)")
UNITS = re.compile(r"(?<!\w)(phường|quận|xã|huyện|ấp|thôn)\s+(.+?)(?=,|\s+[-–—]\s+|$)", re.I)


def _normalize(text: str) -> str:
    text = text.casefold().strip()
    text = re.sub(r"(?<!\w)no\.\s*(?=\d)", "số ", text)
    text = re.sub(r"(?<!\w)(\d+[a-z]?)\s+street(?!\w)", r"đường \1", text)
    for pattern, value in ABBREVIATIONS:
        text = pattern.sub(value, text)
    text = text.replace("hoà", "hòa").replace("hoá", "hóa")
    return " ".join(text.split()).strip(" ,.-")


def _units(text: str) -> dict[str, str] | None:
    if re.search(r",\s*phương\s+", _normalize(text)):
        # An unrecognized possible admin marker cannot prove matching units.
        return None
    units: dict[str, str] = {}
    for match in UNITS.finditer(_normalize(text)):
        kind, value = match.group(1), match.group(2).strip(" ,.-")
        if value.isdecimal():
            value = str(int(value))
        if kind in units and units[kind] != value:
            return None
        units[kind] = value
    return units


def compatible_units(left: str, right: str) -> bool:
    """Even exact prefixes must not bypass mutually contradictory units."""
    a, b = _units(left), _units(right)
    return a is not None and b is not None and all(a[k] == b[k] for k in a.keys() & b.keys())


def address_key(text: str) -> AddressKey | None:
    """Require one unambiguous house/street pair; compare supplied admin names."""
    text = _normalize(text)
    keys: set[tuple[str, str]] = set()
    house_fields: set[int] = set()
    for match in NUMBER.finditer(text):
        preceding_field = re.split(r",|\s+[-–—]\s+", text[: match.start()])[-1].strip()
        if preceding_field and not match.group().startswith("số"):
            continue
        if NON_HOUSE_PREFIX.search(text[max(0, match.start() - 30) : match.start()]):
            continue
        tail = text[match.end() :].lstrip()
        separated_street = tail.startswith(",")
        if tail.startswith(","):
            tail = tail[1:].lstrip()
            if not ROAD_PREFIX.search(tail):
                continue
        boundary = FIELD_BOUNDARY.search(tail)
        street = tail[: boundary.start()] if boundary else tail
        explicit_road = bool(ROAD_PREFIX.search(street))
        street = re.sub(r"(?<!\w)(?:đường(?: số)?|phố|street)(?!\w)", " ", street)
        street = " ".join(street.split()).strip(" ,.-")
        if not street or not (
            any(c.isalpha() for c in street) or (explicit_road and street.isdecimal())
        ):
            continue
        if not explicit_road and len(re.findall(r"[^\W\d_]+", street)) < 2:
            continue
        keys.add((match.group(1), street))
        house_fields.add(text[: match.start()].count(","))
        if separated_street:
            house_fields.add(text[: match.start()].count(",") + 1)
    if len(keys) != 1:
        return None
    units = _units(text)
    if units is None:
        return None
    house, street = next(iter(keys))
    qualifiers = tuple(
        part.strip()
        for i, part in enumerate(text.split(","))
        if i not in house_fields
        and part.strip()
        and not re.match(r"\s*(?:tầng|lầu|floor|khu phố|phường|quận|xã|huyện|ấp|thôn)\b", part)
    )
    return AddressKey(house, street, tuple(sorted(units.items())), qualifiers, text)


def same_address(left: AddressKey | None, right: AddressKey | None) -> bool:
    if left is None or right is None or (left.house, left.street) != (right.house, right.street):
        return False
    a, b = dict(left.units), dict(right.units)
    return all(a[kind] == b[kind] for kind in a.keys() & b.keys()) and all(
        value in set(b.values()) | set(right.qualifiers) for value in left.qualifiers
    )
