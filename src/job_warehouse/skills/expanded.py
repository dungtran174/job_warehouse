"""Literal expanded vocabulary with conservative, requirements-only context checks.

This is a new candidate extractor. It does not turn curated, document-specific
AI/owner judgements into global aliases or claim validated recall.
"""

import re
from dataclasses import replace
from pathlib import Path

from job_warehouse.skills.context import MARKETING_CONTEXT, STRONG_BOUNDARY, clauses
from job_warehouse.skills.matcher import SkillMatcher
from job_warehouse.skills.models import Alias, Evidence, Extraction, SkillPolicy
from job_warehouse.skills.proposal_review import assess_proposal
from job_warehouse.skills.taxonomy import Taxonomy, load_taxonomy

EXPANDED_MAPPINGS = Path(__file__).with_name("mappings_expanded")
EXPANDED_VERSION = "requirements-skills-expanded-v5"
EXPANDED_TAXONOMY_VERSION = "reviewed-skills-expanded-v2"

MEDIA_SURFACES = {
    "chỉnh sửa video": ("review_bien_tap_dung_video",),
    "quay video": ("review_quay_phim",),
    "quay dựng video": ("review_quay_phim", "review_bien_tap_dung_video"),
    "chỉnh sửa hình ảnh": ("review_chinh_sua_hinh_anh",),
    "chỉnh sửa ảnh": ("review_chinh_sua_hinh_anh",),
    "chỉnh sửa ảnh/video": ("review_chinh_sua_hinh_anh", "review_bien_tap_dung_video"),
    "chỉnh sửa ảnh, video": ("review_chinh_sua_hinh_anh", "review_bien_tap_dung_video"),
    "viết bài": ("review_viet_noi_dung_copywriting",),
    "sáng tạo nội dung": ("review_san_xuat_noi_dung",),
    "quay chụp": ("review_quay_phim", "review_chup_anh"),
    "quay, chụp": ("review_quay_phim", "review_chup_anh"),
}


def inherited_degree_context(text: str, start: int) -> bool:
    """A dash inside a degree list must not turn the next major into a skill."""
    boundaries = list(re.finditer(r"(?<!\d)\.(?=\s|$)|[;\n!?•●]", text[:start]))
    left = boundaries[-1].end() if boundaries else 0
    prefix = text[left:start]
    degrees = list(
        re.finditer(
            r"tốt nghiệp|chuyên ngành|degree\s+in|major(?:ing)?\s+in|"
            r"bachelor|cử nhân|đại học|cao đẳng",
            prefix,
            re.I,
        )
    )
    if not degrees:
        return False
    tail = prefix[degrees[-1].end() :]
    if not re.search(r"[-–—]", tail):
        return False
    return not re.search(
        r"kinh nghiệm|am hiểu|hiểu biết|thành thạo|thông thạo|đã làm|đã từng|"
        r"\bbiết\b|có (?:khả năng|kiến thức|kỹ năng)|yêu cầu|experience|skills?|proficien",
        tail,
        re.I,
    )


def has_marketing_context(text: str) -> bool:
    """A marketing degree alone cannot establish the work context of media skills."""
    for marker in MARKETING_CONTEXT.finditer(text):
        if inherited_degree_context(text, marker.start()):
            continue
        left, _, _ = next(
            segment
            for segment in clauses(text, [marker.span()])
            if segment[0] <= marker.start() < segment[1]
        )
        prefix = text[left : marker.start()]
        education = list(
            re.finditer(
                r"tốt nghiệp|chuyên ngành|degree\s+in|major(?:ing)?\s+in|"
                r"bachelor|cử nhân|đại học|cao đẳng",
                prefix,
                re.I,
            )
        )
        if education and not re.search(
            r"kinh nghiệm|am hiểu|hiểu biết|thành thạo|đã làm|đã từng|"
            r"\bbiết\b|experience|proficien",
            prefix[education[-1].end() :],
            re.I,
        ):
            continue
        return True
    return False


class ExpandedSkillMatcher(SkillMatcher):
    """Keep literal product boundaries, then assess the actual recruiting clause."""

    def __init__(self, taxonomy: Taxonomy, policy: SkillPolicy) -> None:
        if any(STRONG_BOUNDARY.search(alias.text) for alias in taxonomy.aliases):
            raise ValueError("Expanded aliases may not cross strong clause boundaries")
        super().__init__(taxonomy, policy)
        self.original = SkillMatcher(load_taxonomy(), policy)

    @staticmethod
    def _alias_context_ok(text: str, start: int, end: int, alias: Alias) -> bool:
        local = text[max(0, start - 160) : end + 160]
        if (
            alias.skill_code == "review_nghiep_vu_ngan_hang"
            and alias.text.casefold() == "ngân hàng"
        ):
            prefix = text[max(0, start - 160) : start]
            return bool(re.search(r"nghiệp vụ|hoạt động|kiến thức|hiểu biết|am hiểu", prefix, re.I))
        if (
            alias.skill_code == "rest_api"
            and alias.text.casefold() == "rest"
            and re.search(r"dữ liệu từ xa|HTTP|web service", local, re.I)
        ):
            return True
        if alias.skill_code == "illustrator" and alias.text.casefold() == "ai":
            after = text[end : end + 50]
            if re.match(r"\s+(?:hỗ trợ|tạo sinh|generative|assist)", after, re.I):
                return False
            if re.search(
                r"Photoshop|Figma|Canva|Corel|InDesign|\bPTS\b", local, re.I
            ) and re.search(r"[,/]", local):
                return True
        return SkillMatcher._alias_context_ok(text, start, end, alias)

    def _candidates(self, text: str) -> list[tuple[int, int, Alias]]:
        candidates = super()._candidates(text)
        for surface, codes in MEDIA_SURFACES.items():
            for match in re.finditer(r"(?<!\w)" + re.escape(surface) + r"(?!\w)", text, re.I):
                candidates.extend(
                    (match.start(), match.end(), Alias(code, match.group()))
                    for code in codes
                    if code in self.taxonomy.skills
                )
        # Bare AI is routed independently of the Illustrator alias, and only
        # with technical/AI context in requirements rather than source industry.
        for match in re.finditer(r"(?<!\w)AI(?!\w)", text, re.I):
            left, right = max(0, match.start() - 180), match.end() + 180
            local = text[left:right]
            design = any(
                s <= match.start() and match.end() <= e and a.skill_code == "illustrator"
                for s, e, a in candidates
            )
            if (
                not design
                and re.search(
                    r"trí tuệ nhân tạo|machine learning|mô hình|model|ChatGPT|tạo sinh|"
                    r"lĩnh vực AI|dự án AI|AI thực tế|AI tools?|công cụ AI|công nghệ AI",
                    local,
                    re.I,
                )
                and "review_tri_tue_nhan_tao_ai" in self.taxonomy.skills
            ):
                candidates.append(
                    (match.start(), match.end(), Alias("review_tri_tue_nhan_tao_ai", match.group()))
                )
        for match in re.finditer(
            r"mạng xã hội|social media(?: platforms)?|các kênh truyền thông", text, re.I
        ):
            prefix = text[max(0, match.start() - 140) : match.start()]
            if "review_su_dung_mang_xa_hoi" in self.taxonomy.skills and re.search(
                r"active user|sử dụng|thành thạo|thông thạo|tìm kiếm|qua các kênh", prefix, re.I
            ):
                candidates.append(
                    (match.start(), match.end(), Alias("review_su_dung_mang_xa_hoi", match.group()))
                )
        unique = {(s, e, a.skill_code): (s, e, a) for s, e, a in candidates}
        return sorted(unique.values(), key=lambda row: (row[0], -row[1], row[2].skill_code))

    def extract(self, text: str | None) -> Extraction:
        original = super().extract(text)
        if text is None or original.status in {"missing_requirements", "unusable_requirements"}:
            return original
        # Only the new automatic layer follows longest explicit concepts. Reviewed
        # owner claims are applied separately by ID + full requirements hash.
        candidates = self._candidates(text)
        marketing_context = has_marketing_context(text)
        spans = [(s, e) for s, e, _ in candidates]
        segments = clauses(text, spans)
        keep: list[Evidence] = []
        for evidence in original.evidence:
            start, end = evidence.start, evidence.end
            if any(
                s <= start
                and end <= e
                and e - s > end - start
                and a.skill_code != evidence.skill_code
                for s, e, a in candidates
            ):
                continue
            skill = self.taxonomy.skills[evidence.skill_code]
            left, right, _ = next(
                (a, b, section) for a, b, section in segments if a <= start and end <= b
            )
            # Certificate, shared-language and explicit owner exceptions already
            # have purpose-built checks in the original matcher.
            special = evidence.rule_id.startswith(
                ("certificate_", "shared_language_name:", "owner_context:")
            )
            if special:
                updated = evidence
            else:
                assessment = assess_proposal(
                    skill.name, text[left:right], text, re.escape(evidence.text)
                )
                # assess_proposal can find another repeated occurrence; use its
                # verified offsets instead of attaching a positive to a negation.
                new_start, new_end = assessment.start, assessment.end
                if new_start < 0:
                    updated = replace(evidence, context="ambiguous", rule_id=assessment.reason)
                else:
                    a, b, _ = next(
                        (a, b, section)
                        for a, b, section in clauses(text, [(new_start, new_end)])
                        if a <= new_start and new_end <= b
                    )
                    updated = replace(
                        evidence,
                        start=new_start,
                        end=new_end,
                        text=text[new_start:new_end],
                        context_start=a,
                        context_end=b,
                        context={
                            "accept": "required",
                            "reject": "mentioned",
                            "unclear": "ambiguous",
                        }[assessment.decision],
                        rule_id="expanded:" + assessment.reason,
                    )
                # Preserve contextual alias safeguards (FAST, AI, short names,
                # platform advertising heads, etc.) from the original matcher.
                if evidence.context == "ambiguous" and evidence.rule_id in {
                    "short_or_ambiguous_alias",
                    "product_context_unclear",
                    "conflicting_assertions",
                }:
                    updated = evidence
            local = text[updated.context_start : updated.context_end]
            before = text[updated.context_start : updated.start]
            after = text[updated.end : updated.context_end]
            if inherited_degree_context(text, updated.start):
                updated = replace(updated, context="mentioned", rule_id="degree_list_continuation")
            if (
                skill.code == "review_mang_may_tinh"
                and updated.text.casefold() == "mạng"
                and (
                    re.match(r"\s+xã hội", after, re.I)
                    or not re.search(
                        r"máy tính|CNTT|\bIT\b|LAN|WAN|router|server|Cisco", local, re.I
                    )
                )
            ):
                updated = replace(
                    updated, context="mentioned", rule_id="network_subject_not_grounded"
                )
            if (
                skill.code == "review_nghiep_vu_ke_toan"
                and re.search(r"(?:có\s+)?(?:bằng|chứng chỉ)\s*[“\"]?\s*$", before, re.I)
                and re.match(r"\s+trưởng", after, re.I)
            ):
                updated = replace(
                    updated, context="required", rule_id="specific_professional_certificate"
                )
            if skill.code == "review_nghiep_vu_ke_toan" and re.search(
                r"công ty dịch vụ\s*$|báo cáo\s*$", before, re.I
            ):
                updated = replace(
                    updated, context="mentioned", rule_id="accounting_object_not_generic_skill"
                )
            if skill.code == "review_kien_thuc_marketing" and re.search(
                r"agency\s*$|lĩnh vực công ty\s*$", before, re.I
            ):
                updated = replace(
                    updated, context="mentioned", rule_id="employer_sector_not_marketing_skill"
                )
            if skill.code == "review_ban_hang_sales" and (
                re.match(r"\s+admin\b", after, re.I)
                or re.search(r"(?:liên quan đến|ghi nhận).{0,30}hoạt động\s*$", before, re.I)
            ):
                updated = replace(
                    updated,
                    context="mentioned",
                    rule_id="sales_administration_or_accounting_context",
                )
            if skill.code in {"review_lap_trinh", "review_lap_trinh_ung_dung"} and re.search(
                r"quản lý dự án|trưởng dự án|đầu ra dự án", before, re.I
            ):
                updated = replace(
                    updated, context="mentioned", rule_id="project_scope_not_coding_capability"
                )
            if (
                skill.code == "review_viet_noi_dung_copywriting"
                and updated.text.casefold() in {"viết tốt", "khả năng viết tốt", "viết lách"}
                and not (
                    marketing_context
                    or re.search(
                        r"văn phong|nội dung|content|biên tập|kịch bản|viết bài", text, re.I
                    )
                )
            ):
                updated = replace(updated, context="ambiguous", rule_id="writing_subject_unclear")
            if re.search(r"quan tâm(?: đến)?\s*$", before, re.I):
                updated = replace(updated, context="mentioned", rule_id="interest_not_capability")
            if skill.code == "content_marketing" and not marketing_context:
                updated = replace(
                    updated, context="mentioned", rule_id="marketing_context_missing_or_degree_only"
                )
            if (
                skill.code == "review_kien_thuc_marketing"
                and re.search(r"(?:trong|cho|phục vụ)\s*$", before, re.I)
                and not re.search(
                    r"(?:kinh nghiệm|kiến thức|hiểu biết|am hiểu)\s*(?:trong|về)?\s*"
                    r"(?:lĩnh vực|vị trí)?\s*$",
                    before,
                    re.I,
                )
            ):
                updated = replace(
                    updated, context="mentioned", rule_id="marketing_work_context_not_skill"
                )
            english_interests = list(
                re.finditer(r"interest(?:ed)?\s+in|passion(?:ate)?\s+(?:for|about)", before, re.I)
            )
            if skill.code == "review_kien_thuc_marketing" and re.search(
                r"(?:bằng cấp|chứng chỉ).{0,50}kiến thức liên quan", before, re.I
            ):
                updated = replace(
                    updated, context="mentioned", rule_id="related_qualification_only"
                )
            if english_interests and not re.search(
                r"knowledge|skills?|experience|proficien|ability|familiar",
                before[english_interests[-1].end() :],
                re.I,
            ):
                updated = replace(updated, context="mentioned", rule_id="interest_not_capability")
            if skill.code == "review_cam" and not re.search(
                r"\bCAD\b|\bCNC\b|gia công|cơ khí|manufactur|Mastercam|PowerMill|\bNX\b",
                local,
                re.I,
            ):
                updated = replace(updated, context="mentioned", rule_id="cam_word_not_technical")
            if skill.code == "review_solid" and re.match(
                r"\s+(?:knowledge|track|experience|understanding|background)\b", after, re.I
            ):
                updated = replace(updated, context="mentioned", rule_id="solid_ordinary_adjective")
            if (
                skill.code in {"review_ngon_ngu_lap_trinh_c", "review_ngon_ngu_lap_trinh_r"}
                and len(updated.text) == 1
                and not re.search(
                    r"lập trình|programming|\.NET|C\+\+|C#|Python|Java|ngôn ngữ|"
                    r"thống kê|statistics|data science",
                    local,
                    re.I,
                )
            ):
                updated = replace(
                    updated, context="ambiguous", rule_id="single_letter_not_grounded"
                )
            if (
                skill.code == "review_amazon_s3"
                and updated.text.casefold() == "s3"
                and not re.search(r"\bAWS\b|Amazon|EC2|RDS|cloud|đám mây", local, re.I)
            ):
                updated = replace(
                    updated, context="ambiguous", rule_id="s3_product_context_unclear"
                )
            if skill.code in {"review_api", "review_firewall"} and re.match(
                r"\s+(?:Gateway|Manager)\b", after, re.I
            ):
                updated = replace(
                    updated, context="mentioned", rule_id="specific_product_not_parent"
                )
            if skill.code == "review_lap_trinh" and (
                re.search(r"ngôn ngữ\s*$|mô hình\s*$", before, re.I)
                or (
                    updated.text.casefold() == "programming"
                    and re.search(r"(?:C#|C\+\+|Java|Python)\s*$", before, re.I)
                )
            ):
                updated = replace(
                    updated, context="mentioned", rule_id="language_or_model_descriptor"
                )
            if skill.code == "review_lan_he_thong_mang" and re.match(r"/WAN\b", after, re.I):
                updated = replace(
                    updated, context="mentioned", rule_id="specific_lan_wan_not_prefix"
                )
            if skill.code in {"review_logistics", "review_xuat_nhap_khau", "review_quang_cao"} and (
                re.search(r"(?:công ty|doanh nghiệp|ngành|lĩnh vực).{0,40}$", before, re.I)
                and not re.search(
                    r"nghiệp vụ|kiến thức|kỹ năng|thực hiện|vận hành", before[-60:], re.I
                )
            ):
                updated = replace(
                    updated, context="mentioned", rule_id="employer_or_project_sector"
                )
            if skill.code in {"review_ban_hang_sales", "review_ban_hang_online"} and re.search(
                r"(?:sản phẩm|video|livestream|marketing trong lĩnh vực)\s*$", before, re.I
            ):
                updated = replace(
                    updated, context="mentioned", rule_id="promotion_purpose_not_sales_skill"
                )
            if skill.code == "review_content" and re.search(r"SEO\s*$", before, re.I):
                updated = replace(updated, context="mentioned", rule_id="specific_content_subject")
            if (
                skill.code == "social_media"
                and updated.text.casefold()
                in {"social media", "mạng xã hội", "mạng xh", "tiktok/reels"}
                and not re.search(
                    r"marketing|tiếp thị|quảng cáo|chiến dịch|truyền thông|social media marketing",
                    local,
                    re.I,
                )
            ):
                updated = replace(updated, context="mentioned", rule_id="social_use_not_marketing")
            if skill.code == "review_su_dung_may_tinh" and re.search(
                r"(?:có|sở hữu|trang bị)\s*$", before, re.I
            ):
                updated = replace(
                    updated, context="mentioned", rule_id="owning_computer_not_capability"
                )
            if (
                skill.code == "illustrator"
                and updated.text.casefold() == "ai"
                and updated.context == "ambiguous"
                and updated.rule_id == "short_or_ambiguous_alias"
                and re.search(r"Photoshop|Figma|Canva|Corel|InDesign|\bPTS\b", local, re.I)
                and re.search(r"[,/]", local)
            ):
                updated = replace(
                    updated, context="required", rule_id="explicit_design_software_list"
                )
            if (
                updated.context == "mentioned"
                and updated.rule_id == "expanded:education_not_capability"
                and re.search(
                    r"(?:tốt nghiệp|hoàn thành)\s+(?:khóa|khoá)(?: học)?\s*(?:về\s+)?$",
                    before,
                    re.I,
                )
                and not re.search(r"sẽ|sau khi|will|không (?:yêu cầu|cần)", before, re.I)
            ):
                updated = replace(
                    updated, context="required", rule_id="specific_vocational_course_to_skill"
                )
            if (
                skill.code == "review_agile"
                and re.search(
                    r"agile.{0,20}(?:mind|think|person|organi[sz]ed|attitude)|nhanh nhẹn",
                    local,
                    re.I,
                )
                and not re.search(r"scrum|methodolog|phương pháp|quy trình", local, re.I)
            ):
                updated = replace(updated, context="mentioned", rule_id="agile_personal_trait")
            if skill.code in {"review_sketch", "review_notion", "review_unity"} and not re.search(
                r"phần mềm|công cụ|software|tools?|sử dụng|thành thạo|biết|experience|proficien|"
                r"game|engine|design|thiết kế",
                local,
                re.I,
            ):
                updated = replace(updated, context="ambiguous", rule_id="ambiguous_product_name")
            keep.append(updated)
        # The owner-approved Content Marketing parent rule is explicitly limited
        # to marketing context inside requirements, never source industry/title.
        if "content_marketing" in self.taxonomy.skills and marketing_context:
            keep.extend(
                e
                for e in self.original.extract(text).evidence
                if e.skill_code == "content_marketing"
            )
            media_codes = {
                "review_viet_noi_dung_copywriting",
                "review_chinh_sua_hinh_anh",
                "review_bien_tap_dung_video",
                "review_quay_phim",
                "review_chup_anh",
                "review_thiet_ke_do_hoa",
                "review_thiet_ke_hinh_anh",
                "review_san_xuat_noi_dung",
                "review_san_xuat_video",
            }
            keep.extend(
                [
                    replace(
                        e, skill_code="content_marketing", rule_id="owner_approved_media_parent"
                    )
                    for e in keep
                    if e.skill_code in media_codes and e.context in self.policy.positive_contexts
                ]
            )
        unique = {(e.skill_code, e.start, e.end, e.context): e for e in keep}
        evidence_rows = tuple(sorted(unique.values(), key=lambda e: (e.start, e.end, e.skill_code)))
        codes = tuple(
            sorted(
                {e.skill_code for e in evidence_rows if e.context in self.policy.positive_contexts}
            )
        )
        reasons = tuple(sorted({e.rule_id for e in evidence_rows if e.context == "ambiguous"}))
        return Extraction(
            "expanded_partial_match"
            if codes and reasons
            else "needs_review"
            if reasons
            else "processed_match"
            if codes
            else "processed_no_match",
            codes,
            evidence_rows,
            reasons,
        )
