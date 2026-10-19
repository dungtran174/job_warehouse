"""Bounded keyword completion: keep explicit matches, skip uncertain claims."""

import re
from dataclasses import replace

from job_warehouse.skills.hr_finance import HRFinanceSkillMatcher
from job_warehouse.skills.models import Evidence, Extraction

KEYWORD_COMPLETION = "owner_explicit_keywords_skip_unclear"
CONSERVATIVE_VERSION = "requirements-skills-explicit-keywords-v1"

# These short terms have several meanings. Longer, explicit professional aliases
# remain available; skipping these never removes the source job.
UNSAFE_TERMS = {
    "hành chính",
    "trợ lý",
    "admin",
    "administration",
    "nhân sự",
    "pháp luật",
    "luật pháp",
    "soạn thảo",
    "viết báo cáo",
    "report writing",
    "đào tạo",
}


class ConservativeHRFinanceMatcher(HRFinanceSkillMatcher):
    @staticmethod
    def _skip_reason(text: str, item: Evidence) -> str | None:
        term = item.text.casefold()
        before = text[item.context_start : item.start]
        after = text[item.end : item.context_end]
        near = text[max(0, item.start - 180) : item.end + 80]
        if term in UNSAFE_TERMS:
            return "keyword_skip_polysemous_short_term"
        if item.skill_code == "sql" and re.search(r"PL/\s*$", before, re.I):
            return "owner_specific_plsql_not_sql_parent"
        if item.skill_code == "dotnet" and re.search(r"ASP\s*$", before, re.I):
            return "owner_specific_aspnet_not_dotnet_parent"
        if item.skill_code == "swift" and not re.search(
            r"iOS|lập trình|programming|mobile|SwiftUI|Objective.C", near, re.I
        ):
            return "keyword_skip_swift_ambiguous_with_banking_network"
        if item.skill_code == "review_oracle" and (
            re.match(r"\s+(?:Forms?|Reports?|Database|DB)\b", after, re.I)
            or re.search(r"cơ sở dữ liệu|database", before[-70:], re.I)
        ):
            return "keyword_skip_oracle_product_parent"
        if item.skill_code == "social_media" and not re.search(
            r"marketing|tiếp thị|nội dung|quảng cáo", near, re.I
        ):
            return "keyword_skip_recruitment_network_not_marketing"
        if item.skill_code == "review_cham_soc_khach_hang" and re.match(
            r"\s+attitude\b", after, re.I
        ):
            return "keyword_skip_customer_service_attitude"
        if item.skill_code in {
            "review_ban_hang_sales",
            "review_telesales",
            "review_cham_soc_khach_hang",
        } and re.search(r"tuyển(?: dụng| mass)?[^.;\n]{0,130}$", before, re.I):
            return "keyword_skip_hiring_other_roles"
        if item.skill_code == "hr_recruitment" and (
            re.search(r"mục đích|nhằm|dữ liệu cá nhân|phần mềm|công cụ", before, re.I)
            or re.match(r"\s+(?:nhân sự )?của công ty", after, re.I)
        ):
            return "keyword_skip_recruitment_notice_or_software"
        if item.skill_code == "legal_legal_knowledge" and re.search(
            r"liên quan|thuế|lao động|kế toán|đất đai|bất động sản", after[:90], re.I
        ):
            return "keyword_skip_general_law_parent"
        if item.skill_code == "review_nghiep_vu_ke_toan" and re.search(
            r"luật\s*$|ngành[^.;\n]{0,40}$", before, re.I
        ):
            return "keyword_skip_accounting_degree_or_law"
        if item.skill_code == "review_nghiep_vu_ke_toan" and not re.search(
            r"nghiệp vụ kế toán|nguyên tắc kế toán|làm kế toán|kinh nghiệm kế toán",
            text[max(0, item.start - 65) : item.end],
            re.I,
        ):
            return "keyword_skip_generic_accounting_without_professional_phrase"
        if item.skill_code == "review_bao_hiem_xa_hoi" and re.search(
            r"luật|quy định", text[max(0, item.start - 120) : item.start], re.I
        ):
            return "keyword_skip_insurance_law_not_generic_practice"
        if re.search(r"được đào tại|sẽ được đào tạo", before, re.I):
            return "keyword_skip_training_offer"
        return None

    def extract(self, text: str | None) -> Extraction:
        base = super().extract(text)
        if text is None or base.status in {"missing_requirements", "unusable_requirements"}:
            return base
        evidence = []
        for item in base.evidence:
            reason = self._skip_reason(text, item)
            if reason and item.context in self.policy.positive_contexts:
                item = replace(item, context="ambiguous", rule_id=reason)
            evidence.append(item)
        codes = tuple(
            sorted({e.skill_code for e in evidence if e.context in self.policy.positive_contexts})
        )
        # Ambiguous evidence is retained for traceability, not a blocking review
        # queue. No-match means no accepted keyword, never no skills in real life.
        skipped = any(e.context == "ambiguous" for e in evidence)
        return Extraction(
            "processed_match" if codes else "processed_no_match",
            codes,
            tuple(evidence),
            ("skipped_unclear_keywords",) if skipped else (),
        )
