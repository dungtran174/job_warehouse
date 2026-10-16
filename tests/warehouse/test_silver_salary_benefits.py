"""Owner-reviewed benefits are guarded by ID/raw/hash, never extracted automatically."""

from dataclasses import replace
from decimal import Decimal
from hashlib import sha256

import pytest

import job_warehouse.silver.salary.policy as policy
from job_warehouse.silver.salary.models import Salary
from job_warehouse.silver.salary.parser import convert_salary, parse_salary

APPROVED = [
    (653, 3, 5),
    (1148, 80, 150),
    (1310, 17, 42),
    (1469, 17, 59),
    (2402, 50, 300),
    (5489, 10, 25),
    (6446, None, 25),
    (7263, 10, 17),
    (9087, 15, 25),
    (9267, None, 16),
    (9524, 7, None),
    (9827, 2, 3),
    (9830, 2, "3.5"),
    (9894, 5, 7),
    (9903, 2, 3),
    (10296, 6, None),
    (10297, 4, None),
    (10366, 20, None),
    (10939, 7, 15),
    (11112, 7, None),
    (11195, 5, 15),
    (11198, 8, 16),
    (11201, "5.5", "11.5"),
    (11205, "5.5", 18),
    (11214, "5.5", "11.5"),
    (11246, 18, 18),
    (11420, None, 16),
    (11627, 30, 30),
    (11685, 9, 13),
    (11686, 9, 13),
    (12328, 8, 10),
    (12737, 3, 6),
    (13314, None, 1),
    (13341, None, 15),
    (13842, 8, 8),
    (13845, 8, 8),
    (13863, 12, 24),
    (13874, 8, 15),
    (13919, 6, 15),
    (13934, "5.5", 18),
    (13937, "5.5", 18),
    (13962, "6.5", "7.5"),
    (13979, "5.5", 18),
    (14146, 7, 9),
    (14548, 6, None),
    (16700, 30, 45),
    (16726, 100, 250),
]
NULL_IDS = [
    292,
    1398,
    1448,
    1794,
    1986,
    2000,
    4104,
    4491,
    5242,
    5577,
    8025,
    9095,
    9511,
    9521,
    11344,
    11954,
    12172,
    12701,
    15611,
    17285,
    50613,
    13872,
    1152,
    3987,
    6011,
    10243,
    16518,
    16623,
    2354,
    12471,
    16620,
]


def synthetic_decision(monkeypatch, ident):
    original = policy.owner_overrides()[ident]
    benefits = "Synthetic reviewed compensation text"
    decision = replace(
        original, expected_raw="100", evidence_sha256=sha256(benefits.encode()).hexdigest()
    )
    monkeypatch.setattr(policy, "owner_overrides", lambda: {ident: decision})
    return benefits


@pytest.mark.parametrize("ident,minimum,maximum", APPROVED)
def test_all_positive_owner_decisions_match_requested_bounds(monkeypatch, ident, minimum, maximum):
    benefits = synthetic_decision(monkeypatch, ident)
    parsed = policy.apply_override(ident, "100", benefits=benefits)
    result = convert_salary(parsed, None)
    assert result.status == "mapped"
    expected = [None if x is None else Decimal(str(x)) * 1_000_000 for x in (minimum, maximum)]
    assert [result.salary_min, result.salary_max] == expected
    assert result.evidence_column == "benefits"
    assert result.evidence_sha256 == sha256(benefits.encode()).hexdigest()
    # A new posting with identical money text is not covered by this owner decision.
    assert policy.apply_override(999999, "100", benefits=benefits) is None
    assert parse_salary("100").status == "needs_review"


@pytest.mark.parametrize("ident", NULL_IDS)
def test_all_owner_null_decisions_keep_evidence_without_money(monkeypatch, ident):
    benefits = synthetic_decision(monkeypatch, ident)
    result = policy.apply_override(ident, "100", benefits=benefits)
    assert result.status == "owner_unresolved"
    assert result.salary_min is None and result.salary_max is None
    assert result.evidence_column == "benefits"


def test_owner_decision_requires_both_source_text_and_reviewed_benefits(monkeypatch):
    benefits = synthetic_decision(monkeypatch, 653)
    with pytest.raises(ValueError, match="benefits evidence mismatch"):
        policy.apply_override(653, "100", benefits=benefits + " changed")
    with pytest.raises(ValueError, match="benefits evidence mismatch"):
        policy.apply_override(653, "100")
    with pytest.raises(ValueError, match="raw mismatch"):
        policy.apply_override(653, "200", benefits=benefits)


def test_null_benefits_are_distinct_from_empty_text(monkeypatch):
    entry = replace(policy.owner_overrides()[3987], expected_raw="800", evidence_sha256=None)
    monkeypatch.setattr(policy, "owner_overrides", lambda: {3987: entry})
    assert policy.apply_override(3987, "800", benefits=None).status == "owner_unresolved"
    with pytest.raises(ValueError, match="benefits evidence mismatch"):
        policy.apply_override(3987, "800", benefits="")


@pytest.mark.parametrize(
    "annual,expected",
    [
        ("200000000", "17000000"),
        ("500000000", "42000000"),
        ("700000000", "59000000"),
        ("120000000", "10000000"),
        ("300000000", "25000000"),
    ],
)
def test_year_division_ceil_does_not_inflate_exact_integer_results(annual, expected):
    source = Salary(
        "mapped",
        "point",
        Decimal(annual),
        Decimal(annual),
        "VND",
        "year",
        rounding_quantum="1000000",
    )
    result = convert_salary(source, None)
    assert result.salary_min == result.salary_max == Decimal(expected)
    assert "owner_ceiling_monthly_amount" in result.flags
