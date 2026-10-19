"""Apply explicit professional keywords to general labels without reclassification."""

import re
from dataclasses import replace
from pathlib import Path

from job_warehouse.skills.expanded import has_marketing_context
from job_warehouse.skills.life_sciences import LifeSciencesSkillMatcher
from job_warehouse.skills.models import Extraction

GENERAL_MAPPINGS = Path(__file__).with_name("mappings_general")


class GeneralSkillMatcher(LifeSciencesSkillMatcher):
    def extract(self, text: str | None) -> Extraction:
        base = super().extract(text)
        if text is None or base.status in {"missing_requirements", "unusable_requirements"}:
            return base
        marketing_context = has_marketing_context(text)
        evidence = []
        for e in base.evidence:
            local = text[e.context_start : e.context_end]
            before = text[e.context_start : e.start]
            prefix = re.split(r"[.;\n]", text[max(0, e.start - 160) : e.start])[-1]
            if e.skill_code == "content_marketing" and not marketing_context:
                e = replace(e, context="mentioned", rule_id="general_no_marketing_work_context")
            interests = list(re.finditer(r"yêu thích|đam mê|mong muốn|định hướng", prefix, re.I))
            if (
                interests
                and not re.search(
                    r"kinh nghiệm|thành thạo|biết|am hiểu|có kỹ năng|có khả năng",
                    prefix[interests[-1].end() :],
                    re.I,
                )
                and e.context in self.policy.positive_contexts
            ):
                e = replace(e, context="mentioned", rule_id="general_interest_without_capability")
            if e.skill_code.startswith("general_"):
                if (
                    e.context == "ambiguous"
                    and e.rule_id == "sales_bare_list_without_capability"
                    and not re.search(
                        r"tốt nghiệp|chuyên ngành|major|degree|sẽ|được đào tạo|không|yêu thích",
                        local,
                        re.I,
                    )
                ):
                    e = replace(e, context="required", rule_id="general_explicit_professional_duty")
                if (
                    re.search(r"(?:phần mềm|thiết bị|máy|công ty)[^.;\n]{0,35}$", before, re.I)
                    and e.context in self.policy.positive_contexts
                ):
                    e = replace(
                        e,
                        context="ambiguous",
                        rule_id="general_equipment_or_employer_not_operation",
                    )
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
