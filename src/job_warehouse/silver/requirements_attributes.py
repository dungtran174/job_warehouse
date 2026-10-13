"""Conservative requirement claims. Complex clauses abstain; no skill extraction."""

import re
from dataclasses import replace
from functools import lru_cache

from job_warehouse.silver.categorical import mapping
from job_warehouse.silver.experience import EXPRESSION, parse_experience
from job_warehouse.silver.models import Claim, Experience, Inference

# A dot inside a decimal or Node.js does not end a clause.
BOUNDARY = re.compile(r"(?<![\d.])\.(?=\s|$)|[;\n!?]|\s+-\s+|(?<!\S)[+·•]\s*")
EXP_NUMBER = re.compile(
    rf"(?P<before>{EXPRESSION})\s+kinh nghiệm\b(?P<post>\s+trở lên|\s+trở xuống)?|"
    rf"\bkinh nghiệm\s*:?\s*(?P<after>{EXPRESSION})(?!\w)",
    re.I,
)
EXP_GENERIC = re.compile(r"\b(?:có|yêu cầu)\s+kinh nghiệm\b", re.I)
NO_EXPERIENCE = re.compile(r"\bkhông (?:yêu cầu|cần) (?:có )?kinh nghiệm\b", re.I)
NO_EDUCATION = re.compile(r"\bkhông (?:yêu cầu|cần) (?:về )?(?:bằng cấp|học vấn)\b", re.I)
CRITERION = re.compile(
    r"\b(?:tốt nghiệp|trình độ|kỹ năng|ngoại ngữ|độ tuổi|có kinh nghiệm|"
    r"kinh nghiệm\s*:|(?<!được )ưu tiên|có khả năng|có\s+(?:tối thiểu|tối thiệu|ít nhất|từ|\d+)|"
    r"thành thạo|sử dụng|từng làm|đã từng|biết|hiểu biết|am hiểu|đam mê|yêu thích|"
    r"kinh nghiệm\s+(?:làm|trong|tại|về|ở))\b",
    re.I,
)


@lru_cache
def education_pattern() -> re.Pattern[str]:
    alias = "|".join(
        re.escape(x) for x in sorted(mapping("education_aliases"), key=len, reverse=True)
    )
    degree = rf"(?:{alias})(?!\w)"
    return re.compile(
        r"\b(?:tốt nghiệp(?:\s+(?:trình độ|bằng))?|"
        r"trình độ(?: học vấn)?|bằng(?: tốt nghiệp)?)\s*:?\s*"
        rf"(?P<from>từ\s+)?(?:bậc\s+)?(?P<options>{degree}(?:\s*(?:hoặc|or|/|,|và|hay|[-–—])\s*{degree})*)"
        r"(?P<minimum>\s+trở lên)?",
        re.I,
    )


@lru_cache
def cues() -> dict[str, re.Pattern[str]]:
    return {
        row["context"]: re.compile(row["pattern"], re.I)
        for row in mapping("requirement_context").values()
    }


def _clause(text: str, start: int, end: int) -> tuple[int, int]:
    left, right = 0, len(text)
    for boundary in BOUNDARY.finditer(text):
        if boundary.end() <= start:
            left = boundary.end()
        elif boundary.start() >= end:
            right = boundary.start()
            break
    return left, right


def _context(text: str, start: int, end: int, left: int, right: int, attribute: str) -> str:
    original_before = text[max(left, start - 100) : start]
    full_before = text[left:start]
    if re.search(r"ưu tiên|preferred", full_before, re.I) and not re.search(
        r"ưu tiên|preferred", original_before, re.I
    ):
        return "ambiguous"
    if (
        left
        and text[left - 1] == ";"
        and re.search(r"ưu tiên|preferred", text[max(0, left - 500) : left - 1], re.I)
    ):
        return "ambiguous"
    before = original_before
    # Only leading preference qualifies this claim. A previous criterion's
    # trailing 'là lợi thế' does not turn the following degree into preference.
    before = re.split(
        r"\b(?:tốt nghiệp|trình độ|độ tuổi|có kinh nghiệm|kinh nghiệm\s*:|thành thạo|sử dụng)\b",
        before,
        flags=re.I,
    )[-1]
    after = text[end : min(right, end + 220)]
    parenthetic_preference = re.search(r"\(\s*ưu tiên\s*\)", after, re.I)
    if parenthetic_preference and not CRITERION.search(after[: parenthetic_preference.start()]):
        return "preferred"
    if re.search(r",\s*đã qua.*(?:lợi thế|ưu thế)", after, re.I) or re.search(
        r"phù hợp\s*$", before, re.I
    ):
        return "ambiguous"
    # A new predicate starts another criterion; a benefit qualifier about this
    # same experience can follow a role/list of domains before 'là lợi thế'.
    after = CRITERION.split(after)[0]
    next_experience = EXP_NUMBER.search(after)
    if next_experience:
        after = after[: next_experience.start()]
    if len(list(cues()["negated"].finditer(before))) > 1:
        return "ambiguous"
    if re.search(
        r"\b(?:không (?:yêu cầu|cần|nhận|chấp nhận)|không phải|chưa|không)\s*(?:có\s*)?$",
        before,
        re.I,
    ):
        return "negated"
    if (
        attribute == "experience"
        and re.search(r"ưu tiên|preferred", original_before, re.I)
        and not re.search(r"ưu tiên|preferred", before, re.I)
        and re.search(r"\bcó kinh nghiệm\b", original_before, re.I)
    ):
        return "ambiguous"
    if left and re.search(r"ưu tiên\s*:", text[max(0, left - 120) : left], re.I):
        previous = text[max(0, left - 120) : left]
        if not re.search(r"[\n;·•]|\s+-\s+", previous):
            return "ambiguous"
    gender_preference = re.search(r"ưu tiên\s+(?:ứng viên\s+)?(?:nam|nữ)\b", before, re.I)
    if gender_preference:
        if attribute == "experience":
            return "ambiguous"
        before = before[: gender_preference.start()]
    if re.search(r"ưu tiên|preferred", before, re.I) or re.search(
        r"là (?:một |1 )?(?:lợi thế|ưu thế|điểm cộng)|được ưu tiên|preferred", after, re.I
    ):
        if "(" in after and not re.search(r"ưu tiên|preferred", before, re.I):
            return "ambiguous"
        return "preferred"
    return "required"


def _scope(text: str) -> tuple[str, str | None]:
    # Never borrow a following claim's scope. Only inspect the first experience
    # phrase, after its own amount, and stop at the next criterion/comma.
    noun = re.search(r"\bkinh nghiệm\b", text, re.I)
    if noun is None:
        return "unspecified", None
    tail = text[noun.end() :].lstrip(" :")
    amount = re.match(EXPRESSION, tail, re.I)
    if amount:
        tail = tail[amount.end() :].lstrip()
    tail = re.sub(r"^(?:trở lên|trở xuống)\s*", "", tail, flags=re.I)
    tail = re.sub(r"^làm việc\s+(?:trở lên|trở xuống)\s*", "", tail, flags=re.I)
    tail = re.sub(r"^làm việc\s+", "", tail, flags=re.I)
    tail = CRITERION.split(tail)[0].split(",", 1)[0]
    match = re.match(r"(?:trong|về|ở|làm|tại)\s+(.{1,60})", tail, re.I)
    if match:
        return (
            "management"
            if re.search(
                r"^(?:vị trí\s+)?(?:trưởng phòng|trưởng nhóm|chỉ huy|giám sát|giám đốc)\b|"
                r"^vị trí quản l[ýí](?:\s+(?:trong|ngành)\b|$)|"
                r"quản l[ýí]\s+(?:đội|nhóm|nhân sự|nhân viên|team|con người)\b",
                match[1],
                re.I,
            )
            else "related_role",
            match[1],
        )
    return "unspecified", None


def extract_attributes(text: str | None, requirements_status: str) -> Inference:
    if requirements_status != "present" or text is None:
        status = (
            "missing_requirements"
            if requirements_status in {"missing", "blank"}
            else "unusable_requirements"
        )
        return Inference(education_status=status, experience_status=status)
    claims: list[Claim] = []
    # Explicit absence is semantically different from negating a specific level.
    for attribute, pattern in [("education", NO_EDUCATION), ("experience", NO_EXPERIENCE)]:
        for m in pattern.finditer(text):
            left, right = _clause(text, m.start(), m.end())
            tail = text[m.end() : min(right, m.end() + 35)]
            if re.match(r"\s+(?:cao|đại học|chuyên|trong|về)", tail, re.I):
                continue
            exp = (
                Experience(kind="no_requirement", group="no_requirement", status="no_requirement")
                if attribute == "experience"
                else None
            )
            before = text[max(left, m.start() - 60) : m.start()]
            if re.search(r"không phải|không có nghĩa|không nhận", before, re.I) or cues()[
                "preferred"
            ].search(before):
                absence_context, absence_confidence, absence_status = (
                    "ambiguous",
                    "low",
                    "needs_review",
                )
            else:
                absence_context, absence_confidence, absence_status = (
                    "no_requirement",
                    "high",
                    "accepted",
                )
            claims.append(
                Claim(
                    attribute,
                    m.start(),
                    m.end(),
                    left,
                    right,
                    absence_context,
                    f"{attribute}_no_requirement",
                    relation="no_requirement",
                    experience=exp,
                    confidence=absence_confidence,
                    status=absence_status,
                )
            )
    for m in education_pattern().finditer(text):
        left, right = _clause(text, m.start(), m.end())
        option_text = m["options"]
        aliases = mapping("education_aliases")
        options = tuple(
            sorted(
                {
                    aliases[x.strip().casefold()]["category"]
                    for x in re.split(
                        r"\s*(?:\bhoặc\b|\bor\b|/|,|\bvà\b|\bhay\b|[-–—])\s*",
                        option_text,
                        flags=re.I,
                    )
                }
            )
        )
        context = _context(text, m.start(), m.end(), left, right, "education")
        unclear = bool(re.search(r"/|,|\bvà\b|\bhay\b|[-–—]", option_text, re.I))
        tail = CRITERION.split(text[m.end() : min(right, m.end() + 90)])[0]
        nonadjacent_minimum = not m["minimum"] and bool(re.search(r"\btrở lên\b", tail, re.I))
        unparsed_list = bool(
            re.match(
                r"\s*(?:nghề\s*)?(?:;|,|&|\+|tới|đến|[-–—]|/|và|hay|hoặc)?\s*"
                r"(?:hoặc\s+)?"
                r"(?:trung cấp|cao đẳng|đại học|thpt|thcs|sơ cấp)\b",
                text[m.end() : m.end() + 100],
                re.I,
            )
            or re.search(
                r"\bhoặc\s+(?:trên\s+)?(?:trung cấp|cao đẳng|đại học|đh|cđ|thpt|thcs)\b",
                tail,
                re.I,
            )
        )
        preceding = text[max(left, m.start() - 40) : m.start()]
        has_minimum = bool(
            m["minimum"] or m["from"] or re.search(r"(?:tối thiểu|ít nhất)\s*$", preceding, re.I)
        )
        mixed_branch_bound = has_minimum and len(options) > 1
        unclear = unclear or nonadjacent_minimum or unparsed_list or mixed_branch_bound
        relation = (
            "minimum_level" if has_minimum else "any_of" if len(options) > 1 else "specified_level"
        )
        qualification = (
            "graduated"
            if m.group().casefold().startswith(("tốt nghiệp", "bằng"))
            else "unspecified"
        )
        claims.append(
            Claim(
                "education",
                m.start(),
                m.end(),
                left,
                right,
                "ambiguous" if unclear else context,
                "education_explicit",
                options,
                relation,
                qualification,
                confidence="medium" if unclear else "high",
                status="needs_review" if unclear else "accepted",
                reasons=("degree_list_or_nonadjacent_bound_unclear",)
                if unclear
                else ("explicit_degree_phrase", "owner_from_degree_minimum")
                if m["from"] and not m["minimum"]
                else ("explicit_degree_phrase",),
                logic="unclear" if unclear else "any_of" if len(options) > 1 else "single",
            )
        )
    student_pattern = re.compile(r"\bsinh viên\s+(?:đại học|cao đẳng)(?:\s+năm cuối)?", re.I)
    for m in student_pattern.finditer(text):
        left, right = _clause(text, m.start(), m.end())
        student_context = _context(text, m.start(), m.end(), left, right, "education")
        claims.append(
            Claim(
                "education",
                m.start(),
                m.end(),
                left,
                right,
                "preferred" if student_context == "preferred" else "mentioned",
                "education_student",
                options=("college",) if "cao đẳng" in m.group().casefold() else ("bachelor",),
                qualification="student_final_year"
                if "năm cuối" in m.group().casefold()
                else "student",
            )
        )
    for m in EXP_NUMBER.finditer(text):
        claim_start = m.start()
        claim_end = m.end()
        expression = m["before"] or m["after"]
        leading_minimum = re.search(
            r"(ít nhất|tối thiểu|không dưới)\s+có\s*$",
            text[max(0, claim_start - 40) : claim_start],
            re.I,
        )
        if leading_minimum:
            expression = leading_minimum[1] + " " + expression
            claim_start = max(0, m.start() - 40) + leading_minimum.start()
        if m["after"]:
            prefix = re.search(
                r"(?:ít nhất|tối thiểu|không dưới)\s+$",
                text[max(0, m.start() - 25) : m.start()],
                re.I,
            )
            if prefix:
                expression = prefix.group().strip() + " " + expression
                claim_start = max(0, m.start() - 25) + prefix.start()
        if m["post"]:
            expression += m["post"]
        work_bound = re.match(r"\s+làm việc\s+(trở lên|trở xuống)\b", text[m.end() :], re.I)
        if work_bound:
            expression += " " + work_bound[1]
            claim_end += work_bound.end()
        exp = parse_experience(expression)
        left, right = _clause(text, claim_start, claim_end)
        scope, scope_text = _scope(text[m.start() : min(right, claim_end + 80)])
        context = _context(text, claim_start, claim_end, left, right, "experience")
        status = "accepted" if exp.status == "mapped" else "needs_review"
        preceding = text[max(left, claim_start - 35) : claim_start]
        if exp.kind == "range" and re.search(r"ít nhất|tối thiểu|không dưới", preceding, re.I):
            status, context = "needs_review", "ambiguous"
        bound_prefix = text[max(0, claim_start - 35) : claim_start]
        if re.search(
            r"\d+\s*(?:năm|tháng)\s*[-–—]\s*$|tối thiếu\s*$", bound_prefix, re.I
        ) or re.match(r"\s*trờ lên\b", text[m.end() : right], re.I):
            status, context = "needs_review", "ambiguous"
        if re.match(r"\s*(?:[-–—]|đến|tới)\s*\d", text[claim_end:], re.I) or (
            m["post"] and re.match(r"(?:trên|hơn|>)", expression, re.I)
        ):
            status, context = "needs_review", "ambiguous"
        claims.append(
            Claim(
                "experience",
                claim_start,
                claim_end,
                left,
                right,
                context,
                "experience_numeric",
                experience=exp,
                scope=scope,
                scope_text=scope_text,
                confidence="high" if status == "accepted" else "low",
                status=status,
            )
        )
    for m in EXP_GENERIC.finditer(text):
        if any(
            c.attribute == "experience" and c.start <= m.end() and c.end >= m.start()
            for c in claims
        ):
            continue
        left, right = _clause(text, m.start(), m.end())
        numeric_nearby = bool(
            re.search(
                r"(?:\d+(?:[.,]\d+)?|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|nửa)\s*(?:năm|tháng)",
                text[m.end() : min(right, m.end() + 100)],
                re.I,
            )
        )
        context = _context(text, m.start(), m.end(), left, right, "experience")
        scope, scope_text = _scope(text[m.start() : min(right, m.end() + 80)])
        claims.append(
            Claim(
                "experience",
                m.start(),
                m.end(),
                left,
                right,
                context,
                "experience_unspecified",
                status="needs_review" if numeric_nearby else "accepted",
                confidence="low" if numeric_nearby else "high",
                reasons=("numeric_nonadjacent_unparsed",)
                if numeric_nearby
                else ("explicit_phrase",),
                scope=scope,
                scope_text=scope_text,
                experience=None
                if context == "negated"
                else Experience(
                    kind="required_unspecified", group="required_unspecified", status="mapped"
                ),
            )
        )
    claims = [
        replace(c, status="needs_review", confidence="low", reasons=(*c.reasons, "context_unclear"))
        if c.context == "ambiguous"
        else c
        for c in claims
    ]
    claims.sort(key=lambda c: (c.start, c.end, c.attribute, c.rule_id))
    # Whole linked clause becomes review-only; independent clauses stay usable.
    spans = {(c.context_start, c.context_end) for c in claims}
    for left, right in spans:
        chunk = text[left:right]
        local = [c for c in claims if c.context_start == left and c.context_end == right]
        numeric = [c for c in local if c.experience and c.experience.min_months is not None]
        linked_or = bool(cues()["alternatives"].search(chunk)) and (
            len(numeric) > 1 or (numeric and re.search(r"đại học|cao đẳng|trung cấp", chunk, re.I))
        )
        linked_or = (
            linked_or
            or bool(
                re.search(r"\bhoặc\s+(?:có kinh nghiệm|từng làm)", chunk, re.I)
                and any(c.attribute == "education" for c in local)
            )
            or bool(numeric and re.search(r"\bhoặc\s+có kinh nghiệm", chunk, re.I))
        )
        # An alternative can follow a semicolon, which otherwise ends context.
        linked_or = linked_or or bool(
            local
            and re.match(r"[.;\s–—-]+hoặc\s+(?:từng làm|có kinh nghiệm|đã qua)", text[right:], re.I)
        )
        linked_or = linked_or or bool(
            re.search(
                r"\bhoặc\s+(?:đã\s+|sắp\s+|chưa\s+|mới\s+)?"
                r"(?:có|kinh nghiệm|tốt nghiệp|ra trường|từng làm|"
                r"(?:các\s+)?(?:chứng chỉ|trường đào tạo nghề|trường nghề)|người)\b",
                chunk,
                re.I,
            )
            and local
        )
        conditional = bool(local) and bool(
            cues()["conditional"].search(chunk) or re.search(r"\b(?:nếu|nhưng)\b", chunk, re.I)
        )
        if linked_or or conditional:
            claims = [
                replace(
                    c,
                    status="needs_review",
                    context="ambiguous",
                    confidence="low",
                    reasons=("complex_linked_clause",),
                    logic="unclear",
                )
                if c.context_start == left and c.context_end == right
                else c
                for c in claims
            ]
    # A fresher exception can be separated by a semicolon/full stop, not just 'but'.
    fresher_exception = bool(
        re.search(
            r"(?:chấp nhận|vẫn nhận).{0,80}(?:sinh viên|sv\b|mới ra trường|mới tốt nghiệp)|"
            r"(?:mới ra trường|mới tốt nghiệp|sinh viên|sv\b).{0,150}(?:cân nhắc|chờ bằng)|"
            r"sắp tốt nghiệp",
            text,
            re.I,
        )
    )
    if fresher_exception:
        claims = [
            replace(
                c,
                status="needs_review",
                context="ambiguous",
                confidence="low",
                reasons=("complex_linked_clause",),
                logic="unclear",
            )
            if (
                c.attribute == "experience" and c.experience and c.experience.min_months is not None
            )
            or (c.attribute == "education" and c.qualification == "graduated")
            else c
            for c in claims
        ]
    # Different mandatory attribute values without a resolved branch/scope are
    # already unsafe for summaries; do not advertise their claims as high/accepted.
    for attribute in ["education", "experience"]:
        positive = [
            c
            for c in claims
            if c.attribute == attribute and c.context in {"required", "no_requirement"}
        ]
        values = {
            (c.options, c.relation, c.qualification)
            if attribute == "education"
            else (c.experience, c.scope, c.scope_text)
            for c in positive
        }
        if len(values) > 1:
            claims = [
                replace(
                    c,
                    status="needs_review",
                    context="ambiguous",
                    confidence="low",
                    reasons=(*c.reasons, "complex_linked_clause"),
                    logic="unclear",
                )
                if c.attribute == attribute
                else c
                for c in claims
            ]
    role_headings = re.findall(
        r"\b\d+\s*[.):]?\s*(?:nhân viên|kỹ sư|kỹ thuật|quản lý|thực tập)\b", text, re.I
    )
    edu_claims = [c for c in claims if c.attribute == "education"]
    unparsed_education = any(
        not any(c.start <= m.start() and m.end() <= c.end for c in edu_claims)
        for m in re.finditer(
            r"\btốt nghiệp\s+(?:các\s+)?(?:chuyên ngành|ngành)\b|"
            r"\b(?:cử nhân|thạc s[ĩỹ])\b",
            text,
            re.I,
        )
    )
    edu_role_condition = bool(
        re.search(
            r"\bđối với\b|\bđang học\b|không áp dụng.{0,80}tiêu chuẩn|"
            r"chấp nhận.{0,80}(?:bằng|tốt nghiệp)|chưa tốt nghiệp",
            text,
            re.I,
        )
    )
    edu_minimum_header = bool(
        re.search(r"(?:bằng cấp|học vấn|trình độ)\s*\(\s*tối thiểu\s*\)", text, re.I)
    )
    unparsed_experience = any(
        not any(
            c.attribute == "experience" and c.start <= m.start() and m.end() <= c.end
            for c in claims
        )
        for m in re.finditer(r"\bkinh nghiệm[^.;\n]{0,60}\d+\s*(?:năm|tháng)\b", text, re.I)
    )
    has_absence = any(
        c.attribute == "experience" and c.relation == "no_requirement" for c in claims
    )
    unresolved_attributes = {
        c.attribute
        for c in claims
        if c.status == "needs_review"
        and sum(other.attribute == c.attribute for other in claims) > 1
    }
    claims = [
        replace(
            c,
            status="needs_review",
            context="ambiguous",
            confidence="low",
            reasons=(*c.reasons, "unresolved_document_conditions"),
            logic="unclear",
        )
        if c.attribute in unresolved_attributes
        or len(role_headings) > 1
        or (c.attribute == "education" and (unparsed_education or edu_role_condition))
        or (c.attribute == "education" and edu_minimum_header and c.relation == "specified_level")
        or (c.attribute == "experience" and has_absence and unparsed_experience)
        else c
        for c in claims
    ]
    education_claims = [c for c in claims if c.attribute == "education"]
    experience_claims = [c for c in claims if c.attribute == "experience"]
    edu_options, edu_relation, edu_status = _education_summary(education_claims)
    exp, exp_status = _experience_summary(experience_claims)
    return Inference(edu_options, edu_relation, edu_status, exp, exp_status, tuple(claims))


def _status(claims: list[Claim]) -> str:
    if not claims:
        return "not_mentioned"
    if any("complex_linked_clause" in c.reasons for c in claims):
        return "complex"
    if any(c.status == "needs_review" for c in claims):
        return "ambiguous"
    return "mentions_only"


def _education_summary(claims: list[Claim]) -> tuple[tuple[str, ...], str | None, str]:
    status = _status(claims)
    if status in {"complex", "ambiguous"}:
        return (), None, status
    positive = [
        c for c in claims if c.context in {"required", "no_requirement"} and c.status == "accepted"
    ]
    values = {(c.options, c.relation, c.qualification) for c in positive}
    if len(values) > 1:
        return (), None, "complex"
    if not positive:
        return (), None, status
    claim = positive[0]
    return claim.options, claim.relation, "alternatives" if len(claim.options) > 1 else "single"


def _experience_summary(claims: list[Claim]) -> tuple[Experience | None, str]:
    status = _status(claims)
    if status in {"complex", "ambiguous"}:
        return None, status
    positive = [
        c for c in claims if c.context in {"required", "no_requirement"} and c.status == "accepted"
    ]
    values = {(c.experience, c.scope, c.scope_text) for c in positive}
    if len(values) > 1:
        return None, "complex"
    return (positive[0].experience, "single") if positive else (None, status)
