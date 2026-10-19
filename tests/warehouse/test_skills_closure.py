"""Closing pending jobs preserves other results, evidence and deterministic replay."""

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from job_warehouse.history.identity import file_sha256
from job_warehouse.skills.batches import batch_scope
from job_warehouse.skills.closure import close_reviews, resolve_text
from job_warehouse.skills.general import GENERAL_MAPPINGS, GeneralSkillMatcher
from job_warehouse.skills.runner import ARTIFACT_SCHEMAS, load_policy, run_skills
from job_warehouse.skills.taxonomy import load_taxonomy


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Excel khá", {"excel"}),
        ("Tiếng Anh thành thạo", {"english"}),
        ("Có kỹ năng vi tính văn phòng. Không yêu cầu về kỹ năng vi tính văn phòng", {"office_it"}),
        ("Không yêu cầu về kỹ năng vi tính văn phòng", set()),
        ("Giáo viên tiếng Đức, bằng B2, vững ngữ pháp", set()),
        ("Có bằng lái xe B2", {"log_car_driving"}),
        ("Chăm chỉ và trung thực", set()),
        ("Có ý định muốn nâng cao kỹ năng tiếng Trung", set()),
        ("Am hiểu pháp luật quản lý chất lượng", set()),
    ],
)
def test_clear_or_closed_without_review(text, expected):
    matcher = GeneralSkillMatcher(
        load_taxonomy(GENERAL_MAPPINGS),
        load_policy(GENERAL_MAPPINGS, scope=batch_scope("general_industries"))[0],
    )
    x = resolve_text(text, matcher)
    assert set(x.skill_codes) == expected
    assert x.status in {"processed_match", "processed_no_match"}
    assert all(e.context != "ambiguous" for e in x.evidence)


def fixture_runs(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    rows = [
        {"id": i, "year": 2026, "job_industry": "Chưa xác định", "requirements": t}
        for i, t in enumerate(["Biết Python", "Excel khá", "Chăm chỉ, trung thực"], 1)
    ]
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
    baseline = tmp_path / "baseline"
    run_skills(
        source,
        baseline,
        taxonomy_dir=GENERAL_MAPPINGS,
        batch_name="general_industries",
        allow_unpinned_fixture=True,
    )
    for name, schema in ARTIFACT_SCHEMAS.items():
        p = baseline / name
        data = pq.read_table(p).to_pylist()
        if name == "job_skill_status.parquet":
            for r in data:
                if r["job_id"] in {2, 3}:
                    r.update(status="needs_review", positive_skill_count=0, evidence_count=0)
        else:
            data = [r for r in data if r["job_id"] == 1]
        pq.write_table(pa.Table.from_pylist(data, schema=schema), p)
    p = baseline / "manifest.json"
    d = json.loads(p.read_text())
    d["artifacts"] = {n: {"sha256": file_sha256(baseline / n)} for n in ARTIFACT_SCHEMAS}
    p.write_text(json.dumps(d))
    (baseline / "freeze_receipt.json").write_text(
        json.dumps({"run_manifest_sha256": file_sha256(p)})
    )
    return source, baseline


def test_close_preserve_and_replay(tmp_path):
    source, baseline = fixture_runs(tmp_path)
    for name in ["one", "two"]:
        r = close_reviews(source, baseline, tmp_path / name, allow_unpinned_fixture=True)
        assert (
            r["target_jobs"],
            r["jobs_with_new_skills"],
            r["added_pairs"],
            r["pending_review_jobs"],
        ) == (2, 1, 1, 0)
    for n in ARTIFACT_SCHEMAS:
        assert file_sha256(tmp_path / "one" / n) == file_sha256(tmp_path / "two" / n)
    st = pq.read_table(tmp_path / "one/job_skill_status.parquet").to_pylist()
    assert [r["status"] for r in st] == ["processed_match", "processed_match", "processed_no_match"]
    assert st[0] == pq.read_table(baseline / "job_skill_status.parquet").to_pylist()[0]
    pairs = pq.read_table(tmp_path / "one/job_skill_match.parquet").to_pylist()
    assert [(r["job_id"], r["skill_code"]) for r in pairs] == [(1, "python"), (2, "excel")]


def test_closure_rejects_modified_baseline(tmp_path):
    source, baseline = fixture_runs(tmp_path)
    p = baseline / "manifest.json"
    p.write_text(p.read_text() + " ")
    with pytest.raises(ValueError, match="freeze receipt"):
        close_reviews(source, baseline, tmp_path / "bad", allow_unpinned_fixture=True)
