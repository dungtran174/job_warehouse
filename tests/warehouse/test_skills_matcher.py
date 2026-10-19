"""Semantic counterexamples: symbols, negation, degrees, alternatives and aliases."""

import pytest

from job_warehouse.skills.matcher import SkillMatcher
from job_warehouse.skills.models import Alias, Skill, SkillPolicy
from job_warehouse.skills.taxonomy import Taxonomy, load_taxonomy


@pytest.fixture
def matcher():
    return SkillMatcher(load_taxonomy(), SkillPolicy("test", ("required", "preferred")))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Thành thạo Excel, Microsoft Excel, MS Excel", {"excel"}),
        ("Biết JavaScript", {"javascript"}),
        ("Có kinh nghiệm C++, C# và .NET", {"cpp", "csharp", "dotnet"}),
        ("Biết PostgreSQL", {"postgresql"}),
        ("Biết SQL Server", {"sql_server"}),
        ("Biết React Native", {"react_native"}),
        ("Biết Spring Boot, PySpark và AngularJS", {"spring_boot", "pyspark", "angularjs"}),
        ("Không yêu cầu kinh nghiệm nhưng cần biết Excel", {"excel"}),
        ("Không yêu cầu Python", set()),
        ("Python không bắt buộc, biết là lợi thế", {"python"}),
        ("Ưu tiên ứng viên biết Python", {"python"}),
        (
            "Có kinh nghiệm chạy kênh FBads hoặc Tiktok Ads khoảng 0-3 tháng "
            "(nếu ko có sẽ được training đào tạo)",
            {"facebook_ads", "tiktok_ads"},
        ),
        ("Biết FB Ads, FBads và Facebook Ads", {"facebook_ads"}),
        ("Không yêu cầu FBads", set()),
        ("Sẽ được đào tạo FBads sau khi nhận việc", set()),
        (
            "Thành thạo phần mềm thiết kế ảnh/video: AI, PS, Pr, Canva, CapCut",
            {"illustrator", "photoshop", "premiere", "canva", "capcut"},
        ),
        ("Có kỹ năng AI và PR", set()),
        ("Biết các công cụ AI hỗ trợ bán hàng", set()),
        ("Sử dụng công cụ AI và Canva hỗ trợ marketing", {"canva"}),
        ("Không yêu cầu phần mềm thiết kế Photoshop, AI", set()),
        (
            "Biết Adobe Premier, After effect, Ilustrator",
            {"premiere", "after_effects", "illustrator"},
        ),
        ("Thành thạo GG ads", {"google_ads"}),
        ("Sử dụng tin học VP, công cụ văn phòng", {"office_it"}),
        ("Có kinh nghiệm viết quảng cáo", {"content_marketing"}),
        ("Sử dụng công cụ quảng cáo Google Analytics", {"google_analytics"}),
        ("Biết công cụ AI hỗ trợ; biết phần mềm thiết kế PTS, Canva", {"photoshop", "canva"}),
        ("Ưu tiên làm tại công ty bán hàng livestream", set()),
        ("Có kinh nghiệm livestream bán hàng", {"content_marketing"}),
        ("Yêu thích và định hướng lĩnh vực Digital Marketing", set()),
        ("Ưu tiên kiến thức về sản phẩm tiếng Anh", set()),
        ("Có hiểu biết về thị trường tiếng Hàn", set()),
        ("Marketing; kinh nghiệm Edit Video trên social media", set()),
        ("Key Performance Indicators (KPIs) Social media engagement", set()),
        (
            "Có kinh nghiệm các kênh quảng cáo Google, Facebook, TikTok",
            {"google_ads", "facebook_ads", "tiktok_ads"},
        ),
        ("Biết chạy Ads Facebook, Google", {"facebook_ads", "google_ads"}),
        ("Có kinh nghiệm quảng cáo. Hiểu biết TikTok", set()),
        ("Có kinh nghiệm chạy quảng cáo - Hiểu biết TikTok", set()),
        (
            "Biết quản trị fanpage và xây dựng nội dung quảng bá",
            {"social_media", "content_marketing"},
        ),
        ("Biết viết bài PR; biết phần mềm thiết kế và chỉnh sửa video", set()),
        (
            "Không có kinh nghiệm được đào tạo Có hiểu biết về SEO và Content Marketing",
            {"seo", "content_marketing"},
        ),
        ("Biết PTS và Canva", {"photoshop", "canva"}),
        (
            "Thành thạo Social Media và sáng tạo nội dung bán hàng",
            {"social_media", "content_marketing"},
        ),
        ("Biết Python hoặc Java", {"python", "java"}),
        ("Thành thạo tin học văn phòng", {"office_it"}),
        ("Sẽ được đào tạo Python sau khi nhận việc", set()),
        ("Có kinh nghiệm đào tạo Python", {"python"}),
        ("Tốt nghiệp ngành Ngôn ngữ Anh", set()),
        ("Tốt nghiệp đại học chuyên ngành tiếng Anh", set()),
        ("Tốt nghiệp đại học; có khả năng đọc tài liệu tiếng Anh", {"english"}),
        ("IELTS 6.5 hoặc TOEIC 700", {"english"}),
        ("Không yêu cầu IELTS", set()),
        ("Tốt nghiệp đại học, có chứng chỉ IELTS 6.5", {"english"}),
        ("HSK 4, JLPT N2, TOPIK 3", {"chinese", "japanese", "korean"}),
        ("Ưu tiên:\nPython\nExcel\nYêu cầu:\nJava", {"python", "excel", "java"}),
        ("Không yêu cầu Python; thành thạo Excel", {"excel"}),
        ("Không yêu cầu Python, thành thạo Excel", {"excel"}),
        ("Thành thạo Excel, Python không bắt buộc", {"excel"}),
        ("Python không bắt buộc, Excel", {"excel"}),
        ("Không yêu cầu Python, Java", set()),
        ("Our company uses Python", set()),
        ("Work with Japanese company", set()),
        ("Gửi CV và link GitHub", set()),
        ("Biết sử dụng GitHub", {"github"}),
        ("Biết GitHub Actions", set()),
        ("Biết viết API REST và REST APIs", {"rest_api"}),
        ("Understanding REST and SOAP integrations", {"rest_api"}),
        ("Take a rest after work", set()),
        ("Có kinh nghiệm object-oriented programming và C #", {"oop", "csharp"}),
        ("Sử dụng phần mềm kế toán (MISA, Fast)", {"misa", "fast_accounting"}),
        ("Biết Python, fast-evolving environment", {"python"}),
        ("CV: https://github.com/example", set()),
        ("I love this word", set()),
        ("Sử dụng Word và Excel", {"word", "excel"}),
        ("Sử dụng Office", {"ms_office"}),
        ("Có kiến thức Digital Marketing", {"digital_marketing"}),
        ("Có kinh nghiệm digital; hiểu về marketing", {"digital_marketing"}),
        ("Có kinh nghiệm viết content và SEO", {"content_marketing", "seo"}),
        ("Am hiểu marketing, biết viết bài", {"content_marketing"}),
        ("Có khả năng thiết kế banner và dựng video, am hiểu marketing", {"content_marketing"}),
        ("Kỹ năng quay chụp media; tốt nghiệp chuyên ngành Marketing", {"content_marketing"}),
        ("Có khả năng thiết kế banner và dựng video", set()),
        ("Tốt nghiệp chuyên ngành thiết kế đồ họa hoặc Marketing", set()),
        ("Biết viết content", set()),
        (
            "Có kinh nghiệm viết SEO, post social; am hiểu marketing",
            {"content_marketing", "seo", "social_media"},
        ),
        ("Có kinh nghiệm Front Office tại khách sạn", set()),
        ("Ability to learn fast, work in fast-moving teams", set()),
        ("Không yêu cầu kinh nghiệm, được đào tạo. Kỹ năng đọc tiếng Anh cơ bản", {"english"}),
        ("Tiếng Anh tốt, không yêu cầu IELTS", {"english"}),
        ("Làm digital products; tốt nghiệp Marketing", set()),
        ("Biết tiếng Trung (Anh) giao tiếp", {"chinese", "english"}),
        ("Tiếng Anh hoặc Hàn giao tiếp tốt", {"english", "korean"}),
        ("Tốt nghiệp chuyên ngành tiếng Trung (Anh)", set()),
        ("Anh chị có kiến thức Python", {"python"}),
        (
            "Có kinh nghiệm lập báo cáo thuế và báo cáo tài chính",
            {"tax_reporting", "financial_reporting"},
        ),
        (None, set()),
        (" KHÔNG ", set()),
    ],
)
def test_positive_pairs(matcher, text, expected):
    result = matcher.extract(text)
    assert set(result.skill_codes) == expected
    if text:
        assert all(text[e.start : e.end] == e.text for e in result.evidence)
        assert all(e.context_start <= e.start < e.end <= e.context_end for e in result.evidence)


def test_conflict_withholds_whole_job_but_retains_evidence(matcher):
    result = matcher.extract("Biết Python và Excel; không yêu cầu Python")
    assert result.status == "needs_review"
    assert not result.skill_codes
    assert {e.skill_code for e in result.evidence} == {"python", "excel"}
    assert "conflicting_assertions" in result.reasons


def test_owner_training_override_is_exact_and_does_not_change_generic_training():
    from job_warehouse.skills.models import ContextOverride
    from job_warehouse.skills.profile import text_hash

    text = "Kiến thức: Được đào tạo Tin học văn phòng"
    policy = SkillPolicy(
        "owner-test",
        ("required", "preferred"),
        context_overrides=(
            ContextOverride(
                text_hash(text),
                "office_it",
                "Được đào tạo Tin học văn phòng",
                "required",
                "test_Q8",
            ),
        ),
    )
    matcher = SkillMatcher(load_taxonomy(), policy)
    assert matcher.extract(text).skill_codes == ("office_it",)
    assert matcher.extract(text + ".").status == "needs_review"
    assert matcher.extract("Sẽ được đào tạo Tin học văn phòng sau khi nhận việc").skill_codes == ()
    result = matcher.extract(text)
    assert result.evidence[0].rule_id == "owner_context:test_Q8"


def test_slash_list_does_not_claim_an_explicit_or(matcher):
    result = matcher.extract("Biết Python/Java")
    assert result.skill_codes == ("java", "python")
    assert {e.logic for e in result.evidence} == {"listed_together_unspecified"}


def test_content_and_explicit_seo_can_share_the_same_phrase(matcher):
    result = matcher.extract("Có kinh nghiệm viết SEO; am hiểu marketing")
    assert set(result.skill_codes) == {"content_marketing", "seo"}
    assert len(result.evidence) == 2


def test_minimum_subset_is_retained_without_claiming_every_skill_is_mandatory(matcher):
    result = matcher.extract("Biết ít nhất 2 ngôn ngữ (Java, Python, PHP)")
    assert result.skill_codes == ("java", "php", "python")
    assert {e.logic for e in result.evidence} == {"minimum_subset:2"}


def test_alternatives_keep_group_and_do_not_duplicate_pairs(matcher):
    result = matcher.extract("Biết Python/Java hoặc Python")
    assert result.skill_codes == ("java", "python")
    assert len(result.evidence) == 3
    assert {e.logic for e in result.evidence} == {"any_of"}
    assert len({e.group_id for e in result.evidence}) == 1


def test_preference_and_certificate_policies_are_explicit():
    matcher = SkillMatcher(
        load_taxonomy(), SkillPolicy("only-required", ("required",), "evidence_only")
    )
    assert matcher.extract("Ưu tiên Excel").skill_codes == ()
    result = matcher.extract("IELTS 6.5")
    assert result.skill_codes == ()
    assert result.evidence[0].context == "mentioned"
    assert result.evidence[0].rule_id.startswith("certificate_to_language:")


def test_unicode_offsets_are_on_original_text(matcher):
    text = "İstanbul: Thành thạo EXCEL, C++, C# và .NET"
    result = matcher.extract(text)
    assert set(result.skill_codes) == {"excel", "cpp", "csharp", "dotnet"}
    for e in result.evidence:
        assert text[e.start : e.end] == e.text


def test_unicode_casefold_expansion_preserves_full_source_span():
    taxonomy = Taxonomy(
        {"sample": Skill("sample", "Synthetic concept", "tool", "Unicode offset test")},
        (Alias("sample", "STRASSE"),),
    )
    matcher = SkillMatcher(taxonomy, SkillPolicy("test", ("required", "preferred")))
    text = "Synthetic: Straße"
    result = matcher.extract(text)
    assert result.skill_codes == ("sample",)
    assert result.evidence[0].text == "Straße"
    assert text[result.evidence[0].start : result.evidence[0].end] == "Straße"


def test_short_alias_and_symbol_boundaries():
    skills = {
        code: Skill(code, name, "technology", "Synthetic language")
        for code, name in [("c", "C"), ("cpp", "C++"), ("csharp", "C#"), ("go", "Go")]
    }
    taxonomy = Taxonomy(
        skills,
        (
            Alias("c", "C", "contextual"),
            Alias("go", "Go", "contextual"),
            Alias("cpp", "C++"),
            Alias("csharp", "C#"),
        ),
    )
    matcher = SkillMatcher(taxonomy, SkillPolicy("test", ("required", "preferred")))
    assert matcher.extract("Biết C++ và C#").skill_codes == ("cpp", "csharp")
    assert matcher.extract("Go to the office").status == "needs_review"


@pytest.mark.parametrize("contexts", [(), ("preferred",), ("required", "mentioned")])
def test_invalid_pair_semantics_are_rejected(contexts):
    with pytest.raises(ValueError, match="contexts"):
        SkillPolicy("test", contexts)


def test_alias_collision_and_short_unqualified_aliases_are_rejected():
    skills = {"a": Skill("a", "A", "tool", "Synthetic tool")}
    with pytest.raises(ValueError, match="Duplicate"):
        Taxonomy(skills, (Alias("a", "Excel"), Alias("a", "EXCEL")))
    with pytest.raises(ValueError, match="Short"):
        Taxonomy(skills, (Alias("a", "AI"),))
