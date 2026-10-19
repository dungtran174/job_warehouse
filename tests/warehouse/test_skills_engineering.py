"""Finite engineering skills, typed parent exclusions and nonblocking skips."""

import pytest

from job_warehouse.skills.batches import batch_scope
from job_warehouse.skills.engineering import ENGINEERING_MAPPINGS, EngineeringSkillMatcher
from job_warehouse.skills.runner import load_policy
from job_warehouse.skills.taxonomy import load_taxonomy


@pytest.fixture
def matcher():
    return EngineeringSkillMatcher(
        load_taxonomy(ENGINEERING_MAPPINGS),
        load_policy(ENGINEERING_MAPPINGS, scope=batch_scope("engineering_production"))[0],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Thành thạo AutoCAD, SolidWorks", {"review_autocad", "review_solidworks"}),
        ("Biết sử dụng CAD", {"review_cad"}),
        ("Có kinh nghiệm lập trình PLC", {"eng_plc_programming"}),
        ("Có kiến thức PLC", {"eng_plc"}),
        ("Biết lập trình CNC", {"review_lap_trinh_cnc"}),
        ("Có kinh nghiệm vận hành máy CNC", {"eng_cnc_operation"}),
        ("Có kinh nghiệm vận hành máy quay", set()),
        ("Có khả năng đọc hiểu bản vẽ kỹ thuật", {"review_doc_ban_ve_ky_thuat"}),
        ("Biết sử dụng dụng cụ đo", {"eng_measurement_tools"}),
        ("Biết dùng dụng cụ đo cơ khí", {"review_dung_cu_do_co_khi"}),
        ("Sử dụng tốt thước cặp và panme", {"review_dung_cu_do_co_khi"}),
        ("Tốt nghiệp ngành cơ khí chế tạo máy", set()),
        ("Am hiểu cơ khí chế tạo máy", {"eng_mechanical_manufacturing"}),
        ("Tốt nghiệp chuyên ngành điện công nghiệp", set()),
        ("Có kiến thức điện công nghiệp", {"eng_industrial_electricity"}),
        ("Có kinh nghiệm bảo trì thiết bị", {"eng_equipment_maintenance"}),
        ("Có kinh nghiệm bảo trì", set()),
        ("Có kinh nghiệm sửa chữa điện thoại", set()),
        ("Có kinh nghiệm quản lý sản xuất", {"eng_production_management"}),
        ("Thành thạo phần mềm quản lý sản xuất", set()),
        ("Thành thạo phần mềm quản lý chất lượng", set()),
        ("Có kinh nghiệm kiểm tra chất lượng", {"review_kiem_soat_chat_luong_qc"}),
        ("Có kinh nghiệm QA/QC", {"eng_quality_assurance", "review_kiem_soat_chat_luong_qc"}),
        ("Phối hợp với phòng QC", set()),
        ("Có kiến thức ISO 9001:2015", {"review_iso_9001"}),
        ("Có kiến thức ISO 14001 và ISO 45001", {"eng_iso_14001", "eng_iso_45001"}),
        ("Có hiểu biết về ISO", {"eng_iso_generic"}),
        ("Có kinh nghiệm làm tại công ty đạt ISO 9001", set()),
        ("Công ty đã được chứng nhận ISO 9001", set()),
        ("Có hiểu biết về tiêu chuẩn IATF 16949", {"review_iatf_16949"}),
        (
            "Có kiến thức Six Sigma, Kaizen và Lean trong cải tiến sản xuất",
            {"eng_six_sigma", "eng_kaizen", "eng_lean"},
        ),
        (
            "Thành thạo các công cụ FMEA, SPC, APQP, MSA, PPAP",
            {"review_fmea", "review_spc", "review_apqp", "review_msa", "review_ppap"},
        ),
        ("Biết hàn", {"eng_welding"}),
        ("Có kinh nghiệm hàn TIG", {"eng_tig_welding"}),
        ("Tiếng Hàn thành thạo", {"korean"}),
        ("Có kinh nghiệm Hàn Quốc", set()),
        ("Am hiểu an toàn lao động", {"eng_safety"}),
        ("Tuân thủ nội quy an toàn lao động", set()),
        ("Có bằng B2", {"log_car_driving"}),
        ("Có kỹ năng giao tiếp, cẩn thận, chăm chỉ", set()),
    ],
)
def test_engineering_boundaries(matcher, text, expected):
    x = matcher.extract(text)
    assert set(x.skill_codes) == expected
    assert x.status in {"processed_match", "processed_no_match"}
    for e in x.evidence:
        assert text[e.start : e.end] == e.text
        assert 0 <= e.context_start <= e.start < e.end <= e.context_end <= len(text)


def test_cli_engineering_scope():
    from job_warehouse.cli import build_parser

    a = build_parser().parse_args(
        [
            "silver",
            "skills",
            "--jobs-run",
            "/tmp/in",
            "--output-dir",
            "/tmp/out",
            "--batch",
            "engineering_production",
        ]
    )
    assert a.batch == "engineering_production"


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
            "job_industry": batch_scope("engineering_production")[0],
            "requirements": "Thành thạo AutoCAD và Excel",
        },
        {
            "id": 2,
            "year": 2025,
            "job_industry": batch_scope("engineering_production")[1],
            "requirements": "Có bằng B2",
        },
        {
            "id": 3,
            "year": 2026,
            "job_industry": batch_scope("engineering_production")[1],
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
            taxonomy_dir=ENGINEERING_MAPPINGS,
            batch_name="engineering_production",
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


def test_exact_five_source_labels():
    assert len(batch_scope("engineering_production")) == 5
