"""Explicit hospitality/retail skills; unclear claims never block a batch."""

import re
from dataclasses import replace
from pathlib import Path

from job_warehouse.skills.education import EducationSkillMatcher
from job_warehouse.skills.models import Alias, Extraction

HOSPITALITY_MAPPINGS = Path(__file__).with_name("mappings_hospitality")
DUTY = re.compile(
    r"phục vụ (?:bàn|món ăn)|chế biến món ăn|nấu ăn|pha chế|đặt phòng|"
    r"(?:đặt|book|xuất) vé|điều hành tour|quản l[ýí] (?:cửa hàng|nhà hàng|quán ăn)|thu ngân",
    re.I,
)


class HospitalitySkillMatcher(EducationSkillMatcher):
    @staticmethod
    def _alias_context_ok(text: str, start: int, end: int, alias: Alias) -> bool:
        near = text[max(0, start - 120) : end + 100]
        if alias.skill_code == "ret_pms" and not re.search(
            r"khách sạn|hotel|hospitality|Opera|đặt phòng", near, re.I
        ):
            return False
        if alias.skill_code in {
            "ret_opera",
            "ret_pms",
            "ret_abacus",
            "ret_galileo",
        } and not re.search(
            r"khách sạn|hotel|hospitality|đặt|vé|booking|reservation|"
            r"Amadeus|Sabre|PMS|Cloud|phần mềm|hệ thống",
            near,
            re.I,
        ):
            return False
        return EducationSkillMatcher._alias_context_ok(text, start, end, alias)

    def extract(self, text: str | None) -> Extraction:
        base = super().extract(text)
        if text is None or base.status in {"missing_requirements", "unusable_requirements"}:
            return base
        evidence = []
        for e in base.evidence:
            before = text[e.context_start : e.start]
            prefix = re.split(r"[.;\n]", text[max(0, e.start - 160) : e.start])[-1]
            local = text[e.context_start : e.context_end]
            reason = None
            if (
                e.skill_code == "ret_tour_guiding"
                and re.search(r"(?:có|sở hữu|yêu cầu) thẻ\s*$", before, re.I)
                and e.context == "ambiguous"
                and not re.search(r"sẽ|được cấp|đào tạo|không", local, re.I)
            ):
                e = replace(e, context="required", rule_id="hospitality_explicit_vocational_card")
            if (
                e.skill_code.startswith("ret_")
                and self.taxonomy.skills[e.skill_code].group == "domain"
            ):
                if (
                    e.context == "ambiguous"
                    and e.rule_id == "sales_bare_list_without_capability"
                    and DUTY.search(e.text)
                    and not re.search(
                        r"tốt nghiệp|chuyên ngành|major|degree|sẽ|được đào tạo|"
                        r"không|yêu thích|đam mê",
                        local,
                        re.I,
                    )
                ):
                    e = replace(
                        e, context="required", rule_id="hospitality_explicit_professional_duty"
                    )
                if re.search(
                    r"(?:phần mềm|hệ thống|công cụ|software|system)[^.;\n]{0,45}$", prefix, re.I
                ):
                    reason = "hospitality_software_purpose_not_operational_skill"
                if re.search(
                    r"(?:tốt nghiệp|chuyên ngành|major|degree)[^.;\n]{0,120}$", prefix, re.I
                ) and not re.search(
                    r"kinh nghiệm|kỹ năng|thành thạo|am hiểu|chứng chỉ|nghiệp vụ", before, re.I
                ):
                    reason = "hospitality_major_not_practical_skill"
                if re.search(
                    r"(?:tuyển dụng|đào tạo cho|huấn luyện cho)[^.;\n]{0,40}$", prefix, re.I
                ):
                    reason = "hospitality_recruiting_other_workers_not_own_operation"
            if (
                e.skill_code == "ret_food_safety"
                and re.search(r"tuân thủ|chấp hành|nội quy", local, re.I)
                and not re.search(r"kiến thức|am hiểu|hiểu biết|chứng chỉ|knowledge", local, re.I)
            ):
                reason = "hospitality_general_hygiene_behavior_not_professional_knowledge"
            if reason and e.context in self.policy.positive_contexts:
                e = replace(e, context="ambiguous", rule_id=reason)
            evidence.append(e)
        codes = tuple(
            sorted({e.skill_code for e in evidence if e.context in self.policy.positive_contexts})
        )
        return Extraction(
            "processed_match" if codes else "processed_no_match",
            codes,
            tuple(evidence),
            ("skipped_unclear_keywords",)
            if any(e.context == "ambiguous" for e in evidence)
            else (),
        )
