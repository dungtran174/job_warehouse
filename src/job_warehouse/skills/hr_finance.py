"""Explicit HR, finance and legal capabilities; old accepted batches stay frozen."""

import re
from dataclasses import replace
from pathlib import Path

from job_warehouse.skills.context import EDUCATION, NEGATED, PREFERRED, STRONG_BOUNDARY
from job_warehouse.skills.models import Alias, Extraction
from job_warehouse.skills.sales import SalesSkillMatcher

HR_FINANCE_MAPPINGS = Path(__file__).with_name("mappings_hr_finance")
HR_FINANCE_VERSION = "requirements-skills-hr-finance-legal-v3"
LAW_COMPONENTS = {
    "dân sự",
    "thương mại",
    "doanh nghiệp",
    "đất đai",
    "đầu tư",
    "xây dựng",
    "lao động",
    "thuế",
    "bảo hiểm",
}
LAW_LIST = re.compile(
    r"(?:luật|pháp luật)\s+(?:liên quan đến\s+)?(?:(?:dân sự|thương mại|doanh nghiệp|"
    r"tố tụng|lao động|bảo hiểm|thuế|về|"
    r"đầu tư|xây dựng|đất đai|kinh doanh bất động sản|kinh doanh BĐS|"
    r"bất động sản|kinh tế|nhà ở|và|[/,;\s])+)$",
    re.I,
)
PROFESSIONAL_TASK = re.compile(
    r"soạn thảo|rà soát|chấm công|tính lương|phân tích (?:tài chính|báo cáo|BCTC|dữ liệu)|"
    r"thẩm định|quản lý (?:hồ sơ|nguồn vốn|dòng tiền|rủi ro)|thu hồi nợ|xử lý nợ|"
    r"lưu trữ hồ sơ|quản lý sắp xếp hồ sơ|tra cứu biểu thuế",
    re.I,
)
ABILITY = re.compile(
    r"kinh nghiệm|kinh nghiệp|am hiểu|hiểu biết|hiều biết|nắm (?:vững|được|chắc)|biết|"
    r"thành thạo|sử dụng|kỹ năng|kiến thức|nền tảng|am hiệu|quen thuộc|"
    r"experience|knowledge|proficien|competenc",
    re.I,
)
OFFER = re.compile(
    r"được (?:hưởng|cấp|đào tạo|tham gia)|tham gia đầy đủ|sẽ được|"
    r"công ty (?:đóng|hỗ trợ)|quyền lợi|phúc lợi|benefits",
    re.I,
)
SPECIALIST_PARENTS = {
    "review_ke_toan_tong_hop": {"review_nghiep_vu_ke_toan"},
    "review_phan_tich_bao_cao_tai_chinh": {"financial_reporting"},
    "legal_drafting": {"hr_document_drafting"},
    "review_soan_thao_hop_dong": {"hr_document_drafting"},
    "hr_personnel_administration": {"hr_administration", "hr_human_resources"},
    "hr_hrm": {"hr_human_resources"},
    "hr_payroll_software": {"payroll", "hr_timekeeping"},
    "finance_consulting": {"sales_product_consulting"},
    "review_phan_mem_ke_toan": {"review_nghiep_vu_ke_toan"},
    "hr_insurance_law": {"review_bao_hiem_xa_hoi"},
    "oracle_db": {"review_oracle"},
    "legal_consulting": {"legal_legal_knowledge"},
    "legal_debt_recovery_law": {"legal_legal_knowledge", "finance_debt_recovery"},
    "sales_real_estate_legal": {"legal_legal_knowledge"},
}


class HRFinanceSkillMatcher(SalesSkillMatcher):
    @staticmethod
    def _alias_context_ok(text: str, start: int, end: int, alias: Alias) -> bool:
        before = text[max(0, start - 240) : start]
        local = text[max(0, start - 140) : end + 70]
        term = alias.text.casefold()
        if term in LAW_COMPONENTS:
            expanded_list = re.search(
                r"pháp luật[^.;\n]{0,180}:\s*(?:(?:thương mại|doanh nghiệp|đầu tư|"
                r"an toàn thực phẩm|thuế|kế toán|dân sự|đất đai|xây dựng|và|[,\s])+)$",
                before,
                re.I,
            )
            return LAW_LIST.search(before) is not None or expanded_list is not None
        if term == "hành chính" and re.search(r"(?:giờ|cơ quan)\s*$", before, re.I):
            return False
        if alias.skill_code == "legal_litigation" and re.search(r"ngoài\s*$", before, re.I):
            return False
        if alias.skill_code == "review_oracle":
            return not bool(re.search(r"(?:làm việc tại|công ty|tập đoàn)\s*$", before, re.I))
        if term == "đào tạo":
            return bool(re.search(r"tuyển dụng|nhân sự|nhân viên|đội ngũ|HR", local, re.I))
        if term == "pp":
            return bool(re.search(r"tin học|vi tính|office|word|excel|phần mềm", local, re.I))
        if term == "words" and not re.search(
            r"office|word|excel|exel|phần mềm|tin học|vi tính", before, re.I
        ):
            return False
        return SalesSkillMatcher._alias_context_ok(text, start, end, alias)

    def _candidates(self, text: str) -> list[tuple[int, int, Alias]]:
        items = super()._candidates(text)
        return [
            (s, e, a)
            for s, e, a in items
            if not any(
                bs < e and s < be and a.skill_code in SPECIALIST_PARENTS.get(b.skill_code, set())
                for bs, be, b in items
                if b.skill_code != a.skill_code
            )
        ]

    def _segments(self, text: str, spans: list[tuple[int, int]]) -> list[tuple[int, int, str]]:
        segments = super()._segments(text, spans)
        # Merge only boundaries crossed by a literal dictionary concept, not
        # unrelated neighboring claims. Never change source offsets or text.
        for start, end in spans:
            touched = [i for i, (s, e, _) in enumerate(segments) if s < end and start < e]
            if len(touched) > 1:
                first, last = touched[0], touched[-1]
                merged = (segments[first][0], segments[last][1], segments[first][2])
                segments[first : last + 1] = [merged]
        return segments

    def extract(self, text: str | None) -> Extraction:
        base = super().extract(text)
        if text is None or not base.evidence:
            return base
        result = []
        for item in base.evidence:
            before = text[item.context_start : item.start]
            local = text[item.context_start : item.context_end]
            context, rule = item.context, item.rule_id
            if (
                self.taxonomy.skills[item.skill_code].group == "language"
                and re.match(
                    r"\s*:?\s*(?:thông thạo|thành thạo|cơ bản|khá|tốt|lưu loát)",
                    text[item.end : item.end + 70],
                    re.I,
                )
                and context == "ambiguous"
                and not NEGATED.search(before)
            ):
                item = replace(
                    item, context_end=max(item.context_end, min(len(text), item.end + 70))
                )
                context = (
                    "preferred" if PREFERRED.search(text[item.end : item.end + 70]) else "required"
                )
                rule = "hr_language_level_after_name"
            if item.skill_code == "office_it" and context in {"mentioned", "ambiguous"}:
                after = text[item.end : item.end + 30]
                if re.match(r"\s*:?\s*(?:cơ bản|tốt|khá|thành thạo)", after, re.I) and (
                    re.search(r"kinh nghiệm|giới tính|trình độ tin học", before, re.I)
                    or not EDUCATION.search(before)
                ):
                    item = replace(
                        item, context_end=max(item.context_end, min(len(text), item.end + 30))
                    )
                    context, rule = "required", "hr_office_level_field"
            if (
                self.taxonomy.skills[item.skill_code].group == "tool"
                and context == "ambiguous"
                and rule == "sales_bare_list_without_capability"
            ):
                prefix = text[max(0, item.start - 160) : item.start]
                governed = re.search(
                    r"(?:thành thạo|thông thạo|sử dụng tốt|biết sử dụng)\s+"
                    r"(?:(?:Word|Excel|PowerPoint|Outlook|Microsoft Office|[,/\s–—-])+)$",
                    prefix,
                    re.I,
                )
                if governed:
                    item = replace(item, context_start=max(0, item.start - 160) + governed.start())
                    context, rule = "required", "hr_office_tool_shared_predicate"
            if item.skill_code == "financial_reporting" and re.search(
                r"phân tích\s*[:;,]?\s*$", before, re.I
            ):
                item = replace(item, skill_code="review_phan_tich_bao_cao_tai_chinh")
                rule = "hr_finance_explicit_statement_analysis"
            if context == "mentioned" and rule == "education_not_capability":
                education = list(EDUCATION.finditer(before))
                abilities = list(ABILITY.finditer(before))
                if (
                    abilities
                    and (not education or abilities[-1].start() > education[-1].start())
                    and not NEGATED.search(before[abilities[-1].start() :])
                    and not re.search(
                        r"được đào tạo|sẽ đào tạo|đam mê|định hướng",
                        before[abilities[-1].start() :],
                        re.I,
                    )
                ):
                    context, rule = "required", "hr_explicit_capability_after_education"
            if (
                item.skill_code == "office_it"
                and item.text.casefold() in {"tin học: văn phòng", "vi tính: văn phòng"}
                and re.search(r"ngoại ngữ|trình độ|kinh nghiệm", before, re.I)
                and not OFFER.search(before)
            ):
                context, rule = "required", "hr_explicit_office_field_heading"
            # Some finite product/professional lists inherit a predicate before a dash.
            raw_prefix = text[max(0, item.start - 180) : item.start]
            if (
                item.skill_code == "review_phan_mem_ke_toan"
                and re.search(r"thành thạo[^.;\n]{0,160}$", raw_prefix, re.I)
                and context == "ambiguous"
            ):
                item = replace(item, context_start=max(0, item.start - 180))
                context, rule = "required", "hr_shared_professional_software_predicate"
            # A later explicit competency field is independent from an earlier degree.
            prefix = text[max(0, item.start - 200) : item.start]
            suffix = text[item.end : min(len(text), item.end + 100)]
            heading = re.search(
                r"(?:ngoại ngữ|kiến thức|kỹ năng|kĩ năng|nền tảng|am hiểu|am hiệu|"
                r"quen thuộc|knowledge|skills?|proficient)\s*(?:về\s+|of\s+|"
                r"in\s+|[:：]\s*)?[^.;\n]{0,100}$",
                prefix,
                re.I,
            )
            if (
                context in {"mentioned", "ambiguous"}
                and heading
                and not (
                    EDUCATION.search(prefix[heading.start() :])
                    or OFFER.search(prefix[heading.start() :])
                    or NEGATED.search(prefix[heading.start() :])
                )
            ):
                item = replace(item, context_start=max(0, item.start - 200) + heading.start())
                context, rule = "required", "hr_explicit_later_competency_field"
            if self.taxonomy.skills[item.skill_code].group in {"language", "tool"}:
                # Proficiency can follow a bounded office-tool list or language name.
                tail = re.match(
                    r"\s*(?:nghe nói đọc đánh máy\s+)?(?:[:;,/\s]*(?:Word|Excel|"
                    r"PowerPoint|Outlook))*"
                    r"\s*[:：]?\s*(?:tốt|khá|cơ bản|thành thạo|lưu loát)\b",
                    suffix,
                    re.I,
                )
                if (
                    tail
                    and context in {"mentioned", "ambiguous"}
                    and not NEGATED.search(prefix[-60:])
                ):
                    item = replace(item, context_end=max(item.context_end, item.end + tail.end()))
                    context, rule = "required", "hr_proficiency_after_bounded_skill_list"
            # MISA is accounting by default; owner chose a separate HR concept.
            if (
                item.skill_code == "misa"
                and re.search(r"quản lý nhân sự|\bHRM\b|\bHRIS\b", local, re.I)
                and not re.search(r"kế toán", local, re.I)
            ):
                item = replace(item, skill_code="hr_misa")
                rule = "owner_batch02_q1_misa_hr_context"
            if item.skill_code in {
                "hr_recruitment",
                "hr_human_resources",
                "hr_personnel_administration",
            } and re.search(r"(?:quy mô|công ty có|trên|hơn)\s*\d+\s*$", before, re.I):
                context, rule = "mentioned", "hr_company_headcount_not_capability"
            if (
                item.skill_code == "hr_recruitment"
                and re.search(r"(?:công ty|chúng tôi|đang|cần)\s*$", before, re.I)
                and not ABILITY.search(before)
            ):
                context, rule = "mentioned", "hr_company_recruiting_applicant"
            if item.skill_code == "review_cham_soc_khach_hang" and re.search(
                r"phần mềm|công cụ|hệ thống|nền tảng", before, re.I
            ):
                context, rule = "mentioned", "hr_service_software_not_service_capability"
            if item.skill_code.startswith(
                ("hr_", "finance_", "legal_", "review_luat_", "review_thue_", "review_bao_hiem_")
            ):
                offer = OFFER.search(before)
                if offer is not None and not re.search(
                    r"có kinh nghiệm|am hiểu|nắm vững|biết (?:xử lý|thực hiện)|có kiến thức",
                    before[offer.end() :],
                    re.I,
                ):
                    context, rule = "mentioned", "hr_offered_benefit_or_training"
                elif (
                    context == "ambiguous"
                    and rule == "sales_bare_list_without_capability"
                    and PROFESSIONAL_TASK.search(item.text)
                    and not NEGATED.search(local)
                ):
                    context, rule = "required", "hr_concrete_professional_duty"
                # Bare 'đào tạo' can name an HR process, not a promise of training.
                elif (
                    rule == "sales_future_training_not_skill"
                    and re.search(r"am hiểu|kiến thức|kinh nghiệm", before, re.I)
                    and not re.search(r"được đào tạo|sẽ đào tạo", before, re.I)
                ):
                    context, rule = "required", "hr_training_process_not_offered_training"
            if item.skill_code == "hr_recruitment" and re.search(
                r"(?:trang|website|cổng)\s*$|vị trí\s*$",
                before,
                re.I,
            ):
                context, rule = "ambiguous", "hr_recruiting_site_or_advertised_position"
            if item.skill_code == "review_ban_hang_sales" and (
                re.search(r"hợp đồng\s*$|kế toán[^.;\n]{0,45}$", before, re.I)
                or re.search(r"tuyển dụng[^.;\n]{0,100}$", before, re.I)
            ):
                context, rule = "mentioned", "hr_sales_is_contract_accounting_or_hiring_object"
            if (
                item.skill_code in {"review_livestream", "social_media"}
                and re.search(
                    r"(?:ngành|tuyển dụng)[^.;\n]{0,120}$",
                    before,
                    re.I,
                )
                and not re.search(r"thực hiện|biết làm|kỹ năng|biết sử dụng", before, re.I)
            ):
                context, rule = "mentioned", "hr_media_sector_not_operating_skill"
            if item.skill_code in {"hr_timekeeping", "payroll"} and re.search(
                r"phần mềm[^.;\n]{0,45}$",
                before,
                re.I,
            ):
                context, rule = "mentioned", "hr_payroll_software_not_process_skill"
            if item.skill_code == "legal_legal_knowledge":
                after = text[item.end : item.end + 100]
                if re.match(
                    r"\s*(?:lao động|dân sự|doanh nghiệp|thương mại|BHXH|bảo hiểm)", after, re.I
                ) or re.match(
                    r"\s*(?:về|đầu tư|kinh doanh)[^.;\n]{0,70}(?:bất động sản|năng lượng|đất đai)",
                    after,
                    re.I,
                ):
                    context, rule = "mentioned", "hr_specialist_law_not_general_parent"
            if item.skill_code == "hr_human_resources" and re.search(
                r"tuyển dụng\s*$", before, re.I
            ):
                context, rule = "mentioned", "hr_staff_are_recruitment_object"
            if item.skill_code == "review_thong_ke_so_lieu" and re.search(
                r"phần mềm\s*$", before, re.I
            ):
                context, rule = "mentioned", "hr_statistics_software_not_statistics_practice"
            if item.skill_code == "review_nghiep_vu_ke_toan" and re.search(
                r"tại (?:các )?phòng[^.;\n]{0,40}$", before, re.I
            ):
                context, rule = "ambiguous", "hr_department_not_specific_accounting_role"
            if item.skill_code == "review_nghiep_vu_tin_dung" and re.search(
                r"tổ chức\s*$", before, re.I
            ):
                context, rule = "mentioned", "hr_credit_institution_not_credit_capability"
            # A count or industry name is never a qualification by itself.
            if (
                item.skill_code in {"hr_compensation_benefits", "review_bao_hiem_xa_hoi"}
                and not ABILITY.search(local)
                and not re.search(r"thực hiện|phụ trách|xử lý|khai báo|quản lý", local, re.I)
            ):
                context, rule = "mentioned", "hr_benefits_without_professional_capability"
            if (
                item.skill_code in {"legal_contract_review", "review_soan_thao_hop_dong"}
                and re.search(r"ký hợp đồng|thử việc|nhận việc", local, re.I)
                and not re.search(r"soạn thảo|rà soát|kiểm tra", before + item.text, re.I)
            ):
                context, rule = "mentioned", "hr_employment_contract_not_professional_skill"
            if item.skill_code == "hr_human_resources" and (
                re.search(r"luật\s*$|quy mô\s*$", before, re.I)
                or re.match(r"\s+(?:hơn|trên|từ)\s*\d+", suffix, re.I)
                or re.search(r"phần mềm[^.;\n]{0,60}$", before, re.I)
            ):
                context, rule = "mentioned", "hr_staff_domain_or_software_not_hr_practice"
            if item.skill_code in {
                "tax_reporting",
                "review_phan_tich_tai_chinh",
                "sales_order_management",
            } and re.search(r"(?:phần mềm|công cụ|hệ thống)[^.;\n]{0,50}$", before, re.I):
                context, rule = "mentioned", "hr_software_purpose_not_professional_practice"
            if item.skill_code == "review_cham_soc_khach_hang" and re.search(
                r"phối hợp[^.;\n]{0,100}$|tư duy[^.;\n]{0,40}$", before, re.I
            ):
                context, rule = "mentioned", "hr_collaborating_department_or_mindset"
            if item.skill_code == "review_ban_hang_sales" and re.search(
                r"(?:xử lý hồ sơ|kế toán)[^.;\n]{0,70}$", before, re.I
            ):
                context, rule = "mentioned", "hr_sales_document_or_accounting_object"
            if item.skill_code == "finance_debt_recovery" and re.search(
                r"công ty\s*$", before, re.I
            ):
                context, rule = "mentioned", "hr_debt_recovery_employer_not_practice"
            if item.skill_code == "hr_recruitment" and re.search(r"\bweb\s*$", before, re.I):
                context, rule = "mentioned", "hr_recruitment_sector_not_hr_practice"
            if item.skill_code == "legal_legal_knowledge" and re.match(
                r"\s+(?:liên quan|về)[^.;\n]{0,60}(?:chế độ|chính sách|tài chính|kế toán)",
                suffix,
                re.I,
            ):
                context, rule = "mentioned", "hr_specialist_law_not_general_parent"
            if item.skill_code in {
                "review_nghiep_vu_ke_toan",
                "review_quan_ly_tai_chinh",
            } and re.search(r"pháp luật[^.;\n]{0,70}$", before, re.I):
                context, rule = "mentioned", "hr_law_knowledge_not_practice"
            if item.skill_code == "ms_office" and re.match(r"\s+application", suffix, re.I):
                context, rule = "mentioned", "hr_generic_office_application_not_brand"
            if context in {"required", "preferred"} and PREFERRED.search(before):
                context = "preferred"
            boundaries = list(STRONG_BOUNDARY.finditer(text, 0, item.start))
            clause_start = boundaries[-1].end() if boundaries else 0
            clause_before = text[clause_start : item.start]
            training = list(re.finditer(r"được (?:đào tạo|hướng dẫn)", clause_before, re.I))
            if training and not re.search(
                r"cần bạn có|yêu cầu|có kinh nghiệm|có kỹ năng|có khả năng|biết sử dụng|thành thạo",
                clause_before[training[-1].end() :],
                re.I,
            ):
                item = replace(item, context_start=min(item.context_start, clause_start))
                context, rule = "mentioned", "hr_training_governs_named_tool"
            result.append(replace(item, context=context, rule_id=rule))
        # Preserve explicit positive/negative conflicts as unresolved per skill.
        conflicts = {
            e.skill_code
            for e in result
            if e.context == "negated"
            and any(
                x.skill_code == e.skill_code and x.context in self.policy.positive_contexts
                for x in result
            )
        }
        result = [
            replace(e, context="ambiguous", rule_id="conflicting_assertions")
            if e.skill_code in conflicts
            else e
            for e in result
        ]
        codes = tuple(
            sorted({e.skill_code for e in result if e.context in self.policy.positive_contexts})
        )
        reasons = tuple(sorted({e.rule_id for e in result if e.context == "ambiguous"}))
        status = (
            "expanded_partial_match"
            if codes and reasons
            else "needs_review"
            if reasons
            else "processed_match"
            if codes
            else "processed_no_match"
        )
        return Extraction(status, codes, tuple(result), reasons)
