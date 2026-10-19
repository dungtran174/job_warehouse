"""Real-estate follow-up: finite source aliases and explicit local capabilities."""

import re
from dataclasses import replace
from pathlib import Path

from job_warehouse.skills.models import Alias, Extraction
from job_warehouse.skills.sales import SalesSkillMatcher

REAL_ESTATE_MAPPINGS = Path(__file__).with_name("mappings_real_estate")
REAL_ESTATE_VERSION = "requirements-skills-real-estate-v2"
DOMAIN = re.compile(r"bất động sản|\bBĐS\b|nhà đất|đất đai", re.I)
KNOWLEDGE = re.compile(r"am hiểu|hiểu rõ|hiểu biết|kiến thức|nắm (?:vững|rõ)", re.I)
INTEREST = re.compile(r"thích|yêu thích|đam mê|mong muốn|định hướng", re.I)
LEARNING = re.compile(r"học hỏi (?:được|về|nhiều)|sẽ (?:được )?học|được học|được đào tạo", re.I)


class RealEstateSkillMatcher(SalesSkillMatcher):
    """Never change the frozen sales matcher or infer skills from industry routing."""

    @staticmethod
    def _alias_context_ok(text: str, start: int, end: int, alias: Alias) -> bool:
        if alias.text.casefold() == "preier":
            local = text[max(0, start - 180) : end + 80]
            if not re.search(r"thiết kế|video|phần mềm", local, re.I) or not re.search(
                r"Photoshop|Illustrator|InDesign|Adobe", local, re.I
            ):
                return False
        return SalesSkillMatcher._alias_context_ok(text, start, end, alias)

    def extract(self, text: str | None) -> Extraction:
        base = super().extract(text)
        if text is None:
            return base
        evidence = []
        for item in base.evidence:
            before = text[item.context_start : item.start]
            local = text[item.context_start : item.context_end]
            context, rule = item.context, item.rule_id
            if (
                item.skill_code == "sales_real_estate_legal"
                and context == "ambiguous"
                and re.search(
                    r"am hiểu các quy định\s*[-–—]\s*$",
                    text[max(0, item.start - 100) : item.start],
                    re.I,
                )
                and DOMAIN.search(local)
            ):
                left = max(0, item.start - 100)
                cue = re.search(r"am hiểu các quy định", text[left : item.start], re.I)
                assert cue is not None
                item = replace(item, context_start=left + cue.start())
                context, rule = "required", "real_estate_governed_legal_list"
            if (
                item.skill_code == "review_ban_hang_sales"
                and item.text.casefold() == "lĩnh vực kinh doanh"
                and re.search(r"đã từng làm(?: qua)?\s*$", before, re.I)
            ):
                context, rule = (
                    "preferred" if re.search(r"ưu tiên", before, re.I) else "required",
                    "real_estate_explicit_past_sales_work",
                )
            if (
                item.skill_code == "sales_prospecting"
                and item.text.casefold() == "khai thác khách hàng"
                and context == "ambiguous"
                and rule == "sales_bare_list_without_capability"
            ):
                context, rule = "required", "real_estate_concrete_prospecting_duty"
            if (
                item.skill_code
                in {"review_cham_soc_khach_hang", "review_ban_hang_sales", "review_telesales"}
                and context == "ambiguous"
                and rule == "sales_bare_list_without_capability"
                and re.fullmatch(
                    r"[\s,/:–—-]*(?:(?:CSKH|Sales?|Telesales?)[\s,/:–—-]*)+",
                    local,
                    re.I,
                )
            ):
                prefix = text[max(0, item.context_start - 200) : item.context_start]
                previous = re.search(
                    r"(?:Ưu tiên\s+)?(?:có\s+)?kinh nghiệm[^.;\n]{1,150}\.\s*[-–—]?\s*$",
                    prefix,
                    re.I,
                )
                if previous:
                    left = max(0, item.context_start - 200) + previous.start()
                    item = replace(item, context_start=left)
                    context, rule = (
                        "preferred"
                        if re.search(r"ưu tiên", previous.group(), re.I)
                        else "required",
                        "owner_real_estate_q1_adjacent_experience_list",
                    )
            # Explicit source knowledge can mention a domain in a governed list:
            # "Có kiến thức về Ngân hàng, Tài chính, Bất động sản".
            if item.skill_code == "review_kien_thuc_bat_dong_san":
                knowledge = list(KNOWLEDGE.finditer(before + item.text))
                intervening = (before + item.text)[knowledge[-1].end() :] if knowledge else ""
                if not knowledge or re.search(
                    r"marketing|chiến lược|công nghệ|nền tảng|pháp luật|quy định|pháp lý",
                    intervening,
                    re.I,
                ):
                    context, rule = "mentioned", "real_estate_domain_experience_not_knowledge"
                elif (
                    KNOWLEDGE.match(item.text)
                    and context == "mentioned"
                    and rule == "education_not_capability"
                ):
                    context, rule = "required", "real_estate_explicit_knowledge_after_education"
            if item.skill_code in {"sales_real_estate_brokerage", "sales_real_estate_legal"}:
                if not DOMAIN.search(local):
                    context, rule = "ambiguous", "real_estate_specialism_domain_unclear"
                elif item.text.casefold() == "pháp luật" and not DOMAIN.search(
                    text[item.end : item.context_end]
                ):
                    context, rule = "ambiguous", "real_estate_generic_law_relation_unclear"
                # Owner Q3 permits resolving generic business law against the
                # immediately preceding explicit real-estate paragraph context.
                if (
                    context == "ambiguous"
                    and item.skill_code == "sales_real_estate_legal"
                    and re.search(r"liên quan đến lĩnh vực kinh doanh", local, re.I)
                    and KNOWLEDGE.search(before)
                ):
                    left = max(0, item.context_start - 250)
                    prior = text[left : item.context_start].split("\n\n")[-1]
                    anchors = list(DOMAIN.finditer(prior))
                    if anchors and not re.search(
                        r"ngân hàng|chứng khoán|bảo hiểm|lao động|thuế|hình sự", prior + local, re.I
                    ):
                        anchor = item.context_start - len(prior) + anchors[-1].start()
                        item = replace(item, context_start=anchor)
                        context, rule = "required", "owner_real_estate_q3_business_law_paragraph"
            if item.skill_code == "review_cham_soc_khach_hang" and re.search(
                r"phần mềm|công cụ|nền tảng|hệ thống", before, re.I
            ):
                context, rule = "mentioned", "real_estate_service_software_not_service_capability"
            # Managing a headcount does not establish personal sales capability.
            if item.skill_code == "review_ban_hang_sales" and re.search(
                r"(?:quản lý|đội nhóm|nhân viên)\s*(?:ít nhất\s*)?\d+(?:\s*[-–]\s*\d+)?\s*$",
                before,
                re.I,
            ):
                context, rule = "mentioned", "real_estate_sales_headcount_not_capability"
            # 'thích chốt đơn' and promised learning are not prior skills.
            cues = list(INTEREST.finditer(before)) + list(LEARNING.finditer(before))
            if cues:
                last = max(cues, key=lambda m: m.start())
                remaining = before[last.end() :]
                if not re.search(
                    r"có kinh nghiệm|biết sử dụng|thành thạo|có khả năng", remaining, re.I
                ):
                    context, rule = "mentioned", "real_estate_interest_or_learning_only"
            evidence.append(replace(item, context=context, rule_id=rule))
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
            else base.status
            if not evidence
            else "processed_no_match"
        )
        return Extraction(status, codes, tuple(evidence), reasons)
