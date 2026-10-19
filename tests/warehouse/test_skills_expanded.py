"""Expanded rules cannot inherit degrees, training promises or unrelated contexts."""

import pytest

from job_warehouse.skills.expanded import ExpandedSkillMatcher
from job_warehouse.skills.models import Alias, Skill, SkillPolicy
from job_warehouse.skills.taxonomy import Taxonomy


@pytest.fixture
def matcher():
    names = {
        "review_quyet_toan_thue": "Quyết toán thuế",
        "review_thiet_ke_do_hoa": "Thiết kế đồ họa",
        "review_oracle": "Oracle",
        "oracle_db": "Oracle Database",
        "review_notion": "Notion",
        "review_agile": "Agile",
        "cpp": "C++",
        "csharp": "C#",
        "dotnet": ".NET",
        "content_marketing": "Content Marketing",
    }
    return ExpandedSkillMatcher(
        Taxonomy(
            {k: Skill(k, v, "technology", v) for k, v in names.items()},
            tuple(Alias(k, v) for k, v in names.items()),
        ),
        SkillPolicy("fixture", ("required", "preferred")),
    )


@pytest.mark.parametrize("prefix", ["Biết", "Ưu tiên biết", "Có kinh nghiệm"])
def test_explicit_professional_capability(matcher, prefix):
    assert "review_quyet_toan_thue" in matcher.extract(prefix + " quyết toán thuế").skill_codes


@pytest.mark.parametrize(
    "text",
    [
        "Tốt nghiệp chuyên ngành thiết kế đồ họa",
        "Công ty sẽ được đào tạo thiết kế đồ họa sau khi nhận việc",
        "Có đam mê thiết kế đồ họa",
        "Không yêu cầu biết thiết kế đồ họa",
    ],
)
def test_degree_future_training_interest_negation_are_not_capability(matcher, text):
    assert "review_thiet_ke_do_hoa" not in matcher.extract(text).skill_codes


def test_degree_does_not_erase_separate_demonstrated_skill(matcher):
    result = matcher.extract("Tốt nghiệp thiết kế đồ họa; có kinh nghiệm thiết kế đồ họa")
    assert "review_thiet_ke_do_hoa" in result.skill_codes


def test_zero_years_does_not_negate_professional_knowledge(matcher):
    result = matcher.extract("Không yêu cầu kinh nghiệm; biết quyết toán thuế")
    assert "review_quyet_toan_thue" in result.skill_codes


def test_explicit_database_does_not_emit_generic_oracle(matcher):
    assert matcher.extract("Biết Oracle Database").skill_codes == ("oracle_db",)


def test_generic_oracle_does_not_invent_product(matcher):
    assert matcher.extract("Có kinh nghiệm Oracle").skill_codes == ("review_oracle",)


def test_distinct_tools_and_symbol_boundaries(matcher):
    result = matcher.extract("Biết C++, C# và .NET; không phải C++foo")
    assert set(result.skill_codes) == {"cpp", "csharp", "dotnet"}


def test_ordinary_agile_adjective(matcher):
    assert "review_agile" not in matcher.extract("Agile, organized person").skill_codes


def test_unknown_notion_word_is_pending_but_clear_skill_is_kept(matcher):
    result = matcher.extract("Notion; biết quyết toán thuế")
    assert result.status == "expanded_partial_match"
    assert result.skill_codes == ("review_quyet_toan_thue",)


def test_reviewed_offsets_remain_original_substrings(matcher):
    text = "Tốt nghiệp thiết kế đồ họa; Biết thiết kế đồ họa và C++"
    for e in matcher.extract(text).evidence:
        assert text[e.start : e.end] == e.text
        assert e.context_start <= e.start < e.end <= e.context_end


def test_full_expanded_dictionary_and_owner_specialist_routing():
    from job_warehouse.skills.expanded import EXPANDED_MAPPINGS
    from job_warehouse.skills.runner import load_policy
    from job_warehouse.skills.taxonomy import load_taxonomy

    tax = load_taxonomy(EXPANDED_MAPPINGS)
    assert len(tax.skills) == 602
    full = ExpandedSkillMatcher(tax, load_policy(EXPANDED_MAPPINGS)[0])
    assert full.extract("Biết quyết toán thuế").skill_codes == ("review_quyet_toan_thue",)
    assert full.extract("Biết kê khai thuế").skill_codes == ("review_ke_khai_thue",)
    assert full.extract("Có kinh nghiệm quản trị Fanpage").skill_codes == (
        "review_quan_tri_fanpage",
    )
    assert set(full.extract("Biết thiết kế đồ họa trong marketing").skill_codes) == {
        "content_marketing",
        "review_thiet_ke_do_hoa",
    }
    assert "content_marketing" not in full.extract("Biết thiết kế đồ họa").skill_codes


def test_specific_vocational_course_is_distinct_from_generic_major():
    from job_warehouse.skills.expanded import EXPANDED_MAPPINGS
    from job_warehouse.skills.runner import load_policy
    from job_warehouse.skills.taxonomy import load_taxonomy

    full = ExpandedSkillMatcher(load_taxonomy(EXPANDED_MAPPINGS), load_policy(EXPANDED_MAPPINGS)[0])
    assert "review_bien_tap_dung_video" in full.extract("Tốt nghiệp khóa dựng phim").skill_codes
    assert (
        "review_bien_tap_dung_video" not in full.extract("Tốt nghiệp ngành dựng phim").skill_codes
    )


@pytest.fixture
def full_matcher():
    from job_warehouse.skills.expanded import EXPANDED_MAPPINGS
    from job_warehouse.skills.runner import load_policy
    from job_warehouse.skills.taxonomy import load_taxonomy

    return ExpandedSkillMatcher(load_taxonomy(EXPANDED_MAPPINGS), load_policy(EXPANDED_MAPPINGS)[0])


def test_degree_only_does_not_supply_content_marketing_context(full_matcher):
    text = "Tốt nghiệp ngành Marketing. Có kỹ năng viết bài và chỉnh sửa video."
    result = full_matcher.extract(text)
    assert "content_marketing" not in result.skill_codes
    assert {"review_viet_noi_dung_copywriting", "review_bien_tap_dung_video"} <= set(
        result.skill_codes
    )


def test_marketing_work_context_allows_media_rollup(full_matcher):
    text = "Có kinh nghiệm marketing. Biết chỉnh sửa video và hình ảnh."
    assert "content_marketing" in full_matcher.extract(text).skill_codes


def test_photo_editing_does_not_invent_image_design(full_matcher):
    codes = full_matcher.extract("Biết chỉnh sửa ảnh").skill_codes
    assert "review_chinh_sua_hinh_anh" in codes
    assert "review_thiet_ke_hinh_anh" not in codes


@pytest.mark.parametrize(
    "text,code",
    [
        ("Có cam kết trong công việc", "review_cam"),
        ("Solid knowledge of UX design", "review_solid"),
        ("Strong interest in affiliate marketing", "review_affiliate_marketing"),
        ("Đã làm ở doanh nghiệp xuất nhập khẩu", "review_xuat_nhap_khau"),
        ("Biết MSSQL Server", "review_server_storage"),
        ("Biết API Gateway", "review_api"),
    ],
)
def test_ordinary_words_sectors_and_product_names_are_not_extra_skills(full_matcher, text, code):
    assert code not in full_matcher.extract(text).skill_codes


def test_explicit_generic_and_tool_both_kept(full_matcher):
    codes = full_matcher.extract("Thành thạo phần mềm kế toán MISA").skill_codes
    assert {"review_phan_mem_ke_toan", "misa"} <= set(codes)
    assert "review_phan_mem_ke_toan" not in full_matcher.extract("Biết MISA").skill_codes


def test_ai_design_list_and_generative_ai_are_distinct(full_matcher):
    assert "illustrator" in full_matcher.extract("Photoshop, AI, Figma").skill_codes
    codes = full_matcher.extract("Có kinh nghiệm triển khai mô hình AI và ChatGPT").skill_codes
    assert "illustrator" not in codes
    assert "review_ai_ung_dung" in codes


def test_keyword_familiarity_is_not_research(full_matcher):
    assert (
        "review_nghien_cuu_tu_khoa" not in full_matcher.extract("Hiểu biết về Keyword").skill_codes
    )


def test_dash_within_degree_list_does_not_create_a_skill(full_matcher):
    text = "Tốt nghiệp Đại học chuyên ngành Tài chính – Kế toán."
    assert "review_nghiep_vu_ke_toan" not in full_matcher.extract(text).skill_codes
    text = "Tốt nghiệp Đại học chuyên ngành Marketing – Kế toán."
    assert "review_nghiep_vu_ke_toan" not in full_matcher.extract(text).skill_codes


def test_new_capability_after_degree_dash_is_kept(full_matcher):
    text = "Tốt nghiệp Đại học – Có kinh nghiệm làm kế toán."
    assert "review_nghiep_vu_ke_toan" in full_matcher.extract(text).skill_codes


def test_computer_repair_and_network_are_not_generic_device_usage(full_matcher):
    text = "Có kinh nghiệm xử lý các vấn đề liên quan tới máy tính, mạng, hệ thống trong công ty."
    codes = full_matcher.extract(text).skill_codes
    assert {"review_khac_phuc_su_co_may_tinh", "review_mang_may_tinh"} <= set(codes)
    assert "review_su_dung_may_tinh" not in codes


def test_warehouse_role_experience_has_explicit_professional_scope(full_matcher):
    assert (
        "review_quan_ly_kho" in full_matcher.extract("Có kinh nghiệm thủ kho 6 tháng").skill_codes
    )


def test_customer_care_word_order_variant(full_matcher):
    assert (
        "review_cham_soc_khach_hang"
        in full_matcher.extract("Biết chăm sóc tốt khách hàng").skill_codes
    )


def test_specific_accountant_certificate_is_not_generic_degree(full_matcher):
    assert (
        "review_nghiep_vu_ke_toan"
        in full_matcher.extract("Cử nhân, có bằng kế toán trưởng").skill_codes
    )
    assert (
        "review_nghiep_vu_ke_toan"
        not in full_matcher.extract("Có bằng cử nhân ngành kế toán").skill_codes
    )


def test_sales_admin_does_not_establish_sales_function(full_matcher):
    assert (
        "review_ban_hang_sales"
        not in full_matcher.extract("Có kinh nghiệm sales admin").skill_codes
    )


def test_marketing_agency_is_employer_sector(full_matcher):
    assert (
        "review_kien_thuc_marketing"
        not in full_matcher.extract("Đã từng làm ở agency marketing").skill_codes
    )


def test_new_writing_alias_has_owner_approved_media_parent(full_matcher):
    codes = full_matcher.extract("Có kinh nghiệm Marketing. Có khả năng viết tốt.").skill_codes
    assert {"review_viet_noi_dung_copywriting", "content_marketing"} <= set(codes)


def test_coordinated_finance_banking_phrase_keeps_safe_offsets(full_matcher):
    text = "Có kinh nghiệm trong hoạt động tài chính - ngân hàng."
    result = full_matcher.extract(text)
    assert "review_nghiep_vu_ngan_hang" in result.skill_codes
    for evidence in result.evidence:
        assert text[evidence.start : evidence.end] == evidence.text
        assert evidence.context_start <= evidence.start < evidence.end <= evidence.context_end
    assert (
        "review_nghiep_vu_ngan_hang"
        not in full_matcher.extract("Tốt nghiệp chuyên ngành tài chính - ngân hàng.").skill_codes
    )


def test_expanded_alias_crossing_clause_boundary_fails_before_processing():
    tax = Taxonomy(
        {"banking": Skill("banking", "Banking", "domain", "Banking")},
        (Alias("banking", "finance - banking"),),
    )
    with pytest.raises(ValueError, match="strong clause boundaries"):
        ExpandedSkillMatcher(tax, SkillPolicy("fixture", ("required", "preferred")))
