"""Finite healthcare, food and garment keywords; no inference from job sectors."""

import re
from dataclasses import replace
from pathlib import Path

from job_warehouse.skills.hospitality import HospitalitySkillMatcher
from job_warehouse.skills.models import Alias, Extraction

LIFE_SCIENCES_MAPPINGS = Path(__file__).with_name("mappings_life_sciences")
STANDARDS = {"life_gmp", "life_gpp", "life_glp", "life_gdp", "life_iso22000", "life_fssc"}
DUTY = re.compile(
    r"chăm sóc (?:bệnh nhân|người bệnh)|lấy máu|đo (?:sinh hiệu|dấu hiệu sinh tồn)|"
    r"sơ cứu|hồi sức tim phổi|bào chế|kiểm nghiệm|thiết kế (?:mẫu )?rập|"
    r"nhảy (?:size|cỡ)|giác sơ đồ|may mẫu|kỹ thuật cắt may",
    re.I,
)


class LifeSciencesSkillMatcher(HospitalitySkillMatcher):
    @staticmethod
    def _alias_context_ok(text: str, start: int, end: int, alias: Alias) -> bool:
        near = text[max(0, start - 160) : end + 120]
        if alias.skill_code == "life_gdp" and not re.search(
            r"dược|thuốc|pharmaceutical|GMP|GPP|GLP", near, re.I
        ):
            return False
        if alias.skill_code == "life_gerber" and not re.search(
            r"phần mềm|CAD|rập|may|AccuMark|pattern|software", near, re.I
        ):
            return False
        if (
            alias.skill_code == "life_clo3d"
            and alias.text.casefold() == "clo"
            and not re.search(r"phần mềm|3D|rập|may|garment|pattern|software|Browzwear", near, re.I)
        ):
            return False
        return HospitalitySkillMatcher._alias_context_ok(text, start, end, alias)

    def _candidates(self, text: str) -> list[tuple[int, int, Alias]]:
        items = super()._candidates(text)
        return [
            (s, e, a)
            for s, e, a in items
            if not any(
                bs < e
                and s < be
                and (b.skill_code, a.skill_code)
                in {
                    ("life_accumark", "life_gerber"),
                    ("life_pharmacy_law", "legal_legal_knowledge"),
                }
                for bs, be, b in items
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
            prefix = re.split(r"[.;\n]", text[max(0, e.start - 180) : e.start])[-1]
            local = text[e.context_start : e.context_end]
            reason = None
            if re.search(
                r"(?:phối hợp|làm việc) với[^.;\n]{0,50}(?:phòng|bộ phận)[^.;\n]{0,50}$",
                prefix,
                re.I,
            ):
                reason = "life_collaborating_department_not_own_skill"
            if e.skill_code == "hr_recruitment" and re.search(r"chi nhánh\s*$", prefix, re.I):
                reason = "life_recruiting_branch_notice_not_skill"
            if e.skill_code.startswith("life_"):
                if (
                    e.context == "ambiguous"
                    and e.rule_id == "sales_bare_list_without_capability"
                    and DUTY.search(e.text)
                    and not re.search(
                        r"tốt nghiệp|chuyên ngành|major|degree|sẽ|được đào tạo|không", local, re.I
                    )
                ):
                    e = replace(e, context="required", rule_id="life_explicit_professional_duty")
                if re.search(
                    r"(?:tốt nghiệp|chuyên ngành|major|degree|graduated|college)[^.;\n]{0,120}$",
                    prefix,
                    re.I,
                ) and not re.search(
                    r"kinh nghiệm|kỹ năng|thành thạo|am hiểu|kiến thức|"
                    r"knowledge|experience|proficien",
                    before,
                    re.I,
                ):
                    reason = "life_major_not_practical_skill"
                if self.taxonomy.skills[e.skill_code].group == "domain" and re.search(
                    r"(?:phần mềm|thiết bị|công cụ|software)[^.;\n]{0,45}$", prefix, re.I
                ):
                    reason = "life_tool_purpose_not_practical_operation"
                if re.search(
                    r"(?:phối hợp|làm việc) với[^.;\n]{0,40}(?:phòng|bộ phận)[^.;\n]{0,20}$",
                    prefix,
                    re.I,
                ):
                    reason = "life_other_department_not_own_skill"
            if e.skill_code in STANDARDS and (
                re.search(
                    r"(?:công ty|nhà máy|sản phẩm|factory|company)[^.;\n]{0,80}"
                    r"(?:đạt|chứng nhận|certified)[^.;\n]{0,30}$",
                    prefix,
                    re.I,
                )
                or re.match(r"[-\s]*certified (?:factory|company|plant)", after, re.I)
            ):
                reason = "life_employer_standard_not_applicant_knowledge"
            if (
                e.skill_code == "life_vaccination"
                and (
                    re.search(r"đã (?:được )?$|chứng nhận\s*$|certificate of\s*$", prefix, re.I)
                    or re.search(
                        r"tiêm chủng (?:đầy đủ|đủ|vắc.?xin)|"
                        r"vaccination (?:record|status|certificate)",
                        local,
                        re.I,
                    )
                )
                and not re.search(
                    r"tập huấn|an toàn tiêm chủng|kỹ thuật|kinh nghiệm thực hiện", local, re.I
                )
            ):
                reason = "life_personal_vaccination_not_professional_skill"
            if e.skill_code == "life_nursing" and re.match(
                r"\s+(?:practice )?licen[cs]e", after, re.I
            ):
                reason = "life_generic_license_not_practical_procedure"
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
