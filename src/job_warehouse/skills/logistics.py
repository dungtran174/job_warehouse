"""Finite logistics keywords and explicitly authorized driving certificates."""

import re
from dataclasses import replace
from pathlib import Path

from job_warehouse.skills.conservative import ConservativeHRFinanceMatcher
from job_warehouse.skills.models import Alias, Evidence, Extraction

LOGISTICS_MAPPINGS = Path(__file__).with_name("mappings_logistics")
DRIVING_CERTIFICATES = (
    (
        "log_car_driving",
        re.compile(
            r"(?:bằng(?: lái(?: xe)?)?|giấy phép lái xe)\s*(?:hạng|dấu)?\s*B[12]\b|"
            r"(?:bằng lái(?: xe)?|giấy phép lái xe)\s*(?:hạng|dấu)?\s*(?:C|D|E|FE|CE)\b|"
            r"(?:bằng lái|giấy phép lái) xe ô tô",
            re.I,
        ),
    ),
    (
        "log_motorcycle_driving",
        re.compile(
            r"(?:bằng lái|giấy phép lái)\s*(?:xe máy|xe mô tô)|"
            r"(?:bằng lái(?: xe)?|giấy phép lái xe)\s*(?:hạng)?\s*A[12]\b",
            re.I,
        ),
    ),
    ("log_forklift", re.compile(r"chứng chỉ\s*(?:lái|vận hành)\s*xe nâng", re.I)),
)
TASK = re.compile(
    r"quản lý (?:kho|tồn kho|đội xe|xe|lộ trình)|kiểm (?:kê|soát tồn kho)|"
    r"tìm kiếm nhà cung cấp|phát triển nhà cung cấp|đánh giá nhà cung cấp|"
    r"khai báo hải quan|thủ tục hải quan|điều (?:phối|độ|hành)|giao hàng|"
    r"lái xe|rành đường|thông thạo đường|am hiểu đường|vận hành (?:xe nâng|kho)",
    re.I,
)


class LogisticsSkillMatcher(ConservativeHRFinanceMatcher):
    def _candidates(self, text: str) -> list[tuple[int, int, Alias]]:
        items = super()._candidates(text)
        specifics = {"log_car_driving", "log_motorcycle_driving", "log_forklift"}
        return [
            (s, e, a)
            for s, e, a in items
            if not (
                a.skill_code == "log_driving"
                and any(
                    s < be and bs < e and other.skill_code in specifics for bs, be, other in items
                )
            )
        ]

    def extract(self, text: str | None) -> Extraction:
        base = super().extract(text)
        if text is None or base.status in {"missing_requirements", "unusable_requirements"}:
            return base
        evidence = []
        for e in base.evidence:
            before = text[e.context_start : e.start]
            local = text[e.context_start : e.context_end]
            reason = None
            if e.skill_code.startswith("log_") or e.skill_code in {
                "review_quan_ly_kho",
                "review_kiem_ke_hang_hoa",
                "review_thu_mua",
                "review_xuat_nhap_khau",
                "review_khai_bao_hai_quan",
                "review_dieu_do_van_tai",
            }:
                if re.search(r"(?:phần mềm|hệ thống|công cụ)[^.;\n]{0,50}$", before, re.I) and (
                    self.taxonomy.skills[e.skill_code].group != "tool"
                ):
                    reason = "logistics_software_not_its_business_process"
                elif re.search(
                    r"(?:bán|sales|kinh doanh)\s+(?:các )?(?:dịch vụ|phần mềm)[^.;\n]{0,90}$|"
                    r"khách hàng[^.;\n]{0,50}$",
                    before,
                    re.I,
                ):
                    reason = "logistics_sold_service_or_customer_not_own_operation"
                elif re.search(r"phụ cấp|thưởng|thu nhập|quyền lợi", before[-70:], re.I):
                    reason = "logistics_benefit_not_skill"
                elif (
                    e.context == "ambiguous"
                    and e.rule_id == "sales_bare_list_without_capability"
                    and TASK.search(e.text)
                    and not re.search(
                        r"tốt nghiệp|chuyên ngành|degree|major|được đào tạo|sẽ được|không",
                        local,
                        re.I,
                    )
                ):
                    e = replace(e, context="required", rule_id="logistics_explicit_duty")
            if e.skill_code in {
                "log_car_driving",
                "log_motorcycle_driving",
                "log_forklift",
            } and re.search(r"được cấp|hỗ trợ thi|đào tạo", before, re.I):
                reason = "logistics_future_driving_certificate"
            if reason and e.context in self.policy.positive_contexts:
                e = replace(e, context="ambiguous", rule_id=reason)
            evidence.append(e)
        for code, pattern in DRIVING_CERTIFICATES:
            for match in pattern.finditer(text):
                start, end = match.span()
                left = max([0, *[m.end() for m in re.finditer(r"[.;\n]", text[:start])]])
                left = max(left, start - 100)
                prefix = text[left:start]
                if re.search(
                    r"không (?:có|yêu cầu|cần)|chưa có|sẽ|được cấp|hỗ trợ thi|"
                    r"đào tạo|tiếng anh|ngoại ngữ",
                    prefix,
                    re.I,
                ):
                    continue
                if re.search(r"tiếng anh|ngoại ngữ", text[end : end + 30], re.I):
                    continue
                evidence.append(
                    Evidence(
                        code,
                        start,
                        end,
                        text[start:end],
                        left,
                        end,
                        "preferred" if re.search(r"ưu tiên", prefix, re.I) else "required",
                        "owner_batch03_driving_certificate",
                        "single",
                    )
                )
        # Conflicting direct claims stay skipped, even beside a positive license.
        negated = {e.skill_code for e in evidence if e.context == "negated"}
        evidence = [
            replace(e, context="ambiguous", rule_id="conflicting_assertions")
            if e.skill_code in negated and e.context in self.policy.positive_contexts
            else e
            for e in evidence
        ]
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
