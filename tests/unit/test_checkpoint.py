import json
from datetime import UTC, date, datetime

import pytest

from job_crawler.models import DiscoveredJob, JobRecord
from job_crawler.storage.jsonl import BatchStorage, batch_paths


@pytest.mark.parametrize(
    ("source", "job_id", "url", "parser_version"),
    [
        (
            "topcv",
            "1001",
            "https://www.topcv.vn/viec-lam/a/1001.html",
            "topcv-1.0.0",
        ),
        (
            "careerviet",
            "35C00001",
            "https://careerviet.vn/vi/tim-viec-lam/a.35C00001.html",
            "careerviet-1.1.0",
        ),
    ],
)
def test_resume_syncs_jsonl_before_checkpoint_to_avoid_duplicates(
    tmp_path, source: str, job_id: str, url: str, parser_version: str
) -> None:
    paths = batch_paths(tmp_path, source, "2026-09-22", "batch-test")
    storage = BatchStorage(paths, create=True)
    job = DiscoveredJob(
        source_name=source,
        source_job_id=job_id,
        source_url=url,
        canonical_url=url,
        listing_url="https://example.invalid/jobs",
    )
    storage.checkpoint.enqueue_detail(job)
    record = JobRecord(
        source_name=source,
        source_job_id=job_id,
        source_url=job.source_url,
        canonical_url=job.canonical_url,
        listing_url=job.listing_url,
        crawled_at=datetime(2026, 9, 22, tzinfo=UTC),
        snapshot_date=date(2026, 9, 22),
        batch_id="batch-test",
        schema_version="1.0.0",
        parser_version=parser_version,
        content_hash="a" * 64,
        job_title="Example",
    )
    assert storage.append_job(record)
    storage.close()  # simulate a crash before mark_completed

    resumed = BatchStorage.resume(paths.root)
    assert resumed.checkpoint.is_completed(job_id)
    assert resumed.checkpoint.next_detail() is None
    assert not resumed.append_job(record)
    lines = [json.loads(line) for line in paths.jobs.read_text().splitlines()]
    assert [line["source_job_id"] for line in lines] == [job_id]
    resumed.close()


def test_resume_repairs_and_preserves_a_partial_final_jsonl_line(tmp_path) -> None:
    paths = batch_paths(tmp_path, "careerviet", "2026-09-22", "batch-partial")
    storage = BatchStorage(paths, create=True)
    record = JobRecord(
        source_name="careerviet",
        source_job_id="35C00001",
        source_url="https://careerviet.vn/vi/tim-viec-lam/a.35C00001.html",
        canonical_url="https://careerviet.vn/vi/tim-viec-lam/a.35C00001.html",
        listing_url="https://careerviet.vn/jobs",
        crawled_at=datetime(2026, 9, 22, tzinfo=UTC),
        snapshot_date=date(2026, 9, 22),
        batch_id="batch-partial",
        schema_version="1.0.0",
        parser_version="careerviet-1.1.0",
        content_hash="a" * 64,
        job_title="Example",
    )
    assert storage.append_job(record)
    storage.close()
    with paths.jobs.open("ab") as handle:
        handle.write(b'{"source_job_id":"incomplete')

    resumed = BatchStorage.resume(paths.root)
    lines = [json.loads(line) for line in paths.jobs.read_text().splitlines()]
    assert [line["source_job_id"] for line in lines] == ["35C00001"]
    assert paths.jobs.with_name("jobs.jsonl.partial").read_bytes().startswith(b'{"source_job_id"')
    resumed.close()
