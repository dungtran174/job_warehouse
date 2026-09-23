import json
import sqlite3
from datetime import UTC, date, datetime

import pytest

from job_crawler.models import DiscoveredJob, JobRecord
from job_crawler.storage.checkpoint import Checkpoint, CheckpointConflict
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


def test_listing_enqueue_rolls_back_if_completion_fails(tmp_path) -> None:
    checkpoint = Checkpoint(tmp_path / "checkpoint.sqlite3")
    listing_url = "https://careerviet.vn/viec-lam/tat-ca-viec-lam-vi.html"
    checkpoint.enqueue_listing(listing_url)
    assert checkpoint.next_listing() == listing_url
    jobs = [
        DiscoveredJob(
            source_name="careerviet",
            source_job_id=f"35C{number:05X}",
            source_url=f"https://careerviet.vn/vi/tim-viec-lam/test.35C{number:05X}.html",
            canonical_url=f"https://careerviet.vn/vi/tim-viec-lam/test.35C{number:05X}.html",
            listing_url=listing_url,
        )
        for number in (1, 2)
    ]
    checkpoint.connection.execute(
        "CREATE TEMP TRIGGER fail_completion BEFORE UPDATE OF status ON listing_queue "
        "WHEN NEW.status = 'completed' BEGIN SELECT RAISE(ABORT, 'interrupted'); END"
    )
    with pytest.raises(sqlite3.IntegrityError):
        checkpoint.commit_listing_page(listing_url, "fingerprint", jobs)
    assert checkpoint.count_details() == 0
    assert (
        checkpoint.connection.execute("SELECT count(*) FROM page_fingerprints").fetchone()[0] == 0
    )
    assert (
        checkpoint.connection.execute(
            "SELECT status FROM listing_queue WHERE url = ?", (listing_url,)
        ).fetchone()[0]
        == "processing"
    )
    checkpoint.close()

    resumed = Checkpoint(tmp_path / "checkpoint.sqlite3")
    assert resumed.next_listing() == listing_url
    assert resumed.commit_listing_page(listing_url, "fingerprint", jobs) == (2, 0)
    assert resumed.count_details() == 2
    assert (
        resumed.connection.execute(
            "SELECT status FROM listing_queue WHERE url = ?", (listing_url,)
        ).fetchone()[0]
        == "completed"
    )
    second_listing = "https://careerviet.vn/viec-lam/tat-ca-viec-lam-trang-2-vi.html"
    assert resumed.enqueue_listing(second_listing)
    assert resumed.next_listing() == second_listing
    conflicting = jobs[0].model_copy(
        update={
            "canonical_url": "https://careerviet.vn/vi/tim-viec-lam/different.35C00001.html",
            "listing_url": second_listing,
        }
    )
    with pytest.raises(CheckpointConflict, match="Conflicting mapping"):
        resumed.commit_listing_page(second_listing, "fingerprint-2", [conflicting])
    assert resumed.count_details() == 2
    assert resumed.connection.execute("SELECT count(*) FROM page_fingerprints").fetchone()[0] == 1
    assert (
        resumed.connection.execute(
            "SELECT status FROM listing_queue WHERE url = ?", (second_listing,)
        ).fetchone()[0]
        == "processing"
    )
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
