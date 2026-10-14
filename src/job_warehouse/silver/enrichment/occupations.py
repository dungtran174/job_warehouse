"""Conservative function classification: explicit title rules, exact source aliases."""

import re
from functools import lru_cache

from job_warehouse.silver.enrichment.assets import Rule, load_rules, read_csv
from job_warehouse.silver.enrichment.models import Evidence, Occupation
from job_warehouse.silver.text import normalize_text


@lru_cache(maxsize=1)
def families() -> dict[str, str]:
    rows = read_csv("families.csv")
    result = {row["code"]: row["label"] for row in rows}
    if len(result) != len(rows) or any(not row["definition"] for row in rows):
        raise ValueError("Families need unique codes and definitions")
    return result


@lru_cache(maxsize=1)
def aliases() -> dict[str, str]:
    result: dict[str, str] = {}
    for row in read_csv("occupation_aliases.csv"):
        key = (normalize_text(row["alias"], short=True).clean or "").casefold()
        if not key or row["value"] not in families() or key in result:
            raise ValueError("Invalid or duplicate occupation alias")
        result[key] = row["value"]
    return result


@lru_cache(maxsize=1)
def title_rules() -> tuple[Rule, ...]:
    return load_rules("occupation_rules.csv", set(families()))


@lru_cache(maxsize=1)
def domain_rules() -> tuple[Rule, ...]:
    return load_rules("domain_rules.csv", {row["value"] for row in read_csv("domain_rules.csv")})


ADVISORY = re.compile(
    r"trình dược|tư vấn (?:tuyển sinh|tài chính|khóa học)|course advisor|financial advisor", re.I
)
SALES = re.compile(r"(?<!\w)(?:sales?|telesales?|kinh doanh|bán hàng)(?!\w)", re.I)
LISTING = re.compile(r"(?:nhiều vị trí|các vị trí|vị trí sau|tuyển dụng:|cần tuyển:)", re.I)
SECOND_FUNCTION = {
    "ACCOUNTING": re.compile(r"kế toán.*(?:/| - | – |,|&).*bán hàng|thống kê phân xưởng", re.I),
    "AGRICULTURE": re.compile(r"nhân viên thị trường", re.I),
    "LANGUAGE": re.compile(
        r"trợ lý|hỗ trợ sếp|làm hồ sơ|kỹ sư\s*[,/&]|tổng vụ|(?<!\w)qa(?!\w)|kiểm chất lượng|"
        r"live operations assistant|kiêm\s+(?:nhiệm\s+)?nhân sự",
        re.I,
    ),
    "RETAIL": re.compile(r"lễ tân|receptionist|phục v[uụ]|waiter|waitress|kiêm\s+kho(?!\w)", re.I),
    "EDUCATION": re.compile(
        r"quản lý chất lượng khách hàng|\bta\s*(?:&|and)\s*training|phát triển sản phẩm|r&d leader",
        re.I,
    ),
    "MARKETING_MEDIA": re.compile(
        r"intern design|design intern|và tuyển dụng|\bgraphic\b|\bdesigner\b|và đào tạo|"
        r"thực tập sinh youtube|tư vấn qua điện thoại|quản trị web(?:site)?",
        re.I,
    ),
    "HR_ADMIN": re.compile(r"vận hành idols|operation coordinator|trực hotline|fanpage", re.I),
    "HOSPITALITY": re.compile(r"nhân viên phòng kế hoạch|học viên spa|phát triển.*đồ uống", re.I),
    "SECURITY": re.compile(r"mang vác hành lý|phòng cháy chữa cháy", re.I),
    "SALES": re.compile(
        r"quản lý dự án|project management|^development\s+and\s+sales?|đóng gói|sắp xếp hàng|"
        r"tư vấn nông nghiệp",
        re.I,
    ),
    "ENGINEERING": re.compile(
        r"/\s*vận hành\s*$|vận hành\s+(?:bảo trì|sửa chữa)|đào tạo học viên|/\s*máy tính", re.I
    ),
    "LEGAL": re.compile(
        r"hành chính nhân sự|trợ lý hành chính|nhân sự|hcns|"
        r"pháp (?:chế|lý)\s*[,/&-]\s*kế hoạch|dự án\s+và\s+pháp lý|thu hồi tín dụng",
        re.I,
    ),
    "LOGISTICS": re.compile(
        r"quan hệ thương mại|\+\s*cắt giấy|kiểm tra chất lượng.*vị trí 2|và công nợ|làm caf[eé]|"
        r"\+\s*khai thác|quản lý dự án",
        re.I,
    ),
    "DESIGN": re.compile(r"(?:&|[-–—])\s*media\b|digital ma[kr]etting|kỹ thuật rập", re.I),
    "CONSTRUCTION": re.compile(r"họa viên", re.I),
    "CUSTOMER_SERVICE": re.compile(
        r"technical support|quản lý đơn hàng|chứng từ|thủ tục|đóng hàng", re.I
    ),
    "IT_DATA": re.compile(r"và kho\b|chạy quảng cáo", re.I),
    "MANUFACTURING": re.compile(r"(?:phó|trưởng) phòng kỹ thuật", re.I),
    "HEALTHCARE": re.compile(r"livestream", re.I),
}
UNCLEAR_ROLE = {
    "CUSTOMER_SERVICE": re.compile(r"nhắc phí|nghiệp vụ và hỗ trợ khách hàng", re.I),
    "IT_DATA": re.compile(r"thiết kế web", re.I),
    "HEALTHCARE": re.compile(r"giao dịch kênh bác sĩ|medical visitor", re.I),
    "LEGAL": re.compile(
        r"trợ lý (?:bộ phận )?pháp chế|pháp lý kỹ thuật|xử lý nợ|thu hồi phí|"
        r"kiểm xưởng|\bcompliance\b|(?<!\w)thn(?!\w)",
        re.I,
    ),
    "SALES": re.compile(r"đối tác kinh doanh", re.I),
    "SAFETY_ENVIRONMENT": re.compile(
        r"tư vấn (?:ngành )?(?:môi trường|an toàn)|kỹ sư giám sát.*cán bộ kỹ thuật hiện trường|"
        r"an toàn sản phẩm|(?<!\w)sqe(?!\w)",
        re.I,
    ),
    "HR_ADMIN": re.compile(r"điều phối viên", re.I),
    "ENGINEERING": re.compile(r"bảo trì cáp mạng|hồ sơ (?:thanh toán|quyết toán)", re.I),
    "MANUFACTURING": re.compile(r"vận hành cẩu", re.I),
    "CLEANING": re.compile(
        r"vệ sinh tổ yến|(?:^|[,;/|&])\s*(?:kỹ thuật|kỹ thuật viên|lễ tân)\s*(?:$|[,;/|&])",
        re.I,
    ),
}
DOMAIN_PREFIX = re.compile(
    r"(?:mảng|lĩnh vực|ngành|dịch vụ|sản phẩm|mua sắm|chi phí|phòng|bộ phận|nhà máy|"
    r"phần mềm|chứng chỉ|công ty|doanh nghiệp|thiết bị|máy)\s*$",
    re.I,
)
MULTI_ROLE_CONNECTOR = re.compile(r"/|\bkiêm\b|\bvà\b|\band\b|&", re.I)
ROLE_CLAUSE_SEPARATOR = re.compile(r"[/;|,&]|\s+[-–—]\s+|\b(?:và|and|kiêm)\b", re.I)
SHARED_TECHNICIAN = re.compile(
    r"(?<!\w)(?:kỹ thuật viên|nhân viên kỹ thuật|qa|qc)(?!\w)(?=\s*(?:$|[/,;|()_–—-]))", re.I
)
NEGATIVE_PREFIX = re.compile(r"(?<!\w)(?:không|no|not|non-)\s*(?:phải\s*)?$", re.I)
MAINTENANCE = re.compile(r"(?<!\w)(?:bảo trì|maintenance)(?!\w)", re.I)
MAINTENANCE_EQUIPMENT = re.compile(
    r"(?:bảo trì|maintenance)\s*(?:[-–—:/()]\s*)?"
    r"(?:(?:hệ thống|thiết bị)\s+)?"
    r"(?:cơ khí|cơ điện|điện(?: tử| lạnh| công nghiệp)?|tự động hóa|"
    r"máy(?!\s+tính)|thiết bị|equipment|machinery|machines?|hvac|m&e)(?!\w)|"
    r"(?:electrical|mechanical|equipment|machine|machinery|hvac)\s+maintenance(?!\w)",
    re.I,
)


def _role_clause(title: str, start: int, end: int) -> str:
    left, right = 0, len(title)
    for separator in ROLE_CLAUSE_SEPARATOR.finditer(title):
        if separator.end() <= start:
            left = separator.end()
        elif separator.start() >= end:
            right = separator.start()
            break
    return title[left:right]


def _positive_exclusion(pattern: re.Pattern[str], text: str) -> bool:
    return any(
        not NEGATIVE_PREFIX.search(text[max(0, m.start() - 25) : m.start()])
        and not re.search(r"(?:chứng chỉ|bằng cấp|certificate)\s*$", text[: m.start()], re.I)
        for m in pattern.finditer(text)
    )


@lru_cache(maxsize=32768)
def classify_occupation(title: str | None, industry: str | None) -> Occupation:
    title = title or ""
    source = normalize_text(industry, short=True).clean or ""
    source_matches: set[str] = set()
    evidence: list[Evidence] = []
    # Try the whole alias before slash/comma splitting: some legitimate aliases
    # denote one occupation family despite containing punctuation.
    if source.casefold() in aliases():
        value = aliases()[source.casefold()]
        source_matches.add(value)
        evidence.append(
            Evidence("job_industry_clean", "source.exact_alias", value, 0, len(source), source)
        )
    else:
        for match in re.finditer(r"[^/;,|]+", source):
            text = match.group().strip()
            alias_value = aliases().get(text.casefold())
            if alias_value:
                start = match.start() + len(match.group()) - len(match.group().lstrip())
                source_matches.add(alias_value)
                evidence.append(
                    Evidence(
                        "job_industry_clean",
                        "source.component_alias",
                        alias_value,
                        start,
                        start + len(text),
                        text,
                    )
                )
    title_matches: set[str] = set()
    unresolved_maintenance: list[Evidence] = []
    active_mentions: list[tuple[str, str]] = []
    flags: set[str] = set()
    for rule in title_rules():
        if (
            rule.id == "role.drug_retail"
            and re.search(r"dược s[ĩỹ]|pharmacist", title, re.I)
            and re.search(r"bán thuốc", title, re.I)
            and not _positive_exclusion(SALES, title)
        ):
            flags.add("pharmacist_dispensing_role")
            continue
        for match in rule.pattern.finditer(title):
            if rule.id == "role.hospitality_listed":
                # Bare recruitment labels count only as standalone role
                # clauses. Equipment/products containing 'bếp' do not create
                # a cooking role merely because punctuation follows them.
                clause = _role_clause(title, match.start(), match.end())
                if not re.fullmatch(
                    r"\s*(?:(?:cần tuyển|tuyển|thực tập sinh)\s*:?\s*)?"
                    r"(?:bếp|phục vụ)(?:\s+(?:nam|nữ))?\s*",
                    clause,
                    re.I,
                ):
                    continue
            if rule.id == "role.hr_listed" and not re.fullmatch(
                r"\s*hành chính(?:\s+không yêu cầu kinh nghiệm)?\s*",
                _role_clause(title, match.start(), match.end()),
                re.I,
            ):
                continue
            if NEGATIVE_PREFIX.search(title[max(0, match.start() - 25) : match.start()]):
                flags.add("negated_role_mention_ignored")
                continue
            if rule.exclude and _positive_exclusion(
                rule.exclude, _role_clause(title, match.start(), match.end())
            ):
                continue
            if DOMAIN_PREFIX.search(title[max(0, match.start() - 35) : match.start()]):
                continue
            if re.search(r"\((?:công ty|doanh nghiệp)\b[^)]*$", title[: match.start()], re.I):
                continue
            if re.search(
                r"(?:giảng dạy|huấn luyện|đào tạo)(?:\s+về)?\s*$", title[: match.start()], re.I
            ):
                continue
            # Q30: maintenance, a salary or a factory name is insufficient
            # to establish equipment maintenance. A later specific role may
            # provide shared title context under Q27.
            if (
                rule.value == "ENGINEERING"
                and MAINTENANCE.search(match.group())
                and not MAINTENANCE_EQUIPMENT.search(
                    _role_clause(title, match.start(), match.end())
                )
            ):
                unresolved_maintenance.append(
                    Evidence(
                        "job_title_clean",
                        "context.unspecified_maintenance_object",
                        "ENGINEERING",
                        match.start(),
                        match.end(),
                        match.group(),
                    )
                )
                continue
            if (
                rule.value == "HR_ADMIN"
                and match.group().casefold() == "recruitment"
                and re.match(r"\s+of\b", title[match.end() :], re.I)
            ):
                continue
            if rule.value == "LEGAL" and re.search(r"khách hàng\s*$", title[: match.start()], re.I):
                continue
            if (
                rule.value == "MANUFACTURING"
                and match.group().casefold() == "sản xuất"
                and re.search(r"video producer|sản xuất video", title, re.I)
                and not re.search(r"nhà máy|công nghiệp|factory|manufactur", title, re.I)
            ):
                continue
            if (
                rule.value == "HR_ADMIN"
                and match.group().casefold() == "admin"
                and re.match(
                    r"\s+(?:chăm sóc khách hàng|điều phối vận tải|kho vận)(?!\w)",
                    title[match.end() :],
                    re.I,
                )
            ):
                # The generic head is qualified by its actual function; an
                # explicit "admin và ..." remains a separate role candidate.
                continue
            if rule.value == "LOGISTICS" and re.search(
                r"(?:hỗ trợ|chăm sóc)\s*$", title[: match.start()], re.I
            ):
                continue
            if (
                rule.value == "IT_DATA"
                and match.group().casefold()
                in {"lập trình", "lập trình viên", "helpdesk", "help desk"}
                and (
                    re.search(r"cnc", title, re.I)
                    or (
                        "help" in match.group().casefold()
                        and not re.search(
                            r"(?<!\w)(?:it|cntt|công nghệ thông tin)(?!\w)", title, re.I
                        )
                    )
                )
            ):
                flags.add("generic_technical_role_not_confirmed_software")
                continue
            # A parenthesized agronomy qualification is not the function of
            # the explicitly stated market-development position (owner Q17).
            if (
                rule.value == "AGRICULTURE"
                and re.search(r"phát triển thị trường", title, re.I)
                and re.search(r"\([^)]*$", title[: match.start()])
            ):
                continue
            title_matches.add(rule.value)
            active_mentions.append((rule.value, match.group().casefold()))
            evidence.append(
                Evidence(
                    "job_title_clean",
                    rule.id,
                    rule.value,
                    match.start(),
                    match.end(),
                    match.group(),
                )
            )
    domains: set[str] = set()
    for field, text in [("job_title_clean", title), ("job_industry_clean", source)]:
        for rule in domain_rules():
            for match in rule.pattern.finditer(text):
                domains.add(rule.value)
                evidence.append(
                    Evidence(field, rule.id, rule.value, match.start(), match.end(), match.group())
                )
    primary: str | None = None
    status, method = "unresolved", "none"
    # Q11: source candidates cannot resolve an otherwise unclear advisory role.
    if ADVISORY.search(title) and not _positive_exclusion(SALES, title):
        flags.add("advisory_role_without_sales_evidence")
        status = "needs_review"
    elif len(title_matches) > 1 or (LISTING.search(title) and not title_matches):
        status = "multiple_or_ambiguous"
        flags.add("multiple_role_candidates")
    elif title_matches:
        primary = next(iter(title_matches))
        status, method = "assigned", "title_rule"
        if source_matches and source_matches != {primary}:
            flags.add("title_overrides_source_candidates")
        if primary == "CUSTOMER_SERVICE" and re.search(r"tư vấn", title, re.I):
            flags.add("generic_advisory_context_not_resolved")
        if primary == "HR_ADMIN" and re.search(r"đào tạo", title, re.I):
            flags.add("recruitment_and_staff_training")
        if MULTI_ROLE_CONNECTOR.search(title) and len(set(active_mentions)) > 1:
            flags.add("multiple_roles_same_family")
        if primary in {"CONSTRUCTION", "HEALTHCARE", "ENGINEERING", "IT_DATA"}:
            for match in SHARED_TECHNICIAN.finditer(title):
                if not any(
                    e.field == "job_title_clean"
                    and e.start <= match.start()
                    and e.end > match.end()
                    for e in evidence
                ):
                    flags.add("shared_specialization_from_title")
                    flags.add("multiple_roles_same_family")
                    evidence.append(
                        Evidence(
                            "job_title_clean",
                            "context.shared_title_specialization",
                            primary,
                            match.start(),
                            match.end(),
                            match.group(),
                        )
                    )
        if primary == "IT_DATA" and re.search(r"camera", title, re.I):
            flags.add("computer_network_camera_shared_context")
        if LISTING.search(title) and any(
            part.group().strip()
            and not any(
                e.field == "job_title_clean" and e.start < part.end() and e.end > part.start()
                for e in evidence
            )
            for part in re.finditer(r"[^/,&]+", title)
        ):
            primary, status, method = None, "needs_review", "none"
            flags.add("listing_contains_unresolved_role")
    elif source_matches:
        status, method = "needs_review", "source_candidate"
        flags.add("source_label_cannot_resolve_unclear_title")
        if len(source_matches) > 1:
            flags.add("multiple_source_candidates")
    if unresolved_maintenance:
        evidence.extend(unresolved_maintenance)
        if primary in {
            "ENGINEERING",
            "SAFETY_ENVIRONMENT",
            "CONSTRUCTION",
            "IT_DATA",
        }:
            # A clear specialty in this title can qualify a generic
            # maintenance role, just as it qualifies a generic technician.
            flags.add("shared_specialization_from_title")
        else:
            primary, status, method = None, "needs_review", "none"
            flags.add("maintenance_object_not_resolved")
    if primary in SECOND_FUNCTION and _positive_exclusion(SECOND_FUNCTION[primary], title):
        primary, status, method = None, "multiple_or_ambiguous", "none"
        flags.add("additional_role_function_not_resolved")
    if primary in UNCLEAR_ROLE and UNCLEAR_ROLE[primary].search(title):
        primary, status, method = None, "needs_review", "none"
        flags.add("role_context_not_clear")
    if (
        primary == "MANUFACTURING"
        and re.search(r"truyền thông|quảng cáo|media|film|video", source + " " + title, re.I)
        and not re.search(r"nhà máy|công nghiệp|công nhân|factory|manufactur", title, re.I)
    ):
        primary, status, method = None, "needs_review", "none"
        flags.add("production_domain_not_confirmed_industrial")
    if primary and re.search(r"[\u3400-\u9fff]", title):
        primary, status, method = None, "needs_review", "none"
        flags.add("unvalidated_parallel_language_role")
    # Long and visibly truncated job lists cannot justify selecting one function.
    if title.endswith(("...", "…")) and len(title) >= 240:
        primary, status, method = None, "needs_review", "none"
        flags.add("truncated_title")
    return Occupation(
        primary,
        tuple(
            sorted(
                title_matches
                | source_matches
                | ({"ENGINEERING"} if unresolved_maintenance else set())
            )
        ),
        tuple(sorted(source_matches)),
        tuple(sorted(domains)),
        status,
        method,
        tuple(sorted(flags)),
        tuple(evidence),
    )
