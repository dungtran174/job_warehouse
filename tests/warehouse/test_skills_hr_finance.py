"""Professional capabilities, benefit exclusions, and separate MISA product scopes."""

import json

import pytest

from job_warehouse.history.identity import file_sha256
from job_warehouse.skills.batches import batch_scope, prepare_batch
from job_warehouse.skills.hr_finance import HR_FINANCE_MAPPINGS, HRFinanceSkillMatcher
from job_warehouse.skills.runner import load_policy, run_skills
from job_warehouse.skills.taxonomy import load_taxonomy


@pytest.fixture
def matcher():
    return HRFinanceSkillMatcher(
        load_taxonomy(HR_FINANCE_MAPPINGS),
        load_policy(HR_FINANCE_MAPPINGS, scope=batch_scope("hr_finance_legal"))[0],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Có kinh nghiệm tuyển dụng và chấm công", {"hr_recruitment", "hr_timekeeping"}),
        ("Tốt nghiệp luật. Có 3 năm kinh nghiệm HCNS", {"hr_personnel_administration"}),
        ("Tốt nghiệp chuyên ngành HCNS", set()),
        (
            "Có kinh nghiệm quản lý HCNS và hiểu biết về luật lao động",
            {"hr_personnel_administration", "review_luat_lao_dong"},
        ),
        ("Công ty có quy mô 500 nhân sự", set()),
        ("Có kinh nghiệm sử dụng phần mềm quản lý nhân sự MISA", {"hr_hrm", "hr_misa"}),
        ("Sử dụng phần mềm kế toán MISA", {"review_phan_mem_ke_toan", "misa"}),
        ("Được đào tạo sử dụng phần mềm quản lý nhân sự MISA", set()),
        ("Tham gia đầy đủ BHXH, BHYT", set()),
        ("Am hiểu BHXH", {"review_bao_hiem_xa_hoi"}),
        (
            "Am hiểu quy trình tuyển dụng, đào tạo và nghiệp vụ nhân sự",
            {"hr_recruitment", "hr_employee_training", "hr_human_resources"},
        ),
        ("Ưu tiên ứng viên định hướng theo mảng Tuyển dụng", set()),
        (
            "Có kiến thức về nghiệp vụ tín dụng và thẩm định tín dụng",
            {"review_nghiep_vu_tin_dung", "finance_credit_assessment"},
        ),
        ("Có kinh nghiệm làm việc tại ngân hàng", set()),
        (
            "Am hiểu luật dân sự, thương mại, doanh nghiệp và đất đai",
            {
                "legal_civil_law",
                "legal_commercial_law",
                "review_luat_doanh_nghiep",
                "legal_land_law",
            },
        ),
        ("Tốt nghiệp chuyên ngành luật dân sự, thương mại", set()),
        ("Có kinh nghiệm trong doanh nghiệp thương mại và xây dựng", set()),
        (
            "Biết soạn thảo và rà soát hợp đồng",
            {"review_soan_thao_hop_dong", "legal_contract_review"},
        ),
        ("Sau thử việc được ký hợp đồng lao động", set()),
        ("Có kinh nghiệm tham gia tố tụng", {"legal_litigation"}),
        ("Am hiểu quy trình tuân thủ", {"legal_compliance"}),
        ("Có tính tuân thủ, trung thực, chăm chỉ", set()),
        ("Kỹ năng tư vấn tài chính", {"finance_consulting"}),
        ("Có kinh nghiệm phân tích báo cáo tài chính", {"review_phan_tich_bao_cao_tai_chinh"}),
        ("Có khả năng phân tích: BCTC", {"review_phan_tich_bao_cao_tai_chinh"}),
        ("Biết kê khai thuế và quyết toán thuế", {"review_ke_khai_thue", "review_quyet_toan_thue"}),
        (
            "Tốt nghiệp chuyên ngành kế toán hoặc có 2 năm kinh nghiệm lĩnh vực kế toán",
            {"review_nghiep_vu_ke_toan"},
        ),
        ("Sử dụng phần mềm ECUS/VNACCS", {"legal_ecus", "legal_vnaccs"}),
        (
            "Thành thạo tin học văn phòng Words, Exel, PP",
            {"office_it", "word", "excel", "powerpoint"},
        ),
        ("Famous words in poetry", set()),
        ("Có kinh nghiệm Oracle", {"review_oracle"}),
        ("Có kinh nghiệm Oracle Database", {"oracle_db"}),
        ("Làm việc tại Oracle", set()),
        ("Tiếng Anh thông thạo là một lợi thế", {"english"}),
        ("Thành thạo Word – Excel", {"word", "excel"}),
        ("Có kinh nghiệm kế toán tổng hợp", {"review_ke_toan_tong_hop"}),
        ("Am hiểu Luật BHXH", {"hr_insurance_law"}),
        ("Am hiểu pháp luật thu hồi nợ", {"legal_debt_recovery_law"}),
        ("Có kinh nghiệm giải quyết tranh chấp ngoài tố tụng", set()),
        ("Có kinh nghiệm tuyển dụng kỹ sư bán hàng", {"hr_recruitment"}),
        ("Có kinh nghiệm soạn thảo hợp đồng bán hàng", {"review_soan_thao_hop_dong"}),
        ("Sử dụng phần mềm chấm công", {"hr_payroll_software"}),
        ("Hiểu biết các phần mềm thống kê", set()),
        ("Sẽ được đào tạo từ đầu. Thành thạo Excel", {"excel"}),
    ],
)
def test_hr_finance_claim_boundaries(matcher, text, expected):
    x = matcher.extract(text)
    assert set(x.skill_codes) == expected
    for e in x.evidence:
        assert text[e.start : e.end] == e.text
        assert 0 <= e.context_start <= e.start < e.end <= e.context_end <= len(text)


def test_cross_clause_alias_does_not_crash_or_join_distinct_claims(matcher):
    x = matcher.extract("Có kinh nghiệm Hành chính – Nhân sự. Thành thạo Excel")
    assert "excel" in x.skill_codes
    assert "hr_personnel_administration" in x.skill_codes
    assert "hr_administration" not in x.skill_codes


def test_sampling_can_exclude_prior_accepted_industry_texts(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    source = tmp_path / "source"
    source.mkdir()
    rows = []
    for i, label in enumerate(batch_scope("hr_finance_legal")):
        for n, text in enumerate(
            ["Known from prior batch", "Unique A " + str(i), "Unique B " + str(i)]
        ):
            rows.append(
                {"id": 1 + i * 3 + n, "year": 2024, "job_industry": label, "requirements": text}
            )
    rows.append(
        {
            "id": 99,
            "year": 2024,
            "job_industry": "Bất động sản",
            "requirements": "Known from prior batch",
        }
    )
    path = source / "jobs_analysis.parquet"
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
        path,
    )
    (source / "manifest.json").write_text(
        json.dumps(
            {
                "source": {"revision": "fixture", "pinned_artifact_verified": False},
                "partition": {"analysis": len(rows)},
                "artifacts": {path.name: {"sha256": file_sha256(path)}},
            }
        )
    )
    out = tmp_path / "samples"
    r = prepare_batch(
        source,
        out,
        batch_name="hr_finance_legal",
        tune_per_industry=1,
        holdout_per_industry=1,
        exclude_industries=("Bất động sản",),
        allow_unpinned_fixture=True,
    )
    assert r["sampling"]["excluded_prior_industries"] == ["Bất động sản"]
    for name in ("tune", "holdout"):
        assert all(
            x["requirements"] != "Known from prior batch"
            for x in json.loads((out / (name + "_unlabelled.json")).read_text())
        )
    first = run_skills(
        source,
        tmp_path / "run_a",
        batch_name="hr_finance_legal",
        taxonomy_dir=HR_FINANCE_MAPPINGS,
        allow_unpinned_fixture=True,
    )
    second = run_skills(
        source,
        tmp_path / "run_b",
        batch_name="hr_finance_legal",
        taxonomy_dir=HR_FINANCE_MAPPINGS,
        allow_unpinned_fixture=True,
    )
    assert first["artifacts"] == second["artifacts"]
    states = pq.read_table(tmp_path / "run_a/job_skill_status.parquet").to_pylist()
    assert states[-1]["status"] == "out_of_scope"


def test_target_industry_cannot_exclude_itself(tmp_path):
    with pytest.raises(ValueError, match="own samples"):
        prepare_batch(
            tmp_path / "absent",
            tmp_path / "out",
            batch_name="hr_finance_legal",
            exclude_industries=(batch_scope("hr_finance_legal")[0],),
        )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Tốt nghiệp đại học. Ngoại ngữ: Tiếng Anh", {"english"}),
        ("Word, Excel tốt", {"word", "excel"}),
        ("Tiếng Trung nghe nói đọc đánh máy khá", {"chinese"}),
        ("Quen thuộc với phần mềm quản trị nguồn nhân lực", {"hr_hrm"}),
        (
            "Có kiến thức về luật lao động, thuế và bảo hiểm",
            {"review_luat_lao_dong", "review_luat_thue", "hr_insurance_law"},
        ),
        ("Thành thạo công cụ phân tích tài chính", set()),
        ("Biết sử dụng hệ thống quản lý đơn hàng", set()),
        ("Có kinh nghiệm làm việc tại công ty thu hồi nợ", set()),
        ("Phối hợp với bộ phận chăm sóc khách hàng", set()),
        ("Công ty có quy mô nhân sự hơn 100", set()),
        ("Kỹ năng Legal writing and drafting", {"legal_drafting"}),
        ("Có khả năng soạn thảo", {"hr_document_drafting"}),
        ("Kỹ năng phân tích số liệu", {"review_phan_tich_du_lieu"}),
        ("Pháp luật liên quan các chế độ chính sách cho người lao động", set()),
        ("Tốt nghiệp Luật. Knowledge: Law", {"legal_legal_knowledge"}),
        ("Được đào tạo phần mềm quản trị nguồn nhân lực", set()),
        ("Tốt nghiệp chuyên ngành phần mềm quản trị nhân sự", set()),
    ],
)
def test_competency_fields_and_domain_exclusions(matcher, text, expected):
    result = matcher.extract(text)
    assert set(result.skill_codes) == expected
    for evidence in result.evidence:
        assert text[evidence.start : evidence.end] == evidence.text
        assert (
            0
            <= evidence.context_start
            <= evidence.start
            < evidence.end
            <= evidence.context_end
            <= len(text)
        )
