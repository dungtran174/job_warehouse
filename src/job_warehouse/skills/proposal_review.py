"""Conservative context checks for externally proposed skills, not a global extractor."""

import re
from dataclasses import dataclass

from job_warehouse.skills.context import classify_context, clauses

CAPABILITY = re.compile(
    r"có (?:năng lực|khả năng|kiến thức|kỹ năng|thời gian)|"
    r"(?:có )?kinh nghiệm|đã từng|thành thạo|sử dụng|biết|am hiểu|nắm vững|"
    r"hiểu biết|đọc hiểu|kiến thức|kỹ năng|khả năng|trình độ (?:tin học|ngoại ngữ)|"
    r"knowledge|experience|skills?|proficien\w*|fluent\w*|familiar\w*|ability",
    re.I,
)
WAIVER = re.compile(
    r"(?:không (?:yêu cầu|cần|bắt buộc)|chưa có)\s*"
    r"(?:nhiều\s+)?(?:kinh nghiệm|bằng cấp|chứng chỉ|giới tính|độ tuổi)|"
    r"(?:giới tính|độ tuổi)\s*:\s*không yêu cầu|"
    r"(?:số năm\s+)?kinh nghiệm\s*:\s*(?:không yêu cầu|không cần)|"
    r"no (?:prior )?experience|experience is not mandatory",
    re.I,
)


def _local_context(text: str, start: int, end: int, left: int, right: int) -> tuple[str, int]:
    """Mask unrelated waivers and retain education/training tied to this skill."""
    before = text[left:start]
    # Source often joins fields without periods, e.g. degree + experience + skill.
    candidates = list(CAPABILITY.finditer(before))
    for cue in reversed(candidates):
        prefix = before[: cue.start()]
        if re.search(r"(?:không|chưa)\s*$|(?:không cần|không yêu cầu)\s*$", prefix, re.I):
            continue
        training = list(re.finditer(r"được (?:đào tạo|hướng dẫn)|will be trained", prefix, re.I))
        if training and not re.search(r"[-;\n•.)]", prefix[training[-1].end() :]):
            continue
        # 'yêu thích biết...' alone is not a new recruiting assertion.
        if re.search(r"yêu thích\s*$|đam mê\s*$|định hướng\s*$", prefix, re.I):
            continue
        left += cue.start()
        break
    before = text[left:start]
    # Explicit skill fields or proficiency after a tool name supersede an older degree.
    field = list(re.finditer(r"tin học văn phòng|vi tính văn phòng|ngoại ngữ\s*:", before, re.I))
    if field and not re.search(
        r"chuyên ngành|chứng chỉ|tốt nghiệp",
        before[max(0, field[-1].start() - 55) : field[-1].start()],
        re.I,
    ):
        left += field[-1].start()
    if re.match(
        r"\s*(?:(?:tốt|thành thạo|fluent|proficien|giao tiếp|nghe|nói|đọc|viết)\b|:\s*[ABC]\b)",
        text[end:right],
        re.I,
    ) and not re.search(r"đào tạo|không (?:cần|yêu cầu)|chưa biết", text[left:start], re.I):
        left = start
    masked = (
        text[:left] + WAIVER.sub(lambda m: " " * len(m.group()), text[left:right]) + text[right:]
    )
    # 'Tài liệu/phần mềm chuyên ngành' is not a degree-major statement.
    for match in re.finditer(r"chuyên ngành", masked[left:right], re.I):
        absolute = left + match.start()
        prefix = masked[max(left, absolute - 65) : absolute]
        if re.search(r"tài liệu|phần mềm|công cụ", prefix, re.I) and not re.search(
            r"tốt nghiệp|đại học|cao đẳng|bằng cấp|degree|major", prefix, re.I
        ):
            masked = (
                masked[:absolute]
                + " " * len(match.group())
                + masked[absolute + len(match.group()) :]
            )
    return masked, left


@dataclass(frozen=True)
class ProposalAssessment:
    decision: str
    reason: str
    start: int
    end: int
    anchor: str


def assess_proposal(name: str, quote: str, requirements: str, pattern: str) -> ProposalAssessment:
    """Check exact quoted evidence and a finite label-specific lexical anchor.

    An accept result means lexical/context support under the supplied rule. It
    does not validate the rule's semantic correctness or measure completeness.
    Unresolved support stays unclear instead of silently becoming no skill.
    """
    if not quote or not pattern or quote not in requirements:
        raise ValueError("Proposal needs nonempty exact evidence and a support pattern")
    expression = re.compile(r"(?<!\w)(?:" + pattern + r")(?!\w)", re.I)
    matches = list(expression.finditer(quote))
    if not matches:
        return ProposalAssessment("unclear", "no_lexical_support_in_quote", -1, -1, "")
    occurrences = [m.start() for m in re.finditer(re.escape(quote), requirements)]
    spans = [(offset + m.start(), offset + m.end()) for offset in occurrences for m in matches]
    segments = clauses(requirements, spans)
    outcomes = []
    for start, end in spans:
        segment = next(((a, b, s) for a, b, s in segments if a <= start and end <= b), None)
        if segment is None:
            outcomes.append(
                ProposalAssessment(
                    "unclear", "anchor_crosses_clauses", start, end, requirements[start:end]
                )
            )
            continue
        left, right, section = segment
        masked, left = _local_context(requirements, start, end, left, right)
        context, reason = classify_context(
            masked,
            start,
            end,
            left,
            right,
            section,
            language=name.startswith("Tiếng "),
        )
        anchor = requirements[start:end]
        before, after = requirements[left:start], requirements[end:right]
        local = requirements[left:right]
        if (
            name.startswith("Kế toán")
            and re.search(r"\bdo\s*$", before, re.I)
            and re.search(r"\bgiao\b|chỉ đạo", after, re.I)
        ):
            context, reason = "mentioned", "supervisor_role_not_applicant_capability"
        # Desired capability remains positive when beginners may receive fallback training.
        if (
            context in {"negated", "ambiguous", "mentioned"}
            and re.search(
                r"biết|thành thạo|sử dụng|có (?:năng lực|khả năng|kiến thức|kỹ năng)|"
                r"kinh nghiệm|know|proficien|skill",
                before,
                re.I,
            )
            and not re.search(r"không (?:cần|yêu cầu)\s*(?:phải\s*)?(?:biết|sử dụng)", before, re.I)
        ) and re.search(
            r"(?:chưa biết|chưa có kinh nghiệm|không biết).{0,30}(?:đào tạo|hướng dẫn)",
            after,
            re.I,
        ):
            context, reason = "preferred", "positive_capability_with_training_fallback"
        if (
            context == "negated"
            and re.search(r"không bắt buộc|not (?:required|mandatory)", after, re.I)
            and CAPABILITY.search(before)
        ):
            context, reason = "preferred", "explicit_optional_capability"
        # Known false positives from browser-AI reviews must not pass as products.
        if name == "Agile" and re.search(r"agile\s*,\s*organi[sz]ed", local, re.I):
            context, reason = "mentioned", "agile_adjective_not_methodology"
        if (
            name == "Sử dụng máy tính"
            and re.search(r"(?:có|sở hữu|trang bị).{0,20}(?:máy tính|laptop)", local, re.I)
            and not re.search(r"sử dụng|thành thạo|biết|kỹ năng|cài đặt|sửa chữa", local, re.I)
        ):
            context, reason = "mentioned", "owning_computer_not_capability"
        if (
            name == "Bảo hiểm xã hội"
            and re.search(
                r"(?:đóng|tham gia|chế độ|hưởng).{0,25}(?:bảo hiểm|BHXH)|social insurance coverage",
                before + anchor + after,
                re.I,
            )
            and not re.search(
                r"nghiệp vụ|am hiểu|nắm vững|giải quyết|thủ tục|tính lương", before, re.I
            )
        ):
            context, reason = "mentioned", "insurance_benefit_not_capability"
        # Education/training/benefit headings continue until a requirements heading.
        headings = list(
            re.finditer(
                r"QUYỀN LỢI|CHẾ ĐỘ ĐÃI NGỘ|WHAT (?:WE OFFER|YOU CAN EXPECT)|"
                r"COMPENSATION(?:\s*&\s*BENEFITS)?|BENEFITS|YÊU CẦU(?: CÔNG VIỆC)?|"
                r"REQUIREMENTS|QUALIFICATIONS|MUST[- ]HAVE",
                requirements[:start],
                re.I,
            )
        )
        if headings and re.match(
            r"QUYỀN LỢI|CHẾ ĐỘ|WHAT|COMPENSATION|BENEFITS", headings[-1].group(), re.I
        ):
            context, reason = "mentioned", "benefit_section_not_capability"
        # Merely being a student/graduate of the subject remains education.
        if re.search(
            r"(?:sinh viên|đang học|đang theo học|student).{0,40}$", before, re.I
        ) and not re.search(
            r"kinh nghiệm|kiến thức|kỹ năng|biết|thành thạo|experience|knowledge|skill",
            before,
            re.I,
        ):
            context, reason = "mentioned", "student_subject_not_capability"
        # Owner-approved distinction: bare 'được đào tạo' is not prior capability.
        if context == "ambiguous" and reason == "training_time_unspecified":
            context, reason = "mentioned", "training_only_owner_excludes"
        # A waiver of years does not negate another clear capability in the clause.
        if context in {"negated", "ambiguous"} and re.search(
            r"không (?:yêu cầu|cần) (?:nhiều )?kinh nghiệm|chưa có kinh nghiệm|"
            r"no (?:prior )?experience|experience is not mandatory",
            before,
            re.I,
        ):
            waiver = list(
                re.finditer(
                    r"không (?:yêu cầu|cần) (?:nhiều )?kinh nghiệm|chưa có kinh nghiệm|"
                    r"no (?:prior )?experience|experience is not mandatory",
                    before,
                    re.I,
                )
            )[-1]
            if re.search(
                r"biết|thành thạo|sử dụng|có khả năng|có kiến thức|know|proficien",
                before[waiver.end() :],
                re.I,
            ):
                context, reason = "required", "explicit_capability_after_experience_waiver"
        decision = (
            "accept"
            if context in {"required", "preferred"}
            else "reject"
            if context in {"mentioned", "negated"}
            else "unclear"
        )
        outcomes.append(ProposalAssessment(decision, reason, start, end, anchor))
    # A demonstrated occurrence suffices; do not let an education occurrence erase it.
    return min(outcomes, key=lambda x: {"accept": 0, "unclear": 1, "reject": 2}[x.decision])
