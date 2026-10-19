"""Clause-local recruiting context; keep ambiguity instead of inventing a requirement."""

import re
from collections.abc import Sequence

STRONG_BOUNDARY = re.compile(r"(?<!\d)\.(?=\s|$)|[;\n!?•·●]|\s+[-–—]\s+")
INLINE_BOUNDARY = re.compile(
    r"\b(?:nhưng|tuy nhiên|however|but)\b\s*|"
    r",\s*(?=(?:ưu tiên|không (?:yêu cầu|cần)|cần biết|phải biết|"
    r"thành thạo|sử dụng|có khả năng|biết)\b)|"
    r"(?<!\S)(?=Tốt nghiệp\b|Có (?:khả năng|kinh nghiệm|hiểu biết|kiến thức|kĩ năng)\b|"
    r"Thành thạo\b|"
    r"Sử dụng\b|Ưu tiên\b|Biết\b|Am hiểu\b|Kỹ năng\b|Khả năng\b|Hiểu biết\b|"
    r"Nắm vững\b|Kiến thức\b|Ngoại ngữ\b|Giỏi\b|Trình độ học vấn\b|Giới tính\b|"
    r"Độ tuổi\b|Học vấn\b)"
)
PREFERRED = re.compile(
    r"ưu tiên|(?:là |một )?(?:lợi thế|điểm cộng|ưu thế)|preferred|nice[ -]to[ -]have|"
    r"(?:is |a )?plus\b|advantage|bonus",
    re.I,
)
NEGATED = re.compile(
    r"không\s+(?:yêu cầu|cần|đòi hỏi|bắt buộc)|chưa\s+(?:biết|có kinh nghiệm)|"
    r"(?:not|isn't|aren't)\s+(?:required|mandatory|necessary)|"
    r"no\s+(?:prior\s+)?(?:knowledge|experience|skills?).{0,60}\brequired\b",
    re.I,
)
TRAINING = re.compile(
    r"(?:sẽ\s+)?được\s+(?:công ty\s+)?(?:đào tạo|hướng dẫn)|"
    r"(?:will|shall)\s+(?:be\s+)?(?:trained|taught)|training\s+(?:is\s+)?provided",
    re.I,
)
ABILITY = re.compile(
    r"\b(?:biết|hiểu biết|am hiểu|thành thạo|sử dụng|có kinh nghiệm|kinh nghiệm\s+(?:về|với)|"
    r"có kiến thức|kiến thức\s+(?:về|với)|kỹ năng|đọc hiểu|giao tiếp|nghe|nói|đọc|viết|"
    r"giỏi|nắm vững|hiểu rõ|thành tạo|"
    r"know|knowledge|proficien\w*|fluent\w*|familiar\w*|experience|skill\w*|ability|"
    r"using|use|working with)\b",
    re.I,
)
EDUCATION = re.compile(
    r"\b(?:tốt nghiệp|chuyên ngành|ngành ngôn ngữ|cử nhân|đại học|cao đẳng|"
    r"degree\s+in|major(?:ing)?\s+in|bachelor\w*\s+in)\b",
    re.I,
)
OR = re.compile(r"\b(?:hoặc|or|hay)\b", re.I)
MARKETING_CONTEXT = re.compile(
    r"marketing|quảng cáo|tiếp thị|truyền thông|thương hiệu|\bSEO\b|paid media|"
    r"engagement strateg|community building|phát triển cộng đồng|quảng bá|bán hàng|"
    r"\bads\b|\badwords\b|fanpage|social media|truyền thông xã hội|\bSEM\b",
    re.I,
)
SHARED_LANGUAGE_PREFIX = re.compile(
    r"\btiếng\s+(?:Anh|Trung|Hoa|Nhật|Hàn|Pháp|Đức)"
    r"(?:\s*(?:[,/(]|hoặc|hay|or|và)\s*(?:tiếng\s+)?"
    r"(?:Anh|Trung|Hoa|Nhật|Hàn|Pháp|Đức))*"
    r"\s*(?:[,/(]|hoặc|hay|or|và)\s*(?:tiếng\s+)?$",
    re.I,
)
URL = re.compile(r"https?://\S+|\b[^\s@]+@[^\s@]+\.[^\s@]+", re.I)


def _contains_span(left: int, right: int, spans: Sequence[tuple[int, int]]) -> bool:
    return any(left <= start and end <= right for start, end in spans)


def clauses(text: str, spans: Sequence[tuple[int, int]]) -> list[tuple[int, int, str]]:
    """Headings persist; inline contrast separates claims only with a skill to its right.

    Offset-preserving splits operate on original text, never on casefolded text.
    A trailing 'but not required' remains attached to its skill.
    """
    result: list[tuple[int, int, str]] = []
    section = "required"
    left = 0
    boundaries = [*STRONG_BOUNDARY.finditer(text), None]
    for boundary in boundaries:
        right = boundary.start() if boundary else len(text)
        chunk = text[left:right].strip(" \t:-–—")
        if re.fullmatch(
            r"(?:ưu tiên|preferred(?: qualifications| skills)?|nice[ -]to[ -]have)", chunk, re.I
        ):
            section = "preferred"
        elif re.fullmatch(
            r"(?:yêu cầu(?: công việc)?|requirements|required(?: qualifications| skills)?|"
            r"bắt buộc|must[ -]have)",
            chunk,
            re.I,
        ):
            section = "required"
        cursor = left
        for inline in INLINE_BOUNDARY.finditer(text, left, right):
            # A capitalized predicate at the start is already in this clause.
            if inline.start() <= cursor or not text[cursor : inline.start()].strip():
                continue
            if re.search(
                r"(?:ưu tiên|preferred|nice to have|biết|sử dụng|có kiến thức|"
                r"thành thạo|bắt buộc|yêu cầu)\s*:?\s*$",
                text[cursor : inline.start()],
                re.I,
            ):
                continue
            if not _contains_span(inline.end(), right, spans):
                continue
            result.append((cursor, inline.start(), section))
            cursor = inline.end()
        result.append((cursor, right, section))
        left = boundary.end() if boundary else right
    return result


def classify_context(
    text: str,
    start: int,
    end: int,
    left: int,
    right: int,
    section: str,
    *,
    language: bool = False,
    certificate: bool = False,
) -> tuple[str, str]:
    before, after = text[left:start], text[end:right]
    chunk = text[left:right]
    if any(m.start() <= start and end <= m.end() for m in URL.finditer(text, left, right)):
        return "mentioned", "url_or_email"
    interests = list(re.finditer(r"định hướng|mong muốn|yêu thích|đam mê", before, re.I))
    if interests and not ABILITY.search(before[interests[-1].end() :]):
        return "mentioned", "interest_not_capability"
    if language and re.search(
        r"(?:hiểu biết|kiến thức).{0,60}(?:thị trường|sản phẩm)\s*$", before, re.I
    ):
        return "mentioned", "language_product_or_market"
    if re.search(r"Key Performance Indicators\s*\(KPIs\)", before, re.I):
        return "mentioned", "performance_target_not_capability"
    # Qualification/student context alone is not demonstrated applicant capability.
    education = list(EDUCATION.finditer(before))
    ability = list(ABILITY.finditer(before))
    if (
        education
        and not certificate
        and (not ability or education[-1].start() > ability[-1].start())
    ):
        return "mentioned", "education_not_capability"
    if language and re.search(r"^\s+(?:company|client|customer|market)\b", after, re.I):
        return "mentioned", "language_adjective_not_ability"
    if re.search(r"(?:công ty|our (?:company|stack))\s+(?:sử dụng|uses?|includes?)", before, re.I):
        return "mentioned", "company_stack_not_applicant"
    prior_training = TRAINING.search(before)
    following_training = TRAINING.match(after.lstrip())
    if prior_training or following_training:
        training_text = before if prior_training else after
        if re.search(r"đã\s+được\s+đào tạo", training_text, re.I):
            return "required", "prior_training_explicit"
        if re.search(
            r"sẽ\s+được|sau khi\s+(?:nhận|vào)|công ty\s+đào tạo|"
            r"will|shall|training\s+(?:is\s+)?provided",
            training_text,
            re.I,
        ):
            return "mentioned", "provided_training"
        return "ambiguous", "training_time_unspecified"
    if re.search(r"không phải (?:là )?không|not (?:unnecessary|without)", chunk, re.I):
        return "ambiguous", "nested_negation"
    negative = bool(NEGATED.search(chunk))
    preference = bool(PREFERRED.search(chunk)) or section == "preferred"
    if negative and preference:
        # Optional-but-beneficial is positive preferred, not a contradiction.
        if re.search(r"không bắt buộc|not (?:required|mandatory)", chunk, re.I) and preference:
            return "preferred", "optional_advantage"
        return "ambiguous", "mixed_negation_preference"
    if negative:
        return "negated", "explicit_no_requirement"
    if preference:
        return "preferred", "preference_cue_or_heading"
    return "required", "requirements_assertion"
