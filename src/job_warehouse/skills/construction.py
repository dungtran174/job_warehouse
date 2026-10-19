"""Finite construction/design terms; preserve ambiguous claims without blocking."""

import re
from dataclasses import replace
from pathlib import Path

from job_warehouse.skills.engineering import EngineeringSkillMatcher
from job_warehouse.skills.models import Alias, Extraction

CONSTRUCTION_MAPPINGS = Path(__file__).with_name("mappings_construction")
DUTY = re.compile(
    r"bóc (?:tách|khối lượng)|lập (?:dự toán|tiến độ|tổng tiến độ|hồ sơ)|"
    r"giám sát (?:thi công|công trình|xây dựng|hiện trường)|quản l[ýí] (?:dự án|thi công)|"
    r"nghiệm thu|thiết kế (?:nội thất|kiến trúc|kết cấu)|vẽ tay|shop\s?drawing",
    re.I,
)


class ConstructionSkillMatcher(EngineeringSkillMatcher):
    @staticmethod
    def _alias_context_ok(text: str, start: int, end: int, alias: Alias) -> bool:
        after = text[end : end + 50]
        if alias.skill_code == "sap" and re.match(r"\s*2000\b", after, re.I):
            return False
        if alias.skill_code == "review_kiem_soat_chat_luong_qc" and re.match(
            r"\s*[-/]\s*(?:TCVN|TC)\b", after, re.I
        ):
            return False
        return EngineeringSkillMatcher._alias_context_ok(text, start, end, alias)

    def extract(self, text: str | None) -> Extraction:
        base = super().extract(text)
        if text is None or base.status in {"missing_requirements", "unusable_requirements"}:
            return base
        evidence = []
        for e in base.evidence:
            before = text[e.context_start : e.start]
            prefix = re.split(r"[.;\n]", text[max(0, e.start - 180) : e.start])[-1]
            after = text[e.end : e.context_end]
            local = text[e.context_start : e.context_end]
            reason = None
            if re.search(r"không (?:yêu cầu|cần)(?: phải)?(?: biết| sử dụng)?\s*$", prefix, re.I):
                reason = "construction_explicit_skill_not_required"
            skill = self.taxonomy.skills[e.skill_code]
            if (
                skill.group == "domain"
                and e.skill_code
                in {
                    "review_quan_ly_du_an",
                    "con_construction_management",
                    "review_lap_du_toan",
                    "con_interior_design",
                    "con_architectural_design",
                    "con_structural_design",
                }
                and re.search(r"(?:phần mềm|software|công cụ)[^.;\n]{0,40}$", before, re.I)
            ):
                reason = "construction_software_purpose_not_professional_skill"
            if (
                e.skill_code == "review_quan_ly_du_an"
                and re.search(r"(?:phòng|bộ phận|ban)[^.;\n]{0,20}$", before, re.I)
                and not re.search(r"kinh nghiệm|kỹ năng|am hiểu|kiến thức", before, re.I)
            ):
                reason = "construction_department_not_management_capability"
            if (
                e.context == "ambiguous"
                and e.rule_id == "sales_bare_list_without_capability"
                and DUTY.search(e.text)
                and not re.search(
                    r"tốt nghiệp|chuyên ngành|degree|major|sẽ|được đào tạo|không", local, re.I
                )
            ):
                e = replace(
                    e, context="required", rule_id="construction_explicit_professional_duty"
                )
            if e.skill_code.startswith("con_") or e.skill_code in {
                "review_quan_ly_du_an",
                "review_lap_du_toan",
            }:
                if re.search(r"(?:chuyên ngành|ngành|major|degree)[^.;\n]{0,60}$", prefix, re.I):
                    reason = "construction_major_not_professional_capability"
                if e.skill_code == "con_architectural_design" and re.match(
                    r"\s+(?:dữ liệu|phần mềm|hệ thống|data|software)\b", after, re.I
                ):
                    reason = "construction_data_architecture_not_buildings"
                if re.search(
                    r"(?:hồ sơ|tài liệu|quy chuẩn)[^.;\n]{0,50}$", prefix, re.I
                ) and not re.search(
                    r"kinh nghiệm|thành thạo|am hiểu|nắm vững|kiến thức", prefix, re.I
                ):
                    reason = "construction_document_reference_not_capability"
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
