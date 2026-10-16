"""Salary meaning, finite grammar and monetary calculations on synthetic values."""

import json
from dataclasses import replace
from decimal import Decimal

import pytest

from job_warehouse.silver.salary.models import Rate
from job_warehouse.silver.salary.parser import convert_salary, parse_salary
from job_warehouse.silver.salary.policy import apply_override, load_rates, owner_overrides


@pytest.mark.parametrize(
    "raw,low,high",
    [
        ("10.000.000 - 15.000.000 VND", "10000000", "15000000"),
        ("10000000 - 15000000 VND MONTH", "10000000", "15000000"),
        ("7.5 - 10 triệu", "7500000", "10000000"),
        ("8 triệu - 12 triệu", "8000000", "12000000"),
        ("12.000.000VNĐ", "12000000", "12000000"),
        ("9,5tr–12tr ₫/tháng", "9500000", "12000000"),
        ("0 - 3.000.000 VND", "3000000", "3000000"),
        ("50.000.000 - 0 VND", "50000000", "50000000"),
        ("50.000.000 - 30.000.000 VND", "30000000", "50000000"),
        ("Trên 10 triệu", "10000000", None),
        ("Từ 10 triệu", "10000000", None),
        ("Dưới 20 triệu", None, "20000000"),
        ("Thu nhập lên đến 20 triệu VND", None, "20000000"),
        ("LC 12.5 triệu VND + Hoa Hồng", "12500000", "12500000"),
        ("9-10 triệu lương cứng", "9000000", "10000000"),
        ("Từ 10 Triệu - Dưới 15 Triệu VNĐ / Tháng", "10000000", "15000000"),
        ("Từ 2 - 4 triệu/tháng + phụ cấp 25k/ngày", "2000000", "4000000"),
        ("30 nghìn/giờ", "6240000", "6240000"),
        ("200 nghìn/ngày", "5200000", "5200000"),
        ("3 triệu/tuần", "13000000", "13000000"),
        ("1 nghìn/tuần", "4333.33", "4333.33"),
        ("25,500 - 50,000 VND/giờ", "5304000", "10400000"),
        ("18.000.000 - 303.000.000 VND", "18000000", "303000000"),
    ],
)
def test_bounds_are_vnd_per_month_without_adding_variable_pay(raw, low, high):
    result = convert_salary(parse_salary(raw), None)
    assert result.status == "mapped"
    assert result.salary_min == (Decimal(low) if low else None)
    assert result.salary_max == (Decimal(high) if high else None)


@pytest.mark.parametrize(
    "raw,status",
    [
        (None, "missing"),
        ("Đang cập nhật", "missing"),
        ("Thỏa thuận", "negotiable"),
        ("0 VND", "zero_placeholder"),
        ("0 - 0 VND", "zero_placeholder"),
        ("0 triệu - 0 triệu", "zero_placeholder"),
        ("100", "needs_review"),
        ("80 - 150", "needs_review"),
        ("VND MONTH", "missing"),
        ("$ 13tr-17tr /tháng", "needs_review"),
        ("-5 triệu", "needs_review"),
        ("10 triệu hoặc 20 triệu", "needs_review"),
        ("Upto $1800 x 14 tháng lương/năm + Thưởng", "needs_review"),
        ("10 triệu/ngày/tháng", "needs_review"),
        ("10.20.300 VND", "needs_review"),
    ],
)
def test_abstention_never_publishes_source_numbers_in_wrong_units(raw, status):
    result = convert_salary(parse_salary(raw), None)
    assert result.status == status
    assert result.salary_min is None and result.salary_max is None


def test_qualifiers_assumptions_and_owner_decisions_are_observable():
    assert parse_salary("Dưới 20 triệu").max_inclusive is False
    assert parse_salary("Từ 10 Triệu - Dưới 15 Triệu VNĐ / Tháng").max_inclusive is False
    assert parse_salary("Trên 10 triệu").min_inclusive is False
    assert "assumed_month" in parse_salary("10 triệu").flags
    assert "assumed_month" not in parse_salary("10 triệu/tháng").flags
    assert "positive_bounds_reordered" in parse_salary("50 - 30 triệu").flags
    assert "positive_bound_as_point" in parse_salary("0 - 3 triệu").flags
    assert parse_salary("Thu nhập lên đến 20 triệu").component == "advertised_income"
    result = convert_salary(parse_salary("18 - 303 triệu"), None)
    assert "amount_review_signal" in result.flags
    assert "wide_range_signal" in result.flags


def test_usd_requires_explicit_rate_and_applies_fx_and_period_once():
    source = parse_salary("1,200 USD")
    assert source.source_min == 1200
    assert convert_salary(source, None).status == "fx_missing"
    rate = Rate(
        2026,
        Decimal("25000"),
        "2026-01-01",
        "2026-09-30",
        True,
        "https://example.test/fx",
        "synthetic",
        "fixture",
    )
    result = convert_salary(source, rate)
    assert result.salary_min == 30_000_000
    assert result.fx_reference == "fixture"
    assert "provisional_ytd_fx" in result.flags
    assert convert_salary(parse_salary("10 USD/giờ"), rate).salary_min == 52_000_000
    assert convert_salary(parse_salary("5 triệu"), rate).salary_min == 5_000_000
    assert (
        convert_salary(source, replace(rate, vnd_per_usd=Decimal("1e20"))).status == "needs_review"
    )


def test_every_owner_exception_matches_raw_and_runs_before_period_multiplication():
    assert len(owner_overrides()) == 112
    rate = Rate(
        2026,
        Decimal("25179"),
        "2026-01-01",
        "2026-08-31",
        True,
        "https://example.test/fx",
        "synthetic",
        "fixture",
    )
    for ident, policy in owner_overrides().items():
        if policy.evidence_column is not None:
            continue  # Benefits-backed decisions have separate synthetic evidence tests.
        result = apply_override(ident, policy.expected_raw)
        assert result is not None
        converted = convert_salary(result, rate)
        multiplier = rate.vnd_per_usd if policy.currency == "USD" else Decimal(1)
        assert converted.salary_min == (
            policy.amount * multiplier if policy.amount is not None else None
        )
        assert converted.salary_max == (
            policy.maximum * multiplier if policy.maximum is not None else None
        )
        with pytest.raises(ValueError, match="raw mismatch"):
            apply_override(ident, "different source")
    assert apply_override(42, "10 triệu/giờ") is None
    result = convert_salary(apply_override(43531, "$ 13tr-17tr /tháng"), None)
    assert (result.salary_min, result.salary_max) == (13_000_000, 17_000_000)


@pytest.mark.parametrize(
    "ident,raw,minimum,maximum",
    [
        (50951, "9.000.000 - 12.000.000", 9_000_000, 12_000_000),
        (51109, "10,000,000 - 18,000,000", 10_000_000, 18_000_000),
        (51338, "8.000.000", 8_000_000, 8_000_000),
        (50962, "Thu nhập 6.000.000 - 15.000.000", 6_000_000, 10_000_000),
        (45010, "Từ 15-20 triệu VND hoặc thỏa thuận tùy theo kinh nghiệm", 10_000_000, 15_000_000),
        (50643, "Thu nhập lên đến 20 triệu Lương thỏa thuận + thưởng dự án", None, 20_000_000),
        (51387, "2.000.000 + Thưởng", 2_000_000, 2_000_000),
    ],
)
def test_review_resolutions_apply_only_to_approved_ids(ident, raw, minimum, maximum):
    result = convert_salary(apply_override(ident, raw), None)
    assert (result.salary_min, result.salary_max) == (minimum, maximum)
    # The bare-number grammar is still not permitted to infer units for other IDs.
    assert parse_salary("100").status == "needs_review"


def test_owner_package_override_is_upper_monthly_usd_not_fourteen_times_salary():
    parsed = apply_override(108256, "Upto $1800 x 14 tháng lương/năm + Thưởng")
    assert parsed.currency == "USD" and parsed.period == "month"
    assert parsed.source_min is None and parsed.source_max == 1800
    assert "owner_package_as_monthly_upper" in parsed.flags
    assert convert_salary(parsed, None).status == "fx_missing"
    rate = Rate(
        2026,
        Decimal("25179"),
        "2026-01-01",
        "2026-08-31",
        True,
        "https://example.test/fx",
        "synthetic",
        "fixture",
    )
    normalized = convert_salary(parsed, rate)
    assert normalized.salary_min is None and normalized.salary_max == 45_322_200


def rate_document():
    return {
        "rates": [
            {
                "year": 2026,
                "vnd_per_usd": "25000",
                "period_start": "2026-01-01",
                "period_end": "2026-09-30",
                "provisional": True,
                "source_url": "https://example.test/fx",
                "series": "fixture",
                "reference": "fixture-rate",
                "approved": True,
            }
        ]
    }


def test_rates_are_explicit_and_never_fall_back_to_another_year(tmp_path):
    path = tmp_path / "fx.json"
    path.write_text(json.dumps(rate_document()))
    rates, _ = load_rates(path)
    assert rates[2026].vnd_per_usd == 25000
    assert 2025 not in rates
    assert load_rates(None)[0] == {}


@pytest.mark.parametrize(
    "field,value",
    [
        ("approved", False),
        ("provisional", False),
        ("vnd_per_usd", "NaN"),
        ("vnd_per_usd", "0"),
        ("period_start", "2026-02-01"),
        ("series", ""),
        ("period_end", "2025-12-31"),
    ],
)
def test_unverified_or_mislabeled_rates_are_rejected(tmp_path, field, value):
    document = rate_document()
    document["rates"][0][field] = value
    path = tmp_path / "fx.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        load_rates(path)


@pytest.mark.parametrize(
    "raw,numeric,midpoint",
    [
        ("10 - 15 triệu", True, True),
        ("10 triệu", True, True),
        ("Từ 10 triệu", True, False),
        ("Dưới 20 triệu", True, False),
        ("Thỏa thuận", False, False),
        ("1000 USD", False, False),
        ("0 VND", False, False),
    ],
)
def test_comparison_eligibility_preserves_one_bound_offers(raw, numeric, midpoint):
    result = convert_salary(parse_salary(raw), None)
    assert result.numeric_eligible is numeric
    assert result.midpoint_eligible is midpoint
