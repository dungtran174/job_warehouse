from datetime import UTC, datetime, timedelta

from job_crawler.storage.incremental import IncrementalState


def test_incremental_state_tracks_seen_times_hashes_and_never_auto_deactivates(tmp_path) -> None:
    state = IncrementalState(tmp_path / "careerviet" / "incremental_state.sqlite3")
    first = datetime(2026, 9, 22, 10, tzinfo=UTC)
    second = first + timedelta(days=1)

    assert state.observe_discovery("careerviet", "35C00001", seen_at=first, batch_id="batch-1")
    assert not state.observe_discovery("careerviet", "35C00001", seen_at=first, batch_id="batch-1")
    initial = state.get("careerviet", "35C00001")
    assert initial is not None
    assert initial["first_seen_at"] == first.isoformat()
    assert initial["last_seen_at"] == first.isoformat()
    assert initial["seen_count"] == 1
    assert initial["active"] == 1

    assert not state.observe_discovery("careerviet", "35C00001", seen_at=second, batch_id="batch-2")
    assert (
        state.update_content(
            "careerviet",
            "35C00001",
            content_hash="a" * 64,
            fetched_at=second,
        )
        == "new"
    )
    assert (
        state.update_content(
            "careerviet",
            "35C00001",
            content_hash="a" * 64,
            fetched_at=second + timedelta(hours=1),
        )
        == "unchanged"
    )
    assert (
        state.update_content(
            "careerviet",
            "35C00001",
            content_hash="b" * 64,
            fetched_at=second + timedelta(hours=2),
        )
        == "changed"
    )

    updated = state.get("careerviet", "35C00001")
    assert updated is not None
    assert updated["first_seen_at"] == first.isoformat()
    assert updated["last_seen_at"] == second.isoformat()
    assert updated["last_content_hash"] == "b" * 64
    assert updated["last_detail_fetched_at"] == (second + timedelta(hours=2)).isoformat()
    assert updated["seen_count"] == 2
    assert updated["active"] == 1
    state.close()
