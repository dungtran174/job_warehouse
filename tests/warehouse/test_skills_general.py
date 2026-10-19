"""General labels never establish skills; clear requirements do."""

import pytest

from job_warehouse.skills.batches import batch_scope
from job_warehouse.skills.general import GENERAL_MAPPINGS, GeneralSkillMatcher
from job_warehouse.skills.runner import load_policy
from job_warehouse.skills.taxonomy import load_taxonomy


@pytest.fixture
def matcher():
    return GeneralSkillMatcher(
        load_taxonomy(GENERAL_MAPPINGS),
        load_policy(GENERAL_MAPPINGS, scope=batch_scope("general_industries"))[0],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Đóng gói sản phẩm theo yêu cầu", {"general_packaging"}),
        ("Có kinh nghiệm bốc xếp hàng hóa", {"general_loading"}),
        ("Ưu tiên kinh nghiệm vệ sinh công nghiệp", {"general_industrial_cleaning"}),
        ("Kỹ năng sơ chế sản phẩm", {"general_food_preparation"}),
        ("Biết sử dụng máy đóng gói sản phẩm", set()),
        ("Có kinh nghiệm ở công ty vệ sinh công nghiệp", set()),
        ("Sẽ được đào tạo đóng gói sản phẩm", set()),
        ("Không yêu cầu kinh nghiệm bốc xếp", set()),
        ("Yêu thích công việc tuyển dụng", set()),
        ("Kỹ năng tin học văn phòng cơ bản. Yêu thích công việc tuyển dụng", {"office_it"}),
        ("Yêu thích công việc. Có kinh nghiệm tuyển dụng", {"hr_recruitment"}),
        ("Thành thạo Excel", {"excel"}),
        ("Biết Python", {"python"}),
        ("Biết sử dụng AutoCAD", {"review_autocad"}),
        ("Có kinh nghiệm may mẫu", {"life_sample_sewing"}),
        ("Biết thu ngân", {"ret_cashiering"}),
        ("Có bằng B2", {"log_car_driving"}),
        ("Có xe máy và điện thoại smartphone", set()),
        ("Thực tập, lao động phổ thông", set()),
        ("Tốt nghiệp chuyên ngành kế toán", set()),
        ("Trung thực, chăm chỉ, khỏe mạnh", set()),
        ("Tốt nghiệp ngành truyền thông. Biết quay dựng video", set()),
        ("Có kinh nghiệm marketing. Biết quay dựng video", {"content_marketing"}),
        ("Có khả năng giao tiếp tiếng Anh", {"english"}),
    ],
)
def test_general_boundaries(matcher, text, expected):
    x = matcher.extract(text)
    assert set(x.skill_codes) == expected
    assert x.status in {"processed_match", "processed_no_match"}
    for e in x.evidence:
        assert text[e.start : e.end] == e.text
        assert 0 <= e.context_start <= e.start < e.end <= e.context_end <= len(text)


def test_cli_general_scope():
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
            "general_industries",
        ]
    )
    assert a.batch == "general_industries"


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
            "job_industry": batch_scope("general_industries")[0],
            "requirements": "Thành thạo AutoCAD và Excel",
        },
        {
            "id": 2,
            "year": 2025,
            "job_industry": batch_scope("general_industries")[0],
            "requirements": "Có bằng B2",
        },
        {
            "id": 3,
            "year": 2026,
            "job_industry": batch_scope("general_industries")[0],
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
            taxonomy_dir=GENERAL_MAPPINGS,
            batch_name="general_industries",
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
    assert len(batch_scope("general_industries")) == 5
