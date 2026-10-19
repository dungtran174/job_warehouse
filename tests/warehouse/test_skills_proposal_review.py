"""Proposal guards keep education, waivers and training local to a named skill."""

import pytest

from job_warehouse.skills.proposal_review import assess_proposal


@pytest.mark.parametrize(
    "name,text,pattern,decision",
    [
        ("Kế toán tổng hợp", "Có kinh nghiệm làm kế toán tổng hợp", "kế toán tổng hợp", "accept"),
        ("Kế toán tổng hợp", "Tốt nghiệp ngành kế toán tổng hợp", "kế toán tổng hợp", "reject"),
        (
            "Kế toán tổng hợp",
            "Tốt nghiệp Cao đẳng. Kinh nghiệm 2 năm ở vị trí kế toán tổng hợp",
            "kế toán tổng hợp",
            "accept",
        ),
        ("Microsoft Excel", "Không yêu cầu biết Excel", "Excel", "reject"),
        ("Microsoft Excel", "Không yêu cầu kinh nghiệm, biết Excel", "Excel", "accept"),
        (
            "Tin học văn phòng",
            "Thành thạo tin học văn phòng Không yêu cầu kinh nghiệm",
            "tin học văn phòng",
            "accept",
        ),
        (
            "Microsoft Excel",
            "Tốt nghiệp kế toán. Tin học văn phòng tốt, đặc biệt là Excel",
            "Excel",
            "accept",
        ),
        ("Microsoft Excel", "Tốt Cao Đẳng trở lên, Excel tốt", "Excel", "accept"),
        (
            "Phần mềm kế toán",
            "Biết sử dụng phần mềm kế toán (chưa biết sẽ được đào tạo)",
            "phần mềm kế toán",
            "accept",
        ),
        (
            "Phần mềm kế toán",
            "Sẽ được đào tạo sử dụng phần mềm kế toán",
            "phần mềm kế toán",
            "reject",
        ),
        ("Phần mềm kế toán", "Được đào tạo sử dụng phần mềm kế toán", "phần mềm kế toán", "reject"),
        (
            "Phần mềm kế toán",
            "Đã được đào tạo sử dụng phần mềm kế toán",
            "phần mềm kế toán",
            "accept",
        ),
        ("SEO", "Yêu thích SEO", "SEO", "reject"),
        ("SEO", "QUYỀN LỢI: Được học SEO miễn phí", "SEO", "reject"),
        ("Agile", "Good computer skills, agile, organized skill", "agile", "reject"),
        ("Agile", "Good knowledge of Agile development", "Agile", "accept"),
        ("Sử dụng máy tính", "Có máy tính cá nhân", "máy tính", "reject"),
        ("Sử dụng máy tính", "Sử dụng thành thạo máy tính", "máy tính", "accept"),
        ("Bảo hiểm xã hội", "QUYỀN LỢI: Được đóng BHXH", "BHXH", "reject"),
        ("Tiếng Anh", "Tốt nghiệp ngành tiếng Anh", "tiếng Anh", "reject"),
        ("Tiếng Anh", "Tiếng Anh tốt, giới tính: không yêu cầu", "Tiếng Anh", "accept"),
        ("Video Editing", "Có khả năng edit video (không bắt buộc)", "edit video", "accept"),
        ("Microsoft Word", "Sử dụng Keyword Planner", r"\bWord\b", "unclear"),
    ],
)
def test_local_context(name, text, pattern, decision):
    result = assess_proposal(name, text, text, pattern)
    assert result.decision == decision
    if result.start >= 0:
        assert text[result.start : result.end] == result.anchor


def test_non_source_quote_is_refused():
    with pytest.raises(ValueError, match="exact evidence"):
        assess_proposal("Excel", "Excel", "khác", "Excel")


def test_specific_occurrence_can_be_positive_despite_education_occurrence():
    text = "Tốt nghiệp ngành SEO. Có kinh nghiệm SEO"
    result = assess_proposal("SEO", "SEO", text, "SEO")
    assert result.decision == "accept"
    assert result.start == text.rindex("SEO")


@pytest.mark.parametrize(
    "text",
    [
        "Tốt nghiệp chuyên ngành CNTT, đọc hiểu tài liệu chuyên ngành tiếng Anh",
        "Thành thạo phần mềm chuyên ngành, tiếng Anh tốt",
        "Tiếng Anh: B Chứng chỉ kế toán trưởng",
    ],
)
def test_specialized_material_and_proficiency_are_not_degree_only(text):
    result = assess_proposal("Tiếng Anh", text, text, "tiếng Anh")
    assert result.decision == "accept"


def test_experience_heading_after_excel_does_not_negate_it():
    text = "Tin học căn bản (Word, Excell). Số năm kinh nghiệm: Không yêu cầu"
    assert assess_proposal("Microsoft Excel", text, text, "Excell").decision == "accept"


def test_supervisor_job_name_does_not_become_applicant_skill():
    text = "Thực hiện công việc khác do Kế toán tổng hợp và Giám đốc giao."
    result = assess_proposal("Kế toán tổng hợp", text, text, "kế toán tổng hợp")
    assert result.decision == "reject"
