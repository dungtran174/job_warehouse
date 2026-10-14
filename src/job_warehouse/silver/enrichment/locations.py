"""Extract source-mentioned place names, without geocoding or boundary inference."""

import re
import unicodedata
from functools import lru_cache

from job_warehouse.silver.enrichment.address_matching import (
    address_key,
    compatible_units,
    same_address,
)
from job_warehouse.silver.enrichment.assets import Rule, load_rules, read_csv
from job_warehouse.silver.enrichment.models import AddressLink, Evidence, Location
from job_warehouse.silver.text import normalize_text


@lru_cache(maxsize=1)
def places() -> dict[str, str]:
    rows = read_csv("places.csv")
    result = {row["code"]: row["label"] for row in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate place codes")
    return result


@lru_cache(maxsize=1)
def place_rules() -> tuple[Rule, ...]:
    return load_rules("place_rules.csv", set(places()))


@lru_cache(maxsize=1)
def foreign_rules() -> tuple[Rule, ...]:
    return load_rules("foreign_rules.csv", {r["value"] for r in read_csv("foreign_rules.csv")})


@lru_cache(maxsize=1)
def locality_rules() -> tuple[Rule, ...]:
    rows = read_csv("locality_rules.csv")
    if any(not row["reference_url"].startswith("https://") or not row["basis"] for row in rows):
        raise ValueError("Locality parent rules require references and mapping basis")
    return load_rules("locality_rules.csv", set(places()))


@lru_cache(maxsize=1)
def address_reference_rules() -> tuple[Rule, ...]:
    rows = read_csv("address_reference_rules.csv")
    if any(not row["reference_url"].startswith("https://") or not row["basis"] for row in rows):
        raise ValueError("Address references require source URLs and a bounded mapping basis")
    return load_rules("address_reference_rules.csv", set(places()))


REMOTE = re.compile(
    r"(?<!\w)(?:remote|từ xa|làm việc tại nhà(?!\s+(?:máy|sách|hàng|kho|thuốc)\b)|"
    r"work from home|(?:làm(?: việc)?|work(?:ing)?)\s+online)(?!\w)|"
    r"(?:^|[;|])\s*online\s*(?=$|[;|])",
    re.I,
)
NATIONWIDE = re.compile(r"(?<!\w)(?:toàn quốc|toan quoc|nationwide|cả nước)(?!\w)", re.I)
BRANCH_NETWORK = re.compile(
    r"trụ sở chính|head ?office|chi nhánh.*(?:toàn quốc|cả nước)|(?:toàn quốc|cả nước).*chi nhánh",
    re.I,
)
ROAD = re.compile(
    r"(?:đường|duong|phố|pho|street|xa lộ|xa lo|đại lộ|dai lo|boulevard|avenue|ngõ|hẻm)\s*$",
    re.I,
)
CITY_PREFIX = re.compile(r"(?:thành phố|thanh pho|tỉnh|tinh|\btp\.?)\s*$", re.I)
LOWER_PLACE_PREFIX = re.compile(
    r"(?:\bphường|\bphuong|\bward|\bxã|\bxa|\bquận|\bquan|\bhuyện|\bhuyen|"
    r"\bthị trấn|\bthi tran|\bp\.|\bq\.)\s+[^,;|]*$",
    re.I,
)
LOWER_PLACE_DIRECT_PREFIX = re.compile(
    r"(?:\bphường|\bphuong|\bward|\bxã|\bxa|\bquận|\bquan|\bhuyện|\bhuyen|"
    r"\bthị trấn|\bthi tran|\bấp|\bthôn|\bkhu phố|\bkp\.?|\bp\.?|\bq\.?)\s*$",
    re.I,
)
COMPOUND_LOWER_NAMES = re.compile(
    r"hiệp bình phước|hiep binh phuoc|phú thọ ho[àa]|phu tho hoa|quảng huế|quang hue", re.I
)
LANDMARK_PREFIX = re.compile(
    r"(?:bến xe|ben xe|ga tàu|ga xe lửa|bus station|railway station|công viên|cong vien)\s*$", re.I
)
BUILDING_PREFIX = re.compile(r"(?:(?:tòa|toà)\s+(?:nhà\s+)?|building\s+|tower\s+)$", re.I)
FACILITY_PREFIX = re.compile(
    r"(?:tòa nhà|toà nhà|tòa tháp|toà tháp|chung cư|building|tower|cửa khẩu|"
    r"khu công nghiệp|khu cn|kcn|coop ?mart|co\.opmart|lotte ?mart|nhà máy|factory|"
    r"vsip|vincom|big c|becamex)\s+[^,;|]*$",
    re.I,
)
HOUSE_NUMBER_PREFIX = re.compile(r"(?<!\w)\d+(?:bis|ter|[a-z])?(?:/\d+[a-z]?)*\s+$", re.I)
NUMBERED_ADMIN_PREFIX = re.compile(r"(?:phường|ward|p\.?|quận|district|q\.?)\s*\d+\s*$", re.I)
KNOWN_STREET_NAMES = re.compile(
    r"(?:song hành hà nội|song hanh ha noi|điện biên phủ|dien bien phu|"
    r"ng(?:uỵ|ụy|uy)\s+nh(?:ư|u)\s+kon tum|"
    r"nguy(?:ễn|en)\s+th(?:ái|ai)\s+b(?:ình|inh)|nguy(?:ễn|en)\s+hu(?:ệ|e))",
    re.I,
)
COMPOUND_FACILITY_NAMES = re.compile(
    r"(?:Hòa|Hoà|Hoa)\s+(?:Bình|Binh)\s+Green\s*City|"
    r"(?:Sài Gòn|Sai Gon)\s*[-–—]\s*(?:Chân Mây|Chan May)",
    re.I,
)
FOREIGN_UNSPECIFIED = re.compile(r"(?<!\w)(?:foreign|overseas|nước ngoài)(?!\w)", re.I)
UNKNOWN = {
    "không",
    "khác",
    "chưa xác định",
    "không xác định",
    "n/a",
    "unknown",
}


def _facility_place(text: str, start: int, end: int) -> bool:
    """Q23 accepts a source locality suffix in a named facility, not a street."""
    prefix = text[max(0, start - 120) : start]
    marker = FACILITY_PREFIX.search(prefix)
    if marker and re.search(
        r"(?:phường|phuong|quận|huyện|tỉnh|thành phố|\bp\.|\bq\.|\btp\.?)\s*\S",
        marker.group(),
        re.I,
    ):
        return False
    return bool(
        marker
        and not ROAD.search(prefix)
        and not CITY_PREFIX.search(prefix)
        and re.match(r"\s*(?:$|[:,;|.–—]|\s-\s)", text[end:])
    )


def _non_place_context(text: str, start: int, end: int) -> bool:
    """Place tokens inside streets, wards or building names are not provinces."""
    prefix = text[max(0, start - 120) : start]
    if CITY_PREFIX.search(prefix):
        return False
    if any(
        start < m.end() and end > m.start()
        for pattern in [KNOWN_STREET_NAMES, COMPOUND_LOWER_NAMES]
        for m in pattern.finditer(text)
    ):
        return True
    # House/street context takes precedence over an earlier facility marker.
    # "Tòa nhà số 324 Đà Nẵng" is not a province locality suffix.
    if HOUSE_NUMBER_PREFIX.search(prefix) and not NUMBERED_ADMIN_PREFIX.search(prefix):
        return True
    # A comma may separate a house number from its street name. Require
    # typed ward/district after the name so a numeric province list stays intact.
    if re.search(r"(?<!\w)\d+[a-z]?(?:/\d+)*\s*,\s*$", prefix, re.I) and re.match(
        r"\s*,\s*(?:phường|p\.)\s*\S[^;|]*(?:quận|q\.)\s*\S", text[end:], re.I
    ):
        return True
    if _facility_place(text, start, end):
        return False
    return any(
        pattern.search(prefix) for pattern in [ROAD, LOWER_PLACE_DIRECT_PREFIX, BUILDING_PREFIX]
    )


def _country_context(text: str, rule: Rule, match: re.Match[str]) -> bool:
    """Reject country words belonging to a domestic locality or industrial park."""
    prefix = text[max(0, match.start() - 120) : match.start()]
    if LOWER_PLACE_PREFIX.search(prefix) or ROAD.search(prefix):
        return False
    if rule.value == "LAOS" and re.search(r"(?:tt\.?|thị trấn|thi tran)\s+Quán\s*$", prefix, re.I):
        return False
    if re.search(r"(?:lĩnh vực hoạt động|sản phẩm|mỹ phẩm)\s*:?[^;|]*$", prefix, re.I):
        return False
    if re.search(r"(?:tòa nhà|toà nhà|building|tower)\s+[^,;|]*$", prefix, re.I):
        return False
    if re.match(r"\s+cơ sở\s*\d", text[match.end() :], re.I):
        return False
    if rule.value == "GERMANY" and match.group().casefold() == "đức":
        return text.strip().casefold() == "đức"
    if re.search(r"(?:tập đoàn|công ty|company|group)\s+[^,;|–—-]*$", prefix, re.I):
        return False
    return not (
        rule.value == "SINGAPORE"
        and re.search(r"kcn|khu\s+cn|công nghiệp|cong nghiep|industrial park|vsip", text, re.I)
        and re.search(r"(?:việt\s*nam|viet\s*nam|vietnam)\s*[-–— ]*\s*$", prefix, re.I)
    )


def address_identity(text: str) -> str:
    """Exact prefix comparison only: no fuzzy matching or address transfer."""
    return text.strip().rstrip(" ,.-").casefold()


def has_street_address(text: str) -> bool:
    house_and_street = re.compile(
        r"^\s*(?:số\s*)?\d+[a-z0-9]*(?:[/\-]\d+[a-z0-9]*)*\s+"
        r"(?:[^\W\d_]+\s+){1,6}[^\W\d_]+",
        re.I,
    )
    return (
        any(house_and_street.search(part) for part in text.split(","))
        or bool(
            re.search(r"\bsố\s*\d+\s*,\s*lk\d+[a-z0-9]*\b", text, re.I)
            or re.search(
                r"\blô\s+[a-z]\d+(?:[-–][a-z]?\d+)?\s+(?:kcn|khu công nghiệp)\b", text, re.I
            )
        )
        or bool(
            re.search(r"\bsố\s*\d+[a-z]?(?!\w)", text, re.I)
            and re.search(r"(?:đường|phố|street)\s+[^\W\d_]+", text, re.I)
        )
    )


def repeated_address_links(text: str, evidence: list[Evidence]) -> tuple[AddressLink, ...]:
    components = list(re.finditer(r"[^;|]+", text))
    keys = {m.start(): address_key(m.group()) for m in components}
    result: list[AddressLink] = []
    for partial in components:
        if any(e.start < partial.end() and e.end > partial.start() for e in evidence):
            continue
        identity = address_identity(partial.group())
        if not identity or (not has_street_address(identity) and keys[partial.start()] is None):
            continue
        donors: list[tuple[re.Match[str], set[str]]] = []
        conflicting_donor = False
        for complete in components:
            other = address_identity(complete.group())
            exact = other.startswith(identity + ",") and compatible_units(
                partial.group(), complete.group()
            )
            structured = same_address(keys[partial.start()], keys[complete.start()])
            if not exact and not structured:
                continue
            matches = [e for e in evidence if e.start < complete.end() and e.end > complete.start()]
            codes = {e.value for e in matches if e.rule_id.startswith("place.")}
            if len(codes) > 1 or any(
                e.rule_id.startswith("foreign.") or e.rule_id == "qualifier.foreign"
                for e in matches
            ):
                conflicting_donor = True
                continue
            if len(codes) != 1:
                continue
            donors.append((complete, codes))
        # A same-prefix address stated in two provinces cannot justify a transfer.
        if (
            not conflicting_donor
            and donors
            and len(set().union(*(codes for _, codes in donors))) == 1
        ):
            complete, codes = donors[0]
            result.append(
                AddressLink(
                    (
                        "location.repeated_address_exact_prefix"
                        if address_identity(complete.group()).startswith(identity + ",")
                        else "location.repeated_address_structured"
                    ),
                    next(iter(codes)),
                    partial.start(),
                    partial.end(),
                    complete.start(),
                    complete.end(),
                )
            )
    return tuple(result)


def address_context(text: str) -> bool:
    """A house/street or typed address component, not a bare ambiguous name."""
    return (
        has_street_address(text)
        or bool(
            re.search(
                r"\bsố\s*\d+[a-z]?(?:/\d+)*\s*,\s*(?:[^\W\d_]+\s+){1,5}[^\W\d_]+\s*,", text, re.I
            )
        )
        or bool(
            re.search(r"(?<!\w)\d+[a-z]?(?:/\d+)*\s+[^\W\d_]+", text, re.I)
            and re.search(r"đường|phố|phường|quận|\bp\.?\s*\d|\bq\.?\s*\d|\s[-–—]\s", text, re.I)
        )
    )


def prefer_address_over_facility_name(
    text: str, evidence: list[Evidence], flags: set[str]
) -> list[Evidence]:
    """Q38: independent geography in the same address outranks a brand token."""
    result = list(evidence)
    geographic = sorted(
        (e for e in evidence if e.rule_id.startswith("place.")), key=lambda e: e.start
    )
    wrappers = set()
    if (
        len(geographic) >= 3
        and geographic[0].start == 0
        and geographic[-1].end == len(text)
        and geographic[0].value == geographic[-1].value
    ):
        wrappers = {geographic[0], geographic[-1]}
    for part in re.finditer(r"[^;|]+", text):
        if len(re.findall(r"văn phòng|chi nhánh|\boffice\b|\bbranch\b", part.group(), re.I)) > 1:
            # Q33 keeps all places across an unsplit office list. Another
            # office is not independent geography for this facility's address.
            continue
        local = [e for e in geographic if part.start() <= e.start < e.end <= part.end()]
        facility = [e for e in local if e not in wrappers and _facility_place(text, e.start, e.end)]
        if len({facility_key(text, e) for e in facility}) > 1:
            # Distinct named facilities in a list are separate location slots.
            continue
        for candidate in facility:
            # Repeated outer wrappers do not prove the facility's province.
            expected = {
                e.value
                for e in local
                if e not in facility
                and e.start > candidate.end
                and (
                    CITY_PREFIX.search(text[max(0, e.start - 30) : e.start])
                    or (e.start > candidate.end and "," in text[candidate.end : e.start])
                )
            }
            for rule in locality_rules():
                if rule.exclude and rule.exclude.search(part.group()):
                    continue
                if rule.id.startswith(
                    ("parent.typo_", "parent.contextual_")
                ) and not address_context(part.group()):
                    continue
                for match in rule.pattern.finditer(part.group()):
                    start = part.start() + match.start()
                    end = part.start() + match.end()
                    if start < candidate.end:
                        continue
                    prefix = text[max(0, start - 30) : start]
                    typed = LOWER_PLACE_DIRECT_PREFIX.search(prefix) or CITY_PREFIX.search(prefix)
                    if typed or (
                        address_context(part.group())
                        and not _non_place_context(text, start, end)
                        and not _facility_place(text, start, end)
                    ):
                        expected.add(rule.value)
            if expected and candidate.value not in expected:
                result[result.index(candidate)] = Evidence(
                    candidate.field,
                    "facility_name." + candidate.rule_id,
                    candidate.value,
                    candidate.start,
                    candidate.end,
                    candidate.text,
                )
                flags.add("facility_name_province_overridden_by_address")
    # Q41 removes a repeated brand token, without transferring a province or
    # claiming that two address fragments have the same house/street identity.
    known_brands = {
        facility_key(text, e)
        for e in result
        if e.rule_id.startswith("facility_name.") and facility_key(text, e)
    }
    for i, item in enumerate(result):
        if item in wrappers or not item.rule_id.startswith("place."):
            continue
        key = facility_key(text, item)
        if key and key in known_brands:
            result[i] = Evidence(
                item.field,
                "facility_name." + item.rule_id,
                item.value,
                item.start,
                item.end,
                item.text,
            )
            flags.add("repeated_facility_name_not_additional_province")
    return result


def facility_key(text: str, item: Evidence) -> str | None:
    if not _facility_place(text, item.start, item.end):
        return None
    match = FACILITY_PREFIX.search(text[max(0, item.start - 120) : item.start])
    assert match is not None
    prefix = match.group().casefold()
    prefix = re.sub(r"^(?:khu công nghiệp|khu cn|kcn)\b", "kcn", prefix)
    prefix = re.sub(r"^(?:tòa tháp|toà tháp|tòa nhà|toà nhà)\b", "building", prefix)
    prefix = re.sub(r"^building\s+(?:vp|văn phòng)\s+", "building ", prefix)
    suffix = re.match(r"\s*[-–—]\s*[^,;|]+", text[item.end :])
    if suffix and (
        re.search(
            r"phường|phuong|quận|quan|huyện|huyen|thành phố|thanh pho|tỉnh|tinh",
            suffix.group(),
            re.I,
        )
        or any(rule.pattern.search(suffix.group()) for rule in place_rules())
    ):
        suffix = None
    name = prefix + item.text + (suffix.group() if suffix else "")
    return " ".join(
        "".join(
            c for c in unicodedata.normalize("NFD", name.casefold()) if not unicodedata.combining(c)
        ).split()
    )


def explicit_old_names(text: str, evidence: list[Evidence], flags: set[str]) -> list[Evidence]:
    result = list(evidence)
    geographic = [e for e in evidence if e.rule_id.startswith("place.")]
    # Source explicitly labels a full address as old/new. This reads the
    # relation within one address; it does not convert independent locations.
    for relation in re.finditer(r"\(\s*địa chỉ\s+(cũ|mới)\s*:[^()]+\)", text, re.I):
        boundary = (
            max(text.rfind("|", 0, relation.start()), text.rfind(";", 0, relation.start())) + 1
        )
        before = [e for e in geographic if boundary <= e.start < e.end <= relation.start()]
        inside = [e for e in geographic if relation.start() <= e.start < e.end <= relation.end()]
        prefix = text[boundary : relation.start()]
        if (
            len({e.value for e in before}) != 1
            or len({e.value for e in inside}) != 1
            or before[0].value == inside[0].value
            or not address_context(prefix)
            or re.search(r"\b(?:hoặc|và)\s+(?:số|lô|văn phòng)|văn phòng.*văn phòng", prefix, re.I)
        ):
            continue
        old_items = inside if relation.group(1).casefold() == "cũ" else before
        for item in old_items:
            result[result.index(item)] = Evidence(
                item.field,
                "historical_name." + item.rule_id,
                item.value,
                item.start,
                item.end,
                item.text,
            )
        flags.add("source_explicit_old_address_relation")
    for current in geographic:
        tail = re.match(r"\s*\(\s*[^()]*?\s+cũ\s*\)", text[current.end :], re.I)
        if not tail:
            continue
        start, end = current.end + tail.start(), current.end + tail.end()
        for old in geographic:
            if start <= old.start < old.end <= end and old.value != current.value:
                related = [old]
                # A directly repeated footer is the same source label, not a
                # separately located job. A delimiter or typed province breaks it.
                for item in geographic:
                    if (
                        item.value == old.value
                        and item.start >= end
                        and not text[end : item.start].strip(" ,.")
                    ):
                        related.append(item)
                # Within ONE address, older city/headings are context of the
                # explicit new/old relation. Do not cross separators or another
                # street/lot/office start to drop an independent old province.
                boundary = (
                    max(text.rfind("|", 0, current.start), text.rfind(";", 0, current.start)) + 1
                )
                prefix = text[boundary : current.start]
                starts = re.findall(
                    r"(?<!\w)(?:lô\s+\w+|số\s*\d+|văn phòng|chi nhánh|"
                    r"\d+[a-z]?(?:/\d+)*\s+(?:đường|phố|street))",
                    prefix,
                    re.I,
                )
                if starts and len(starts) == 1:
                    related.extend(
                        item
                        for item in geographic
                        if item.value == old.value
                        and boundary <= item.start < current.start
                        and not re.search(
                            r"(?:tỉnh|tinh)\s*$",
                            text[max(boundary, item.start - 15) : item.start],
                            re.I,
                        )
                    )
                for item in related:
                    i = result.index(item) if item in result else -1
                    if i < 0:
                        continue
                    result[i] = Evidence(
                        item.field,
                        "historical_name." + item.rule_id,
                        item.value,
                        item.start,
                        item.end,
                        item.text,
                    )
                    flags.add("source_explicit_old_province_name")
    return result


def repeated_lower_names(text: str, evidence: list[Evidence], flags: set[str]) -> list[Evidence]:
    """A typed lower name in the same proven address is not a second province."""
    parts = list(re.finditer(r"[^;|]+", text))
    result = list(evidence)
    for item in evidence:
        if not item.rule_id.startswith("place."):
            continue
        part = next(p for p in parts if p.start() <= item.start < item.end <= p.end())
        key = address_key(part.group())
        for other in parts:
            if other == part or not same_address(key, address_key(other.group())):
                continue
            lower = [
                m
                for rule in place_rules()
                if rule.value == item.value
                for m in rule.pattern.finditer(other.group())
                if LOWER_PLACE_DIRECT_PREFIX.search(
                    other.group()[max(0, m.start() - 30) : m.start()]
                )
            ]
            if not lower:
                continue
            result[result.index(item)] = Evidence(
                item.field,
                "repeated_lower_name." + item.rule_id,
                item.value,
                item.start,
                item.end,
                item.text,
            )
            flags.add("province_word_resolved_as_repeated_lower_locality")
            break
    return result


def unsplit_address_parents(text: str, evidence: list[Evidence], flags: set[str]) -> None:
    """Keep a typed parent in a separate numbered address despite a missing delimiter."""
    for component in re.finditer(r"[^;|]+", text):
        starts = [
            component.start() + m.start()
            for m in re.finditer(r"(?<!\w)số\s*\d+[a-z0-9]*(?:-\d+)?", component.group(), re.I)
            if component.group()[: m.start()].count("(")
            == component.group()[: m.start()].count(")")
        ]
        if len(starts) < 2:
            continue
        for start, end in zip(starts, [*starts[1:], component.end()], strict=True):
            body = text[start:end]
            if any(
                e.rule_id.startswith("place.") and start <= e.start < e.end <= end for e in evidence
            ):
                continue
            for rule in locality_rules():
                if rule.exclude and rule.exclude.search(body):
                    continue
                for match in rule.pattern.finditer(body):
                    if not re.match(
                        r"(?:quận|quan|huyện|huyen|thành phố|thanh pho|tp\.?)\s",
                        match.group(),
                        re.I,
                    ):
                        continue
                    if ROAD.search(body[max(0, match.start() - 30) : match.start()]):
                        continue
                    evidence.append(
                        Evidence(
                            "location_clean",
                            "parent.address_component." + rule.id,
                            rule.value,
                            start + match.start(),
                            start + match.end(),
                            match.group(),
                        )
                    )
                    flags.add("province_inferred_from_unsplit_numbered_address")
                    flags.add("province_inferred_from_locality_parent")


def _industrial_park_identity(text: str) -> str | None:
    match = re.search(r"(?:kcn|khu cn|khu công nghiệp)\s+([^,;|()]+)", text, re.I)
    if not match:
        return None
    name = "".join(
        c
        for c in unicodedata.normalize("NFD", match.group(1).casefold())
        if not unicodedata.combining(c)
    )
    name = re.sub(r"^viet nam\s*[-–—]\s*singapore\b", "vsip", name)
    return " ".join(name.split())


def repeated_factory_plot(text: str, evidence: list[Evidence], flags: set[str]) -> None:
    """Q46: a repeated exact lot/park can disambiguate a factory-name token.

    Do not transfer a province into an incomplete fragment or reconcile wards.
    Only the independently typed province in the fuller part is retained.
    """
    parts = list(re.finditer(r"[^;|]+", text))

    def identity(fragment: str) -> tuple[str, str] | None:
        lots = re.findall(r"\blô\s+(?:đất\s+)?([a-z]+[0-9]+(?:[-./][a-z0-9]+)?)\b", fragment, re.I)
        parks = re.findall(r"(?:kcn|khu cn|khu công nghiệp)\s+([^,;|()]+)", fragment, re.I)
        park = _industrial_park_identity(fragment)
        if len(lots) != 1 or len(parks) != 1 or park is None:
            return None
        return lots[0].casefold(), park

    for part in parts:
        key = identity(part.group())
        if key is None:
            continue
        local = [
            e
            for e in evidence
            if e.rule_id.startswith(("place.", "parent.", "address_ref."))
            and part.start() <= e.start < e.end <= part.end()
        ]
        factory = [
            e
            for e in local
            if e.rule_id.startswith("place.")
            and re.search(
                r"(?:nhà máy|factory)\s*$", text[max(part.start(), e.start - 40) : e.start], re.I
            )
            and _facility_place(text, e.start, e.end)
        ]
        if not factory or any(e not in factory for e in local):
            continue
        donor_places = {
            e.value
            for donor in parts
            if donor != part and identity(donor.group()) == key
            for e in evidence
            if e.rule_id.startswith("place.")
            and donor.start() <= e.start < e.end <= donor.end()
            and CITY_PREFIX.search(text[max(donor.start(), e.start - 30) : e.start])
        }
        if len(donor_places) != 1:
            continue
        for item in factory:
            if item.value not in donor_places:
                evidence[evidence.index(item)] = Evidence(
                    item.field,
                    "facility_name.repeated_plot." + item.rule_id,
                    item.value,
                    item.start,
                    item.end,
                    item.text,
                )
                flags.add("repeated_factory_plot_name_not_additional_province")


def repeated_explicit_old_addresses(text: str, evidence: list[Evidence], flags: set[str]) -> None:
    """Q45 resolves only a repeated address matching a source-stated old/new relation."""
    parts = list(re.finditer(r"[^;|]+", text))
    for relation in re.finditer(r"\(\s*địa chỉ\s+cũ\s*:[^()]+\)", text, re.I):
        donor = next(p for p in parts if p.start() <= relation.start() < relation.end() <= p.end())
        new_text = text[donor.start() : relation.start()]
        new_key = address_key(new_text)
        old_text = relation.group()
        park = _industrial_park_identity(old_text)
        if new_key is None or park is None or _industrial_park_identity(new_text) != park:
            continue
        historical = {
            e.value
            for e in evidence
            if e.rule_id.startswith("historical_name.")
            and relation.start() <= e.start < e.end <= relation.end()
        }
        current = {
            e.value
            for e in evidence
            if e.rule_id.startswith("place.")
            and donor.start() <= e.start < e.end <= relation.start()
        }
        if len(historical) != 1 or len(current) != 1 or historical == current:
            continue
        for part in parts:
            key = address_key(part.group())
            if (
                part == donor
                or key is None
                or (key.house, key.street) != (new_key.house, new_key.street)
                or _industrial_park_identity(part.group()) != park
                or not compatible_units(part.group(), old_text)
            ):
                continue
            known = [
                e
                for e in evidence
                if e.rule_id.startswith(("place.", "parent.", "address_ref."))
                and part.start() <= e.start < e.end <= part.end()
            ]
            if not known or {e.value for e in known} != historical:
                continue
            for item in known:
                evidence[evidence.index(item)] = Evidence(
                    item.field,
                    "historical_name.repeated_address." + item.rule_id,
                    item.value,
                    item.start,
                    item.end,
                    item.text,
                )
            flags.add("source_repeated_explicit_old_address")


def resolve_outer_place_wrapper(text: str, evidence: list[Evidence], flags: set[str]) -> set[str]:
    """Q32 prefers the inner province of one full address, retaining all evidence."""
    geographic = sorted(
        (e for e in evidence if e.rule_id.startswith("place.")), key=lambda e: e.start
    )
    values = {
        e.value
        for e in evidence
        if e.value in places() and e.rule_id.startswith(("place.", "parent.", "address_ref."))
    }
    if len(geographic) < 3:
        return values
    first, last = geographic[0], geographic[-1]
    if first.start != 0 or last.end != len(text) or first.value != last.value:
        return values
    inner = text[first.end : last.start].strip()
    inner_places = {
        e.value
        for e in evidence
        if first.end <= e.start < e.end <= last.start
        and e.rule_id.startswith(("place.", "parent.", "address_ref."))
    }
    if not (inner_places - {first.value}):
        return values
    flags.add("outer_place_wrapper_conflicts_with_inner_address")
    # Never choose one city from a network/list of separate work addresses.
    if (
        len(inner_places) == 1
        and "|" not in inner
        and ";" not in inner
        and len(re.findall(r"văn phòng|chi nhánh|trụ sở|office|branch", inner, re.I)) < 2
        and (
            address_context(inner)
            or (
                re.search(r"\b(?:đường|phố|street)\s+\S", inner, re.I)
                and re.search(r"\b(?:phường|quận|huyện|thị trấn|xã)\s+\S", inner, re.I)
            )
            or (
                re.search(r"(?<!\w)(?:phường|quận|huyện|p\.|q\.|tp\.?)\s*\S", inner, re.I)
                and re.search(r"(?<!\w)\d+[a-z]?(?!\w)", inner, re.I)
            )
            or (
                re.search(r"\btòa\b|\btoà\b|\bkcn\b|khu công nghiệp", inner, re.I)
                and re.search(r"\btầng\s*\d|\bthành phố\b|\btỉnh\b|\btp\.?\s*\S", inner, re.I)
            )
            or re.search(r"\bsố\s*\d+\s+lô\s+\d+(?:/\d+)?\s+\S", inner, re.I)
            or re.search(r"nhà vườn\s*\d+\s+khu đô thị\s+\S", inner, re.I)
            or re.search(r"\blô\s+\d+\s+[^;|]*(?:\bkđt\b|khu đô thị)\s+\S", inner, re.I)
            or re.search(r"\bkdc\s+[^,]+,\s*[^,]+,\s*[^,]+,\s*[^,]+$", inner, re.I)
            or (re.search(r"(?<!\w)(?:xã|phường)\s+.+(?:huyện|quận)\s+.+tỉnh\s+", inner, re.I))
            or (re.search(r"tòa nhà|toà nhà", inner, re.I) and re.search(r"đường|phố", inner, re.I))
            or (re.search(r"khu công nghiệp|khu cn|\bkcn\b", inner, re.I) and "," in inner)
        )
    ):
        flags.add("province_selected_from_full_address_over_outer_label")
        return inner_places
    return values


@lru_cache(maxsize=32768)
def classify_location(raw: str | None) -> Location:
    text = normalize_text(raw, short=True).clean or ""
    if not text or text.casefold() in UNKNOWN:
        return Location((), "unknown", "Chưa xác định", False, False, (), (), ())
    evidence: list[Evidence] = []
    place_values: set[str] = set()
    foreign: set[str] = set()
    flags: set[str] = set()
    spans: list[tuple[int, int]] = []
    # Longest nonoverlapping matches prevent Huế inside Thừa Thiên Huế from
    # producing two distinct names. Repeated mentions of one place remain one label.
    candidates = [
        (m.start(), m.end(), rule, m.group())
        for rule in place_rules()
        for m in rule.pattern.finditer(text)
    ]
    compound_hue = re.compile(r"(?<!\w)Huế\s*[,–—-]\s*(?:tỉnh\s+)?Thừa Thiên[ -]+Huế(?!\w)", re.I)
    hue_rule = Rule("place.hue_city_in_thuathien", "THUA_THIEN_HUE", compound_hue, None)
    candidates.extend(
        (m.start(), m.end(), hue_rule, m.group()) for m in compound_hue.finditer(text)
    )
    for start, end, rule, token in sorted(
        candidates, key=lambda x: (-(x[1] - x[0]), x[0], x[2].id)
    ):
        if any(start < b and end > a for a, b in spans):
            continue
        if (
            rule.value == "NINH_THUAN"
            and re.search(r"(?:Bắc|Bac)\s+$", text[max(0, start - 12) : start], re.I)
            and re.match(r"\s+(?:An|Thành|Thanh)(?!\w)", text[end:], re.I)
        ):
            flags.add("cross_locality_words_not_province")
            continue
        if LANDMARK_PREFIX.search(text[max(0, start - 60) : start]):
            flags.add("landmark_name_not_confirmed_place")
            continue
        component_text = next(
            m.group() for m in re.finditer(r"[^;|]+", text) if m.start() <= start < m.end()
        )
        lower_context = (
            rule.value == "PHU_THO"
            and address_context(component_text)
            and any(
                r.id == "parent.context_role_phutho_td_mot" and r.pattern.search(component_text)
                for r in locality_rules()
            )
            and not CITY_PREFIX.search(text[max(0, start - 20) : start])
        )
        lower_context = lower_context or (
            rule.value == "BINH_THUAN"
            and address_context(component_text)
            and any(
                r.id == "parent.context_role_binhthuan_q7" and r.pattern.search(component_text)
                for r in locality_rules()
            )
            and not CITY_PREFIX.search(text[max(0, start - 20) : start])
        )
        street_list = (
            rule.value == "HAU_GIANG"
            and re.match(r"\s*,\s*phường\s*6(?!\w)", text[end:], re.I)
            and all(
                re.search(name, text, re.I)
                for name in ["Nguyễn Thị Thập", "Sư Vạn Hạnh", "Bến Vân Đồn"]
            )
            and re.search(r"quận\s*12(?!\w)", text, re.I)
        )
        if lower_context or street_list:
            kind = "lower_locality_name" if lower_context else "street_name"
            evidence.append(
                Evidence("location_clean", kind + "." + rule.id, rule.value, start, end, token)
            )
            flags.add(kind + "_not_province")
            spans.append((start, end))
            continue
        if any(
            start < m.end()
            and end > m.start()
            and (
                "green" in m.group().casefold()
                or FACILITY_PREFIX.search(text[max(0, m.start() - 120) : m.start()])
            )
            for m in COMPOUND_FACILITY_NAMES.finditer(text)
        ):
            evidence.append(
                Evidence(
                    "location_clean", "facility_name." + rule.id, rule.value, start, end, token
                )
            )
            flags.add("compound_facility_name_not_province")
            spans.append((start, end))
            continue
        if _non_place_context(text, start, end):
            flags.add("street_name_not_place")
            continue
        spans.append((start, end))
        place_values.add(rule.value)
        evidence.append(Evidence("location_clean", rule.id, rule.value, start, end, token))
        if _facility_place(text, start, end):
            flags.add("province_mentioned_in_facility_name")
    evidence = repeated_lower_names(text, evidence, flags)
    evidence = explicit_old_names(text, evidence, flags)
    evidence = prefer_address_over_facility_name(text, evidence, flags)
    direct = [e for e in evidence if e.rule_id.startswith("place.")]
    place_values = {e.value for e in direct}
    # A lower-level locality is a lookup input only; outputs still contain just
    # province/city codes. An explicit province in an address takes precedence
    # over a legacy parent reference, without converting its boundary or name.
    for component in re.finditer(r"[^;|]+", text):
        explicit = [e for e in direct if e.start < component.end() and e.end > component.start()]
        countries_in_component = [
            rule.value
            for rule in foreign_rules()
            for match in rule.pattern.finditer(component.group())
            if _country_context(component.group(), rule, match)
        ]
        if countries_in_component or FOREIGN_UNSPECIFIED.search(component.group()):
            continue
        for rule in locality_rules():
            if rule.id.startswith(("parent.typo_", "parent.contextual_")) and not address_context(
                component.group()
            ):
                continue
            for match in rule.pattern.finditer(component.group()):
                if rule.exclude and rule.exclude.search(component.group()):
                    continue
                start, end = component.start() + match.start(), component.start() + match.end()
                if rule.id.startswith("parent.hcm_named.") and re.search(
                    r"(?:phường|phuong|ward|xã|xa|p\.?)\s*$",
                    text[max(0, start - 30) : start],
                    re.I,
                ):
                    continue
                typed_match = bool(
                    re.match(
                        r"(?:huyện|huyen|quận|quan|thành phố|thanh pho|tp\.?)\s",
                        match.group(),
                        re.I,
                    )
                )
                if (
                    _non_place_context(text, start, end)
                    and not (typed_match and not ROAD.search(text[max(0, start - 30) : start]))
                    and not LOWER_PLACE_DIRECT_PREFIX.search(text[max(0, start - 30) : start])
                ):
                    continue
                if explicit:
                    if rule.value not in {e.value for e in explicit}:
                        flags.add("legacy_parent_not_applied_to_explicit_place")
                    continue
                place_values.add(rule.value)
                evidence.append(
                    Evidence("location_clean", rule.id, rule.value, start, end, match.group())
                )
                flags.add("province_inferred_from_locality_parent")
                if _facility_place(text, start, end):
                    flags.add("province_mentioned_in_facility_name")
        # Q26: researched, bounded source addresses may independently supply
        # a province. Never borrow it from a different address in the same row.
        if not explicit:
            for rule in address_reference_rules():
                for match in rule.pattern.finditer(component.group()):
                    start, end = component.start() + match.start(), component.start() + match.end()
                    place_values.add(rule.value)
                    evidence.append(
                        Evidence("location_clean", rule.id, rule.value, start, end, match.group())
                    )
                    flags.add("province_inferred_from_verified_address_reference")
    for rule in foreign_rules():
        for match in rule.pattern.finditer(text):
            if any(match.start() < b and match.end() > a for a, b in spans):
                continue
            if not _country_context(text, rule, match):
                continue
            foreign.add(rule.value)
            evidence.append(
                Evidence(
                    "location_clean", rule.id, rule.value, match.start(), match.end(), match.group()
                )
            )
    generic_foreign = list(FOREIGN_UNSPECIFIED.finditer(text))
    if generic_foreign:
        if not foreign:
            foreign.add("UNSPECIFIED")
        for match in generic_foreign:
            evidence.append(
                Evidence(
                    "location_clean",
                    "qualifier.foreign",
                    "foreign",
                    match.start(),
                    match.end(),
                    match.group(),
                )
            )
        if any(
            any(
                e.value in place_values and e.start < part.end() and e.end > part.start()
                for e in evidence
            )
            and any(m.start() < part.end() and m.end() > part.start() for m in generic_foreign)
            for part in re.finditer(r"[^;|]+", text)
        ):
            flags.add("outer_foreign_wrapper_conflicts_with_domestic_address")
    unsplit_address_parents(text, evidence, flags)
    repeated_explicit_old_addresses(text, evidence, flags)
    repeated_factory_plot(text, evidence, flags)
    place_values = resolve_outer_place_wrapper(text, evidence, flags)
    if {"HUE", "THUA_THIEN_HUE"} <= place_values:
        place_values.remove("HUE")
        flags.add("hue_alias_collapsed_to_source_province")
    # Q35: a generic Foreign wrapper cannot override an independently clear
    # domestic province. A concrete country or a separate foreign address stays.
    if (
        len(place_values) == 1
        and foreign == {"UNSPECIFIED"}
        and generic_foreign
        and "|" not in text
        and all(
            m.group().casefold() == "foreign" and (m.start() == 0 or m.end() == len(text))
            for m in generic_foreign
        )
    ):
        foreign.clear()
        flags.add("domestic_province_selected_over_generic_foreign_wrapper")
    if place_values and foreign:
        # Q37 retains domestic provinces and foreign locations independently;
        # a mixed source location does not invalidate known domestic labels.
        flags.add("domestic_and_foreign_locations_mentioned")
    qualifiers = {}
    for value, pattern in [("remote", REMOTE), ("nationwide", NATIONWIDE)]:
        qualifiers[value] = bool(pattern.search(text))
        for match in pattern.finditer(text):
            evidence.append(
                Evidence(
                    "location_clean",
                    f"qualifier.{value}",
                    value,
                    match.start(),
                    match.end(),
                    match.group(),
                )
            )
    remote, nationwide = qualifiers["remote"], qualifiers["nationwide"]
    links = repeated_address_links(text, evidence)
    if links:
        flags.add("province_inferred_from_repeated_address")
    status = "unmapped"
    group = "Chưa xác định"
    if place_values:
        status = "mapped_single" if len(place_values) == 1 else "mapped_multiple"
        group = places()[next(iter(place_values))] if len(place_values) == 1 else "Nhiều địa điểm"
    if foreign:
        status, group = "foreign", "Ngoài Việt Nam"
        if place_values:
            status, group = "mapped_multiple", "Nhiều địa điểm"
    if remote:
        status, group = "remote", "Làm việc từ xa"
    if nationwide:
        status, group = "nationwide", "Toàn quốc"
    if ";" in text or "|" in text:
        # Do not silently claim a complete label set when a separated component
        # has neither a known place nor an explicit geographic/work qualifier.
        for component in re.finditer(r"[^;|]+", text):
            part = component.group().strip()
            if (
                part
                and not any(
                    e.start < component.end() and e.end > component.start() for e in evidence
                )
                and not any(link.partial_start == component.start() for link in links)
            ):
                flags.add("unmapped_location_component")
    if BRANCH_NETWORK.search(text):
        flags.add("head_office_or_branch_network_not_confirmed_workplace")
    office_headers = re.findall(
        r"(?:văn phòng|office)\s+(?:hcm|hn|hà nội|hồ chí minh|công ty|nhà máy)[^:;|–—]*[:–—]",
        text,
        re.I,
    )
    if len(office_headers) > 1:
        flags.add("multiple_office_network_not_confirmed_workplace")
    if BRANCH_NETWORK.search(text) or len(office_headers) > 1:
        flags.add("location_mentions_offices_not_confirmed_hiring_sites")
    if re.search(r"các tỉnh lân cận|tỉnh khác chưa xác định", text, re.I):
        flags.add("unspecified_additional_provinces")
    if {"HUE", "THUA_THIEN_HUE"} <= place_values:
        flags.add("related_place_names_without_boundary_crosswalk")
    # Q33 keeps all province mentions; Q34 permits known provinces when other
    # components are unresolved. Flags describe incompleteness, not row exclusion.
    if place_values and flags & {
        "unmapped_location_component",
        "unspecified_additional_provinces",
    }:
        flags.add("province_list_incomplete")
    if flags & {"related_place_names_without_boundary_crosswalk", "ambiguous_country_name"}:
        status, group = "needs_review", "Chờ xác nhận địa điểm"
    if (
        status == "needs_review"
        and not (place_values or foreign or remote or nationwide)
        and flags <= {"unmapped_location_component", "street_name_not_place"}
    ):
        status, group = "unmapped", "Chưa xác định"
    return Location(
        tuple(sorted(place_values)),
        status,
        group,
        remote,
        nationwide,
        tuple(sorted(foreign)),
        tuple(sorted(flags)),
        tuple(evidence),
        links,
    )
