"""Offline healthcare, food and garment boundaries with source preservation."""

import pytest

from job_warehouse.skills.batches import batch_scope
from job_warehouse.skills.life_sciences import LIFE_SCIENCES_MAPPINGS, LifeSciencesSkillMatcher
from job_warehouse.skills.runner import load_policy
from job_warehouse.skills.taxonomy import load_taxonomy


@pytest.fixture
def matcher():
    return LifeSciencesSkillMatcher(
        load_taxonomy(LIFE_SCIENCES_MAPPINGS),
        load_policy(LIFE_SCIENCES_MAPPINGS, scope=batch_scope("healthcare_food_garment"))[0],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Có kiến thức chuyên môn điều dưỡng", {"life_nursing"}),
        ("Tốt nghiệp cao đẳng ngành điều dưỡng", set()),
        ("Graduated from the College of Nursing or higher", set()),
        ("Valid Nursing Practice License", set()),
        ("Có kỹ năng chăm sóc bệnh nhân", {"life_patient_care"}),
        ("Kỹ năng lấy máu và đo sinh hiệu", {"life_blood_collection", "life_vital_signs"}),
        ("Có chứng chỉ sơ cứu", {"life_first_aid"}),
        ("Có kỹ năng hồi sức tim phổi", {"life_cpr"}),
        ("Có kinh nghiệm thực hiện tiêm chủng", {"life_vaccination"}),
        ("Đã tiêm chủng đầy đủ", set()),
        ("Valid doctor's vaccination certificate is preferred", set()),
        ("Am hiểu bào chế", {"life_compounding"}),
        ("Có kinh nghiệm bán thuốc độc lập", {"life_drug_sales"}),
        ("Tốt nghiệp đại học dược", set()),
        ("Có kiến thức GMP, GPP và GLP", {"life_gmp", "life_gpp", "life_glp"}),
        ("Có kinh nghiệm làm tại nhà máy đạt GMP", set()),
        ("Có kỹ năng làm việc theo GDP trong ngành dược", {"life_gdp"}),
        ("Có kiến thức về GDP của nền kinh tế", set()),
        ("Có kiến thức Luật Dược", {"life_pharmacy_law"}),
        ("Am hiểu kiểm nghiệm và vi sinh", {"life_testing", "life_microbiology"}),
        ("Tốt nghiệp chuyên ngành kiểm nghiệm", set()),
        ("Có kiến thức ISO 22000 và FSSC", {"life_iso22000", "life_fssc"}),
        ("Có kiến thức ATVSTP và HACCP", {"ret_food_safety", "eng_haccp"}),
        ("Có kinh nghiệm thiết kế rập", {"life_pattern_design"}),
        ("Thành thạo nhảy size", {"life_pattern_grading"}),
        ("Có kinh nghiệm giác sơ đồ", {"life_marker_making"}),
        ("Có kinh nghiệm may mẫu", {"life_sample_sewing"}),
        ("Sử dụng thành thạo máy may", {"life_sewing_machine"}),
        ("Có kiến thức kỹ thuật may mặc", {"review_ky_thuat_san_xuat_may_mac"}),
        ("Am hiểu kỹ thuật cắt may", {"life_cutting_sewing"}),
        ("Biết phần mềm Gerber, Lectra, Optitex", {"life_gerber", "life_lectra", "life_optitex"}),
        ("Sử dụng thành thạo phần mềm Gerber AccuMark", {"life_accumark"}),
        ("Biết phần mềm CLO 3D và Browzwear", {"life_clo3d", "life_browzwear"}),
        ("Có kiến thức Clo khử trùng nước", set()),
        ("Biết sử dụng phần mềm GSD", {"life_gsd"}),
        ("Có kinh nghiệm bán hàng sản phẩm Gerber", {"review_ban_hang_sales"}),
        ("Kỹ năng phối hợp với các bộ phận nội bộ (R&D, Thu mua, Nhà máy)", set()),
        ("Có chứng chỉ hành nghề. Chi nhánh tuyển dụng: Quận 1", set()),
        ("Sẽ được đào tạo may mẫu", set()),
        ("Chăm chỉ, cẩn thận, trung thực", set()),
    ],
)
def test_life_sciences_boundaries(matcher, text, expected):
    x = matcher.extract(text)
    assert set(x.skill_codes) == expected
    assert x.status in {"processed_match", "processed_no_match"}
    for e in x.evidence:
        assert text[e.start : e.end] == e.text
        assert 0 <= e.context_start <= e.start < e.end <= e.context_end <= len(text)


def test_cli_life_sciences_scope():
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
            "healthcare_food_garment",
        ]
    )
    assert a.batch == "healthcare_food_garment"


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
            "job_industry": batch_scope("healthcare_food_garment")[0],
            "requirements": "Thành thạo AutoCAD và Excel",
        },
        {
            "id": 2,
            "year": 2025,
            "job_industry": batch_scope("healthcare_food_garment")[0],
            "requirements": "Có bằng B2",
        },
        {
            "id": 3,
            "year": 2026,
            "job_industry": batch_scope("healthcare_food_garment")[0],
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
            taxonomy_dir=LIFE_SCIENCES_MAPPINGS,
            batch_name="healthcare_food_garment",
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


def test_exact_three_source_labels():
    assert len(batch_scope("healthcare_food_garment")) == 3
