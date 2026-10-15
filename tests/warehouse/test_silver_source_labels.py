"""Canonical source spellings without semantic merging or inferred replacements."""

import pytest

from job_warehouse.history.contract import COLUMNS
from job_warehouse.silver.categorical import canonical_label, mapping
from job_warehouse.silver.core import normalize_row


@pytest.mark.parametrize(
    "field,values,expected",
    [
        ("job_position", ["Nhân viên", "NHÂN VIÊN", "nhân Viên"], "Nhân viên"),
        ("job_position", ["TRƯỞNG PHÒNG", "Trưởng Phòng"], "Trưởng phòng"),
        ("job_position", ["JUNIOR", "Junior"], "Junior"),
        ("job_position", ["TỐT NGHIỆP THCS", "Tốt Nghiệp Thcs"], "Tốt nghiệp THCS"),
        ("education_level", ["ĐẠI HỌC", "đại học", "Đại học"], "Đại học"),
        ("education_level", ["CỬ NHÂN", "Cử nhân"], "Cử nhân"),
        ("education_level", ["KHÔNG", "không"], "Không"),
        ("job_type", ["REMOTE", "remote", "Remote"], "Remote"),
        (
            "job_type",
            ["TOÀN THỜI GIAN, REMOTE", "toàn thời gian, remote"],
            "Toàn thời gian, Remote",
        ),
    ],
)
def test_case_variants_share_one_display_label_and_are_idempotent(field, values, expected):
    assert {canonical_label(field, value) for value in values} == {expected}
    assert canonical_label(field, expected) == expected


def test_source_meanings_and_multiple_label_order_stay_separate():
    assert canonical_label("education_level", "Đại học") != canonical_label(
        "education_level", "Cử nhân"
    )
    assert canonical_label("education_level", "KỸ SƯ") == "Kỹ sư"
    assert canonical_label("job_position", "NHÂN VIÊN") != canonical_label(
        "job_position", "CHUYÊN VIÊN"
    )
    assert canonical_label("job_type", "REMOTE, THỰC TẬP") == "Remote, Thực tập"
    assert canonical_label("job_type", "THỰC TẬP, REMOTE") == "Thực tập, Remote"
    assert canonical_label("job_type", "Remote, Chế độ mới") == "Remote, Chế độ mới"
    assert canonical_label("job_position", "Chức danh mới") == "Chức danh mới"


@pytest.mark.parametrize("field", ["job_position", "job_type", "education_level"])
@pytest.mark.parametrize("value", [None, "", " \t "])
def test_missing_labels_are_not_filled(field, value):
    assert canonical_label(field, value) is None


def test_display_catalog_changes_case_only():
    for name in ["position", "education", "job_type"]:
        for key, row in mapping(name).items():
            display = row.get("display_label") or row["label"]
            assert display.casefold() == key


def test_core_keeps_all_source_values_and_separates_display_from_inference():
    source = {
        **dict.fromkeys(COLUMNS, "Synthetic"),
        "id": 1,
        "year": 2025,
        "job_title": "C++ Developer",
        "company_name": "CÔNG TY A",
        "education_level": "KHÔNG",
        "job_type": "REMOTE, THỰC TẬP",
        "job_position": "NHÂN VIÊN",
        "experience_level": "Không",
        "requirements": "Tốt nghiệp Đại học.",
    }
    row, reason = normalize_row(source, "a" * 64, 0)
    assert reason is None
    assert {field: row[field] for field in COLUMNS} == source
    assert row["education_label_clean"] == "Không"
    assert row["education_category"] is None
    assert row["education_inferred_options"] == ["bachelor"]
    assert row["job_type_label_clean"] == "Remote, Thực tập"
    assert row["position_label_clean"] == "Nhân viên"
    assert row["position_role_categories"] == ["employee"]
    assert row["seniority_categories"] == []
    assert row["company_name_clean"] == "CÔNG TY A"


def test_wrong_field_content_is_flagged_instead_of_reassigned():
    source = {
        **dict.fromkeys(COLUMNS, "Synthetic"),
        "id": 1,
        "year": 2025,
        "education_level": "Không",
        "job_position": "TỐT NGHIỆP THCS",
    }
    row, _ = normalize_row(source, "a" * 64, 0)
    assert row["position_label_clean"] == "Tốt nghiệp THCS"
    assert row["position_status"] == "wrong_field_content"
    assert row["education_label_clean"] == "Không"
