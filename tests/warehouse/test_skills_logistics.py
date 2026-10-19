"""Logistics keyword boundaries and the owner's finite driving-license policy."""

import pytest

from job_warehouse.skills.batches import batch_scope
from job_warehouse.skills.logistics import LOGISTICS_MAPPINGS, LogisticsSkillMatcher
from job_warehouse.skills.runner import load_policy
from job_warehouse.skills.taxonomy import load_taxonomy


@pytest.fixture
def matcher():
    return LogisticsSkillMatcher(
        load_taxonomy(LOGISTICS_MAPPINGS),
        load_policy(LOGISTICS_MAPPINGS, scope=batch_scope("logistics_transport"))[0],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Có bằng B2", {"log_car_driving"}),
        ("Bằng lái xe hạng B1/B2 trở lên", {"log_car_driving"}),
        ("Có giấy phép lái xe hạng C", {"log_car_driving"}),
        ("Có bằng lái xe máy", {"log_motorcycle_driving"}),
        ("Có chứng chỉ lái xe nâng", {"log_forklift"}),
        ("Có xe máy và smartphone", set()),
        ("Không yêu cầu bằng B2", set()),
        ("Công ty hỗ trợ thi bằng lái xe B2", set()),
        ("Sẽ được cấp chứng chỉ lái xe nâng", set()),
        ("Có bằng B2 tiếng Anh", set()),
        ("Có kinh nghiệm lái xe máy", {"log_motorcycle_driving"}),
        ("Có kinh nghiệm lái xe ô tô", {"log_car_driving"}),
        ("Có kinh nghiệm lái xe", {"log_driving"}),
        ("Biết lái xe nâng", {"log_forklift"}),
        ("Am hiểu quản lý tồn kho", {"log_inventory_control"}),
        ("Có kinh nghiệm kiểm kê hàng hóa", {"review_kiem_ke_hang_hoa"}),
        ("Thành thạo phần mềm quản lý kho WMS", {"review_phan_mem_quan_ly_kho", "review_wms"}),
        (
            "Có kinh nghiệm quản lý kho và kiểm kê",
            {"review_quan_ly_kho", "review_kiem_ke_hang_hoa"},
        ),
        ("Thành thạo hệ thống SAP", {"sap"}),
        ("Có kinh nghiệm thu mua", {"review_thu_mua"}),
        (
            "Am hiểu quy trình xuất nhập khẩu và Incoterms",
            {"review_xuat_nhap_khau", "review_incoterms"},
        ),
        ("Biết sử dụng phần mềm ECUS, VNACCS", {"legal_ecus", "legal_vnaccs"}),
        ("Tốt nghiệp chuyên ngành xuất nhập khẩu", set()),
        ("Có kinh nghiệm sales dịch vụ logistics", {"review_ban_hang_sales"}),
        ("Thành thạo TMS, GPS", {"log_tms", "log_gps"}),
        ("Đã có kinh nghiệm giao hàng", {"log_delivery"}),
        ("Rành đường thành phố", {"log_route_knowledge"}),
    ],
)
def test_logistics_explicit_keywords(matcher, text, expected):
    result = matcher.extract(text)
    assert set(result.skill_codes) == expected
    assert result.status in {"processed_match", "processed_no_match"}
    for e in result.evidence:
        assert text[e.start : e.end] == e.text
        assert 0 <= e.context_start <= e.start < e.end <= e.context_end <= len(text)


def test_cli_accepts_logistics_batch():
    from job_warehouse.cli import build_parser

    args = build_parser().parse_args(
        [
            "silver",
            "skills",
            "--jobs-run",
            "/tmp/in",
            "--output-dir",
            "/tmp/out",
            "--batch",
            "logistics_transport",
        ]
    )
    assert args.batch == "logistics_transport"


def test_runner_preserves_jobs_and_replays_without_recognizing_all_texts(tmp_path):
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    from job_warehouse.history.identity import file_sha256
    from job_warehouse.skills.runner import run_skills

    source = tmp_path / "source"
    source.mkdir()
    rows = [
        {
            "id": 1,
            "year": 2024,
            "job_industry": batch_scope("logistics_transport")[0],
            "requirements": "Thành thạo WMS và Excel",
        },
        {
            "id": 2,
            "year": 2025,
            "job_industry": batch_scope("logistics_transport")[1],
            "requirements": "Có bằng B2",
        },
        {
            "id": 3,
            "year": 2026,
            "job_industry": batch_scope("logistics_transport")[1],
            "requirements": "Siêng năng, chịu khó",
        },
        {"id": 4, "year": 2024, "job_industry": "Marketing", "requirements": "Biết Excel"},
    ]
    p = source / "jobs_analysis.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            rows,
            schema=pa.schema(
                [
                    ("id", pa.int64()),
                    ("year", pa.int16()),
                    ("job_industry", pa.string()),
                    ("requirements", pa.string()),
                ]
            ),
        ),
        p,
    )
    (source / "manifest.json").write_text(
        json.dumps(
            {
                "source": {"revision": "fixture", "pinned_artifact_verified": False},
                "partition": {"analysis": 4},
                "artifacts": {p.name: {"sha256": file_sha256(p)}},
            }
        )
    )
    for name in ("one", "two"):
        run_skills(
            source,
            tmp_path / name,
            taxonomy_dir=LOGISTICS_MAPPINGS,
            batch_name="logistics_transport",
            allow_unpinned_fixture=True,
        )
    for name in (
        "job_skill_status.parquet",
        "job_skill_match.parquet",
        "job_skill_evidence.parquet",
    ):
        assert file_sha256(tmp_path / "one" / name) == file_sha256(tmp_path / "two" / name)
    status = pq.read_table(tmp_path / "one/job_skill_status.parquet").to_pylist()
    assert len(status) == 4
    assert [r["status"] for r in status] == [
        "processed_match",
        "processed_match",
        "processed_no_match",
        "out_of_scope",
    ]
    pairs = pq.read_table(tmp_path / "one/job_skill_match.parquet").to_pylist()
    assert (2, "log_car_driving") in {(r["job_id"], r["skill_code"]) for r in pairs}
