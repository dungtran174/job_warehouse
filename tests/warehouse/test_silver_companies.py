"""Company source spellings collapse only after text cleanup and casefold."""

import pytest

from job_warehouse.silver.companies import (
    canonical_company_name,
    company_spelling,
    preferred_company_names,
)


def test_most_frequent_source_spelling_wins_without_rewriting_its_case():
    values = ["CÔNG TY ABC", "Công ty ABC", "CÔNG TY ABC", "Công ty XYZ"]
    mapping = preferred_company_names(values)
    assert mapping["công ty abc"] == "CÔNG TY ABC"
    assert canonical_company_name("công ty abc", mapping) == "CÔNG TY ABC"
    assert preferred_company_names(reversed(values)) == mapping
    assert preferred_company_names(mapping.values()) == mapping


def test_ties_and_unicode_cleanup_are_deterministic():
    values = ["Công ty A ", "Công ty A", "CÔNG TY A", "công ty B", "CÔNG TY B"]
    mapping = preferred_company_names(values)
    assert mapping["công ty a"] == "Công ty A"
    assert mapping["công ty b"] == min("công ty B", "CÔNG TY B")
    assert preferred_company_names(reversed(values)) == mapping


def test_legal_forms_accents_punctuation_and_branches_are_not_aliases():
    names = ["Công ty ABC", "Cty ABC", "Công ty ABC - Hà Nội", "Cong ty ABC", "Công ty A.B.C"]
    assert len(preferred_company_names(names)) == len(names)


@pytest.mark.parametrize("value", [None, "", " \t ", ".", " . "])
def test_missing_and_placeholder_names_do_not_create_a_company(value):
    assert company_spelling(value) is None
    assert preferred_company_names([value]) == {}


def test_absent_catalog_entry_or_semantic_change_is_rejected():
    with pytest.raises(ValueError, match="absent"):
        canonical_company_name("Công ty A", {})
    with pytest.raises(ValueError, match="more than letter case"):
        canonical_company_name("Công ty A", {"công ty a": "Công ty B"})
