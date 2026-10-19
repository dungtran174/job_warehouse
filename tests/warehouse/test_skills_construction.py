"""Construction skills: finite aliases, source evidence and semantic exclusions."""

import pytest

from job_warehouse.skills.batches import batch_scope
from job_warehouse.skills.construction import CONSTRUCTION_MAPPINGS, ConstructionSkillMatcher
from job_warehouse.skills.runner import load_policy
from job_warehouse.skills.taxonomy import load_taxonomy


@pytest.fixture
def matcher():
    return ConstructionSkillMatcher(
        load_taxonomy(CONSTRUCTION_MAPPINGS),
        load_policy(CONSTRUCTION_MAPPINGS, scope=batch_scope("construction_design_projects"))[0],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Thành thạo MS Project và Primavera", {"review_microsoft_project", "con_primavera"}),
        ("Thành thạo SAP2000 và ETABS", {"con_sap2000", "con_etabs"}),
        ("Có kinh nghiệm BIM modelling", {"con_bim"}),
        (
            "Có kinh nghiệm bóc tách khối lượng, lập dự toán",
            {"con_quantity_takeoff", "review_lap_du_toan"},
        ),
        ("Bóc tách khối lượng từ bản vẽ thi công", {"con_quantity_takeoff"}),
        ("Giám sát thi công công trình", {"con_site_supervision"}),
        ("Có chứng chỉ hành nghề giám sát xây dựng", {"con_site_supervision"}),
        ("Có kinh nghiệm quản lý dự án", {"review_quan_ly_du_an"}),
        ("Tham gia dự án xây dựng", set()),
        ("Làm việc tại phòng quản lý dự án", set()),
        ("Sử dụng phần mềm quản lý dự án", set()),
        ("Sử dụng phần mềm lập dự toán", set()),
        ("Có kinh nghiệm lập hồ sơ dự thầu", {"con_tender_documents"}),
        ("Có kinh nghiệm nghiệm thu khối lượng", {"con_acceptance"}),
        ("Thành thạo lập tiến độ thi công", {"con_progress_planning"}),
        ("Có kinh nghiệm thiết kế nội thất", {"con_interior_design"}),
        ("Tốt nghiệp chuyên ngành thiết kế nội thất", set()),
        ("Tốt nghiệp ngành thiết kế kiến trúc", set()),
        ("Sử dụng phần mềm thiết kế kết cấu", set()),
        ("Có kinh nghiệm thiết kế kết cấu", {"con_structural_design"}),
        ("Biết sử dụng 3Dmax, Lumion, Vray", {"review_3ds_max", "review_lumion", "con_vray"}),
        ("Sử dụng Render Corona và Navisworks", {"con_corona", "con_navisworks"}),
        ("Có kiến thức lý thuyết màu sắc và Typography", {"con_color_theory", "con_typography"}),
        ("Biết vẽ tay", {"con_hand_drawing"}),
        ("Tốt nghiệp ngành xây dựng, chưa có kinh nghiệm sẽ được đào tạo", set()),
        ("Sẽ được đào tạo sử dụng Revit", set()),
        ("Không yêu cầu biết Revit", set()),
        ("Có kiến thức quy chuẩn QC/TCVN", set()),
        ("Biết CAD", {"review_cad"}),
        ("Sinh viên năm 3 ngành thiết kế nội thất", set()),
        ("Kinh nghiệm thiết kế kiến trúc dữ liệu OLAP", set()),
        ("Hồ sơ, tài liệu QC-TCVN về thiết kế kết cấu cần tìm hiểu", set()),
        ("Có kỹ năng làm việc nhóm, sáng tạo", set()),
    ],
)
def test_construction_boundaries(matcher, text, expected):
    x = matcher.extract(text)
    assert set(x.skill_codes) == expected
    assert x.status in {"processed_match", "processed_no_match"}
    for e in x.evidence:
        assert text[e.start : e.end] == e.text
        assert 0 <= e.context_start <= e.start < e.end <= e.context_end <= len(text)


def test_cli_construction_scope():
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
            "construction_design_projects",
        ]
    )
    assert a.batch == "construction_design_projects"


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
            "job_industry": batch_scope("construction_design_projects")[0],
            "requirements": "Thành thạo AutoCAD và Excel",
        },
        {
            "id": 2,
            "year": 2025,
            "job_industry": batch_scope("construction_design_projects")[1],
            "requirements": "Có bằng B2",
        },
        {
            "id": 3,
            "year": 2026,
            "job_industry": batch_scope("construction_design_projects")[1],
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
            taxonomy_dir=CONSTRUCTION_MAPPINGS,
            batch_name="construction_design_projects",
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


def test_exact_four_source_labels():
    assert len(batch_scope("construction_design_projects")) == 4
