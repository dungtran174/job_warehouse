"""Education and translation skills with bounded, explainable context guards."""

import re
from dataclasses import replace
from pathlib import Path

from job_warehouse.skills.construction import ConstructionSkillMatcher
from job_warehouse.skills.models import Alias, Extraction

EDUCATION_MAPPINGS = Path(__file__).with_name("mappings_education")
PROFESSIONAL_CODES = {
    "review_giang_day",
    "review_bien_phien_dich",
    "edu_lesson_planning",
    "edu_classroom_management",
    "edu_translation",
    "edu_interpreting",
    "edu_admissions_counselling",
}
DUTY = re.compile(
    r"soạn (?:giáo án|bài giảng)|(?:lập|xây dựng) giáo án|quản l[ýí] lớp học|"
    r"tư vấn tuyển sinh|lesson planning|classroom management|admissions counsel",
    re.I,
)


class EducationSkillMatcher(ConstructionSkillMatcher):
    @staticmethod
    def _alias_context_ok(text: str, start: int, end: int, alias: Alias) -> bool:
        if alias.skill_code == "edu_zoom":
            near = text[max(0, start - 90) : end + 60]
            if re.search(r"ống kính|camera|phóng to|zoom (?:in|out)", near, re.I) and not re.search(
                r"phần mềm|họp|online|trực tuyến|Google Meet", near, re.I
            ):
                return False
        return ConstructionSkillMatcher._alias_context_ok(text, start, end, alias)

    def _candidates(self, text: str) -> list[tuple[int, int, Alias]]:
        items = super()._candidates(text)
        return [
            (s, e, a)
            for s, e, a in items
            if not any(
                bs <= s
                and e <= be
                and b.skill_code == "review_bien_phien_dich"
                and a.skill_code in {"edu_translation", "edu_interpreting"}
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
            prefix = re.split(r"[.;\n]", text[max(0, e.start - 180) : e.start])[-1]
            after = text[e.end : e.context_end]
            local = text[e.context_start : e.context_end]
            reason = None
            if self.taxonomy.skills[e.skill_code].group == "language" and re.search(
                r"(?:trung tâm|trường|school|university)[^.;\n]{0,35}$", prefix, re.I
            ):
                reason = "education_school_name_not_language_capability"
            privacy = list(
                re.finditer(r"\[lưu ý\]|quy định bảo mật|dữ liệu cá nhân", text[: e.start], re.I)
            )
            if (
                privacy
                and e.start - privacy[-1].end() < 1500
                and not re.search(
                    r"có kinh nghiệm|thành thạo|am hiểu|có kỹ năng",
                    text[privacy[-1].end() : e.start],
                    re.I,
                )
            ):
                reason = "education_applicant_privacy_notice_not_skill"
            if e.skill_code in PROFESSIONAL_CODES:
                if (
                    e.context == "ambiguous"
                    and e.rule_id == "sales_bare_list_without_capability"
                    and DUTY.search(e.text)
                    and not re.search(
                        r"tốt nghiệp|chuyên ngành|major|degree|sẽ|được đào tạo|không|yêu thích",
                        local,
                        re.I,
                    )
                ):
                    e = replace(
                        e, context="required", rule_id="education_explicit_professional_duty"
                    )
                if re.search(
                    r"(?:phần mềm|công cụ|nền tảng|software|platform|tools?)(?:[^.;\n]{0,45})$",
                    prefix,
                    re.I,
                ):
                    reason = "education_tool_purpose_not_professional_skill"
                if re.search(
                    r"(?:chuyên ngành|major|degree|ngành)[^.;\n]{0,60}$", prefix, re.I
                ) and not re.search(
                    r"kinh nghiệm|thành thạo|có khả năng|có kỹ năng|am hiểu|chứng chỉ", before, re.I
                ):
                    reason = "education_major_not_professional_capability"
                if e.skill_code == "edu_interpreting" and re.match(
                    r"\s+(?:of\s+)?data\b", after, re.I
                ):
                    reason = "education_data_interpretation_not_language_interpreting"
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
