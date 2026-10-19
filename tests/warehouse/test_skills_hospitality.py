"""Bounded hospitality/retail keywords and preservation of source rows."""

import pytest

from job_warehouse.skills.batches import batch_scope
from job_warehouse.skills.hospitality import HOSPITALITY_MAPPINGS, HospitalitySkillMatcher
from job_warehouse.skills.runner import load_policy
from job_warehouse.skills.taxonomy import load_taxonomy


@pytest.fixture
def matcher():
    return HospitalitySkillMatcher(
        load_taxonomy(HOSPITALITY_MAPPINGS),
        load_policy(HOSPITALITY_MAPPINGS, scope=batch_scope("hospitality_retail"))[0],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Có kinh nghiệm nghiệp vụ lễ tân", {"ret_front_desk"}),
        ("Có kinh nghiệm phục vụ bàn", {"ret_table_service"}),
        ("Phục vụ món ăn đúng yêu cầu", {"ret_table_service"}),
        ("Có kinh nghiệm nấu ăn", {"ret_cooking"}),
        ("Có kinh nghiệm pha chế", {"ret_bartending"}),
        ("Yêu thích pha chế", set()),
        ("Đam mê ẩm thực", set()),
        ("Sẽ được đào tạo pha chế", set()),
        ("Có kinh nghiệm buồng phòng", {"ret_housekeeping"}),
        ("Có kinh nghiệm đặt phòng", {"ret_room_reservation"}),
        ("Có kinh nghiệm sử dụng hệ thống đặt phòng", set()),
        ("Thành thạo đặt vé", {"ret_ticketing"}),
        ("Có kinh nghiệm điều hành tour", {"ret_tour_operation"}),
        ("Có thẻ hướng dẫn viên du lịch", {"ret_tour_guiding"}),
        ("Có kinh nghiệm quản lý cửa hàng", {"ret_store_management"}),
        ("Có kinh nghiệm quản lý nhà hàng", {"ret_restaurant_management"}),
        ("Biết sử dụng phần mềm quản lý cửa hàng", set()),
        ("Tốt nghiệp chuyên ngành quản lý nhà hàng", set()),
        ("Biết thu ngân", {"ret_cashiering"}),
        ("Có kiến thức vệ sinh an toàn thực phẩm", {"ret_food_safety"}),
        ("Tuân thủ nội quy vệ sinh an toàn thực phẩm", set()),
        ("Sử dụng thành thạo POS và KiotViet, Sapo", {"ret_pos", "review_kiotviet", "review_sapo"}),
        ("Có kinh nghiệm Opera PMS tại khách sạn", {"ret_opera", "ret_pms"}),
        ("Có kiến thức Opera", set()),
        ("Có kiến thức PMS", set()),
        ("Có kinh nghiệm âm nhạc Opera", set()),
        (
            "Sử dụng hệ thống đặt vé Amadeus, Sabre, Galileo, Abacus",
            {"ret_amadeus", "ret_sabre", "ret_galileo", "ret_abacus"},
        ),
        ("Tuyển dụng nhân viên thu ngân", set()),
        ("Có kinh nghiệm bán hàng tại khách sạn", {"review_ban_hang_sales"}),
        ("Trung thực, nhanh nhẹn, chăm chỉ", set()),
        ("Không yêu cầu biết pha chế", set()),
        ("Degree/College from an accredited university in Hotel and Restaurant Management", set()),
        ("Good experience in a similar position", set()),
        ("Sẽ được cấp thẻ hướng dẫn viên du lịch", set()),
    ],
)
def test_hospitality_boundaries(matcher, text, expected):
    x = matcher.extract(text)
    assert set(x.skill_codes) == expected
    assert x.status in {"processed_match", "processed_no_match"}
    for e in x.evidence:
        assert text[e.start : e.end] == e.text
        assert 0 <= e.context_start <= e.start < e.end <= e.context_end <= len(text)


def test_cli_hospitality_scope():
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
            "hospitality_retail",
        ]
    )
    assert a.batch == "hospitality_retail"


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
            "job_industry": batch_scope("hospitality_retail")[0],
            "requirements": "Thành thạo AutoCAD và Excel",
        },
        {
            "id": 2,
            "year": 2025,
            "job_industry": batch_scope("hospitality_retail")[0],
            "requirements": "Có bằng B2",
        },
        {
            "id": 3,
            "year": 2026,
            "job_industry": batch_scope("hospitality_retail")[0],
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
            taxonomy_dir=HOSPITALITY_MAPPINGS,
            batch_name="hospitality_retail",
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


def test_exact_one_source_label():
    assert len(batch_scope("hospitality_retail")) == 1
