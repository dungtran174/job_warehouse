"""Real-estate capabilities are local, explained, and isolated from accepted sales."""

import json

import pytest

from job_warehouse.skills.batches import batch_scope
from job_warehouse.skills.real_estate import REAL_ESTATE_MAPPINGS, RealEstateSkillMatcher
from job_warehouse.skills.runner import load_policy
from job_warehouse.skills.sales import SALES_MAPPINGS, SalesSkillMatcher
from job_warehouse.skills.taxonomy import load_taxonomy


@pytest.fixture
def matcher():
    return RealEstateSkillMatcher(
        load_taxonomy(REAL_ESTATE_MAPPINGS),
        load_policy(REAL_ESTATE_MAPPINGS, scope=batch_scope("real_estate"))[0],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Có kinh nghiệm kinh doanh BĐS", {"review_ban_hang_sales"}),
        ("Hiểu rõ về thị trường bất động sản", {"review_kien_thuc_bat_dong_san"}),
        ("Hiểu biết về bất động sản là lợi thế", {"review_kien_thuc_bat_dong_san"}),
        ("Có kiến thức về Ngân hàng, Tài chính, Bất động sản", {"review_kien_thuc_bat_dong_san"}),
        ("Có kinh nghiệm môi giới trong lĩnh vực BĐS", {"sales_real_estate_brokerage"}),
        (
            "Am hiểu các quy định – luật về kinh doanh và đầu tư bất động sản",
            {"sales_real_estate_legal"},
        ),
        ("Có khả năng phân tích pháp luật liên quan đến đất đai", {"sales_real_estate_legal"}),
        ("Có kinh nghiệm làm Trưởng phòng kinh doanh Bất động sản", {"review_ban_hang_sales"}),
        ("Có kinh nghiệm quản lý đội nhóm bán các sản phẩm nghỉ dưỡng", {"review_ban_hang_sales"}),
        ("Ưu tiên có kinh nghiệm bán shophouse", {"review_ban_hang_sales"}),
        (
            "Ưu tiên có kinh nghiệm tư vấn bán hàng trực tiếp. - CSKH, Sale, Telesale",
            {
                "sales_product_consulting",
                "review_ban_hang_sales",
                "review_cham_soc_khach_hang",
                "review_telesales",
            },
        ),
        ("Khai thác khách hàng mới", {"sales_prospecting"}),
        ("Sử dụng phần mềm Auto Cad để đọc bản vẽ", {"review_autocad"}),
        ("Thành thạo các công cụ Web WP, Google Ads", {"review_wordpress", "google_ads"}),
        ("Có kinh nghiệm trong lĩnh vực bất động sản", set()),
        ("Tốt nghiệp chuyên ngành bất động sản", set()),
        ("Đam mê môi giới bất động sản", set()),
        ("Thích chốt đơn", set()),
        ("Học hỏi được nhiều kỹ năng về sale và đầu tư", set()),
        ("Sẽ được đào tạo môi giới BĐS", set()),
        ("Thành thạo nền tảng công nghệ trong ngành bất động sản", set()),
        ("Am hiểu chiến lược Marketing trong lĩnh vực Bất động sản", set()),
        ("Có kinh nghiệm quản lý 5 sales", set()),
        ("Tốt nghiệp luật. Có kinh nghiệm trong ngành BĐS", set()),
        ("Có kinh nghiệm môi giới chứng khoán", set()),
        ("CRM; Excel", set()),
        ("Thành thạo phần mềm thiết kế Photoshop, Preier", {"photoshop", "premiere"}),
        ("Preier", set()),
    ],
)
def test_real_estate_capability_boundaries(matcher, text, expected):
    result = matcher.extract(text)
    assert set(result.skill_codes) == expected
    for item in result.evidence:
        assert text[item.start : item.end] == item.text
        assert 0 <= item.context_start <= item.start < item.end <= item.context_end <= len(text)


def test_adjacent_list_cannot_jump_unrelated_sentence(matcher):
    r = matcher.extract("Có kinh nghiệm bán hàng. Quyền lợi hấp dẫn. - CSKH, Sale, Telesale")
    assert "review_cham_soc_khach_hang" not in r.skill_codes
    assert "review_telesales" not in r.skill_codes


def test_software_purpose_is_not_customer_service_capability(matcher):
    r = matcher.extract("Hiểu biết về các phần mềm, công cụ quản lý, CSKH (Zalo, CRM)")
    assert "review_cham_soc_khach_hang" not in r.skill_codes


def test_specialist_law_does_not_implicitly_add_general_domain_knowledge(matcher):
    r = matcher.extract("Nắm vững các quy định pháp luật về pháp lý đất dự án BĐS")
    assert "review_kien_thuc_bat_dong_san" not in r.skill_codes


def test_business_law_can_use_explicit_previous_real_estate_context(matcher):
    r = matcher.extract(
        "Am hiểu về bất động sản; "
        "Am hiểu các chính sách pháp luật liên quan đến lĩnh vực kinh doanh"
    )
    assert "sales_real_estate_legal" in r.skill_codes
    e = next(e for e in r.evidence if e.skill_code == "sales_real_estate_legal")
    assert e.rule_id == "owner_real_estate_q3_business_law_paragraph"


def test_business_law_does_not_cross_paragraph_or_conflicting_sector(matcher):
    for text in (
        "Am hiểu bất động sản\n\nAm hiểu pháp luật liên quan đến lĩnh vực kinh doanh",
        "Am hiểu bất động sản và chứng khoán; Am hiểu pháp luật liên quan đến lĩnh vực kinh doanh",
    ):
        assert "sales_real_estate_legal" not in matcher.extract(text).skill_codes


def test_new_alias_does_not_change_frozen_sales():
    old = SalesSkillMatcher(
        load_taxonomy(SALES_MAPPINGS),
        load_policy(SALES_MAPPINGS, scope=batch_scope("sales_customer_service"))[0],
    )
    assert not old.extract("Hiểu rõ về thị trường bất động sản").skill_codes


def test_policy_requires_explicit_real_estate_scope():
    with pytest.raises(ValueError, match="scope"):
        load_policy(REAL_ESTATE_MAPPINGS)


def test_real_estate_runner_replays_and_routes_only_its_label(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    from job_warehouse.history.identity import file_sha256
    from job_warehouse.skills.runner import run_skills

    source = tmp_path / "source"
    source.mkdir()
    rows = [
        {
            "id": 1,
            "job_industry": "Bất động sản",
            "year": 2024,
            "requirements": "Hiểu rõ về thị trường bất động sản",
        },
        {"id": 2, "job_industry": "Marketing", "year": 2024, "requirements": "Biết Excel"},
    ]
    path = source / "jobs_analysis.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            rows,
            schema=pa.schema(
                [
                    ("id", pa.int64()),
                    ("job_industry", pa.string()),
                    ("year", pa.int16()),
                    ("requirements", pa.string()),
                ]
            ),
        ),
        path,
    )
    (source / "manifest.json").write_text(
        json.dumps(
            {
                "source": {"revision": "fixture", "pinned_artifact_verified": False},
                "partition": {"analysis": 2},
                "artifacts": {path.name: {"sha256": file_sha256(path)}},
            }
        )
    )
    reports = []
    for name in ("run_a", "run_b"):
        dest = tmp_path / name
        reports.append(
            run_skills(
                source,
                dest,
                taxonomy_dir=REAL_ESTATE_MAPPINGS,
                batch_name="real_estate",
                allow_unpinned_fixture=True,
            )
        )
    assert reports[0]["artifacts"] == reports[1]["artifacts"]
    assert reports[0]["counts"]["scope_rows"] == 1
    assert pq.read_table(tmp_path / "run_a/job_skill_match.parquet").to_pylist() == [
        {
            "job_id": 1,
            "skill_code": "review_kien_thuc_bat_dong_san",
            "skill_name": "Kiến thức bất động sản",
        }
    ]
    for name in (
        "job_skill_match.parquet",
        "job_skill_status.parquet",
        "job_skill_evidence.parquet",
    ):
        assert pq.read_table(tmp_path / "run_a" / name).equals(
            pq.read_table(tmp_path / "run_b" / name)
        )
