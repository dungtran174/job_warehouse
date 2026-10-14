"""Occupation enrichment must preserve job grain and frozen core provenance."""

import pytest

from job_warehouse.silver.core_runner import configuration_hashes as core_hashes
from job_warehouse.silver.enrichment import assets
from job_warehouse.silver.enrichment.locations import classify_location, places
from job_warehouse.silver.enrichment.occupations import aliases, classify_occupation, families
from job_warehouse.silver.enrichment.scope import scope_reason
from job_warehouse.silver.text import normalize_text


@pytest.mark.parametrize(
    ("title", "source", "primary"),
    [
        ("Sales Manager (ERP)", "IT phần mềm", "SALES"),
        ("Software Tester (Automation & Manual)", "QA-QC/ Thẩm định/ Giám định", "IT_DATA"),
        ("Senior Frontend Developer", "Nhân viên kinh doanh", "IT_DATA"),
        ("Nhân Viên Kế Toán", "Chăm sóc khách hàng", "ACCOUNTING"),
        ("Kế Toán Bán Hàng", "Bán hàng - Kinh doanh", "ACCOUNTING"),
        ("Sales Accountant", "IT Phần mềm", "ACCOUNTING"),
        ("Nhân Viên HSE (ATLĐ)", "Chưa xác định", "SAFETY_ENVIRONMENT"),
        ("Kỹ Sư Môi Trường", "Khoa học - Kỹ thuật", "SAFETY_ENVIRONMENT"),
        ("Kỹ Sư Nông Học", "Nghề nghiệp khác", "AGRICULTURE"),
        ("Kỹ Sư Công Nghệ Thực Phẩm", "Nghề nghiệp khác", "FOOD_TECH"),
        ("Bác sĩ", "Y tế - Dược", "HEALTHCARE"),
        ("Tư vấn tuyển sinh - Telesales", "Giáo dục - Đào tạo", "SALES"),
        ("Trình dược viên", "Bán hàng - Kinh doanh", None),
        ("Giáo Viên Tiếng Anh", "Biên phiên dịch", "EDUCATION"),
        ("Phiên Dịch Tiếng Nhật", "Giáo dục - Đào tạo", "LANGUAGE"),
        ("Lái xe giao hàng", "Nghề nghiệp khác", "LOGISTICS"),
        ("Software Architect", "Kiến trúc - Thiết kế nội thất", "IT_DATA"),
        ("Kỹ Sư Điện", "Nghề nghiệp khác", "ENGINEERING"),
        ("Công Nhân Vận Hành Máy", "Nghề nghiệp khác", "MANUFACTURING"),
        ("Nhân Viên Bảo Vệ", "Chưa xác định", "SECURITY"),
        ("Nhân Viên Kinh Doanh – Môi Trường Trẻ", "Bán hàng", "SALES"),
        ("Sales Engineer", "IT Phần mềm", "SALES"),
        ("Chuyên viên", "Kế toán / Kiểm toán", None),
        ("Quản lý", "Nghề nghiệp khác", None),
        ("Tư Vấn Tuyển Sinh", "Giáo dục - Đào tạo / Chăm sóc khách hàng", None),
        ("Tư Vấn Tài Chính", "Tài chính - Đầu tư - Chứng Khoán", None),
        ("Trình Dược Viên", "Y tế - Dược", None),
        ("Giám Đốc Chi Nhánh", "Bất động sản", None),
        ("Thiết kế kết cấu / tài chính / trưởng nhóm bán hàng", "Xây dựng", None),
        ("Các vị trí: Developer và kế toán", "IT Phần mềm", None),
    ],
)
def test_function_not_product_domain_or_first_source_label(title, source, primary):
    assert classify_occupation(title, source).primary == primary


def test_override_has_audit_and_domains_are_separate():
    result = classify_occupation("Sales Manager (ERP)", "IT phần mềm")
    assert result.primary == "SALES"
    assert result.domains == ("SOFTWARE",)
    assert result.source_candidates == ("IT_DATA",)
    assert "title_overrides_source_candidates" in result.flags
    assert result.method == "title_rule"


@pytest.mark.parametrize(
    ("title", "source", "primary"),
    [
        ("Nhân Viên Thiết Kế", "Thiết kế - Mỹ thuật", None),
        ("Nhân Viên Kỹ Thuật", "Khoa học - Kỹ thuật", None),
        ("Kế Toán Kho - Thủ Kho", "Kế toán / Kiểm toán", None),
        ("Nhân Viên Thiết Kế M&E", "Khoa học - Kỹ thuật", "ENGINEERING"),
        ("Nhân Viên Kỹ Thuật IT", "Chưa xác định", "IT_DATA"),
        ("Lập Trình Viên Chuyên Servo", "IT Phần mềm", "ENGINEERING"),
        ("Nhân Viên Vận Hành Và Lập Trình Máy Phay CNC", "IT Phần mềm", "MANUFACTURING"),
        ("Bác Sĩ Thú Y Lĩnh Vực Nuôi Gà", "Chưa xác định", "HEALTHCARE"),
        ("Y Tá Thú Y", "Chưa xác định", "HEALTHCARE"),
        ("Nhân Viên Kinh Doanh Thuốc Thú Y", "Y tế - Dược", "SALES"),
        ("Tuyển Dụng Nhân Sự Địa Bàn", "Nhân sự", None),
        ("Nhân Viên Trợ Lý Văn Phòng", "Luật - Pháp Lý - Tuân thủ", "HR_ADMIN"),
        ("Nhân Viên Hỗ Trợ Thanh Toán", "Luật - Pháp Lý - Tuân thủ", None),
        ("Giao Dịch Viên FPT Telecom", "Chăm sóc khách hàng", None),
        ("Trợ Lý Phiên Dịch Tiếng Anh", "Hành chính - Thư ký", None),
        ("Quản Lý Sản Xuất", "Thông tin - Truyền thông - Quảng cáo", None),
        ("Kỹ Sư An Toàn Thông Tin Mạng", "Chưa xác định", "IT_DATA"),
        ("Nhân Viên Kỹ Thuật Máy Tính - Camera An Ninh", "Khoa học - Kỹ thuật", "IT_DATA"),
        ("Nhân Viên QA Hệ Thống", "IT Phần mềm", None),
        ("Thợ Làm Thi Công Lắp Đặt Biển Quảng Cáo", "Khoa học - Kỹ thuật", None),
    ],
)
def test_round1_errors_are_tuning_regressions_for_confirmed_v2_policy(title, source, primary):
    assert classify_occupation(title, source).primary == primary


def test_source_candidate_and_animal_domain_do_not_become_invented_primary():
    result = classify_occupation("Chuyên viên", "Kế toán / Kiểm toán")
    assert result.primary is None
    assert result.source_candidates == ("ACCOUNTING",)
    assert result.status == "needs_review"
    assert "ANIMAL_HEALTH" in classify_occupation("Bác Sĩ Thú Y", "Y tế - Dược").domains


@pytest.mark.parametrize(
    ("title", "primary"),
    [
        ("Tư Vấn Giờ Hành Chính", None),
        ("Nhân Viên Văn Phòng - Làm Hành Chính", None),
        ("Nhân Viên Hành Chính", "HR_ADMIN"),
        ("Nhân Viên Product Owner", None),
        ("Nhân Viên Hỗ Trợ Thanh Toán", None),
        ("Nhân Viên Hỗ Trợ Thanh Toán Khoản Vay", "FINANCE"),
        ("Tổng Đài Viên Nhắc Phí Sau Vay", "FINANCE"),
        ("Tổng Đài Viên Nhắc Phí Qua Điện Thoại", None),
        ("Nhân Viên Telemarketing Tổng Đài Sự Kiện", "MARKETING_MEDIA"),
        ("Nhân Viên Phát Triển Thị Trường (Kỹ Sư Nông Nghiệp)", "SALES"),
        ("Content Creator", "MARKETING_MEDIA"),
        ("Chuyên Viên Quay Dựng Video", "MARKETING_MEDIA"),
        ("Nhân Viên Video Editor", "MARKETING_MEDIA"),
        ("Nhân Viên Thiết Kế Truyền Thông", "DESIGN"),
        ("Chuyên Viên Mua Sắm Marketing", "LOGISTICS"),
        ("Senior Cost Analyst (Purchasing Finance Business Partner)", "FINANCE"),
        ("Trợ Lý Giám Đốc (Biết Lái Xe)", "HR_ADMIN"),
        ("Nhân Viên Tư Vấn Bằng Lái Xe", None),
        ("Công Nhân Cầu", None),
        ("Công Nhân Nuôi Ong", "AGRICULTURE"),
        ("Công Nhân Kỹ Thuật Khảo Sát Công Trình", "CONSTRUCTION"),
        ("Nhân Viên IT - Thiết Kế Website", None),
        ("Nhân Viên Truyền Thông Nội Bộ Và Tuyển Dụng", None),
        ("Nhân Viên Pháp Lý Kỹ Thuật", None),
        ("Nhân Viên DVKH - Thu Ngân", None),
    ],
)
def test_round2_exposures_are_tuning_only_for_new_policy(title, primary):
    assert classify_occupation(title, "Chưa xác định").primary == primary


@pytest.mark.parametrize(
    ("title", "primary"),
    [
        ("Nhân Viên Phục Vụ / Phụ Bếp", "HOSPITALITY"),
        ("Nhân Viên Phụ Kho Kiêm Lái Xe", "LOGISTICS"),
        ("KCS Và Kỹ Thuật Sơn", "MANUFACTURING"),
    ],
)
def test_multiple_roles_within_one_confirmed_family_keep_posting_grain(title, primary):
    result = classify_occupation(title, None)
    assert result.primary == primary
    assert "multiple_roles_same_family" in result.flags


def test_multiple_functions_or_unresolved_listing_still_need_review():
    assert classify_occupation("Kiến Trúc Sư / Họa Sỹ", None).primary is None
    assert classify_occupation("Kế Toán / Bảo Vệ", None).primary is None
    assert classify_occupation("Các vị trí: Developer / Nhân viên khác", None).primary is None
    assert classify_occupation("Kế Toán Tổng Hợp - Bán Hàng", None).primary is None


@pytest.mark.parametrize(
    ("raw", "expected", "status"),
    [
        ("Hà Nội; Hồ Chí Minh", {"HA_NOI", "HO_CHI_MINH"}, "mapped_multiple"),
        ("Tân Bình, Hồ Chí Minh", {"HO_CHI_MINH"}, "mapped_single"),
        ("Ha Noi 107 Nguyễn Phong Sắc, Hà Nội Ha Noi", {"HA_NOI"}, "mapped_single"),
        ("Ha Noi 12 Lê Duẩn, Đà Nẵng Ha Noi", {"DA_NANG"}, "mapped_single"),
        ("Hồ Chí Minh; HCM; TP.HCM", {"HO_CHI_MINH"}, "mapped_single"),
        ("Bà Rịa Vũng Tàu", {"BA_RIA_VUNG_TAU"}, "mapped_single"),
        ("Thừa Thiên Huế", {"THUA_THIEN_HUE"}, "mapped_single"),
        ("Huế", {"HUE"}, "mapped_single"),
        ("Huế, Thừa Thiên Huế", {"THUA_THIEN_HUE"}, "mapped_single"),
        ("Toàn quốc (Hà Nội, Hồ Chí Minh)", {"HA_NOI", "HO_CHI_MINH"}, "nationwide"),
        ("Remote tại Hà Nội", {"HA_NOI"}, "remote"),
        ("Làm việc tại nhà", set(), "remote"),
        ("Nhật Bản", set(), "foreign"),
        ("Singapore; Hà Nội", {"HA_NOI"}, "mapped_multiple"),
        ("Hà Nội; Atlantis", {"HA_NOI"}, "mapped_single"),
        ("Trụ sở chính Hà Nội và 25 chi nhánh toàn quốc", {"HA_NOI"}, "nationwide"),
        (None, set(), "unknown"),
        ("Không", set(), "unknown"),
        ("Quận 1", {"HO_CHI_MINH"}, "mapped_single"),
        ("Đường Hồ Chí Minh, Thanh Hóa", {"THANH_HOA"}, "mapped_single"),
    ],
)
def test_location_complete_set_source_names_and_ambiguity(raw, expected, status):
    result = classify_location(raw)
    assert set(result.places) == expected
    assert result.status == status
    assert len(result.places) == len(set(result.places))
    text = normalize_text(raw, short=True).clean or ""
    assert all(text[e.start : e.end] == e.text for e in result.evidence)


def test_taxonomy_is_semantic_not_count_driven():
    assert "AGRICULTURE" in families() and "FOOD_TECH" in families()
    assert "SAFETY_ENVIRONMENT" in families() and "AGRI_ENV" not in families()
    assert "bất động sản" not in aliases()
    assert places()["BA_RIA_VUNG_TAU"] != places()["HO_CHI_MINH"]


@pytest.mark.parametrize(
    "text",
    [
        "Thủ Đức, Hồ Chí Minh",
        "Hoài Đức, Hà Nội",
        "Thành phố Hà Nội",
        "Thành phố Hồ Chí Minh",
    ],
)
def test_city_prefix_and_district_duc_are_not_roads_or_germany(text):
    result = classify_location(text)
    assert result.status == "mapped_single"
    assert not result.foreign
    assert "street_name_not_place" not in result.flags


def test_real_street_name_is_not_province_or_country():
    result = classify_location("Đường Hồ Chí Minh, Thanh Hóa")
    assert result.places == ("THANH_HOA",)
    assert classify_location("Đức").foreign == ("GERMANY",)
    assert classify_location("Philippines").foreign == ("PHILIPPINES",)
    assert classify_location("Foreign").foreign == ("UNSPECIFIED",)
    assert classify_location("Foreign Thành phố Hà Nội Foreign").status == "mapped_single"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("9 Điện Biên Phủ, TP Hồ Chí Minh", ("HO_CHI_MINH",)),
        ("Nguỵ Như Kon Tum, Hà Nội", ("HA_NOI",)),
        ("Phường Hiệp Bình Phước, TP Hồ Chí Minh", ("HO_CHI_MINH",)),
        ("P. Phú Thọ Hoà", ()),
        ("Nguyễn Thái Bình", ()),
        ("37 Hậu Giang, TP HCM", ("HO_CHI_MINH",)),
        ("Tòa nhà Hòa Bình Green", ()),
        ("63 Nguyen Hue Boulevard", ()),
        ("Thành phố Điện Biên Phủ", ("DIEN_BIEN",)),
    ],
)
def test_street_ward_and_building_tokens_are_not_provinces(text, expected):
    assert classify_location(text).places == expected


def test_online_building_name_is_not_work_arrangement():
    result = classify_location("Tầng 9, tòa nhà VTC Online, Hà Nội")
    assert result.status == "mapped_single"
    assert not result.remote
    assert classify_location("Online | Hà Nội").remote
    assert classify_location("Làm việc online").remote


def test_country_in_industrial_park_or_town_name_is_not_foreign_workplace():
    assert not classify_location("KCN Việt Nam-Singapore, Bình Dương").foreign
    assert not classify_location("Thị trấn Quán Lào").foreign
    assert classify_location("Singapore").foreign == ("SINGAPORE",)


def test_exact_repeated_address_can_use_its_complete_copy_without_address_output():
    text = "Tầng 16, tòa nhà X, số 18 Tam Trinh | Tầng 16, tòa nhà X, số 18 Tam Trinh, Hà Nội"
    result = classify_location(text)
    assert result.status == "mapped_single"
    assert result.places == ("HA_NOI",)
    assert "province_inferred_from_repeated_address" in result.flags
    assert len(result.address_links) == 1
    link = result.address_links[0]
    assert (
        text[link.complete_start : link.complete_end]
        .strip()
        .casefold()
        .startswith(text[link.partial_start : link.partial_end].strip().casefold() + ",")
    )
    assert link.place == "HA_NOI"
    assert not hasattr(link, "text")


@pytest.mark.parametrize(
    "text",
    [
        "18 Tam Trinh | 19 Tam Trinh, Hà Nội",
        "18 Tam Trinh | 18 Tam Trinh, Hà Nội | 18 Tam Trinh, Hồ Chí Minh",
        "Tòa nhà X | Tòa nhà X, Hà Nội",
        "Tầng 2, tòa nhà X | Tầng 2, tòa nhà X, Hà Nội",
        "18 Tam Trinh | 18 Tam Trinh, Hà Nội, Singapore",
        "18 Tam Trinh | 18 Tam Trinh, Hà Nội, Hồ Chí Minh",
    ],
)
def test_repeat_inference_never_transfers_between_different_or_ambiguous_addresses(text):
    result = classify_location(text)
    assert not result.address_links
    assert result.status in {"mapped_single", "mapped_multiple"}
    assert "province_list_incomplete" in result.flags


def test_national_country_name_is_unmapped_without_nationwide_claim():
    for text in ["Việt Nam", "Vietnam"]:
        result = classify_location(text)
        assert result.status == "unmapped"
        assert not result.places and not result.nationwide
    assert classify_location("Địa chỉ: tỉnh BRVT").places == ("BA_RIA_VUNG_TAU",)
    assert classify_location("24 Test Street, HCMC").places == ("HO_CHI_MINH",)


@pytest.mark.parametrize(
    ("title", "primary"),
    [
        ("Nhân Viên CSKH - Không Sales", "CUSTOMER_SERVICE"),
        ("Chăm Sóc Khách Hàng - Không Sales", "CUSTOMER_SERVICE"),
        ("Sale Admin / Kế Toán", None),
        ("Thiết Kế Đồ Họa / Thiết Kế Nội Thất", None),
        ("Nhân Viên Tư Vấn - Chăm Sóc Khách Hàng", "CUSTOMER_SERVICE"),
        ("Dược Sĩ Bán Thuốc / Nhân Viên Bán Thuốc", "HEALTHCARE"),
        ("Nhân Viên Bán Thuốc", "SALES"),
        ("Dược Sĩ Kinh Doanh Thuốc", "SALES"),
        ("Nhân Viên Tuyển Dụng Và Đào Tạo", "HR_ADMIN"),
        ("Nhân Viên Đào Tạo", None),
        ("Nhân Viên Business Analyst", None),
        ("Kỹ Sư IT Nhà Máy Sản Xuất", "IT_DATA"),
        ("Trợ Lý Trưởng Phòng Marketing", "HR_ADMIN"),
        ("Teacher Recruitment Executive", "HR_ADMIN"),
    ],
)
def test_round3_exposures_and_owner_Q18_Q20_are_tuning(title, primary):
    assert classify_occupation(title, "Chưa xác định").primary == primary


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Phường 5 Ho Chi Minh City", ("HO_CHI_MINH",)),
        ("Quận Cẩm Lệ - Đà Nẵng", ("DA_NANG",)),
        ("Xã Đạ Ròn Lam Dong", ("LAM_DONG",)),
        ("Phường Hòa Phú Binh Duong", ("BINH_DUONG",)),
        ("Hiệp Bình Phước, Thủ Đức", ("HO_CHI_MINH",)),
        ("Ấp Thanh Hóa - Huyện Trảng Bom - Đồng Nai", ("DONG_NAI",)),
        ("Đắk Lak", ("DAK_LAK",)),
        ("P. An Khánh, Q2", ("HO_CHI_MINH",)),
    ],
)
def test_admin_context_does_not_swallow_a_following_explicit_province(text, expected):
    assert classify_location(text).places == expected


def test_country_company_landmark_and_multiple_offices_stay_distinct():
    assert not classify_location("KCN Vietnam – Singapore II, Bình Dương").foreign
    assert classify_location("Nationwide Tập đoàn Long Đô Singapore - Bavet, Cambodia").foreign == (
        "CAMBODIA",
    )
    assert classify_location("Phía sau bến xe Đà Nẵng").status == "unmapped"
    assert classify_location("Văn phòng HCM: 1 Test Road | Văn phòng HN: 2 Test Road").status == (
        "mapped_multiple"
    )
    assert classify_location("Quận 3 Ho Chi Minh City Foreign").status == "mapped_single"


@pytest.mark.parametrize(
    "text",
    [
        "192 Ngô Gia Tự, P4 | 192 Ngô Gia Tự, Phường 4, Quận 10, TP.HCM",
        "619 Nguyễn Thị Thập, Phường Tân Hưng | "
        "Tầng 5, Số 619 Nguyễn Thị Thập, Khu phố 1, Phường Tân Hưng, TP.HCM",
        "Số nhà 11, ngõ 64 Sài Đồng | Số 11 ngõ 64 phố Sài Đồng, Phường Sài Đồng, Hà Nội",
        "Số 31 Đường B4, An Lợi Đông | Số 31, Đường số B4, Phường An Lợi Đông, TP Hồ Chí Minh",
        "Tầng 8, tòa nhà King Building Số 7 Chùa Bộc | "
        "Tầng 8, tòa nhà King Building số 7 Chùa Bộc, Hà Nội",
    ],
)
def test_structured_repeat_identity_is_bounded_and_evidenced(text):
    result = classify_location(text)
    assert result.status == "mapped_single"
    assert result.address_links


@pytest.mark.parametrize(
    "text",
    [
        "192 Ngô Gia Tự, P4 | 192 Ngô Gia Tự, Phường 5, TP.HCM",
        "192 Ngô Gia Tự, P4 | 193 Ngô Gia Tự, Phường 4, TP.HCM",
        "192 Ngô Gia Tự, P4 | 192 Trần Hưng Đạo, Phường 4, TP.HCM",
        "Sky Garden 3 - Nguyễn Văn Linh | Sky Garden 3 - Nguyễn Văn Linh, TP.HCM",
        "192 Ngô Gia Tự | 192 Ngô Gia Tự, Hà Nội | 192 Ngô Gia Tự, Hồ Chí Minh",
        "Số 31 Đường B4, An Lợi Đông | Số 31 Đường B4, Phường An Lợi Tây, TP.HCM",
    ],
)
def test_structured_repeat_does_not_infer_on_conflicting_or_non_address_text(text):
    assert not classify_location(text).address_links


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Phủ Lý", "HA_NAM"),
        ("Long Biên", "HA_NOI"),
        ("Quận Nam Từ Liêm", "HA_NOI"),
        ("Thủ Đức", "HO_CHI_MINH"),
    ],
)
def test_lower_localities_only_produce_province_codes_with_evidence(text, expected):
    result = classify_location(text)
    assert result.places == (expected,)
    assert result.status == "mapped_single"
    assert "province_inferred_from_locality_parent" in result.flags
    assert any(e.rule_id.startswith("parent.") and e.text in text for e in result.evidence)


def test_parent_lookup_does_not_convert_explicit_modern_source_name():
    result = classify_location("Phủ Lý, Ninh Bình")
    assert result.places == ("NINH_BINH",)
    assert "legacy_parent_not_applied_to_explicit_place" in result.flags
    assert classify_location("Đường Long Biên, Hải Phòng").places == ("HAI_PHONG",)
    assert classify_location("Sơn Tây").places == ()
    assert classify_location("Quận 2, Singapore").places == ()


@pytest.mark.parametrize(
    "rows",
    [
        [{"rule_id": "same", "value": "SALES", "pattern": "sales", "exclude": ""}] * 2,
        [{"rule_id": "bad", "value": "NO_SUCH_FAMILY", "pattern": "sales", "exclude": ""}],
        [{"rule_id": "empty", "value": "SALES", "pattern": ".*", "exclude": ""}],
    ],
)
def test_invalid_rule_assets_fail_instead_of_silently_classifying(monkeypatch, rows):
    monkeypatch.setattr(assets, "read_csv", lambda _: rows)
    with pytest.raises(ValueError):
        assets.load_rules("fixture.csv", {"SALES"})


@pytest.mark.parametrize(
    ("count", "threshold", "expected"),
    [
        (499, 500, "below_family_threshold"),
        (500, 500, "eligible"),
        (999, 1000, "below_family_threshold"),
        (1000, 1000, "eligible"),
    ],
)
def test_scope_boundary_after_semantic_grouping(count, threshold, expected):
    assert scope_reason("SALES", {"SALES": count}, threshold) == expected


def test_scope_never_promotes_unknown_large_source_label():
    assert scope_reason(None, {"Chưa xác định": 25637}) == "occupation_unresolved"


def test_scope_requires_valid_population():
    with pytest.raises(ValueError):
        scope_reason("SALES", {})
    with pytest.raises(ValueError):
        scope_reason("SALES", {"SALES": -1})
    with pytest.raises(ValueError):
        scope_reason(None, {}, 0)


def test_new_enrichment_assets_are_outside_core_inventory():
    # This checks the asset boundary, rather than pinning development hashes.
    assert not any("enrichment" in key for key in core_hashes())
    assert "scope.py" not in core_hashes()


@pytest.mark.parametrize(
    "text",
    [
        "Làm việc tại Nhà máy, tỉnh Long An",
        "Làm việc tại Nhà sách Kim Đồng, TP Huế",
        "Làm việc tại nhà thuốc, Hà Nội",
    ],
)
def test_named_workplace_after_nha_does_not_mean_remote(text):
    assert not classify_location(text).remote
    assert classify_location("Làm online tại nhà, tuyển toàn quốc").remote


@pytest.mark.parametrize(
    "text",
    [
        "Tòa nhà Việt Úc, số 2 Trung Hành",
        "Mỹ Úc Cơ sở 2: 134 Liên Khu",
        "KCN ViệtNam Singapore Phường An Phú",
        "Tp. Thủ Đức. Lĩnh vực hoạt động: Mỹ phẩm Hàn Quốc",
    ],
)
def test_country_words_in_buildings_and_product_metadata_are_not_foreign(text):
    assert not classify_location(text).foreign


@pytest.mark.parametrize(
    "text",
    [
        "136 Cầu Giấy | 148 La Thành, Hà Nội",
        "Dự án 265 Cầu Giấy | Quận Long Biên, Hà Nội",
    ],
)
def test_locality_parent_does_not_use_a_house_number_as_district_evidence(text):
    result = classify_location(text)
    assert result.status == "mapped_single"
    assert result.places == ("HA_NOI",)
    assert not result.address_links
    assert "province_list_incomplete" in result.flags


@pytest.mark.parametrize(
    "text",
    [
        "Số 31 Đường B4, An Lợi Đông | Số 31 Đường B4, Phường An Lợi Đông Mới, TP.HCM",
        "192 Ngô Gia Tự, Phường 4 | 192 Ngô Gia Tự, Phường 4, Phường 5, TP.HCM",
    ],
)
def test_repeated_address_checks_exact_unit_names_and_donor_contradictions(text):
    assert not classify_location(text).address_links
    assert classify_location(
        "179 Đào Duy Anh, P9 | 179 Đào Duy Anh, Phường 09, TP.HCM"
    ).address_links


@pytest.mark.parametrize(
    ("title", "primary"),
    [
        ("Kế Toán Viên Kiêm Hành Chính", None),
        ("Kiến Trúc Sư / Họa Viên", None),
        ("Customer Service & Technical Support Executive", None),
        ("Nhân Viên Chứng Từ, Chăm Sóc Khách Hàng", None),
        ("Nhân Viên Chăm Sóc Khách Hàng (Hỗ Trợ Tài Xế App Taxi)", "CUSTOMER_SERVICE"),
        ("Nhân Viên Lập Trình/Vận Hành Gia Công Máy Tiện CNC", "MANUFACTURING"),
        ("Kế Toán Kho Sản Xuất", "ACCOUNTING"),
        ("Chuyên Viên Helpdesk", None),
        ("IT Helpdesk", "IT_DATA"),
        ("Nhân Viên Kỹ Thuật Máy Tính Và Kho", None),
        ("Nhân Viên Phiên Dịch (Phụ Việc Tổng Vụ)", None),
        ("Biên Phiên Dịch / 中文办公文员", None),
        ("Nhân Viên Xử Lý Nợ Pháp Lý", None),
        ("Compliance Manager", None),
        ("Nhân Viên Kỹ Thuật Sản Xuất Nông Nghiệp", "AGRICULTURE"),
        ("Nhân Viên Kỹ Thuật Thuốc Bảo Vệ Thực Vật", "AGRICULTURE"),
        ("Nhân Viên Marketing (Designer)", None),
        ("Chuyên Viên Truyền Thông Nội Bộ Và Đào Tạo", None),
        ("Cửa Hàng Trưởng Nhà Hàng", "HOSPITALITY"),
        ("Admin Điều Phối Vận Tải", "LOGISTICS"),
        ("Admin Chăm Sóc Khách Hàng", "CUSTOMER_SERVICE"),
        ("Admin Và Chăm Sóc Khách Hàng", None),
        ("Dược Sĩ Kho", "HEALTHCARE"),
        ("Kho Dược Sĩ", "HEALTHCARE"),
    ],
)
def test_round4_exposed_cases_are_tuning_regressions_not_new_holdout(title, primary):
    assert classify_occupation(title, "Chưa xác định").primary == primary


def test_verified_numbered_district_maps_without_guessing_address_identity():
    result = classify_location("284 Lý Thường Kiệt, Phường 14 | 284 Lý Thường Kiệt, Quận 10")
    assert result.status == "mapped_single"
    assert result.places == ("HO_CHI_MINH",)
    assert not result.address_links


def test_neighbouring_provinces_and_offices_keep_known_provinces_with_quality_flags():
    partial = classify_location("Thanh Hóa và các tỉnh lân cận")
    assert partial.status == "mapped_single"
    assert partial.places == ("THANH_HOA",)
    assert "province_list_incomplete" in partial.flags
    assert (
        classify_location("Văn phòng công ty – Thanh Hóa | Văn phòng nhà máy – Thanh Hóa").status
        == "mapped_single"
    )


def test_unsupported_admin_marker_cannot_prove_address_identity():
    result = classify_location(
        "Số 7-9, Đường D5, Phường Hiệp Hòa | Số 7-9, Đường D5, Phương Trấn Biên, Tỉnh Đồng Nai"
    )
    assert result.status == "mapped_single"
    assert not result.address_links


def test_plain_compact_daklak_alias_remains_source_name():
    assert classify_location("219 Ngô Quyền, Daklak").places == ("DAK_LAK",)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("VSIP Bắc Ninh", "BAC_NINH"),
        ("Big C Đồng Nai", "DONG_NAI"),
        ("Becamex Bình Dương", "BINH_DUONG"),
        ("CHUNG CƯ LINH TÂY TOWER THỦ ĐỨC", "HO_CHI_MINH"),
    ],
)
def test_owner_allows_source_place_suffix_in_location_facility_name(text, expected):
    result = classify_location(text)
    assert result.places == (expected,)
    assert result.status == "mapped_single"
    assert "province_mentioned_in_facility_name" in result.flags
    assert not classify_location("Tòa nhà Hòa Bình Green").places


def test_different_wards_with_independent_same_province_do_not_block_province_grain():
    result = classify_location(
        "176 Nguyễn Văn Giáp, Cầu Diễn, Nam Từ Liêm | 176 Nguyễn Văn Giáp, Phường Từ Liêm, Hà Nội"
    )
    assert result.places == ("HA_NOI",)
    assert result.status == "mapped_single"
    assert not result.address_links


def test_researched_addresses_independently_supply_only_province_with_evidence():
    result = classify_location("135 Cầu Giấy | 148 đường La Thành")
    assert result.places == ("HA_NOI",)
    assert result.status == "mapped_single"
    assert not result.address_links
    assert "province_inferred_from_verified_address_reference" in result.flags
    assert {e.rule_id for e in result.evidence} >= {
        "address_ref.hanoi.135_caugiay",
        "address_ref.hanoi.148_lathanh",
    }
    assert classify_location("136 Cầu Giấy").status == "unmapped"
    assert not classify_location("135 Cầu Giấy, Singapore").places
    assert classify_location("135 Cầu Giấy, Hồ Chí Minh").places == ("HO_CHI_MINH",)


@pytest.mark.parametrize(
    ("title", "primary"),
    [
        ("Kỹ Sư QS - Kế Toán Nội Bộ", None),
        ("Nhân Viên Triển Khai Phần Mềm Kế Toán", "IT_DATA"),
        ("Chuyên Viên Thủ Tục Kiêm Chăm Sóc Khách Hàng", None),
        ("Nhân Viên Đóng Hàng Và Chăm Sóc Khách Hàng", None),
        ("Trưởng Nhóm Phát Triển Sản Phẩm (Lương Giảng Dạy Giảng Viên)", None),
        ("Kỹ Thuật Viên Điện Lạnh Và Đào Tạo Học Viên Điện Lạnh", None),
        ("Nhân Viên Kỹ Thuật Điện Tử / Tự Động Hóa / Máy Tính", None),
        ("Dược Sĩ Livestream Mỹ Phẩm", None),
        ("Admin & Operation Coordinator", None),
        ("QA / Kiểm Chất Lượng (Phiên Dịch Tiếng Anh)", None),
        ("Chuyên Viên Điều Phối Hành Chính & Phiên Dịch Trung Việt", None),
        ("Nhân Viên Pháp Chế, Kế Hoạch", None),
        ("Trưởng Phòng HCNS (Kiêm Pháp Lý)", None),
        ("Nhân Viên Tư Vấn Pháp Lý - Thu Hồi Tín Dụng", None),
        ("Trợ Lý Hành Chính - Pháp Lý", None),
        ("Trợ Lý Pháp Lý - Nhân Sự", None),
        ("Trưởng Phòng Dự Án Và Pháp Lý", None),
        ("Giao Hàng Và Làm Cafe", None),
        ("Video Producer - Nhân Viên Sản Xuất", "MARKETING_MEDIA"),
        ("Nhân Viên Phục Vu / Thu Ngân", None),
        ("Kỹ Sư Cơ Điện (Ưu Tiên Có Chứng Chỉ An Toàn Lao Động)", "ENGINEERING"),
        ("Nhân Viên Giám Sát An Toàn Sản Phẩm", None),
        ("Nhân Viên Bán Hàng, Đóng Gói, Sắp Xếp Hàng", None),
        ("Chuyên Viên Pháp Lý Dự Án", "LEGAL"),
    ],
)
def test_round5_multiple_functions_and_qualifications_are_tuning_only(title, primary):
    assert classify_occupation(title, None).primary == primary


@pytest.mark.parametrize(
    ("title", "primary"),
    [
        ("Kỹ Thuật Viên - Kỹ Sư Xây Dựng", "CONSTRUCTION"),
        ("Điều Dưỡng / Nữ Hộ Sinh / Kỹ Thuật Viên", "HEALTHCARE"),
        ("Điều Dưỡng-Kỹ Thuật Viên", "HEALTHCARE"),
        ("Kỹ Sư Xây Dựng / QS / QC _ Dự Án", "CONSTRUCTION"),
    ],
)
def test_owner_shared_specialization_in_title_is_evidenced(title, primary):
    result = classify_occupation(title, None)
    assert result.primary == primary
    assert "shared_specialization_from_title" in result.flags
    assert any(e.rule_id == "context.shared_title_specialization" for e in result.evidence)


@pytest.mark.parametrize(
    ("title", "primary"),
    [
        ("Kỹ Thuật Viên Máy Tính - Mạng - Camera", "IT_DATA"),
        ("Kỹ Thuật Camera", None),
        ("Bảo Trì Cáp Mạng", None),
        ("Nhân Viên Kế Toán / Thống Kê Phân Xưởng", None),
        ("Nhân Viên Kế Toán, Bán Hàng", None),
        ("Nhân Viên Kế Toán & Bán Hàng", None),
        ("Nhân Viên Thiết Kế Đồ Họa - Media", None),
        ("Giáo Viên Giám Thị / Quản Nhiệm Nội Trú", "EDUCATION"),
        ("Nhân Viên Vệ Sinh - Housekeeping Tại Trung Tâm Thương Mại", "CLEANING"),
        ("Nhân Viên Buồng Phòng Khách Sạn", "CLEANING"),
        ("Nhân Viên Phục Vụ - Tạp Vụ - Phụ Bếp", None),
        ("Interpreter & Live Operations Assistant", None),
        ("Phiên Dịch Tiếng Hàn - Kiêm Nhân Sự", None),
        ("Nhân Viên THN Pháp Lý", None),
        ("Nhân Viên Kho Vận + Khai Thác", None),
        ("Quản Lý Dự Án Chi Nhánh (Logistics)", None),
        ("Nhân Viên Môi Trường (Công Ty Sản Xuất Sản Phẩm Đóng Hộp)", "SAFETY_ENVIRONMENT"),
        ("Biên Tập Viên / Thực Tập Sinh Youtube", None),
        ("Nhân Viên Tư Vấn Qua Điện Thoại / Telemarketing", None),
        ("Nhân Viên Y Tế Kiêm Nhiệm Nhân Sự & HSE", None),
        ("Kỹ Sư Môi Trường SQE", None),
        ("Người Huấn Luyện An Toàn Lao Động", "EDUCATION"),
        ("Nhân Viên Bán Hàng - Tư Vấn Nông Nghiệp", None),
        ("Nhân Viên Kinh Doanh Dịch Vụ Vệ Sinh Công Nghiệp", "SALES"),
        ("Giảng Viên Đào Tạo Vệ Sinh Công Nghiệp", "EDUCATION"),
        ("Kỹ Thuật Viên Cơ Khí - Điều Dưỡng", None),
        ("Kỹ Thuật Viên", None),
    ],
)
def test_v7_context_function_domain_boundaries_and_cleaning(title, primary):
    assert classify_occupation(title, "Chưa xác định").primary == primary


def test_family_names_are_compound_umbrella_labels():
    assert len(families()) == 23
    assert families()["CLEANING"] == "Dịch vụ vệ sinh"
    assert all("/" not in value and "," not in value for value in families().values())


@pytest.mark.parametrize(
    "title",
    [
        "Tuyển Bếp, Tạp Vụ, Phục Vụ",
        "Phục Vụ / Tạp Vụ",
    ],
)
def test_cross_family_bare_role_lists_do_not_become_cleaning_only(title):
    result = classify_occupation(title, "Khách sạn - Nhà hàng - Du lịch")
    assert result.primary is None
    assert result.status == "multiple_or_ambiguous"
    assert {"CLEANING", "HOSPITALITY"} <= set(result.candidates)
    for evidence in result.evidence:
        if evidence.field == "job_title_clean":
            assert title[evidence.start : evidence.end] == evidence.text


@pytest.mark.parametrize(
    ("title", "primary"),
    [
        ("Nhân Viên Vệ Sinh Tổ Yến", None),
        ("Thực Tập Sinh: Kỹ Thuật; Lễ Tân; Buồng Phòng; Nhà Hàng", None),
        ("Tạp Vụ / Kỹ Thuật", None),
        ("Nhân Viên Vệ Sinh Thiết Bị Bếp, Nhà Hàng", "CLEANING"),
        ("Nhân Viên Vệ Sinh Thiết Bị Bếp", "CLEANING"),
        ("Tuyển Bếp, Phục Vụ", "HOSPITALITY"),
    ],
)
def test_bare_role_extraction_keeps_product_context_and_unclear_tasks(title, primary):
    assert classify_occupation(title, None).primary == primary


@pytest.mark.parametrize(
    "title",
    [
        "Nhân Viên Bảo Trì",
        "Nhân Viên Kỹ Thuật Bảo Trì (Lương Trên 10 Triệu)",
        "Nhân Viên Bảo Trì (Làm Việc Tại Nhà Máy Sản Xuất)",
        "Bảo Trì Tại Nhà Máy",
        "Maintenance Technician",
        "Nhân Viên Kỹ Thuật Triển Khai & Bảo Trì Mạng Quận 12",
    ],
)
def test_owner_generic_maintenance_is_review_even_with_equipment_source_label(title):
    result = classify_occupation(title, "Cơ khí - Ô tô - Tự động hóa")
    assert result.primary is None
    assert result.status == "needs_review"
    assert "maintenance_object_not_resolved" in result.flags
    assert "ENGINEERING" in result.candidates
    assert any(e.rule_id == "context.unspecified_maintenance_object" for e in result.evidence)


@pytest.mark.parametrize(
    ("title", "primary"),
    [
        ("Nhân Viên Bảo Trì Máy Sản Xuất", "ENGINEERING"),
        ("Nhân Viên Bảo Trì Thiết Bị", "ENGINEERING"),
        ("Nhân Viên Bảo Trì Điện Lạnh Nhà Máy", "ENGINEERING"),
        ("Mechanical Maintenance Technician", "ENGINEERING"),
        ("Nhân Viên Bảo Trì / Kỹ Sư Cơ Điện", "ENGINEERING"),
        ("Kỹ Sư Môi Trường Vận Hành Và Bảo Trì", "SAFETY_ENVIRONMENT"),
        ("Kỹ Thuật Viên Máy Tính / Bảo Trì", "IT_DATA"),
    ],
)
def test_specific_equipment_or_shared_title_specialty_qualifies_maintenance(title, primary):
    result = classify_occupation(title, None)
    assert result.primary == primary
    assert result.status == "assigned"


def test_owner_engineer_with_payment_document_duties_remains_review():
    result = classify_occupation("Kỹ Sư Cơ Điện (Cán Bộ Làm Hồ Sơ Thanh Toán)", "Kế toán")
    assert result.primary is None
    assert result.status == "needs_review"
    assert "role_context_not_clear" in result.flags


@pytest.mark.parametrize(
    ("title", "primary"),
    [
        ("Kế Toán Nội Bộ - Hành Chính Không Yêu Cầu Kinh Nghiệm", None),
        ("Tuyển Dụng CSKH - Nữ Quầy - Lễ Tân - Phục Vụ Nam", None),
        ("Graphic Designer / Video And Images Creator (Junior / Senior)", None),
        ("Nhân Viên Admin Kho Vận Tại Nhà Bè", "LOGISTICS"),
        ("Chuyên Viên Quản Lý Tín Dụng Khách Hàng Pháp Lý", "FINANCE"),
        ("Công Nhân Vận Hành Cẩu Xuất", None),
        ("Nhân Viên SEO Web / Quản Trị Web Tại Hải Phòng", None),
        ("Quản Lý Cửa Hàng Kiêm Kho - Hóc Môn", None),
        ("Giám Sát Cơ Điện (M&E), Giám Sát An Toàn (HSE)", None),
        ("Nhân Viên An Ninh Phòng Cháy Chữa Cháy", None),
        ("Nhân Viên An Ninh Có Chứng Chỉ Phòng Cháy Chữa Cháy", "SECURITY"),
        ("Kỹ Sư Nông Nghiệp / Nhân Viên Thị Trường", None),
        ("TUYỂN DỤNG KẾ TOÁN TỔNG HỢP – CÔNG TY SẢN XUẤT", "ACCOUNTING"),
        ("Recruitment Of Accounting Staff", "ACCOUNTING"),
        ("Chăm Sóc Khách Hàng - Chủ Yếu Làm Giờ Hành Chính", "CUSTOMER_SERVICE"),
    ],
)
def test_v8_function_context_and_multiple_roles_are_tuning_examples(title, primary):
    assert classify_occupation(title, None).primary == primary


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Hà Nội; Bình Dương", ("BINH_DUONG", "HA_NOI")),
        ("Duy Tiên, Hà Nam", ("HA_NAM",)),
        ("Thanh Xuân, Hà Nội", ("HA_NOI",)),
        ("Quận 1, Hồ Chí Minh", ("HO_CHI_MINH",)),
        ("Tân Bình, Hồ Chí Minh", ("HO_CHI_MINH",)),
        (
            "Hung Yen Đường Cách Mạng Tháng 8, Thị Trấn Diêm Điền, "
            "Huyện Thái Thụy, Thái Bình. Hung Yen",
            ("THAI_BINH",),
        ),
        (
            "Ho Chi Minh City 135A/3 Khu phố Bình Đường 3, Phường An Bình, "
            "Thị Xã Dĩ An, Tỉnh Bình Dương Ho Chi Minh City",
            ("BINH_DUONG",),
        ),
        (
            "Đường Nguyễn Chí Thanh | 048 Đường Nguyễn Huệ, Phường Lào Cai, Tỉnh Lào Cai",
            ("LAO_CAI",),
        ),
        ("Cầu Giấy Công Trình ở Hà Nội và các tỉnh lân cận Miền Bắc Ha Noi", ("HA_NOI",)),
        (
            "Văn phòng HCM: 40 Đường 62, Tp. Thủ Đức, Tp. Hồ Chí Minh "
            "- Văn phòng HN: Quận Long Biên, Hà Nội",
            ("HA_NOI", "HO_CHI_MINH"),
        ),
    ],
)
def test_owner_q32_q34_source_examples_are_tuning_regressions(raw, expected):
    result = classify_location(raw)
    assert result.places == expected
    assert result.status == ("mapped_single" if len(expected) == 1 else "mapped_multiple")
    text = normalize_text(raw, short=True).clean
    assert all(text[e.start : e.end] == e.text for e in result.evidence)


def test_outer_wrapper_selection_preserves_conflicting_evidence_and_provenance():
    result = classify_location("Ha Noi 12 Lê Duẩn, Đà Nẵng Ha Noi")
    assert result.places == ("DA_NANG",)
    assert {"HA_NOI", "DA_NANG"} <= {e.value for e in result.evidence}
    assert "province_selected_from_full_address_over_outer_label" in result.flags
    assert "outer_place_wrapper_conflicts_with_inner_address" in result.flags
    multiple = classify_location("Ha Noi 12 Lê Duẩn, Đà Nẵng | 13 Lê Duẩn, Hồ Chí Minh Ha Noi")
    assert set(multiple.places) == {"HA_NOI", "DA_NANG", "HO_CHI_MINH"}
    assert "province_selected_from_full_address_over_outer_label" not in multiple.flags


def test_partial_province_list_never_transfers_to_unresolved_other_address():
    result = classify_location("Hà Nội | 123 Đường Chưa Rõ")
    assert result.places == ("HA_NOI",)
    assert result.status == "mapped_single"
    assert "province_list_incomplete" in result.flags
    assert not result.address_links
    assert not any(e.text == "123 Đường Chưa Rõ" for e in result.evidence)


@pytest.mark.parametrize(
    "raw",
    [
        "Quận 13",
        "Phường 10",
        "Đường Phú Nhuận",
        "Phường Phú Nhuận",
        "Tân Phú",
        "Tân Bình",
        "Quận 1, Singapore",
    ],
)
def test_parent_aliases_do_not_guess_wards_roads_or_other_country(raw):
    assert not classify_location(raw).places


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("198 Hoàng Văn Thụ Phường 9 Phú Nhuận", "HO_CHI_MINH"),
        ("Sailing Tower, 111A Pasteur, Ben Nghe Ward, District 1", "HO_CHI_MINH"),
        ("Quận Bình Thạnh", "HO_CHI_MINH"),
        ("Quận Đống Đa", "HA_NOI"),
        ("Quận Ngũ Hành Sơn", "DA_NANG"),
        ("Thành phố Dĩ An", "BINH_DUONG"),
        ("Quận Hải An", "HAI_PHONG"),
        ("Thành phố Biên Hòa", "DONG_NAI"),
    ],
)
def test_verified_parent_and_address_references_produce_only_provinces(raw, expected):
    result = classify_location(raw)
    assert result.places == (expected,)
    assert result.status == "mapped_single"
    assert any(e.rule_id.startswith(("parent.", "address_ref.")) for e in result.evidence)
    assert classify_location(raw + ", Ninh Bình").places == ("NINH_BINH",)


def test_foreign_wrapper_yields_to_domestic_province_but_preserves_country_addresses():
    result = classify_location("Foreign Tầng 3, đường Mễ Trì, Nam Từ Liêm, Hà Nội Foreign")
    assert result.places == ("HA_NOI",)
    assert result.status == "mapped_single"
    assert not result.foreign
    assert "domestic_province_selected_over_generic_foreign_wrapper" in result.flags
    assert any(e.rule_id == "qualifier.foreign" for e in result.evidence)
    concrete = classify_location("Singapore | Hà Nội")
    assert concrete.foreign == ("SINGAPORE",)
    assert concrete.status == "mapped_multiple"
    separate = classify_location("Foreign | Hà Nội")
    assert separate.foreign == ("UNSPECIFIED",)
    assert separate.status == "mapped_multiple"
    assert classify_location("Làm việc nước ngoài, Hà Nội").status == "mapped_multiple"


@pytest.mark.parametrize(
    "raw",
    [
        "A Lưới Toàn bộ khu vực Thừa Thiên Huế Hue",
        "TP Huế | Thừa Thiên Huế",
        "Hà Nội; Huế; Thừa Thiên Huế",
    ],
)
def test_hue_source_names_collapse_only_when_old_province_is_also_mentioned(raw):
    result = classify_location(raw)
    assert "THUA_THIEN_HUE" in result.places
    assert "HUE" not in result.places
    assert "hue_alias_collapsed_to_source_province" in result.flags
    assert classify_location("Huế").places == ("HUE",)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("180 Trường Chinh, Khương Thượng, Đống Đa", "HA_NOI"),
        ("Lầu 4, Cao ốc H3, 384 Hoàng Diệu, phường 6", "HO_CHI_MINH"),
        ("125 Dương Quảng Hàm, phường Quan Hoa", "HA_NOI"),
        ("Cánh C Tầng 3, Tòa Nhà Trung Yên Plaza", "HA_NOI"),
        ("ấp 4 xã Tóc Tiên, thị xã Phú Mỹ, tỉnh Bà Rịa – Vũng Tàu.", "BA_RIA_VUNG_TAU"),
        ("Thuận An, Binh Dương", "BINH_DUONG"),
        ("20 Cộng Hoà, P.12, Q.Tân Bình", "HO_CHI_MINH"),
        ("44 Phan Khiêm Ích, Tan Phu District", None),
    ],
)
def test_researched_address_and_finite_format_aliases(raw, expected):
    result = classify_location(raw)
    assert result.places == ((expected,) if expected else ())
    assert classify_location("181 Trường Chinh").places == ()
    assert classify_location("126 Dương Quảng Hàm").places == ()


@pytest.mark.parametrize("raw", ["District Tan Phu", "District Binh Tan", "Tan Phu District"])
def test_english_district_does_not_disambiguate_vietnamese_quan_and_huyen(raw):
    assert not classify_location(raw).places


@pytest.mark.parametrize(
    ("raw", "expected_provinces", "expected_countries"),
    [
        ("Hà Đông Lào (nước ngoài), Hà Nội Ha Noi", ("HA_NOI",), ("LAOS",)),
        ("Hồ Chí Minh: Tân Bình, Hà Nội, Nước Ngoài", ("HA_NOI", "HO_CHI_MINH"), ("UNSPECIFIED",)),
        (
            "Hà Nội: FPT Building, 17 Duy Tân Str., Cầu Giấy District, Hanoi. "
            "Hồ Chí Minh: F-Town 3, 3 Võ Chí Công, Phường Long Thạnh Mỹ, TP. Thủ Đức. "
            "Đà Nẵng: Tòa Nhà FPT Complex, Đường Nam Kỳ Khởi Nghĩa, "
            "Phường Hoà Hải, Quận Ngũ Hành Sơn, TP.Đà Nẵng. Nước Ngoài.",
            ("DA_NANG", "HA_NOI", "HO_CHI_MINH"),
            ("UNSPECIFIED",),
        ),
        ("Singapore; Hà Nội", ("HA_NOI",), ("SINGAPORE",)),
    ],
)
def test_q37_mixed_locations_keep_vietnamese_provinces_and_foreign_metadata_separate(
    raw, expected_provinces, expected_countries
):
    result = classify_location(raw)
    assert result.places == expected_provinces
    assert result.foreign == expected_countries
    assert result.status == "mapped_multiple"
    assert "domestic_and_foreign_locations_mentioned" in result.flags
    assert not set(result.places).intersection(result.foreign)
    text = normalize_text(raw, short=True).clean
    assert all(text[e.start : e.end] == e.text for e in result.evidence)


def test_q37_preserves_mode_priority_and_foreign_only_or_country_only_records():
    remote = classify_location("Remote tại Hà Nội, Singapore")
    assert remote.status == "remote"
    assert remote.places == ("HA_NOI",)
    assert remote.foreign == ("SINGAPORE",)
    assert classify_location("Foreign").status == "foreign"
    country = classify_location("Việt Nam")
    assert country.status == "unmapped"
    assert not country.places and not country.foreign and not country.nationwide


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("kho 2A - 429/6 đường Song Hành Hà Nội, Quận Thủ Đức, TP.HCM", ("HO_CHI_MINH",)),
        (
            "Tầng 5-6, Tòa nhà số 324 Đà Nẵng, Phường Đông Hải | "
            "Số 324 đường Đà Nẵng, Quận Hải An, TP Hải Phòng",
            ("HAI_PHONG",),
        ),
        ("Tòa nhà Vicem Comatce - số 61 đường Nguỵ Như Kon Tum, Thanh Xuân, Hà Nội", ("HA_NOI",)),
        (
            "Thôn Quảng Huế, X. Đại An, H. Đại Lộc, T. Quảng Nam | Hồ Chí Minh",
            ("HO_CHI_MINH", "QUANG_NAM"),
        ),
        ("Ha Noi Số 71 lô 3/97 Bạch Đằng, Hạ Lý, Hồng Bàng, Hải Phòng Ha Noi", ("HAI_PHONG",)),
        ("Bac Giang 15, Lê Thánh Tôn, P. Bến Nghé, Quận 1, TP. HCM Bac Giang", ("HO_CHI_MINH",)),
        ("Hung Yen Tầng 3 tòa Symphony - Chu Huy Mân, Long Biên, Hà Nội Hung Yen", ("HA_NOI",)),
        ("Ho Chi Minh City KCN LOTECO- TP BIÊN HÒA, TỈNH ĐỒNG NAI Ho Chi Minh City", ("DONG_NAI",)),
        ("Binh Duong 321 QL 1A, Phường An Phú Đông, Q.12, tp.HCM Binh Duong", ("HO_CHI_MINH",)),
    ],
)
def test_round06_street_compounds_and_clear_wrapper_addresses_are_tuning_examples(raw, expected):
    result = classify_location(raw)
    assert result.places == expected
    text = normalize_text(raw, short=True).clean
    assert all(text[e.start : e.end] == e.text for e in result.evidence)


def test_wrapper_resolution_requires_one_clear_address_not_just_province_mentions():
    assert set(classify_location("Ha Noi Hồ Chí Minh Ha Noi").places) == {"HA_NOI", "HO_CHI_MINH"}
    result = classify_location("Ha Noi Số 15, Lê Duẩn, Đà Nẵng | Kho số 16, Hà Nội Ha Noi")
    assert set(result.places) == {"HA_NOI", "DA_NANG"}
    assert "province_selected_from_full_address_over_outer_label" not in result.flags


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Tòa tháp Hòa Bình, 106 Hoàng Quốc Việt, Q. Cầu Giấy", "HA_NOI"),
        ("Coopmart Hoà Bình, Tân Bình, TpHCM", "HO_CHI_MINH"),
        ("Coopmart Hoà Bình, Tân Bình, Hồ Chí Minh", "HO_CHI_MINH"),
    ],
)
def test_facility_brand_does_not_add_province_when_address_has_independent_parent(raw, expected):
    result = classify_location(raw)
    assert result.places == (expected,)
    assert "facility_name_province_overridden_by_address" in result.flags
    assert any(e.rule_id.startswith("facility_name.") for e in result.evidence)
    assert classify_location("VSIP Bắc Ninh").places == ("BAC_NINH",)
    assert set(classify_location(raw + " | Hòa Bình").places) == {expected, "HOA_BINH"}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("466 TRẦN VĂN GIÀU P TÂN TẠO QUÂN BÌNH TÂN", "HO_CHI_MINH"),
        ("1525/32 đường 3/2, P16, Qq11", "HO_CHI_MINH"),
        ("K55 ngu hanh son, p my an, q ngu hanh son", "DA_NANG"),
        ("Ấp 1, TP Biên Hoà", "DONG_NAI"),
        ("q cau giay", "HA_NOI"),
        ("SỐ 8 QUANG TRUNG, HÀ ĐÔNG", "HA_NOI"),
        ("28 Vương Thừa Vũ - Khương Trung - Thanh Xuân", "HA_NOI"),
        ("Tầng 8 Tháp C Hồ Gươm Plaza 102 Trần Phú Hà Đông", "HA_NOI"),
        ("Vinhomes Green Bay số 7 Đại lộ Thăng Long, Mễ Trì", "HA_NOI"),
    ],
)
def test_bounded_owner_confirmed_spelling_and_contextual_parent_variants(raw, expected):
    result = classify_location(raw)
    assert result.places == (expected,)
    text = normalize_text(raw, short=True).clean
    assert all(text[e.start : e.end] == e.text for e in result.evidence)
    assert classify_location(raw + ", Ninh Bình").places == ("NINH_BINH",)


@pytest.mark.parametrize(
    "raw",
    ["Qq11", "QUÂN BÌNH TÂN", "Thanh Xuân", "Hà Đông", "Đường Thanh Xuân", "Tân Bình"],
)
def test_contextual_parent_and_marker_typos_do_not_geocode_bare_or_road_names(raw):
    assert not classify_location(raw).places


def test_address_facility_lookup_requires_exact_house_street_reference():
    assert not classify_location("Hồ Gươm Plaza 103 Trần Phú").places
    assert not classify_location("Vinhomes Green Bay số 8 Đại lộ Thăng Long").places
    assert not classify_location("12 đường Song Hanh Ha Noi").places
    assert not classify_location("Thôn Quang Hue").places


def test_brand_override_does_not_borrow_province_from_another_office_in_the_same_component():
    result = classify_location("Văn phòng 1: VSIP Bắc Ninh, Văn phòng 2: số 10, phố A, Hà Nội")
    assert result.places == ("BAC_NINH", "HA_NOI")
    assert "facility_name_province_overridden_by_address" not in result.flags


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "Lô F2, Đường số 7, KCN Hòa Bình, Nhị Thành | Lô F2 Đường số 7 Khu "
            "công nghiệp Hòa Bình, Xã Thủ Thừa, Tỉnh Tây Ninh ( Long An cũ )",
            ("TAY_NINH",),
        ),
        (
            "Quang Nam Tòa nhà Annie.193 đường Thanh Thủy . Phường Thuận Phước . "
            "Quận Hải Châu . Tp. Đà Nẵng Quang Nam",
            ("DA_NANG",),
        ),
        (
            "Son La Tầng 22 - Toà Nhà Intracom - P.Phúc Diễn - Q. Bắc Từ Liêm - Hà Nội Son La",
            ("HA_NOI",),
        ),
        (
            "KCN Hòa Bình, Nhị Thành | Lô A8, Đường số 2, Khu công nghiệp Hòa "
            "Bình, Xã Thủ Thừa, Tỉnh Tây Ninh, Việt Nam",
            ("TAY_NINH",),
        ),
        (
            "Long An Lô B10-11-12/II Đường số 5-KCN Vĩnh Lộc -P Bình Hưng Hòa B- Q "
            "Bình Tân-TP HCM Long An",
            ("HO_CHI_MINH",),
        ),
        (
            "Phòng 502, tòa nhà Hòa Bình, 431 Tam Trinh | Tầng 05 tòa nhà Hòa Bình "
            ", khu đô thị mới Vĩnh Hoàng , Hoàng Mai, Hà nội",
            ("HA_NOI",),
        ),
        (
            "Quận 7 Tòa nhà Thuận Hải, Lô Vb.20a2, Đường 24, KCX Tân Thuận Ho Chi "
            "Minh City Gò Dầu Khu công nghiệp Phước Đông Tay Ninh",
            ("HO_CHI_MINH", "TAY_NINH"),
        ),
        (
            "Lô C II-2, đường ven biển Cảnh Dương, Khu công nghiệp và Khu phi thuế "
            "quan Sài Gòn - Chân Mây | Lô C II-2, đường ven biển Cảnh Dương, Khu "
            "công nghiệp và Khu phi thuế quan Sài Gòn - Chân Mây, Xã Lộc Vĩnh, "
            "Huyện Phú Lộc, Tỉnh Thừa Thiên Huế, Việt Nam",
            ("THUA_THIEN_HUE",),
        ),
        (
            "Lô C1, Đường số 8, Khu CN Hoà Bình, Nhị Thành | Lô C1 đường số 8, Khu "
            "công nghiệp Hòa Bình, Xã Nhị Thành, Huyện Thủ Thừa, Tỉnh Long An, "
            "Việt Nam",
            ("LONG_AN",),
        ),
        (
            "Lô C1A KCN Hòa Bình | Lô C1A, Khu Công Nghiệp Hòa Bình - Phường Lê "
            "Lợi - Thành phố Kon Tum - Kon Tum.",
            ("KON_TUM",),
        ),
        (
            "Ha Noi Tầng 3- B2 - Hòa Bình Green city- 505 Minh Khai, P Vĩnh Tuy, "
            "Hai Bà Trưng, Hà Nội Ha Noi",
            ("HA_NOI",),
        ),
        (
            "Số 1A, đường D3, KP Bình Dương, Phường Long Bình Tân | Số 1A, đường "
            "D3, KP Bình Dương, Phường Long Bình Tân, Thành phố Biên Hoà, Tỉnh "
            "Đồng Nai, Việt Nam",
            ("DONG_NAI",),
        ),
        ("Nghe An Nhà vườn 23 khu đô thị mới Trung Văn Nam Từ Liêm HN Nghe An", ("HA_NOI",)),
    ],
)
def test_round07_tuning_and_confirmed_q41_q42(raw, expected):
    result = classify_location(raw)
    assert result.places == expected
    text = normalize_text(raw, short=True).clean
    assert all(text[e.start : e.end] == e.text for e in result.evidence)


def test_repeated_brand_suppression_does_not_claim_same_address_or_remove_explicit_other_place():
    result = classify_location("KCN Hòa Bình | Khu công nghiệp Hòa Bình, tỉnh Tây Ninh")
    assert result.places == ("TAY_NINH",)
    assert not result.address_links
    assert "repeated_facility_name_not_additional_province" in result.flags
    assert set(
        classify_location(
            "KCN Hòa Bình, tỉnh Hòa Bình | Khu công nghiệp Hòa Bình, tỉnh Tây Ninh"
        ).places
    ) == {"HOA_BINH", "TAY_NINH"}
    assert set(classify_location("VSIP Bắc Ninh | Tòa nhà Hòa Bình, Hà Nội").places) == {
        "BAC_NINH",
        "HA_NOI",
    }


def test_explicit_old_name_is_evidence_and_independent_old_province_stays_in_labels():
    result = classify_location("Tỉnh Tây Ninh (Long An cũ)")
    assert result.places == ("TAY_NINH",)
    assert any(
        e.rule_id.startswith("historical_name.") and e.value == "LONG_AN" for e in result.evidence
    )
    assert classify_location("Tây Ninh; Long An").places == ("LONG_AN", "TAY_NINH")
    assert classify_location("Tây Ninh (Long An cũ) | Tỉnh Long An").places == (
        "LONG_AN",
        "TAY_NINH",
    )
    assert classify_location("Tỉnh Long An").places == ("LONG_AN",)
    assert classify_location("Sài Gòn - Chân Mây").places == ("HO_CHI_MINH",)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "KCN Đình Trám Bắc Giang, Tp. Bắc Ninh, KCN Yên Phong - Bắc Ninh. | "
            "153/18 Nguyễn Văn Hưởng, Phường Thảo Điền, Thành phố Thủ Đức, Thành "
            "phố Hồ Chí Minh, Việt Nam",
            ("BAC_GIANG", "BAC_NINH", "HO_CHI_MINH"),
        ),
        (
            "Tòa tháp Hòa Bình, 106 Hoàng Quốc Việt, P. Nghĩa Đô | Tòa nhà Lottery "
            "Tower, 77 Trần Nhân Tôn, Phường 9 | Số 0114, Chung cư Phúc Đạt, Đường "
            "D2, Tổ 57, Khu phố 6, Phường Phú Lợi | Tầng 11 tòa tháp VP Hòa Bình, "
            "106 Hoàng Quốc Việt, Phường Nghĩa Đô, Quận Cầu Giấy, Hà Nội",
            ("HA_NOI",),
        ),
        (
            "Tòa nhà OCT, KĐT Handi Resco, Phạm Văn Đồng, Bắc Từ Liêm, Hà Nội (đối "
            "diện Công viên Hòa Bình) | P901, Tầng 9 Tòa nhà Sky City Tower A, Số "
            "88 Láng Hạ, Phường Láng Hạ, Quận Đống đa, Hà Nội",
            ("HA_NOI",),
        ),
        (
            "214 Tân Hương, Tân Phú, TP.HCM | 683A Âu Cơ, Tân Phú, TP.HCM | 81 Đại "
            "lộ Bình Dương, Phú Thọ, Thủ Dầu Một, Bình Dương | 111-113-115 Đường "
            "10, Khu dân cư Mỹ Phước 1, Phước Hòa, Bến Cát, Bình Dương | 604 CMT8, "
            "Thủ Dầu Một, Bình Dương | Tầng 6, số 49 Thái Hà - Phường Trung Liệt - "
            "Quận Đống đa - Hà Nội.",
            ("BINH_DUONG", "HA_NOI", "HO_CHI_MINH"),
        ),
        (
            "Hoa Binh VP công ty: Lô 58 BT4 x2 KĐT Bắc Linh Đàm - Hoàng Mai - Hà Nội Hoa Binh",
            ("HA_NOI",),
        ),
        (
            "A54 khu dân cư Thới An, đường Lê Thị Riêng - Phường Thới An | Nguyễn "
            "Thị Thập | Hậu Giang, phường 6 | Sư Vạn Hạnh | Bến Vân Đồn, phường 1 "
            "| A54 Khu dân cư Thới An, đường Lê Thị Riêng, phường Thới An quận 12",
            ("HO_CHI_MINH",),
        ),
        (
            "TTC PLAZA TÂY NINH – 217-219 đường 30/04, Phường Tân Ninh, Tỉnh Tây "
            "Ninh | Lô TM, Trung tâm VHTTDL TP Bắc Giang, đường Hoàng Văn Thụ, Bắc "
            "Giang, Bắc Ninh (Bắc Giang cũ) | 469 Nguyễn Hữu Thọ, Quận 7, TP Hồ "
            "Chí Minh",
            ("BAC_NINH", "HO_CHI_MINH", "TAY_NINH"),
        ),
        (
            "Kim Bảng Lô CN1 - CCN Lê Hồ - Lê Hồ - Ninh Bình (Hà Nam cũ) Ha Nam",
            ("NINH_BINH",),
        ),
        (
            "Dĩ An Số 3 đường số 1, KCN Sóng Thần, phường Dĩ An, Tp. Hồ Chí Minh "
            "(Bình Dương cũ) Binh Duong",
            ("HO_CHI_MINH",),
        ),
        (
            "Bắc Giang Lô TM, Trung tâm VHTTDL TP Bắc Giang, đường Hoàng Văn Thụ, "
            "Bắc Giang, Bắc Ninh (Bắc Giang cũ) Bac Giang Tây Ninh TTC PLAZA TÂY "
            "NINH – 217-219 đường 30/04, Phường Tân Ninh, Tỉnh Tây Ninh Tay Ninh "
            "Ba Đình 54 Liễu Giai, Phường Cống Vị, Quận Ba Đình Ha Noi Tây Hồ 683 "
            "Lạc Long Quân, Phường Phú Thượng Ha Noi Quận 7 469 Nguyễn Hữu Thọ, "
            "Phường Tân Hưng, Quận 7 Ho Chi Minh City",
            ("BAC_NINH", "HA_NOI", "HO_CHI_MINH", "TAY_NINH"),
        ),
        (
            "Thuận An Ô 34&36, Lô DC36, Đường D33, KDC Việt Sing, P.An Phú,Tp.HCM "
            "(Bình Dương cũ) Binh Duong",
            ("HO_CHI_MINH",),
        ),
        (
            "Phú Quốc Bến Tràm, Phú Quốc, An Giang Kien Giang Bác Ái Bác Ái, Khánh "
            "Hòa (Ninh Thuận cũ) Ninh Thuan Vĩnh Cửu Thủy điện Trị An Dong Nai Kỳ "
            "Sơn Thủy điện Nam Neun 1, Huyện Nọng Hét, tỉnh Xiêng Khoảng, Lào "
            "(Cách cửa khẩu Nậm Cắn Nghệ An 40km) Nghe An Quy Nhơn Số 8 Biên "
            "Cương, Quy Nhơn, Gia Lai Binh Dinh",
            ("AN_GIANG", "BINH_DINH", "DONG_NAI", "GIA_LAI", "KHANH_HOA", "KIEN_GIANG", "NGHE_AN"),
        ),
        (
            "Bắc Ninh 137 Bình Than, Phường Võ Cường, Thành phố Bắc Ninh Bac Ninh "
            "Thuận An Ô 34&36, Lô DC36, Đường D33, KDC Việt Sing, P.An Phú,Tp.HCM "
            "(Bình Dương cũ) Binh Duong",
            ("BAC_NINH", "HO_CHI_MINH"),
        ),
        (
            "Bắc Ninh 137 Bình Than, Phường Võ Cường, Thành phố Bắc Ninh Bac Ninh "
            "Quận 1 2A1 Nguyễn Thị Minh Khai, Phường Sài Gòn, TP HCM Ho Chi Minh "
            "City Cầu Giấy 02 phố Đỗ Quang, Phường Yên Hòa, Thành phố Hà Nội Ha "
            "Noi Thuận An Ô 34&36, Lô DC36, Đường D33, KDC Việt Sing, P.An "
            "Phú,Tp.HCM (Bình Dương cũ) Binh Duong",
            ("BAC_NINH", "HA_NOI", "HO_CHI_MINH"),
        ),
        (
            "Lô TM, Trung tâm VHTTDL TP Bắc Giang, đường Hoàng Văn Thụ, Bắc Giang, "
            "Bắc Ninh (Bắc Giang cũ) | TTC PLAZA TÂY NINH – 217-219 đường 30/04, "
            "Phường Tân Ninh, Tỉnh Tây Ninh | 469 Nguyễn Hữu Thọ, Quận 7, TP Hồ "
            "Chí Minh",
            ("BAC_NINH", "HO_CHI_MINH", "TAY_NINH"),
        ),
        (
            "Việt Yên Văn phòng DDT VINA, Số 4, Thôn Chùa, Nếnh, Bắc Ninh (Bắc Giang cũ) Bac Giang",
            ("BAC_NINH",),
        ),
        (
            "TTC PLAZA TÂY NINH – 217-219 đường 30/04, Phường Tân Ninh, Tỉnh Tây "
            "Ninh | Lô TM, Trung tâm VHTTDL TP Bắc Giang, đường Hoàng Văn Thụ, Bắc "
            "Giang, Bắc Ninh (Bắc Giang cũ) | Tầng B1, LOTTE Mall, 272 Võ Chí "
            "Công, Quận Tây Hồ | 54 Liễu Giai, Phường Cống Vị, Quận Ba Đình, Tp. "
            "Hà Nội | 469 Nguyễn Hữu Thọ, phường Tân Hưng quận 7 | 469 Nguyễn Hữu "
            "Thọ, Quận 7, TP Hồ Chí Minh",
            ("BAC_NINH", "HA_NOI", "HO_CHI_MINH", "TAY_NINH"),
        ),
    ],
)
def test_round08_tuning_and_confirmed_q43(raw, expected):
    result = classify_location(raw)
    assert result.places == expected
    text = normalize_text(raw, short=True).clean
    assert all(text[e.start : e.end] == e.text for e in result.evidence)


@pytest.mark.parametrize(
    "raw",
    [
        "Tỉnh Hậu Giang",
        "Hậu Giang",
        "Hậu Giang, phường 6 | Quận 12",
    ],
)
def test_street_list_context_does_not_remove_real_or_unclear_haugiang_province(raw):
    assert "HAU_GIANG" in classify_location(raw).places


def test_lower_ward_role_does_not_remove_phutho_from_a_list_or_explicit_province():
    assert "PHU_THO" in classify_location("Phú Thọ; Thủ Dầu Một; Bình Dương").places
    assert (
        "PHU_THO" in classify_location("81 đường A, tỉnh Phú Thọ, Thủ Dầu Một, Bình Dương").places
    )
    assert classify_location("Bắc Ninh Thuận An").places == ("BAC_NINH",)
    assert classify_location("Tỉnh Ninh Thuận").places == ("NINH_THUAN",)


def test_old_name_resolution_does_not_drop_independently_stated_old_province():
    assert classify_location("Tỉnh Bắc Giang, lô A1 | Bắc Ninh (Bắc Giang cũ)").places == (
        "BAC_GIANG",
        "BAC_NINH",
    )
    assert classify_location(
        "Tỉnh Bắc Giang, số 1 đường A, lô B2 tỉnh Bắc Ninh (Bắc Giang cũ)"
    ).places == (
        "BAC_GIANG",
        "BAC_NINH",
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "Quang Ninh Lô A4-A5 Khu công nghiệp Đài Tư, Phúc Lợi, Long Biên, Hà Nội Quang Ninh",
            ("HA_NOI",),
        ),
        (
            "Ho Chi Minh City Số 4N8B Nguyễn Thị Thập, Thanh Xuân - Hà Nội Ho Chi Minh City",
            ("HA_NOI",),
        ),
        (
            "226, Hậu Giang, Phường 9, Quận 6 | 31 Lê Văn Duyệt, Phường Gia Định, "
            "TP Hồ Chí Minh, Việt Nam",
            ("HO_CHI_MINH",),
        ),
        ("Số 3, LK11B2, Làng Việt Kiều Châu Âu, Mỗ Lao, Hà Đông", ("HA_NOI",)),
        ("Kcn Quế Võ, Bắc Ning", ("BAC_NINH",)),
        (
            "Số 26-28 đường số 1, Khu công nghiệp Việt Nam-Singapore II, Phường Bình Dương, "
            "Tp. Hồ Chí Minh (Địa chỉ cũ: KCN VSIP II, P. Hoà Phú, Thành phố Thủ Dầu Một, "
            "Tỉnh Bình Dương, Việt Nam)",
            ("HO_CHI_MINH",),
        ),
        (
            "Số 32 Tô Ngọc Vân, Phường 8, Thành phố Vũng Tàu, Tỉnh Bà Rịa - Vũng Tàu "
            "(Địa chỉ mới: 32 Tô Ngọc Vân, Phường Tam Thắng, TP.Hồ Chí Minh)",
            ("HO_CHI_MINH",),
        ),
        (
            "Ha Noi Lầu 8 - 9 & lầu 10 số 02 đường Ngô Đức Kế, phường Bến Nghé, Quận 1, "
            "thành phố Hồ Chí Minh hoặc Số 182-184 Tòa nhà Flemington, Quận 11, TP.HCM Ha Noi",
            ("HO_CHI_MINH",),
        ),
    ],
)
def test_round09_disagreements_are_tuning_examples_with_q44(raw, expected):
    result = classify_location(raw)
    assert result.places == expected
    text = normalize_text(raw, short=True).clean
    assert all(text[e.start : e.end] == e.text for e in result.evidence)


def test_full_old_address_relation_keeps_independent_places_and_evidence():
    result = classify_location("32 đường A, tỉnh HCM (Địa chỉ cũ: 32 đường A, tỉnh Bình Dương)")
    assert result.places == ("HO_CHI_MINH",)
    assert any(
        e.rule_id.startswith("historical_name.") and e.value == "BINH_DUONG"
        for e in result.evidence
    )
    assert classify_location(
        "Tỉnh Bình Dương | 32 đường A, HCM (Địa chỉ cũ: 32 đường A, tỉnh Bình Dương)"
    ).places == ("BINH_DUONG", "HO_CHI_MINH")
    assert classify_location(
        "32 đường A, HCM (Địa chỉ cũ: 32 đường A, tỉnh Bình Dương) | Tỉnh Bình Dương"
    ).places == ("BINH_DUONG", "HO_CHI_MINH")
    assert classify_location("Tỉnh Bình Dương; Tỉnh Hồ Chí Minh").places == (
        "BINH_DUONG",
        "HO_CHI_MINH",
    )
    assert classify_location("226, Tỉnh Hậu Giang").places == ("HAU_GIANG",)
    assert classify_location("Quế Võ").places == ()
    assert classify_location("Bắc Ning").places == ()


def test_wrapper_with_different_inner_provinces_keeps_province_list():
    result = classify_location("Ha Noi Số 1 đường A, Hồ Chí Minh hoặc Số 2 đường B, Đà Nẵng Ha Noi")
    assert result.places == ("DA_NANG", "HA_NOI", "HO_CHI_MINH")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "Ha Noi Tháp 1 tầng 3 tòa nhà Time Tower,số 35 Lê Văn Lương, Phường Nhân "
            "Chính ,Quận Thanh Xuân , HNP318 tòa nhà Thành Đạt, số 3 Lê Thánh Tông, - "
            "Phường Máy Chai - Quận Ngô Quyền - Hải Phòng Ha Noi",
            ("HAI_PHONG", "HA_NOI"),
        ),
        (
            "No.21, 25B Street, Long An | Số 21, Đường 25B, Ấp Xóm Gốc, Xã Long An, Huyện "
            "Long Thành, Tỉnh Đồng Nai, Việt Nam",
            ("DONG_NAI",),
        ),
        (
            "320/12 Nguyen Van Linh, Binh Thuan, District 7, Ho Chi Minh City, Vietnam, "
            "Ho Chi Minh City, Vietnam",
            ("HO_CHI_MINH",),
        ),
        (
            "Bắc Ninh Toàn khu vực Bac Ninh Gia Bình Toàn khu vực Bac Ninh Thuận Thành "
            "Toàn khu vực Bac Ninh Yên Phong Toàn khu vực Bac Ninh",
            ("BAC_NINH",),
        ),
        (
            "Ho Chi Minh City KDC Bình Đáng, Bình Hòa, Thuận An, Bình Dương Ho Chi Minh City",
            ("BINH_DUONG",),
        ),
        (
            "21Bis Hậu Giang, phường 04 | Tầng 17 Toà nhà Vincom Center, 72 Lê Thánh Tôn, "
            "Phường Sài Gòn, TP Hồ Chí Minh",
            ("HO_CHI_MINH",),
        ),
        (
            "40 Đường Đinh Đức Thiện, Xã Tân Quý Tây, 71807 Huyện Bình Chánh, Vietnam",
            ("HO_CHI_MINH",),
        ),
    ],
)
def test_round10_clear_disagreements_are_tuning_examples(raw, expected):
    result = classify_location(raw)
    assert result.places == expected
    text = normalize_text(raw, short=True).clean
    assert all(text[e.start : e.end] == e.text for e in result.evidence)


def test_lower_role_and_house_suffix_do_not_remove_independent_provinces():
    assert classify_location("Tỉnh Bình Thuận, District 7, Hồ Chí Minh").places == (
        "BINH_THUAN",
        "HO_CHI_MINH",
    )
    assert classify_location("Binh Thuan; District 7, Ho Chi Minh City").places == (
        "BINH_THUAN",
        "HO_CHI_MINH",
    )
    assert classify_location("Tỉnh Ninh Thuận").places == ("NINH_THUAN",)
    assert classify_location("Hậu Giang").places == ("HAU_GIANG",)
    assert classify_location("Đường Huyện Bình Chánh").places == ()
    assert classify_location(
        "No.22, 25B Street, Long An | Số 21, Đường 25B, Xã Long An, Huyện Long Thành, Tỉnh Đồng Nai"
    ).places == ("DONG_NAI", "LONG_AN")
    assert classify_location(
        "No.21, 26B Street, Long An | Số 21, Đường 25B, Xã Long An, Huyện Long Thành, Tỉnh Đồng Nai"
    ).places == ("DONG_NAI", "LONG_AN")
    assert classify_location("Long An | Xã Long An, tỉnh Đồng Nai").places == (
        "DONG_NAI",
        "LONG_AN",
    )


def test_q45_source_linked_old_address_collapses_only_proven_repetitions():
    raw = (
        "Số 26-28, đường số 1, KCN VSIP II, P. Hòa Phú, Tp. Thủ Dầu Một | Số 26-28 "
        "đường số 1, Khu công nghiệp Việt Nam-Singapore II, Phường Bình Dương, Tp. Hồ "
        "Chí Minh (Địa chỉ cũ: KCN VSIP II, P. Hoà Phú, Thành phố Thủ Dầu Một, Tỉnh "
        "Bình Dương, Việt Nam)"
    )
    result = classify_location(raw)
    assert result.places == ("HO_CHI_MINH",)
    assert "source_repeated_explicit_old_address" in result.flags
    assert any(e.rule_id.startswith("historical_name.repeated_address.") for e in result.evidence)
    text = normalize_text(raw, short=True).clean
    assert all(text[e.start : e.end] == e.text for e in result.evidence)
    first, full = raw.split(" | ", 1)
    for independent in [
        first.replace("26-28", "29-31"),
        first.replace("đường số 1", "đường số 2"),
        first.replace("VSIP II", "VSIP III"),
        first.replace("Hòa Phú", "Tân Hiệp"),
        "Tỉnh Bình Dương",
    ]:
        assert classify_location(independent + " | " + full).places == ("BINH_DUONG", "HO_CHI_MINH")
    assert classify_location(first + ", Tỉnh Bình Dương | " + full).places == ("HO_CHI_MINH",)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "37 Lê Hồng Phong, P. Hưng Bình, Tp. Vinh, T. Nghệ An | 88 Đại lộ Lê Lợi, P. "
            "Đông Hương, Tp. Thanh Hóa, T. Thanh Hóa | Tiểu khu 4, TT. Quán Lào, H. Yên "
            "Định, T. Thanh Hóa | Số 399 đường Phạm Văn Đồng, Phường Xuân Đỉnh, TP Hà "
            "Nội, Việt Nam",
            ("HA_NOI", "NGHE_AN", "THANH_HOA"),
        ),
        (
            "Binh Thuan Xã Nhựt Chánh, huyện Bến Lức, tỉnh Long An Binh Thuan",
            ("LONG_AN",),
        ),
        (
            "Hai Phong Tòa nhà Symphony - Đường Chu Huy Mân - Long Biên - Hà Nội Hai Phong",
            ("HA_NOI",),
        ),
        (
            "Ha Noi Khu công nghiệp Tân Quang, Văn Lâm Hưng Yên Ha Noi",
            ("HUNG_YEN",),
        ),
        (
            "Binh Duong Số 17, Phan Bội Châu, Khu 6, Phú Thọ, TP TDM, Bình Dương Binh Duong",
            ("BINH_DUONG",),
        ),
        (
            "Lầu 2, 13 Cao Thắng, Phường 2, Quận 3, Thành phố Hồ Chí Minh | Tầng 5, Lotte "
            "Mart Phú Thọ, 968 đường 3/2, Phường 15, Quận 11, Thành phố Hồ Chí Minh | 340 "
            "Cộng Hòa, Phường 13, Quận Tân Bình, Thành phố Hồ Chí Minh | 98 Đường Số 17A, "
            "Bình Trị Đông B, Bình Tân, Thành phố Hồ Chí Minh | 174 Hòa Bình, Phường Tân "
            "Thới Hòa, Quận Tân Phú, Thành phố Hồ Chí Minh",
            ("HO_CHI_MINH",),
        ),
        (
            "Số 2, Đại lộ Hữu Nghị, Khu CN Việt Nam-Singapore - Xã Tịnh Phong - Huyện Sơn "
            "Tịnh - Quảng Ngãi.",
            ("QUANG_NGAI",),
        ),
    ],
)
def test_round11_clear_disagreements_are_tuning_examples(raw, expected):
    result = classify_location(raw)
    assert result.places == expected
    assert result.foreign == ()
    text = normalize_text(raw, short=True).clean
    assert all(text[e.start : e.end] == e.text for e in result.evidence)


def test_town_and_park_names_do_not_remove_real_foreign_places():
    assert classify_location("Lào (nước ngoài)").foreign == ("LAOS",)
    assert classify_location("Singapore").foreign == ("SINGAPORE",)
    assert classify_location("Hà Nội; Singapore").foreign == ("SINGAPORE",)
    assert classify_location("Khu CN Việt Nam-Singapore, Quảng Ngãi").foreign == ()
    assert "PHU_THO" in classify_location("Phú Thọ; TP TDM, Bình Dương").places
    assert "PHU_THO" in classify_location("Số 17, đường A, tỉnh Phú Thọ, TP TDM, Bình Dương").places
    assert classify_location("Hà Nội; Lotte Mart Phú Thọ").places == ("HA_NOI", "PHU_THO")


def test_q46_repeated_plot_prefers_explicit_province_over_factory_name():
    text = (
        "Nhà máy Hải Dương :Lô đất CN8, KCN Tân Trường, X. Tân Trường | "
        "Lô đất CN8, khu công nghiệp Tân Trường, Xã Mao Điền, TP Hải Phòng"
    )
    result = classify_location(text)
    assert result.places == ("HAI_PHONG",)
    assert "repeated_factory_plot_name_not_additional_province" in result.flags
    assert any(
        e.rule_id.startswith("facility_name.repeated_plot.") and e.value == "HAI_DUONG"
        for e in result.evidence
    )
    assert not result.address_links


@pytest.mark.parametrize(
    "second",
    [
        "Lô đất CN9, KCN Tân Trường, Xã Mao Điền, TP Hải Phòng",
        "Lô đất CN8, KCN Khác, Xã Mao Điền, TP Hải Phòng",
    ],
)
def test_q46_different_plot_or_park_preserves_independent_places(second):
    result = classify_location(
        "Nhà máy Hải Dương: Lô đất CN8, KCN Tân Trường, X. Tân Trường | " + second
    )
    assert result.places == ("HAI_DUONG", "HAI_PHONG")


def test_q46_explicit_independent_province_is_not_a_factory_name():
    result = classify_location(
        "Lô đất CN8, KCN Tân Trường, tỉnh Hải Dương | Lô đất CN8, KCN Tân Trường, TP Hải Phòng"
    )
    assert result.places == ("HAI_DUONG", "HAI_PHONG")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Hải Dương", ("HAI_DUONG",)),
        ("Bình Dương", ("BINH_DUONG",)),
        ("Bà Rịa - Vũng Tàu", ("BA_RIA_VUNG_TAU",)),
        ("Hải Dương; Hải Phòng", ("HAI_DUONG", "HAI_PHONG")),
        ("Hà Nội; Bình Dương", ("BINH_DUONG", "HA_NOI")),
    ],
)
def test_source_province_names_are_retained_without_post_merger_projection(raw, expected):
    assert classify_location(raw).places == expected
