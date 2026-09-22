import json
from datetime import UTC, date, datetime

from job_crawler.models import DiscoveredJob, JobRecord
from job_crawler.storage.jsonl import BatchStorage, batch_paths


def test_resume_syncs_jsonl_before_checkpoint_to_avoid_duplicates(tmp_path) -> None:
    paths = batch_paths(tmp_path, "topcv", "2026-09-22", "batch-test")
    storage = BatchStorage(paths, create=True)
    job = DiscoveredJob(
        source_job_id="1001",
        source_url="https://www.topcv.vn/viec-lam/a/1001.html",
        canonical_url="https://www.topcv.vn/viec-lam/a/1001.html",
        listing_url="https://www.topcv.vn/jobs",
    )
    storage.checkpoint.enqueue_detail(job)
    record = JobRecord(
        source_name="topcv",
        source_job_id="1001",
        source_url=job.source_url,
        canonical_url=job.canonical_url,
        listing_url=job.listing_url,
        crawled_at=datetime(2026, 9, 22, tzinfo=UTC),
        snapshot_date=date(2026, 9, 22),
        batch_id="batch-test",
        schema_version="1.0.0",
        parser_version="topcv-1.0.0",
        content_hash="a" * 64,
        job_title="Example",
    )
    assert storage.append_job(record)
    storage.close()  # simulate a crash before mark_completed

    resumed = BatchStorage.resume(paths.root)
    assert resumed.checkpoint.is_completed("1001")
    assert resumed.checkpoint.next_detail() is None
    assert not resumed.append_job(record)
    lines = [json.loads(line) for line in paths.jobs.read_text().splitlines()]
    assert [line["source_job_id"] for line in lines] == ["1001"]
    resumed.close()
