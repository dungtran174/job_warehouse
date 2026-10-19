"""Explicit engineering keywords; no skills inferred from majors or employers."""

import re
from dataclasses import replace
from pathlib import Path

from job_warehouse.skills.logistics import LogisticsSkillMatcher
from job_warehouse.skills.models import Alias, Extraction

ENGINEERING_MAPPINGS = Path(__file__).with_name("mappings_engineering")
PARENTS = {
    "eng_plc_programming": {"eng_plc"},
    "review_lap_trinh_cnc": {"review_cnc"},
    "eng_cnc_operation": {"review_cnc", "eng_machine_operation"},
    "eng_tig_welding": {"eng_welding"},
    "eng_mig_welding": {"eng_welding"},
    "review_dung_cu_do_co_khi": {"eng_measurement_tools"},
    "eng_7qc": {"review_kiem_soat_chat_luong_qc"},
}
PROFESSIONAL_DUTY = re.compile(
    r"đọc.{0,15}bản vẽ|lập trình|vận hành máy|bảo trì|bảo dưỡng|sửa chữa|"
    r"gia công|quản lý sản xuất|kiểm (?:tra|soát|định) chất lượng|"
    r"đảm bảo chất lượng|bảo đảm chất lượng|quality (?:control|assurance|inspection)",
    re.I,
)
STANDARD_CODES = {
    "review_iso_9001",
    "eng_iso_14001",
    "eng_iso_45001",
    "review_iatf_16949",
    "eng_iso_generic",
    "eng_haccp",
}


class EngineeringSkillMatcher(LogisticsSkillMatcher):
    @staticmethod
    def _alias_context_ok(text: str, start: int, end: int, alias: Alias) -> bool:
        before = text[max(0, start - 140) : start]
        after = text[end : end + 80]
        near = before + text[start:end] + after
        if alias.skill_code == "eng_iso_generic" and re.match(r"\s*:?\s*\d", after):
            return False
        if (
            alias.skill_code == "eng_inventor"
            and alias.text.casefold() == "inventor"
            and not re.search(r"phần mềm|software|AutoCAD|SolidWorks|thiết kế|design", near, re.I)
        ):
            return False
        if alias.skill_code == "eng_lean" and not re.search(
            r"manufacturing|sản xuất|cải tiến|quy trình|tinh gọn|Kaizen|Six.?Sigma", near, re.I
        ):
            return False
        if alias.skill_code == "review_msa" and not re.search(
            r"công cụ|tools?|FMEA|SPC|PPAP|APQP|đo lường", near, re.I
        ):
            return False
        if alias.skill_code in {"eng_welding", "eng_tig_welding", "eng_mig_welding"} and (
            re.match(r"\s+Quốc\b", after, re.I) or re.search(r"tiếng\s*$", before, re.I)
        ):
            return False
        return LogisticsSkillMatcher._alias_context_ok(text, start, end, alias)

    def _candidates(self, text: str) -> list[tuple[int, int, Alias]]:
        items = super()._candidates(text)
        return [
            (s, e, a)
            for s, e, a in items
            if not any(
                bs < e and s < be and a.skill_code in PARENTS.get(b.skill_code, set())
                for bs, be, b in items
                if b.skill_code != a.skill_code
            )
        ]

    def extract(self, text: str | None) -> Extraction:
        base = super().extract(text)
        if text is None or base.status in {"missing_requirements", "unusable_requirements"}:
            return base
        evidence = []
        for e in base.evidence:
            before = text[e.context_start : e.start]
            after = text[e.end : e.context_end]
            local = text[e.context_start : e.context_end]
            reason = None
            if e.skill_code in STANDARD_CODES and re.search(
                r"(?:công ty|nhà máy|doanh nghiệp|sản phẩm)[^.;\n]{0,80}"
                r"(?:đạt|có|chứng nhận)[^.;\n]{0,40}$|"
                r"chứng nhận của (?:công ty|nhà máy)[^.;\n]{0,30}$",
                before,
                re.I,
            ):
                reason = "engineering_company_standard_not_applicant_knowledge"
            if e.skill_code.startswith("eng_") or e.skill_code in {
                "review_kiem_soat_chat_luong_qc",
                "review_quan_ly_chat_luong",
                "review_doc_ban_ve_ky_thuat",
                "review_lap_trinh_cnc",
                "review_dung_cu_do_co_khi",
            }:
                if self.taxonomy.skills[e.skill_code].group == "domain" and re.search(
                    r"phần mềm[^.;\n]{0,60}$", before, re.I
                ):
                    reason = "engineering_software_not_professional_operation"
                elif re.search(
                    r"phối hợp[^.;\n]{0,70}(?:phòng|bộ phận)[^.;\n]{0,20}$", before, re.I
                ):
                    reason = "engineering_collaborating_department_not_own_skill"
                elif (
                    e.context == "ambiguous"
                    and e.rule_id == "sales_bare_list_without_capability"
                    and PROFESSIONAL_DUTY.search(e.text)
                    and not re.search(
                        r"tốt nghiệp|chuyên ngành|degree|major|sẽ|được đào tạo|không", local, re.I
                    )
                ):
                    e = replace(
                        e, context="required", rule_id="engineering_explicit_professional_duty"
                    )
            if (
                e.skill_code == "eng_safety"
                and re.search(r"tuân thủ|chấp hành|nội quy|tác phong", local, re.I)
                and not re.search(r"kiến thức|kinh nghiệm|am hiểu|knowledge", local, re.I)
            ):
                reason = "engineering_general_safety_behavior_not_professional_skill"
            if e.skill_code == "eng_machine_operation" and re.match(r"\s+quay", after, re.I):
                reason = "engineering_camera_not_industrial_machine"
            if e.skill_code == "eng_electrical_maintenance" and re.match(r"\s+thoại", after, re.I):
                reason = "engineering_phone_not_electrical_system"
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
