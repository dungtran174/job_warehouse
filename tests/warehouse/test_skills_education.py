"""Offline education boundaries and preservation of every source job."""

import pytest

from job_warehouse.skills.batches import batch_scope
from job_warehouse.skills.education import EDUCATION_MAPPINGS, EducationSkillMatcher
from job_warehouse.skills.runner import load_policy
from job_warehouse.skills.taxonomy import load_taxonomy


@pytest.fixture
def matcher():
    return EducationSkillMatcher(
        load_taxonomy(EDUCATION_MAPPINGS),
        load_policy(EDUCATION_MAPPINGS, scope=batch_scope("education_language"))[0],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Có kinh nghiệm giảng dạy", {"review_giang_day"}),
        ("Yêu thích công việc giảng dạy", set()),
        ("Sẽ được đào tạo giảng dạy", set()),
        ("Tốt nghiệp ngành sư phạm", set()),
        ("Tốt nghiệp chuyên ngành biên phiên dịch", set()),
        ("Có kinh nghiệm biên phiên dịch", {"review_bien_phien_dich"}),
        ("Có kinh nghiệm biên dịch", {"edu_translation"}),
        ("Có kỹ năng phiên dịch", {"edu_interpreting"}),
        ("Có kiến thức translation and interpretation", {"review_bien_phien_dich"}),
        ("Có kinh nghiệm interpretation of data", set()),
        ("Soạn giáo án điện tử", {"edu_lesson_planning"}),
        ("Có kỹ năng quản lý lớp học", {"edu_classroom_management"}),
        ("Có kinh nghiệm tư vấn tuyển sinh", {"edu_admissions_counselling"}),
        ("Sử dụng công cụ giảng dạy Zoom", {"edu_zoom"}),
        (
            "Sử dụng công cụ dịch thuật Trados, memoQ, Wordfast",
            {"edu_trados", "edu_memoq", "edu_wordfast"},
        ),
        ("Có chứng chỉ TESOL", {"review_giang_day"}),
        ("Có chứng chỉ CELTA hoặc TEFL", {"review_giang_day"}),
        ("Sẽ được cấp chứng chỉ TESOL", set()),
        ("Có chứng chỉ IELTS 7.5", {"english"}),
        ("Có chứng chỉ HSK 6", {"chinese"}),
        ("Có chứng chỉ JLPT N2", {"japanese"}),
        ("Tốt nghiệp chuyên ngành tiếng Anh", set()),
        ("Có kinh nghiệm làm việc tại trung tâm Anh ngữ", set()),
        ("Có kinh nghiệm CSKH tại Trung tâm Tiếng Anh", {"review_cham_soc_khach_hang"}),
        ("Giao tiếp tiếng Anh thành thạo", {"english"}),
        (
            "Thành thạo Zoom, Google Meet và Google Classroom",
            {"edu_zoom", "edu_google_meet", "edu_google_classroom"},
        ),
        ("Biết sử dụng Moodle và LMS", {"edu_moodle", "edu_lms"}),
        ("Có kinh nghiệm sử dụng camera zoom", set()),
        ("Trung thực, giao tiếp tốt, yêu trẻ", set()),
        ("Không yêu cầu biết Zoom", set()),
        (
            "Có kinh nghiệm giảng dạy. [Lưu ý]: Công ty thu thập và lưu trữ thông tin ứng viên",
            {"review_giang_day"},
        ),
        (
            "Có kinh nghiệm giảng dạy. [Lưu ý]: Yêu cầu có kỹ năng quản lý lớp học",
            {"review_giang_day", "edu_classroom_management"},
        ),
    ],
)
def test_education_boundaries(matcher, text, expected):
    x = matcher.extract(text)
    assert set(x.skill_codes) == expected
    assert x.status in {"processed_match", "processed_no_match"}
    for e in x.evidence:
        assert text[e.start : e.end] == e.text
        assert 0 <= e.context_start <= e.start < e.end <= e.context_end <= len(text)


def test_cli_education_scope():
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
            "education_language",
        ]
    )
    assert a.batch == "education_language"


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
            "job_industry": batch_scope("education_language")[0],
            "requirements": "Thành thạo AutoCAD và Excel",
        },
        {
            "id": 2,
            "year": 2025,
            "job_industry": batch_scope("education_language")[1],
            "requirements": "Có bằng B2",
        },
        {
            "id": 3,
            "year": 2026,
            "job_industry": batch_scope("education_language")[1],
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
            taxonomy_dir=EDUCATION_MAPPINGS,
            batch_name="education_language",
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
    assert len(batch_scope("education_language")) == 3
