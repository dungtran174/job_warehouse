"""Normalize source industry labels without inferring occupations from job text.

Only typography, explicit equivalent aliases and ordering of slash-separated
source categories are normalized. Comma-separated taxonomy paths retain order.
"""

from __future__ import annotations

import re
import unicodedata

INDUSTRY_LABEL_VERSION = "source-label-v2"

# Owner-approved whole labels: a comma elsewhere may be a taxonomy boundary.
EXACT_LABEL_ALIASES: tuple[tuple[str, str], ...] = (
    ("Kế toán, Kiểm toán", "Kế toán / Kiểm toán"),
    ("Tư vấn/ Chăm sóc khách hàng", "Tư vấn chăm sóc khách hàng"),
    ("Tư vấn Chăm sóc khách hàng", "Tư vấn chăm sóc khách hàng"),
)

# Closed aliases: do not add broader/narrower categories or occupational guesses.
EQUIVALENT_ALIASES: tuple[tuple[str, str], ...] = (
    ("Banking", "Ngân hàng"),
    ("E-commerce", "Thương mại điện tử"),
    ("An Ninh / Bảo Vệ", "An ninh - Bảo vệ"),
    ("Dệt may / Da giày", "Dệt may - Da giày"),
    ("Môi trường / Xử lý chất thải", "Môi trường - Xử lý chất thải"),
    ("Ngành nghề khác", "Nghề nghiệp khác"),
    # Explicit owner decision: use Marketing for Marketing - PR as well.
    ("Marketing - PR", "Marketing"),
    ("Dịch vụ khách hàng", "Chăm sóc khách hàng"),
    ("Thực tập sinh", "Thực tập"),
    ("Chăm sóc sức khỏe / Y tế", "Y tế - Chăm sóc sức khỏe"),
    ("Y tế / Chăm sóc sức khỏe", "Y tế - Chăm sóc sức khỏe"),
    ("Kế toán - Kiểm toán", "Kế toán / Kiểm toán"),
    ("Bán hàng / Kinh doanh", "Bán hàng - Kinh doanh"),
    ("CNTT - Phần mềm", "IT phần mềm"),
    ("IT phần cứng/mạng", "IT Phần cứng - Mạng"),
    ("Xuất - Nhập khẩu", "Xuất Nhập Khẩu"),
    ("Giáo dục / Đào tạo", "Giáo dục - Đào tạo"),
)


def _typography(value: str) -> str:
    text = unicodedata.normalize("NFC", value)
    text = re.sub(r"[–—−]", "-", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s*;\s*", "; ", text)
    # A specific Vietnamese orthographic variant, not general accent removal.
    text = re.sub(r"\bhoạ\b", "họa", text, flags=re.IGNORECASE)
    return text


def industry_display_candidate(value: str) -> str:
    """Apply explicit spelling aliases while retaining category order."""
    text = _typography(value)
    for source, target in EXACT_LABEL_ALIASES:
        parts = [re.escape(part.strip()) for part in source.split("/")]
        if re.fullmatch(r"\s*/\s*".join(parts), text, flags=re.IGNORECASE):
            text = target
            break
    for source, target in EQUIVALENT_ALIASES:
        # Whitespace beside a slash is merely formatting in these closed aliases.
        parts = [re.escape(part.strip()) for part in source.split("/")]
        pattern = r"\s*/\s*".join(parts)
        text = re.sub(r"(?<!\w)" + pattern + r"(?!\w)", target, text, flags=re.IGNORECASE)
    text = re.sub(r"\bIT phần mềm\b", "IT phần mềm", text, flags=re.IGNORECASE)
    text = re.sub(r"\bCông nghệ thông tin\b", "Công nghệ thông tin", text, flags=re.IGNORECASE)
    text = re.sub(r"\bAn toàn lao động\b", "An toàn lao động", text, flags=re.IGNORECASE)
    return text


def industry_equivalence_key(value: str) -> tuple[str, ...]:
    """Return a grouping key; no fuzzy matching or interpretation of job text.

    Slash components are sorted as a multiset, retaining repeated components.
    Internal unspaced slashes (UI/UX, PR/Quảng cáo) and ordered comma paths
    are not interpreted as unordered categories.
    """
    text = industry_display_candidate(value).casefold()
    if any(char in text for char in ",;()[]"):
        return ("ordered", re.sub(r"\s*/\s*", "/", text))
    components = re.split(r"\s+/\s*|\s*/\s+", text)
    return ("categories", *sorted(part.strip() for part in components))
