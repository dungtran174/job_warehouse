"""Offline semantic regressions; fixtures are synthetic or short source labels."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from job_warehouse.history.contract import COLUMNS
from job_warehouse.silver.categorical import education, job_type, position
from job_warehouse.silver.core import normalize_row
from job_warehouse.silver.experience import parse_experience
from job_warehouse.silver.requirements_attributes import extract_attributes
from job_warehouse.silver.text import normalize_content, normalize_text

LABELS = json.loads((Path(__file__).parents[1] / "fixtures/warehouse/core_labels.json").read_text())


@pytest.mark.parametrize("value", [None, "", " \t "])
def test_missing_text_is_not_stringified(value):
    assert normalize_text(value).clean is None


@pytest.mark.parametrize(
    "value,expected",
    [
        ("  Công ty A  ", "Công ty A"),
        ("C++ C# .NET Node.js a < b <T>", "C++ C# .NET Node.js a < b <T>"),
        ("A&amp;amp;B &CN; &MKT; &GT; &#38;", "A&B &CN; &MKT; > &"),
        ("Java\x02Script", "Java Script"),
        ("a\r\nb\tc", "a\nb c"),
    ],
)
def test_text_keeps_content_and_replay_is_stable(value, expected):
    result = normalize_text(value)
    assert result.clean == expected
    assert normalize_text(result.clean).clean == expected
    assert normalize_text(value) == result


def test_deep_entity_falls_back_and_does_not_decode_gradually():
    value = "&" + "amp;" * 8
    first = normalize_text(value)
    assert first.clean == value
    assert "entity_depth_exceeded" in first.flags
    assert normalize_text(first.clean).clean == value
    assert normalize_text("&#0;").flags == ("entity_decoded", "entity_replacement_character")


@pytest.mark.parametrize(
    "value,status",
    [
        (None, "missing"),
        (".", "placeholder"),
        ("Không", "ambiguous_literal"),
        ("khác", "other_unspecified"),
    ],
)
def test_requirements_status_is_not_no_match(value, status):
    assert normalize_content(value, requirements=True).status == status


@pytest.mark.parametrize("value", LABELS["job_type"])
def test_all_observed_types_have_reviewed_route(value):
    assert job_type(value).status not in {"unmapped", "partial"}


@pytest.mark.parametrize("value", LABELS["job_position"])
def test_all_observed_positions_have_route(value):
    assert position(value).status != "unmapped"


@pytest.mark.parametrize("value", LABELS["education_level"])
def test_all_observed_education_labels_have_route(value):
    assert education(value).status != "unmapped"


@pytest.mark.parametrize("value", LABELS["experience_level"])
def test_all_observed_experience_labels_have_parse_route(value):
    assert parse_experience(value).status in {"mapped", "ambiguous_literal"}


@pytest.mark.parametrize(
    "value,low,high,kind,closed,group",
    [
        ("3 năm", 36, 36, "stated_point", True, "3_lt_5"),
        ("1–3 năm", 12, 36, "range", True, "range_crossing"),
        ("Dưới 1 năm", 0, 12, "upper_bound", False, "lt_1"),
        ("Trên 3 năm", 36, None, "lower_bound", None, "range_crossing"),
        ("từ 3 năm", 36, None, "lower_bound", None, "range_crossing"),
        ("0,25–1 năm", 3, 12, "range", True, "range_crossing"),
        ("6 tháng", 6, 6, "stated_point", True, "lt_1"),
        ("05–10 năm", 60, 120, "range", True, "ge_5"),
    ],
)
def test_experience_preserves_bounds(value, low, high, kind, closed, group):
    result = parse_experience(value)
    assert (
        result.min_months,
        result.max_months,
        result.kind,
        result.max_inclusive,
        result.group,
    ) == (low, high, kind, closed, group)
    if value.startswith("Trên"):
        assert result.min_inclusive is False


def test_months_are_exact_and_unknown_is_not_zero():
    result = parse_experience("1 tháng")
    assert result.min_months == Decimal(1)
    assert result.years(result.min_months) == Decimal("0.083333")
    assert parse_experience("Không").min_months is None
    assert parse_experience("Không yêu cầu kinh nghiệm").kind == "no_requirement"
    assert parse_experience("3–1 năm").status == "invalid_bounds"
    assert parse_experience("tuổi 25–35").status == "unmapped"
    assert parse_experience("Trên 3 năm trở xuống").status == "ambiguous"
    assert job_type("Remote").employment_types == ()
    assert job_type("Toàn thời gian").work_arrangement is None
    assert job_type("Theo ca").shift_work is True
    assert position("Nhân viên").seniorities == ()
    assert position("Loại Hợp Đồng:").status == "wrong_field_content"
    assert education("Kỹ sư").category is None


@pytest.mark.parametrize(
    "text,edu,kind,status",
    [
        (
            "Tốt nghiệp Đại học ngành CNTT hoặc ngành liên quan.",
            ("bachelor",),
            None,
            "not_mentioned",
        ),
        ("Tốt nghiệp cao đẳng hoặc đại học.", ("bachelor", "college"), None, "not_mentioned"),
        ("Có tối thiểu 2 năm kinh nghiệm kế toán.", (), "lower_bound", "single"),
        ("Có kinh nghiệm từ 3 năm trở lên.", (), "lower_bound", "single"),
        ("Có 1–3 năm kinh nghiệm.", (), "range", "single"),
        ("Không yêu cầu kinh nghiệm, sẽ được đào tạo.", (), "no_requirement", "single"),
        ("Ưu tiên có 2 năm kinh nghiệm.", (), None, "mentions_only"),
        ("Không yêu cầu 3 năm kinh nghiệm.", (), None, "mentions_only"),
        ("Tuổi 25–35; tốt nghiệp năm 2020.", (), None, "not_mentioned"),
        ("Cao đẳng và 3 năm kinh nghiệm hoặc đại học và 1 năm.", (), None, "complex"),
        ("Tốt nghiệp cao đẳng và 3 năm kinh nghiệm hoặc đại học và 1 năm.", (), None, "complex"),
        ("Từ 3 năm kinh nghiệm; chấp nhận sinh viên mới ra trường.", (), None, "complex"),
        ("Từ 3 năm kinh nghiệm nhưng chấp nhận sinh viên mới ra trường.", (), None, "complex"),
    ],
)
def test_requirement_summary_meaning(text, edu, kind, status):
    result = extract_attributes(text, "present")
    assert result.education_options == edu
    assert (result.experience.kind if result.experience else None) == kind
    assert result.experience_status == status
    for claim in result.claims:
        assert text[claim.start : claim.end]


def test_preferred_degree_no_requirement_and_student_are_not_graduated():
    assert extract_attributes("Ưu tiên tốt nghiệp đại học.", "present").education_options == ()
    assert (
        extract_attributes("Không yêu cầu bằng cấp.", "present").education_relation
        == "no_requirement"
    )
    assert extract_attributes("Sinh viên đại học năm cuối.", "present").education_options == ()
    assert (
        extract_attributes(
            "Không nhận ứng viên chưa tốt nghiệp đại học.", "present"
        ).education_options
        == ()
    )


def make_row(**overrides):
    return {
        **dict.fromkeys(COLUMNS, "Synthetic"),
        "id": 1,
        "year": 2025,
        "job_title": "Developer",
        "company_name": None,
        "education_level": "Không",
        "experience_level": "Không",
        "job_type": "Toàn thời gian",
        "job_position": "Nhân viên",
        "requirements": "Tốt nghiệp đại học. Có tối thiểu 2 năm kinh nghiệm.",
        **overrides,
    }


def test_core_keeps_raw_unknown_and_separate_evidence():
    row = make_row()
    result, reason = normalize_row(row, "a" * 64, 8)
    assert reason is None
    assert all(result[c] == row[c] for c in COLUMNS)
    assert result["education_category"] is None
    assert result["education_inferred_options"] == ["bachelor"]
    assert result["experience_min_years"] is None
    assert result["experience_inferred_min_years"] == 2
    assert result["company_name_clean"] is None
    assert result["source_row_index"] == 8
    for name in ["education", "experience"]:
        for claim in result[f"{name}_inference_claims"]:
            assert (
                claim["evidence_text"]
                == result["requirements_clean"][claim["start_offset"] : claim["end_offset"]]
            )
            assert claim["requirements_text_hash"] == result["requirements_text_hash"]


@pytest.mark.parametrize(
    "title,reason", [(None, "missing_title"), ("Không", "title_ambiguous_literal")]
)
def test_quarantine_title_keeps_every_source_value(title, reason):
    row = make_row(job_title=title)
    result, actual = normalize_row(row, "a" * 64, 0)
    assert actual == reason
    assert all(result[c] == row[c] for c in COLUMNS)
    assert "education_inferred_options" not in result


def test_no_skill_or_cross_field_fallback():
    result, _ = normalize_row(
        make_row(job_title="Senior Python", requirements=None, job_description="Biết SQL"),
        "a" * 64,
        0,
    )
    assert result["requirements_clean"] is None
    assert result["education_inferred_options"] == []
    assert result["experience_inferred_min_years"] is None
    assert not any("skill" in key for key in result)
    assert result["seniority_categories"] == []


@pytest.mark.parametrize(
    "text",
    [
        "Tốt nghiệp trung cấp, cao đẳng, đại học.",
        "Trình độ Cao đẳng – Đại học.",
        "Tốt nghiệp trung cấp Dược trở lên.",
    ],
)
def test_incomplete_degree_list_or_bound_abstains(text):
    result = extract_attributes(text, "present")
    assert result.education_options == ()
    assert result.education_status == "ambiguous"
    assert all(c.status == "needs_review" for c in result.claims)


@pytest.mark.parametrize(
    "text",
    [
        "Tốt nghiệp cao đẳng. Có kinh nghiệm sẽ là một lợi thế.",
        "Tốt nghiệp cao đẳng Có kinh nghiệm sẽ là một lợi thế.",
        "Có kinh nghiệm là một lợi thế Học vấn: Tốt nghiệp cao đẳng.",
        "Ưu tiên có kinh nghiệm Tốt nghiệp cao đẳng.",
        "Tốt nghiệp cao đẳng và có tối thiểu 1 năm kinh nghiệm bán hàng là lợi thế.",
    ],
)
def test_preference_belongs_to_its_criterion(text):
    result = extract_attributes(text, "present")
    assert result.education_options == ("college",)


def test_no_experience_phrase_never_becomes_positive_requirement():
    result = extract_attributes("Không có kinh nghiệm sẽ được đào tạo.", "present")
    assert result.experience is None
    assert result.claims[0].context == "negated"
    result = extract_attributes("Có ít nhất kinh nghiệm 1 năm ở vị trí A.", "present")
    assert result.experience is not None
    assert result.experience.kind == "lower_bound"
    assert result.experience.min_months == 12


@pytest.mark.parametrize(
    "text",
    [
        "Tốt nghiệp đại học hoặc có kinh nghiệm bán hàng.",
        "Tốt nghiệp đại học; hoặc từng làm bán hàng.",
        "Có từ 1 năm kinh nghiệm giảng dạy hoặc có kinh nghiệm gia sư.",
    ],
)
def test_alternative_to_degree_or_numeric_experience_abstains(text):
    result = extract_attributes(text, "present")
    assert result.education_options == ()
    assert result.experience is None
    assert "complex" in {result.education_status, result.experience_status}


@pytest.mark.parametrize(
    "text,attribute",
    [
        ("Chưa có gia đình Tốt nghiệp cao đẳng trở lên.", "education"),
        ("Không yêu cầu kinh nghiệm, sẽ đào tạo Trình độ trung cấp trở lên.", "education"),
        ("Kỹ năng này chưa bắt buộc) Kinh nghiệm trên 1 năm.", "experience"),
    ],
)
def test_round1_negation_does_not_leak_from_unrelated_criterion(text, attribute):
    result = extract_attributes(text, "present")
    claim = next(c for c in result.claims if c.attribute == attribute)
    assert claim.context == "required"


def test_round1_numeric_criterion_ends_previous_degree_preference_scope():
    result = extract_attributes(
        "Tốt nghiệp đại học Từ 1 năm kinh nghiệm minh họa Yêu thích game là lợi thế.",
        "present",
    )
    assert next(c for c in result.claims if c.attribute == "education").context == "required"


def test_round1_scope_stays_with_its_own_experience_phrase():
    result = extract_attributes(
        "Có kinh nghiệm từ 2 năm trở lên, ưu tiên có kinh nghiệm làm hồ sơ đấu thầu.",
        "present",
    )
    numeric = next(c for c in result.claims if c.experience and c.experience.min_months)
    assert numeric.scope == "unspecified"
    assert numeric.scope_text is None
    result = extract_attributes("Có ít nhất 3 năm kinh nghiệm ở vị trí Trưởng phòng.", "present")
    assert result.claims[0].scope == "management"


@pytest.mark.parametrize(
    "text",
    [
        "Có ít nhất từ 2-3 năm kinh nghiệm.",
        "Có kinh nghiệm ít nhất một năm rưỡi sửa chữa điện lạnh.",
        "Có kinh nghiệm hoặc mới ra trường.",
        "Tốt nghiệp đại học hoặc có chứng chỉ tương đương.",
        "Tốt nghiệp hoặc sắp tốt nghiệp đại học.",
        "Tốt nghiệp cao đẳng (chấp nhận sinh viên đang chờ bằng).",
        "Có ít nhất 1 năm kinh nghiệm. Mới ra trường: vẫn có thể được cân nhắc.",
        "Tốt nghiệp đại học ngành A. Tốt nghiệp trung cấp ngành B.",
        "Tốt nghiệp cao đẳng nghề, trung cấp nghề hoặc sơ cấp nghề.",
        "Tốt nghiệp trung cấp tới cao đẳng ngành điện.",
        "Tốt nghiệp trung cấp hoặc cao đẳng trở lên.",
    ],
)
def test_round1_unresolved_applicability_is_not_high_accepted(text):
    result = extract_attributes(text, "present")
    assert result.claims
    assert all(c.status == "needs_review" for c in result.claims)
    assert result.education_options == ()
    assert result.experience is None


def test_round1_generic_negation_has_no_positive_requirement_value():
    result = extract_attributes("Chưa có kinh nghiệm sẽ được đào tạo.", "present")
    assert result.claims[0].context == "negated"
    assert result.claims[0].experience is None
    assert result.experience is None


@pytest.mark.parametrize(
    "text,context",
    [
        ("Bằng cử nhân trở lên.", "required"),
        ("Ưu tiên ứng viên có bằng thạc sĩ.", "preferred"),
        ("Tốt nghiệp bằng trung cấp.", "required"),
    ],
)
def test_owner_degree_possession_is_requested_graduation(text, context):
    claim = extract_attributes(text, "present").claims[0]
    assert claim.qualification == "graduated"
    assert claim.context == context


@pytest.mark.parametrize("text", ["Tốt nghiệp từ Đại học.", "Tốt nghiệp từ THPT."])
def test_owner_from_degree_without_suffix_means_minimum(text):
    result = extract_attributes(text, "present")
    assert result.education_relation == "minimum_level"
    assert result.claims[0].status == "accepted"
    assert "owner_from_degree_minimum" in result.claims[0].reasons


@pytest.mark.parametrize(
    "text",
    [
        "Có 2-4 năm kinh nghiệm là ưu thế.",
        "Ứng viên có kinh nghiệm tư vấn, bán hàng... là ưu thế.",
        "Có kinh nghiệm trong ngành điện là một lợi thế.",
    ],
)
def test_round2_preference_synonym_and_ellipsis_stay_with_criterion(text):
    result = extract_attributes(text, "present")
    assert result.claims[0].context == "preferred"
    assert result.experience is None


@pytest.mark.parametrize(
    "text,attribute",
    [
        ("Ưu tiên Nữ Tốt nghiệp Cao đẳng trở lên.", "education"),
        ("Tốt nghiệp Cao đẳng Từng làm việc giáo dục là lợi thế.", "education"),
        ("Từ 2 năm kinh nghiệm bán hàng Hiểu biết B2B là lợi thế.", "experience"),
        ("Có kinh nghiệm làm bài giảng, biết làm video là lợi thế.", "experience"),
        ("Có ít nhất 2 năm kinh nghiệm bán hàng và đam mê ẩm thực là lợi thế.", "experience"),
    ],
)
def test_round2_unrelated_preference_does_not_change_required_claim(text, attribute):
    claim = next(c for c in extract_attributes(text, "present").claims if c.attribute == attribute)
    assert claim.context == "required"
    assert claim.status == "accepted"


@pytest.mark.parametrize(
    "text",
    [
        "Tốt nghiệp đại học hoặc chứng chỉ hành nghề tương đương.",
        "Tốt nghiệp Đại học & Cao đẳng.",
        "Tốt nghiệp Đại học. Cử nhân hoặc thạc sỹ.",
        "Trình độ Đại học. Chuyên môn: Tốt nghiệp chuyên ngành thống kê.",
        "1. Nhân viên: Tốt nghiệp Cao đẳng. 2. Quản lý: Tốt nghiệp Đại học.",
        "Tốt nghiệp Đại học đối với vị trí giảng viên.",
        "Tốt nghiệp THPT. Chấp nhận SV chờ bằng ra trường.",
        "Có kinh nghiệm 2 năm trở lên. - Hoặc đã qua vị trí kế toán tổng hợp.",
        "Có ít nhất 2 năm kinh nghiệm bán hàng hoặc từng làm lễ tân.",
        "Có kinh nghiệm 6 tháng trờ lên.",
        "Tối thiếu 4 năm kinh nghiệm.",
        "Có tối thiểu 6 tháng - 1,5 năm kinh nghiệm.",
        "Không yêu cầu kinh nghiệm. Kinh nghiệm tương đương từ 3 năm trở lên.",
        "Ưu tiên ứng viên Nam, có 2 năm kinh nghiệm.",
        "Có ít nhất 2 năm kinh nghiệm tư vấn (trong ngành cà phê là lợi thế).",
        "Ưu tiên ứng viên không yêu cầu có kinh nghiệm.",
        "Tốt nghiệp Cao đẳng, Đại học trở lên. Tốt nghiệp từ Cao đẳng ngành khác.",
        "Kinh nghiệm từ 3-5 năm. Không yêu cầu kinh nghiệm, ưu tiên sinh viên mới ra trường.",
    ],
)
def test_round2_unresolved_whole_document_or_partial_bound_abstains(text):
    result = extract_attributes(text, "present")
    assert result.claims
    assert all(c.status == "needs_review" for c in result.claims)
    assert result.education_options == ()
    assert result.experience is None


def test_round2_minimum_prefix_modifies_degree():
    result = extract_attributes("Trình độ: Tối thiểu tốt nghiệp Trung cấp.", "present")
    assert result.education_relation == "minimum_level"


@pytest.mark.parametrize("scope", ["quản lý dự án", "quản lý website", "quản lý kênh Marketing"])
def test_round2_managed_object_is_not_people_management_experience(scope):
    result = extract_attributes(f"Có từ 2 năm kinh nghiệm về {scope}.", "present")
    assert result.claims[0].scope == "related_role"


def test_student_evidence_and_nested_negation_require_caution():
    result = extract_attributes("Sinh viên đại học năm cuối.", "present")
    assert result.education_options == ()
    assert result.claims[0].qualification == "student_final_year"
    result = extract_attributes("Không phải không yêu cầu kinh nghiệm.", "present")
    assert result.experience is None
    assert result.experience_status == "ambiguous"
    result = extract_attributes("Không nhận ứng viên chưa tốt nghiệp đại học.", "present")
    assert result.education_options == ()
    assert result.education_status == "ambiguous"
    result = extract_attributes("Có 2 năm kinh nghiệm được ưu tiên.", "present")
    assert result.experience is None
    assert result.claims[0].context == "preferred"
    assert job_type("Toàn thời gian, Không").status == "partial"


@pytest.mark.parametrize(
    "text,context",
    [
        ("Đang là sinh viên Đại học năm 3, 4.", "mentioned"),
        ("Sinh viên cao đẳng năm cuối.", "mentioned"),
        ("Ưu tiên sinh viên Đại học năm cuối.", "preferred"),
        ("Sinh viên Đại học năm cuối được ưu tiên.", "preferred"),
    ],
)
def test_owner_student_policy_keeps_explicit_preference_without_mandatory_degree(text, context):
    result = extract_attributes(text, "present")
    claim = result.claims[0]
    assert claim.context == context
    assert claim.qualification in {"student", "student_final_year"}
    assert result.education_options == ()
    assert text[claim.start : claim.end].casefold().startswith("sinh viên")


@pytest.mark.parametrize(
    "text,low,high,source_low,source_high",
    [
        ("6 tháng–1 năm", 6, 12, "6 tháng", "1 năm"),
        ("từ 6 tháng - 1,5 năm", 6, 18, "6 tháng", "1,5 năm"),
        ("1 năm đến 18 tháng", 12, 18, "1 năm", "18 tháng"),
        ("1 năm–2 năm", 12, 24, "1 năm", "2 năm"),
    ],
)
def test_explicit_endpoint_units_preserve_whole_range(text, low, high, source_low, source_high):
    value = parse_experience(text)
    assert value.status == "mapped"
    assert (value.kind, value.min_months, value.max_months) == ("range", low, high)
    assert value.min_inclusive is True and value.max_inclusive is True
    assert (value.source_min, value.source_max) == (source_low, source_high)
    result = extract_attributes(f"Có {text} kinh nghiệm.", "present")
    assert result.experience == value
    assert len(result.claims) == 1
    assert result.claims[0].status == "accepted"


@pytest.mark.parametrize("text", ["2 năm–6 tháng", "1000000000 tháng–1000000001 năm"])
def test_mixed_unit_invalid_bounds_are_not_partially_accepted(text):
    assert parse_experience(text).status == "invalid_bounds"
    result = extract_attributes(f"Có {text} kinh nghiệm.", "present")
    assert result.experience is None
    assert all(c.status == "needs_review" for c in result.claims)


@pytest.mark.parametrize(
    "text",
    [
        "Tốt nghiệp Đại học ngành logistics hoặc cao đẳng ngành kinh tế.",
        "Tốt nghiệp Trung cấp hoặc các trường đào tạo nghề phù hợp.",
        "Tốt nghiệp Đại học hoặc các chứng chỉ chuyên môn tương đương.",
        "Tốt nghiệp Cao đẳng; Đại học.",
        "Tốt nghiệp Cao đẳng, hoặc Đại học.",
        "Tốt nghiệp THPT, chưa tốt nghiệp cũng có thể ứng tuyển.",
        "Tốt nghiệp Đại học đối với nhân viên, đang học đại học đối với thực tập.",
        "Có trên 1 năm kinh nghiệm trở lên.",
        "Có kinh nghiệm, đã qua nghĩa vụ quân sự là lợi thế.",
    ],
)
def test_round3_unresolved_alternatives_and_qualifiers_abstain(text):
    result = extract_attributes(text, "present")
    assert result.claims
    assert all(c.status == "needs_review" for c in result.claims)
    assert result.education_options == () and result.experience is None


@pytest.mark.parametrize(
    "text,kind,context,scope",
    [
        ("Tối thiểu có 5 năm kinh nghiệm.", "lower_bound", "required", "unspecified"),
        ("Kinh nghiệm 3 năm làm việc trở lên.", "lower_bound", "required", "unspecified"),
        ("Có 2 năm kinh nghiệm (ưu tiên).", "stated_point", "preferred", "unspecified"),
        ("Có 3 năm kinh nghiệm tại vị trí quản lý.", "stated_point", "required", "management"),
    ],
)
def test_round3_clear_claim_bounds_preference_and_scope(text, kind, context, scope):
    claim = extract_attributes(text, "present").claims[0]
    assert claim.status == "accepted"
    assert claim.experience.kind == kind
    assert claim.context == context and claim.scope == scope


@pytest.mark.parametrize(
    "text,context",
    [
        ("Đã có kinh nghiệm làm việc là một lợi thế.", "preferred"),
        ("Ứng viên có kinh nghiệm về bán hàng/ kinh doanh/ tư vấn là lợi thế.", "preferred"),
        ("Học vấn tối thiểu: Tốt nghiệp THPT Ưu tiên sinh viên.", "required"),
        (
            "Tốt nghiệp đại học, ưu tiên ngành Marketing + Có kinh nghiệm 1 năm trong Content.",
            "required",
        ),
    ],
)
def test_tune_regressions_do_not_move_preference_between_criteria(text, context):
    result = extract_attributes(text, "present")
    claim = next(
        c
        for c in result.claims
        if c.attribute == ("experience" if "kinh nghiệm" in text else "education")
    )
    assert claim.context == context


def test_lower_bound_after_experience_noun_and_nonadjacent_numeric_abstention():
    result = extract_attributes("Yêu cầu 1 năm kinh nghiệm trở lên.", "present")
    assert result.experience.kind == "lower_bound"
    assert result.experience.min_months == 12
    assert result.experience.max_months is None
    result = extract_attributes("Có kinh nghiệm về quản lý từ 2 năm trở lên.", "present")
    assert result.experience is None
    assert result.experience_status == "ambiguous"
    assert result.claims[0].reasons == ("numeric_nonadjacent_unparsed",)


def test_cpp_inside_context_is_not_a_bullet_separator():
    result = extract_attributes("Có kinh nghiệm C++ là lợi thế.", "present")
    assert result.experience is None
    assert result.claims[0].context == "preferred"
    assert (
        "C++"
        in "Có kinh nghiệm C++ là lợi thế."[
            result.claims[0].context_start : result.claims[0].context_end
        ]
    )
