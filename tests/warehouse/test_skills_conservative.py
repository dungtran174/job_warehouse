"""Skip ambiguous keywords without blocking jobs or changing older matchers."""

import pytest

from job_warehouse.skills.batches import batch_scope
from job_warehouse.skills.conservative import ConservativeHRFinanceMatcher
from job_warehouse.skills.hr_finance import HR_FINANCE_MAPPINGS
from job_warehouse.skills.runner import load_policy
from job_warehouse.skills.taxonomy import load_taxonomy


@pytest.fixture
def matcher():
    return ConservativeHRFinanceMatcher(
        load_taxonomy(HR_FINANCE_MAPPINGS),
        load_policy(HR_FINANCE_MAPPINGS, scope=batch_scope("hr_finance_legal"))[0],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Thành thạo Excel; tên phần mềm chưa rõ", {"excel"}),
        ("Word; Excel", set()),
        ("Trực tiếp đảm nhận công tác trả lương", set()),
        ("Có kinh nghiệm tính lương", {"payroll"}),
        ("Kinh nghiệm ASP.NET và PL/SQL", {"review_asp_net", "plsql"}),
        ("Có kinh nghiệm lập trình SQL và .NET", {"sql", "dotnet"}),
        ("Thời gian làm việc: Hành chính 8:30 – 17:30", set()),
        ("Dữ liệu cá nhân được xử lý nhằm mục đích tuyển dụng nhân sự của Công ty", set()),
        ("Có kinh nghiệm tuyển dụng nhân viên", {"hr_recruitment"}),
        ("Có khả năng sử dụng phần mềm tuyển dụng online", set()),
        ("Proven work experience. Customer service attitude", set()),
        ("Kinh nghiệm tuyển mass các vị trí telesales, nhân viên kinh doanh, CSKH", set()),
        ("Kinh nghiệm nghiệp vụ ngân hàng: SWIFT, CITAD", {"review_nghiep_vu_ngan_hang"}),
        ("Có kinh nghiệm lập trình iOS với Swift", {"swift"}),
        ("Ưu tiên biết MISA, chưa biết sẽ được đào tạo", {"misa"}),
        ("Tốt nghiệp ngành kế toán", set()),
        ("Được đào tạo sử dụng phần mềm MISA", set()),
    ],
)
def test_explicit_keywords_skip_unclear(matcher, text, expected):
    result = matcher.extract(text)
    assert set(result.skill_codes) == expected
    assert result.status in {"processed_match", "processed_no_match"}
    for e in result.evidence:
        assert text[e.start : e.end] == e.text
        assert 0 <= e.context_start <= e.start < e.end <= e.context_end <= len(text)


def test_absent_requirements_are_not_fabricated(matcher):
    assert matcher.extract(None).status == "missing_requirements"
    assert matcher.extract("Không").status == "unusable_requirements"


@pytest.mark.parametrize(
    "text",
    [
        "Am hiểu các quy định của luật lao động, BHXH, BHYT, thuế TNCN",
        "Am hiểu về luật kế toán, thuế và chế độ kế toán Việt Nam",
        "Tốt nghiệp kinh tế, chuyên ngành tài chính - kế toán. Có kinh nghiệm trợ lý",
    ],
)
def test_general_profession_not_inferred_from_law_or_degree(matcher, text):
    codes = set(matcher.extract(text).skill_codes)
    assert not codes & {"review_bao_hiem_xa_hoi", "review_nghiep_vu_ke_toan"}
