"""Finite grammar: abstain rather than invent units, periods or missing bounds."""

import re
from dataclasses import replace
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from functools import lru_cache
from typing import TypedDict

from job_warehouse.silver.salary.models import Rate, Salary
from job_warehouse.silver.text import normalize_text

NUMBER = r"\d+(?:[.,]\d+)*"
UNIT = r"triệu|nghìn|ngàn|tr|k|m"
AMOUNT = rf"({NUMBER})\s*({UNIT})?"
EXPRESSION = re.compile(rf"{AMOUNT}(?:\s*(-|đến|tới|dưới)\s*{AMOUNT})?")
CURRENCY = re.compile(r"(?<![a-z])(?:vnd|vnđ|usd)(?![a-z])|\bđồng\b|[₫$]|(?<=\d)đ\b")
PERIOD = re.compile(r"/\s*(tháng|tuần|ngày|giờ|month)\b|\b(month)\b")
NEGOTIABLE = (
    "thỏa thuận",
    "thoả thuận",
    "thương lượng",
    "cạnh tranh",
    "negotiable",
    "mức lương thỏa thuận",
    "competitive salary",
    "theo năng lực trao đổi trực tiếp khi phỏng vấn",
    "theo thỏa thuận",
    "lương thỏa thuận",
    "thỏa thuân",
    "tùy năng lực",
)
LOWER = ("từ", "trên", "ít nhất", "tối thiểu")
UPPER = ("lên tới", "lên đến", "tới", "dưới", "upto", "up to", "tối đa")


class _Common(TypedDict):
    currency: str | None
    period: str | None
    flags: tuple[str, ...]
    component: str


def _number(text: str, unit: str | None) -> Decimal:
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", text):
        text = text.replace(".", "").replace(",", "")
    elif re.fullmatch(r"\d+[.,]\d{1,2}", text):
        text = text.replace(",", ".")
    elif not text.isdigit():
        raise ValueError("ambiguous_number")
    multiplier = Decimal(1_000_000 if unit in {"triệu", "tr", "m"} else 1000 if unit else 1)
    return Decimal(text) * multiplier


@lru_cache(maxsize=8192)
def parse_salary(raw: str | None) -> Salary:
    text = normalize_text(raw, short=True).clean
    if text is None:
        return Salary("missing", reason="missing_source")
    text = re.sub(r"[–—−]", "-", text.casefold()).strip()
    if text == "đang cập nhật":
        return Salary("missing", reason="not_updated")
    if any(text.startswith(s) for s in NEGOTIABLE) or text in {
        "you'll love it",
        "you'll surely love it",
    }:
        return Salary("negotiable", reason="no_numeric_offer")
    if not re.search(r"\d", text):
        return Salary("missing", reason="no_numeric_amount")
    if "hoặc" in text:
        return Salary("needs_review", reason="alternative_offers")
    # A '+' starts a variable component. A trailing '++' is also a qualifier.
    main, *extra = text.split("+", 1)
    flags = ["variable_component"] if extra else []
    if "triêu" in main:
        main = main.replace("triêu", "triệu")
        flags.append("observed_unit_typo")
    component = "advertised_income" if main.startswith("thu nhập") else "unspecified"
    if main.startswith(("lc ", "lương cứng")):
        component = "base_salary"
    if re.search(r"\b(net|gross)\b", main):
        flags.append("net" if re.search(r"\bnet\b", main) else "gross")
        main = re.sub(r"\b(net|gross)\b", "", main)
    usd = bool(re.search(r"usd|\$", main))
    vnd = bool(re.search(r"vnd|vnđ|đồng|₫|triệu|nghìn|ngàn|\d\s*(?:tr|k|đ)\b", main))
    if usd and vnd:
        return Salary("needs_review", flags=tuple(flags), reason="currency_conflict")
    currency = "USD" if usd else "VND" if vnd else None
    periods = [a or b for a, b in PERIOD.findall(main)]
    if len(set(periods)) > 1:
        return Salary("needs_review", reason="multiple_periods")
    period = (
        {"tháng": "month", "month": "month", "tuần": "week", "ngày": "day", "giờ": "hour"}.get(
            periods[0]
        )
        if periods
        else "month"
    )
    if not periods:
        flags.append("assumed_month")
    main = PERIOD.sub("", CURRENCY.sub("", main)).strip()
    main = re.sub(r"\s+", " ", main)
    for prefix in ("thu nhập", "lương cứng", "khởi điểm", "lc", "cứng", "cơ bản", "chính thức"):
        if main.startswith(prefix + " "):
            main = main[len(prefix) :].strip()
            break
    prefix = ""
    for word in (*LOWER, *UPPER):
        if main.startswith(word + " "):
            prefix, main = word, main[len(word) :].strip()
            break
    main = re.sub(r"-\s*dưới\s+", "dưới ", main)
    main = re.sub(r"(?:tới|đến)\s*<\s*", "dưới ", main)
    if main.endswith("lương cứng"):
        main = main[: -len("lương cứng")].strip()
        component = "base_salary"
    suffix_lower = main.endswith("trở lên")
    if suffix_lower:
        main = main[: -len("trở lên")].strip()
    match = EXPRESSION.fullmatch(main)
    if match is None:
        return Salary(
            "needs_review",
            currency=currency,
            period=period,
            flags=tuple(flags),
            reason="unsupported_expression",
            component=component,
        )
    if currency is None:
        return Salary(
            "needs_review",
            period=period,
            flags=tuple(flags),
            reason="missing_currency_or_scale",
            component=component,
        )
    first, unit_a, separator, second, unit_b = match.groups()
    # A single unit at the end of a plain range applies to both amounts.
    if unit_a is None and unit_b is not None:
        unit_a = unit_b
    try:
        a = _number(first, unit_a)
        b = _number(second, unit_b) if second is not None else None
    except (ValueError, InvalidOperation):
        return Salary(
            "needs_review",
            currency=currency,
            period=period,
            flags=tuple(flags),
            reason="ambiguous_number",
            component=component,
        )
    common: _Common = dict(
        currency=currency, period=period, flags=tuple(flags), component=component
    )
    if a == 0 and (b is None or b == 0):
        return Salary("zero_placeholder", reason="all_zero", **common)
    if b is not None and (a == 0 or b == 0):
        positive = max(a, b)
        common["flags"] = (*flags, "positive_bound_as_point")
        return Salary(
            "mapped",
            "point",
            positive,
            positive,
            min_inclusive=True,
            max_inclusive=True,
            **common,
        )
    if b is not None:
        if a > b:
            a, b = b, a
            common["flags"] = (*common["flags"], "positive_bounds_reordered")
        if prefix in UPPER or suffix_lower or prefix == "trên":
            return Salary("needs_review", "range", a, b, reason="contradictory_qualifier", **common)
        return Salary(
            "mapped",
            "point" if a == b else "range",
            a,
            b,
            min_inclusive=True,
            max_inclusive=separator != "dưới",
            **common,
        )
    if prefix in UPPER:
        return Salary("mapped", "upper_only", None, a, max_inclusive=prefix != "dưới", **common)
    if prefix in LOWER or suffix_lower:
        return Salary("mapped", "lower_only", a, None, min_inclusive=prefix != "trên", **common)
    return Salary("mapped", "point", a, a, min_inclusive=True, max_inclusive=True, **common)


def convert_salary(parsed: Salary, rate: Rate | None) -> Salary:
    """Do not label USD/hour as VND/month when either conversion is unavailable."""
    if parsed.status != "mapped":
        return parsed
    if parsed.currency == "USD" and rate is None:
        return replace(parsed, status="fx_missing", reason="verified_year_rate_missing")
    with localcontext() as context:
        context.prec = 40
        fx = rate.vnd_per_usd if parsed.currency == "USD" and rate else Decimal(1)
        numerator, denominator = {
            "month": (1, 1),
            "week": (52, 12),
            "day": (26, 1),
            "hour": (208, 1),
            "year": (1, 12),
        }[str(parsed.period)]
        bounds: list[Decimal | None] = []
        for x in (parsed.source_min, parsed.source_max):
            if x is None:
                bounds.append(None)
                continue
            value = x * fx * numerator / denominator
            if parsed.rounding_quantum is not None:
                quantum = Decimal(parsed.rounding_quantum)
                value = (value / quantum).to_integral_value(rounding=ROUND_CEILING) * quantum
            bounds.append(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if any(x is not None and (x <= 0 or x >= Decimal("1e16")) for x in bounds):
        return replace(parsed, status="needs_review", reason="unrepresentable_positive_money")
    flags = list(parsed.flags)
    if parsed.period != "month":
        flags.append("conventional_month_conversion")
    if parsed.rounding_quantum is not None:
        flags.append("owner_ceiling_monthly_amount")
    if parsed.currency == "USD" and rate and rate.provisional:
        flags.append("provisional_ytd_fx")
    if any(x is not None and (x < 1_000_000 or x > 200_000_000) for x in bounds):
        flags.append("amount_review_signal")
    if bounds[0] is not None and bounds[1] is not None and bounds[1] > bounds[0] * 10:
        flags.append("wide_range_signal")
    return replace(
        parsed,
        salary_min=bounds[0],
        salary_max=bounds[1],
        flags=tuple(flags),
        fx_rate=fx if parsed.currency == "USD" else None,
        fx_reference=rate.reference if parsed.currency == "USD" and rate else None,
    )
