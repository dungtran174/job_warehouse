"""Full-match experience grammar; preserve open bounds and exact source units."""

import re
from decimal import Decimal
from functools import lru_cache

from job_warehouse.silver.models import Experience
from job_warehouse.silver.text import normalize_text

NUMBER = r"\d+(?:[.,]\d+)?"
UNIT = r"(?:năm|tháng)"
EXPRESSION = (
    rf"(?:(?:ít nhất|tối thiểu|không dưới|từ|trên|hơn|dưới|lên đến|>=|<=|>|<)\s*)?"
    rf"(?:{NUMBER}\s*{UNIT}\s*(?:[-–—]|đến|tới)\s*{NUMBER}\s*{UNIT}|"
    rf"{NUMBER}(?:\s*(?:[-–—]|đến|tới)\s*{NUMBER})?\s*{UNIT})"
    r"(?:\s*(?:trở lên|trở xuống))?"
)
MIXED_RANGE = re.compile(
    rf"(?:từ\s+)?({NUMBER})\s*({UNIT})\s*(?:[-–—]|đến|tới)\s*({NUMBER})\s*({UNIT})"
)
RANGE = re.compile(rf"(?:từ\s+)?({NUMBER})\s*(?:[-–—]|đến|tới)\s*({NUMBER})\s*({UNIT})")
POINT = re.compile(rf"({NUMBER})\s*({UNIT})")
BOUND = re.compile(
    rf"(ít nhất|tối thiểu|không dưới|từ|trên|hơn|dưới|lên đến|>=|<=|>|<)?\s*"
    rf"({NUMBER})\s*({UNIT})(?:\s*(trở lên|trở xuống))?"
)


def bucket(low: Decimal | None, high: Decimal | None, high_inclusive: bool | None) -> str:
    # Canonical month boundaries, not inferred exact applicant experience.
    for left, right, name in [(0, 12, "lt_1"), (12, 36, "1_lt_3"), (36, 60, "3_lt_5")]:
        if (
            low is not None
            and low >= left
            and high is not None
            and (high < right or (high == right and high_inclusive is False))
        ):
            return name
    if low is not None and low >= 60:
        return "ge_5"
    return "range_crossing"


@lru_cache(maxsize=4096)
def parse_experience(value: str | None) -> Experience:
    text = normalize_text(value, short=True).clean
    if text is None:
        return Experience(status="missing")
    text = text.casefold()
    text = re.sub(r"\s+kinh nghiệm$", "", text).strip()
    if text in {"không", "chưa xác định", "chưa cập nhật"}:
        return Experience(status="ambiguous_literal" if text == "không" else "unknown")
    if text in {"không yêu cầu kinh nghiệm", "không yêu cầu", "không cần"}:
        return Experience(kind="no_requirement", group="no_requirement", status="no_requirement")
    if text in {"yêu cầu ứng viên có", "có", "yêu cầu"}:
        return Experience(
            kind="required_unspecified", group="required_unspecified", status="mapped"
        )
    low: Decimal | None
    high: Decimal | None
    if mixed := MIXED_RANGE.fullmatch(text):
        if any(Decimal(mixed[i].replace(",", ".")) >= Decimal("1000000000") for i in [1, 3]):
            return Experience(status="invalid_bounds")
        low = Decimal(mixed[1].replace(",", ".")) * (12 if mixed[2] == "năm" else 1)
        high = Decimal(mixed[3].replace(",", ".")) * (12 if mixed[4] == "năm" else 1)
        if low > high:
            return Experience(status="invalid_bounds")
        return Experience(
            min_months=low,
            max_months=high,
            min_inclusive=True,
            max_inclusive=True,
            kind="range",
            group=bucket(low, high, True),
            status="mapped",
            source_unit="mixed",
            source_min=f"{mixed[1]} {mixed[2]}",
            source_max=f"{mixed[3]} {mixed[4]}",
        )
    match = RANGE.fullmatch(text)
    if match:
        low, high = (Decimal(match[i].replace(",", ".")) for i in (1, 2))
        unit = match[3]
        kind, low_closed, high_closed = "range", True, True
    elif match := POINT.fullmatch(text):
        low = high = Decimal(match[1].replace(",", "."))
        unit, kind, low_closed, high_closed = match[2], "stated_point", True, True
    elif match := BOUND.fullmatch(text):
        prefix, number, unit, suffix = match.groups()
        if not prefix and not suffix:
            return Experience(status="unmapped")
        if suffix == "trở xuống" and prefix in {
            "trên",
            "hơn",
            ">",
            "ít nhất",
            "tối thiểu",
            "không dưới",
            "từ",
            ">=",
        }:
            return Experience(status="ambiguous")
        if (
            prefix in {"trên", "hơn", ">", "ít nhất", "tối thiểu", "không dưới", "từ", ">="}
            or suffix == "trở lên"
        ):
            if prefix in {"dưới", "lên đến", "<", "<="}:
                return Experience(status="ambiguous")
            low, high = Decimal(number.replace(",", ".")), None
            kind, low_closed, high_closed = "lower_bound", prefix not in {"trên", "hơn", ">"}, None
        else:
            low, high = Decimal(0), Decimal(number.replace(",", "."))
            kind, low_closed, high_closed = "upper_bound", True, prefix not in {"dưới", "<"}
    else:
        return Experience(status="unmapped")
    if (low is not None and low >= Decimal("1000000000")) or (
        high is not None and high >= Decimal("1000000000")
    ):
        return Experience(status="invalid_bounds")
    if low is not None and high is not None and low > high:
        return Experience(status="invalid_bounds")
    source_low, source_high = (
        str(low) if low is not None else None,
        str(high) if high is not None else None,
    )
    multiplier = 12 if unit == "năm" else 1
    low, high = (
        low * multiplier if low is not None else None,
        high * multiplier if high is not None else None,
    )
    return Experience(
        low,
        high,
        low_closed,
        high_closed,
        kind,
        bucket(low, high, high_closed),
        "mapped",
        "year" if unit == "năm" else "month",
        source_low,
        source_high,
    )
