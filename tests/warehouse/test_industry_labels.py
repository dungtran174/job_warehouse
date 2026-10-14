from __future__ import annotations

import pytest

from job_warehouse.silver.industry_labels import (
    industry_display_candidate,
    industry_equivalence_key,
)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("IT Phần mềm", "IT phần mềm"),
        ("Kế toán, Kiểm toán", "Kế toán / Kiểm toán"),
        ("Tư vấn/ Chăm sóc khách hàng", "Tư vấn Chăm sóc khách hàng"),
        ("Tư vấn / Chăm sóc khách hàng", "Tư vấn chăm sóc khách hàng"),
        ("Banking", "Ngân hàng"),
        ("E-commerce", "Thương mại điện tử"),
        ("An Ninh / Bảo Vệ", "An ninh - Bảo vệ"),
        ("Dệt may / Da giày", "Dệt may - Da giày"),
        ("Môi trường / Xử lý chất thải", "Môi trường - Xử lý chất thải"),
        ("Ngành nghề khác", "Nghề nghiệp khác"),
        ("Marketing", "Marketing - PR"),
        ("Dịch vụ khách hàng", "Chăm sóc khách hàng"),
        ("Thực tập sinh", "Thực tập"),
        ("Chăm sóc sức khỏe / Y tế", "Y tế - Chăm sóc sức khỏe"),
        ("Y tế / Chăm sóc sức khỏe", "Y tế - Chăm sóc sức khỏe"),
        ("IT Phần mềm", "CNTT - Phần mềm"),
        ("Kế toán / Kiểm toán", "Kế toán - Kiểm toán"),
        ("Bán hàng / Kinh doanh", "Bán hàng - Kinh doanh"),
        ("IT phần cứng/mạng", "IT Phần cứng - Mạng"),
        ("Xuất - Nhập khẩu", "Xuất Nhập Khẩu"),
        ("Giáo dục / Đào tạo", "Giáo dục - Đào tạo"),
        (" An Toàn  Lao Động ", "An toàn lao động"),
        ("Thiết kế đồ hoạ", "Thiết kế đồ họa"),
        ("Nhân sự / Hành chính - Thư ký", "Hành chính - Thư ký / Nhân sự"),
        ("Quản lý điều hành , Sản xuất", "Quản lý điều hành, Sản xuất"),
        ("Kế toán - Kiểm toán / Xây dựng", "Xây dựng / Kiểm toán / Kế toán"),
    ],
)
def test_equivalent_source_labels(left: str, right: str) -> None:
    assert industry_equivalence_key(left) == industry_equivalence_key(right)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("Marketing", "Marketing / Bán hàng - Kinh doanh"),
        ("Nhân viên kinh doanh", "Bán hàng - Kinh doanh"),
        ("Tư vấn chăm sóc khách hàng", "Chăm sóc khách hàng"),
        ("Kế toán, Kiểm toán, Xây dựng", "Kế toán / Kiểm toán / Xây dựng"),
        ("Quản lý chất lượng (QA / QC)", "QC) / Quản lý chất lượng (QA"),
        ("Nghề nghiệp khác", "Chưa xác định"),
        ("Kế toán", "Kế toán / Kiểm toán"),
        ("IT phần mềm", "IT Phần cứng - Mạng"),
        ("Nhân sự", "Nhân sự / Hành chính - Thư ký"),
        ("Giáo dục - Đào tạo", "Giáo dục - Đào tạo / Biên phiên dịch"),
        ("Công nghệ thông tin, Backend Developer", "Backend Developer, Công nghệ thông tin"),
        ("A / A / B", "A / B"),
        ("UI/UX", "UX/UI"),
        ("An toàn lao động", "An toan lao dong"),
        ("Thực tập", "Thực tập / Lao động phổ thông"),
        ("Y tế - Chăm sóc sức khỏe", "Y tế - Dược"),
    ],
)
def test_different_source_labels_remain_distinct(left: str, right: str) -> None:
    assert industry_equivalence_key(left) != industry_equivalence_key(right)


def test_display_preserves_scope_and_canonical_spelling() -> None:
    assert industry_display_candidate("CNTT - Phần mềm") == "IT phần mềm"
    assert industry_display_candidate("IT Phần mềm / Xây dựng") == "IT phần mềm / Xây dựng"
    assert industry_display_candidate("Nhân sự / Nhân sự") == "Nhân sự / Nhân sự"
    assert industry_display_candidate("Nhân viên kinh doanh") == "Nhân viên kinh doanh"
    assert industry_display_candidate("Kế toán, Kiểm toán, Xây dựng").startswith(
        "Kế toán, Kiểm toán,"
    )
