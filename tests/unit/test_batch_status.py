import json
import sqlite3

from job_crawler.storage.status import read_batch_status


def test_status_reads_counts_and_preserves_processing_and_bytes(tmp_path):
    manifest = {
        "batch_id": "test",
        "source": "careerlink",
        "mode": "bounded",
        "start_url": "https://www.careerlink.vn/vieclam/list",
        "status": "running",
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    row = {
        "source_name": "careerlink",
        "source_job_id": "1",
        "job_title": "job",
        "company_name": "company",
        "job_description": "full",
        "candidate_requirements": "full",
    }
    (tmp_path / "jobs.jsonl").write_text(json.dumps(row) + "\n" + json.dumps(row) + '\n{"partial":')
    (tmp_path / "errors.jsonl").write_text("{\n")
    with sqlite3.connect(tmp_path / "checkpoint.sqlite3") as db:
        db.executescript(
            "CREATE TABLE listing_queue(url TEXT,status TEXT);"
            "CREATE TABLE detail_queue(source_job_id TEXT,canonical_url TEXT,status TEXT);"
            "INSERT INTO listing_queue VALUES('page2','pending');"
            "INSERT INTO detail_queue VALUES('2','detail2','processing');"
        )
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = read_batch_status(tmp_path)
    assert result["raw_lines"] == 3 and result["parsed_records"] == 2
    assert result["unique_source_ids"] == result["duplicate_source_ids"] == 1
    assert result["invalid_jsonl_lines"] == [3]
    assert result["queue_counts"]["detail_queue"] == {"processing": 1}
    assert result["pending_listing_urls"] == ["page2"]
    assert not any(result["missing_core_fields"].values())
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
