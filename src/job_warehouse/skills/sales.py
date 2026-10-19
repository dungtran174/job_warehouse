"""Batch 01 context checks, isolated from the frozen three-industry extractor."""

import re
from dataclasses import replace
from pathlib import Path

from job_warehouse.skills.context import ABILITY, EDUCATION, NEGATED, PREFERRED, classify_context
from job_warehouse.skills.matcher import SkillMatcher
from job_warehouse.skills.models import Alias, Extraction

SALES_MAPPINGS = Path(__file__).with_name("mappings_sales")
SALES_EXTRACTOR_VERSION = "requirements-skills-sales-v3"

# Concrete professional actions can stand as requirements without an ability verb.
TASK = re.compile(
    r"tìm kiếm khách hàng|phát triển khách hàng|tư vấn (?:sản phẩm|bán hàng|giải pháp)|"
    r"(?:xử lý|giải quyết) khiếu nại|(?:lập|xây dựng) báo giá|"
    r"(?:quản lý|xử lý|theo dõi) đơn hàng|chốt (?:đơn|sales?|deal|hợp đồng)|"
    r"phát triển thị trường|quản lý hệ thống phân phối|"
    r"chăm sóc khách hàng|"
    r"prospecting|lead generation|order processing|complaint handling",
    re.I,
)
CAPABILITY = re.compile(
    ABILITY.pattern + r"|\b(?:kinh nghiệm|kiến thức|kĩ năng|khả năng|trình độ|"
    r"nắm chắc|thông thạo|thành thào|thạo|quen thuộc|thao tác|s ử dụng|chứng chỉ|đã từng|"
    r"thiết kế cơ bản|có thế|kinh ngiệm|"
    r"competenc\w*|qualification\w*|advanced|intermediate|basic|good|strong|"
    r"fluency|working in|speak|communication|communicate|comfortable|"
    r"fluent|fluent in|working knowledge|experienced|experiences?)\b",
    re.I,
)
FUTURE_TRAINING = re.compile(
    r"(?:sẽ |được |công ty |chương trình )?đào tạo|được hướng dẫn|"
    r"training provided|will be trained",
    re.I,
)
INTEREST = re.compile(r"đam mê|yêu thích|định hướng|mong muốn|quan tâm|interest in", re.I)
PREDICATE = re.compile(
    r"\b(?:ưu tiên|thành thạo|thông thạo|sử dụng|s ử dụng|quen thuộc|"
    r"có kinh nghiệm|có kiến thức|có kỹ năng|có khả năng|biết|am hiểu|"
    r"không yêu cầu|không có kinh nghiệm|chưa có kinh nghiệm|"
    r"sẽ được đào tạo|yêu thích|đam mê)\b",
    re.I,
)
LANGUAGE_LEVEL = re.compile(
    r"^\s*[:(]?\s*(?:tốt|khá|cơ bản|trung cấp|thành thạo|lưu loát|"
    r"good|basic|intermediate|fluent|business|conversational|trình độ)\b",
    re.I,
)
GENERIC_CONTEXT_RULES = {
    "requirements_assertion",
    "preference_cue_or_heading",
    "provided_training",
    "explicit_no_requirement",
    "mixed_negation_preference",
    "education_not_capability",
    "conflicting_assertions",
    "training_time_unspecified",
    "short_or_ambiguous_alias",
}
OFFICE_HEADING = re.compile(
    r"tin học (?:văn phòng|VP)|vi tính văn phòng|máy tính văn phòng|"
    r"phần mềm (?:tiện ích )?văn phòng|ứng dụng văn phòng|công cụ văn phòng|office computer",
    re.I,
)
SECTION = re.compile(
    r"Learning\s*&\s*Development Opportunities|Learning Opportunities|"
    r"(?:^|\n|\.\s)\s*(?:Benefits|Thu nhập|Quyền lợi|Phúc lợi)\s*:?|"
    r"Yêu cầu(?: công việc)?|Requirements|Qualifications",
    re.I,
)


class SalesSkillMatcher(SkillMatcher):
    """Re-evaluate claims locally and retain clear pairs beside unclear ones."""

    @staticmethod
    def _alias_context_ok(text: str, start: int, end: int, alias: Alias) -> bool:
        local = text[max(0, start - 120) : end + 100]
        if alias.text.casefold() in {"world", "wold"} and not re.search(
            r"Excel|PowerPoint|Microsoft|tin học|vi tính|phần mềm",
            local,
            re.I,
        ):
            return False
        if alias.skill_code == "word" and re.search(
            r"word\s*[-–]\s*for\s*[-–]\s*word",
            local,
            re.I,
        ):
            return False
        if alias.text.casefold() in {"canvas", "cava"} and not re.search(
            r"Photoshop|CapCut|cupcut|thiết kế|phần mềm|công cụ",
            local,
            re.I,
        ):
            return False
        if alias.text.casefold() == "oracle" and not re.search(
            r"database|\bDB\b|csdl|cơ sở dữ liệu|SQL",
            local,
            re.I,
        ):
            return False
        if alias.mode == "shared_language" and re.search(
            r"ngoại ngữ\s*:?\s*(?:(?:Anh|Hàn|Trung|Nhật|Pháp|Đức)\s*[,/;]\s*)*$",
            text[max(0, start - 100) : start],
            re.I,
        ):
            return True
        if alias.text.casefold() == "sheets" and not re.search(
            r"Google|Workspace|Excel",
            local,
            re.I,
        ):
            return False
        return SkillMatcher._alias_context_ok(text, start, end, alias)

    def extract(self, text: str | None) -> Extraction:
        original = super().extract(text)
        if text is None or not original.evidence:
            return original
        evidence = []
        for item in original.evidence:
            # Separate new recruiting predicates even when the source omitted
            # punctuation. Keep governing predicates inside the evidence window.
            starts = [
                m.start()
                for m in PREDICATE.finditer(text, item.context_start, item.context_end)
                if m.end() <= item.start
            ]
            ends = [
                m.start()
                for m in PREDICATE.finditer(text, item.context_start, item.context_end)
                if m.start() >= item.end
            ]
            left = max(starts) if starts else item.context_start
            right = min(ends) if ends else item.context_end
            # A semicolon inside a bounded tool list does not erase an explicit
            # governing office-skill heading or ability predicate outside '(' .
            for group in re.finditer(r"\([^()\n]{1,300}\)", text):
                if group.start() < item.start < item.end <= group.end():
                    prefix = text[max(0, group.start() - 140) : group.start()]
                    if OFFICE_HEADING.search(prefix) or CAPABILITY.search(prefix):
                        left = min(left, max(0, group.start() - 140))
                        right = max(right, group.end())
                    break
            item = replace(item, context_start=left, context_end=right)
            before = text[item.context_start : item.start]
            after = text[item.end : item.context_end]
            local = text[item.context_start : item.context_end]
            context, rule = item.context, item.rule_id
            certificate = rule.startswith("certificate_to_language:")
            if rule in GENERIC_CONTEXT_RULES or certificate:
                context, rule = classify_context(
                    text,
                    item.start,
                    item.end,
                    left,
                    right,
                    "required",
                    language=self.taxonomy.skills[item.skill_code].group == "language",
                    certificate=certificate,
                )
                if certificate:
                    rule = "certificate_to_language:" + rule
            if re.search(r"\bkhông có kinh nghiệm\b", before, re.I):
                context, rule = "negated", "sales_no_prior_experience"
            # Resolve only the local claim, not a different skill in the paragraph.
            last_education = list(
                re.finditer(
                    EDUCATION.pattern + r"|\b(?:bachelor or college certificate|certificate in)\b",
                    before,
                    re.I,
                )
            )
            last_ability = list(CAPABILITY.finditer(before))
            last_training = list(FUTURE_TRAINING.finditer(before))
            last_interest = list(INTEREST.finditer(before))
            ability_after_education = bool(last_ability) and (
                not last_education or last_ability[-1].start() > last_education[-1].start()
            )
            near_after = after[:80]
            language_level = self.taxonomy.skills[item.skill_code].group == "language" and bool(
                LANGUAGE_LEVEL.search(after)
            )
            office_heading = bool(OFFICE_HEADING.search(local))
            positive = bool(
                CAPABILITY.search(local)
                or PREFERRED.search(local)
                or language_level
                or office_heading
            )
            explicit_task = bool(TASK.search(item.text))
            if (
                context == "mentioned"
                and rule == "provided_training"
                and last_training
                and re.search(
                    r"(?:cần bạn có|yêu cầu|thành thạo|biết sử dụng|có kinh nghiệm|khả năng)",
                    before[last_training[-1].end() :],
                    re.I,
                )
            ):
                context, rule = "required", "sales_capability_after_training_clause"
            if context == "negated" and re.search(
                r"không yêu cầu (?:bằng cấp|độ tuổi|giới tính)", local, re.I
            ):
                without_unrelated = re.sub(
                    r"không yêu cầu (?:bằng cấp|độ tuổi|giới tính)", "", local, flags=re.I
                )
                if CAPABILITY.search(before) and not NEGATED.search(without_unrelated):
                    context, rule = "required", "sales_unrelated_qualification_waiver"
            if context in {"required", "preferred", "ambiguous"}:
                if last_training and not re.search(
                    r"cần bạn có|yêu cầu|thành thạo|biết sử dụng|có kinh nghiệm|khả năng",
                    before[last_training[-1].end() :],
                    re.I,
                ):
                    context, rule = "mentioned", "sales_future_training_not_skill"
                elif last_interest and not re.search(
                    r"có kinh nghiệm|có kỹ năng|biết|sử dụng|am hiểu|thành thạo",
                    before[last_interest[-1].end() :],
                    re.I,
                ):
                    context, rule = "mentioned", "sales_interest_not_skill"
                elif last_education and not ability_after_education:
                    context, rule = "mentioned", "sales_degree_not_skill"
                elif re.search(r"(?:thưởng|bonus|best)\s*(?:best\s*)?$", before[-40:], re.I):
                    context, rule = "mentioned", "sales_reward_not_skill"
                elif context == "ambiguous" and rule == "conflicting_assertions":
                    pass
                elif not positive and not explicit_task:
                    context, rule = "ambiguous", "sales_bare_list_without_capability"
                elif context == "ambiguous" and rule == "short_or_ambiguous_alias":
                    # Keep product-disambiguation checks from the original matcher.
                    pass
                elif context == "ambiguous":
                    pass
            # Owner Q2: an explicit office-skill heading governs its tool list.
            if (
                office_heading
                and context == "ambiguous"
                and rule in {"short_or_ambiguous_alias", "sales_bare_list_without_capability"}
                and not NEGATED.search(local)
                and not FUTURE_TRAINING.search(before)
            ):
                context, rule = "required", "owner_sales_q2_office_skill_heading"
            if item.skill_code in {"misa", "fast_accounting"} and re.search(
                r"sử dụng\s+hoặc\s+bán.{0,100}phần mềm kế toán",
                local,
                re.I,
            ):
                context, rule = "preferred", "owner_sales_q1_used_or_sold_alternative"
                item = replace(item, logic="any_of", group_id=f"{left}:{right}")
            if (
                context in {"negated", "ambiguous"}
                and re.search(
                    r"helpful|advantage|lợi thế|ưu tiên",
                    local,
                    re.I,
                )
                and re.search(r"not mandatory|không bắt buộc", local, re.I)
            ):
                context, rule = "preferred", "sales_optional_benefit"
            # Skill names in commercial metrics, departments or client channels
            # are not applicant capabilities.
            if item.skill_code == "review_ban_hang_sales" and re.search(
                r"(?:doanh số|doanh thu|báo cáo|data|analytics|revenue|targets?|"
                r"partner|collaborat\w*|liên hệ|phối hợp).{0,40}$",
                before,
                re.I,
            ):
                context, rule = "mentioned", "sales_metric_or_department"
            if item.skill_code == "review_ban_hang_sales" and (
                re.search(r"phần mềm|hệ thống|software|tools?", before[-60:], re.I)
                or re.match(r"\s+(?:reporting|reports?|data|revenue|targets?)\b", after, re.I)
            ):
                context, rule = "mentioned", "sales_software_or_metric_not_capability"
            if item.skill_code == "review_ban_hang_sales" and (
                re.match(r"\s+admin\b", after, re.I)
                or re.search(r"tuyển dụng.{0,90}(?:vị trí|vị trí.*giáo viên).{0,80}$", before, re.I)
                or (
                    item.text.casefold() == "lĩnh vực kinh doanh"
                    and not re.search(
                        r"kinh nghiệm|làm việc|am hiểu.{0,20}quy trình",
                        before,
                        re.I,
                    )
                )
            ):
                context, rule = "mentioned", "sales_other_role_or_generic_business_domain"
            if (
                item.skill_code == "review_cham_soc_khach_hang"
                and re.search(
                    r"tư duy|tố chất|tinh thần|tính cách",
                    before[-80:],
                    re.I,
                )
                and not re.search(r"kinh nghiệm|kỹ năng|khả năng", before[-80:], re.I)
            ):
                context, rule = "mentioned", "service_mindset_not_professional_capability"
            if (
                item.skill_code == "ms_office"
                and item.text.casefold() == "office"
                and re.search(
                    r"HORECA|khách hàng|kênh|trường học|bệnh viện",
                    local,
                    re.I,
                )
                and not re.search(r"Microsoft|tin học|phần mềm|thành thạo|sử dụng", local, re.I)
            ):
                context, rule = "mentioned", "office_customer_channel"
            if (
                item.skill_code == "ms_office"
                and item.text.casefold() == "office"
                and re.match(
                    r"\s+computer\b",
                    after,
                    re.I,
                )
            ):
                context, rule = "mentioned", "office_computer_not_microsoft_office"
            if (
                item.skill_code == "illustrator"
                and item.text.casefold() == "ai"
                and re.search(
                    r"\bAI\s*(?:tools?|foundation|agent|ứng dụng|trong|hỗ trợ|tạo sinh)|"
                    r"trí tuệ nhân tạo|prompt engineering|ChatGPT|Gemini|Copilot",
                    local,
                    re.I,
                )
            ):
                context, rule = "mentioned", "artificial_intelligence_not_illustrator"
            if (
                item.skill_code == "review_crm"
                and item.text.casefold() != "crm"
                and not re.search(
                    r"software|tools?|systems?|phần mềm|hệ thống",
                    local,
                    re.I,
                )
            ):
                context, rule = "ambiguous", "crm_software_not_demonstrated"
            if item.skill_code == "social_media" and not re.search(
                r"marketing|truyền thông|quản trị|quản lý|nội dung|xây dựng|phát triển|quảng cáo",
                local,
                re.I,
            ):
                context, rule = "mentioned", "social_platform_usage_not_marketing"
            if item.skill_code == "content_marketing":
                # A marketing degree by itself cannot license content inference.
                content_context = re.sub(
                    r"(?:tốt nghiệp|chuyên ngành|degree|major|bachelor|certificate)"
                    r".{0,250}?(?=[.;\n]|$)",
                    "",
                    text,
                    flags=re.I,
                )
                if not re.search(
                    r"marketing|quảng cáo|quảng bá|fanpage|tiếp thị|truyền thông|\bSEO\b|\bads\b",
                    content_context,
                    re.I,
                ):
                    context, rule = "mentioned", "content_without_marketing_work_context"
            # Source sometimes mixes benefits into requirements. Offered training,
            # credentials and resources are not prior applicant capabilities.
            sections = list(SECTION.finditer(text, 0, item.start))
            if sections and not re.search(
                r"yêu cầu|requirements|qualifications",
                sections[-1].group(),
                re.I,
            ):
                context, rule = "mentioned", "benefits_section_not_applicant_skill"
            if re.search(r"được cấp|cấp chứng chỉ|được hỗ trợ", before[-150:], re.I):
                context, rule = "mentioned", "offered_resource_or_certificate"
            # A professional duty is positive only outside rejected/uncertain context.
            if context == "required" and explicit_task and not NEGATED.search(near_after):
                rule = "sales_concrete_professional_duty"
            evidence.append(replace(item, context=context, rule_id=rule))
        conflicts = {
            e.skill_code
            for e in evidence
            if e.context == "negated"
            and any(
                x.skill_code == e.skill_code and x.context in self.policy.positive_contexts
                for x in evidence
            )
        }
        evidence = [
            replace(e, context="ambiguous", rule_id="conflicting_assertions")
            if e.skill_code in conflicts
            else e
            for e in evidence
        ]
        codes = tuple(
            sorted({e.skill_code for e in evidence if e.context in self.policy.positive_contexts})
        )
        reasons = tuple(sorted({e.rule_id for e in evidence if e.context == "ambiguous"}))
        status = (
            "expanded_partial_match"
            if codes and reasons
            else "needs_review"
            if reasons
            else "processed_match"
            if codes
            else "processed_no_match"
        )
        return Extraction(status, codes, tuple(evidence), reasons)
