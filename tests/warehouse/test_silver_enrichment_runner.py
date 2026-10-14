"""Synthetic S3 publication checks: one row per job, replay, scope and input pin."""

# ruff: noqa: E402
import json

import pytest

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

from job_warehouse.cli import main
from job_warehouse.history.contract import COLUMNS
from job_warehouse.history.identity import file_sha256
from job_warehouse.silver import CORE_VERSION
from job_warehouse.silver.core import normalize_row
from job_warehouse.silver.core_runner import configuration_hashes
from job_warehouse.silver.enrichment import runner
from job_warehouse.silver.enrichment.runner import run_enrichment
from job_warehouse.silver.enrichment.schema import enrichment_schema
from job_warehouse.silver.schema import core_schema


def prepare(tmp_path, titles=None):
    source_hash = "a" * 64
    titles = titles if titles is not None else ["Sales Manager (ERP)"] * 500 + ["Tư Vấn Tuyển Sinh"]
    rows = []
    for i, title in enumerate(titles):
        raw = {
            **dict.fromkeys(COLUMNS, "Synthetic"),
            "id": i + 1,
            "year": 2025,
            "job_title": title,
            "job_industry": (
                "Giáo dục - Đào tạo"
                if title == "Tư Vấn Tuyển Sinh"
                else "IT phần mềm"
                if i % 2
                else "Bán hàng"
            ),
            "location": "Hà Nội; Hồ Chí Minh",
        }
        row, reason = normalize_row(raw, source_hash, i)
        assert not reason
        rows.append(row)
    core = tmp_path / "input.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=core_schema()), core)
    manifest = {
        "artifacts": {"core.parquet": {"sha256": file_sha256(core)}},
        "core_version": CORE_VERSION,
        "asset_hashes": configuration_hashes(),
        "partition": {"core": len(rows), "keys_unique_complete": True},
        "input": {"sha256": source_hash, "rows": len(rows)},
        "source": {"revision": "fixture", "pinned_artifact_verified": False},
        "run_signature": "fixture-core",
    }
    path = tmp_path / "input_manifest.json"
    path.write_text(json.dumps(manifest))
    return core, path


def test_replay_grain_scope_duplicate_sensitivity_and_immutable_input(tmp_path):
    core, manifest = prepare(tmp_path)
    before = core.read_bytes(), manifest.read_bytes()
    a = run_enrichment(core, manifest, tmp_path / "one", batch_size=31, allow_unpinned_fixture=True)
    b = run_enrichment(
        core, manifest, tmp_path / "two", batch_size=101, allow_unpinned_fixture=True
    )
    assert a["run_signature"] == b["run_signature"]
    assert a["content_digest"] == b["content_digest"]
    assert a["partition"] == {"core": 501, "enrichment": 501, "keys_unique_complete": True}
    rows = pq.read_table(tmp_path / "one/enrichment.parquet").to_pylist()
    assert rows == pq.read_table(tmp_path / "two/enrichment.parquet").to_pylist()
    assert all(r["scope_500"] and not r["scope_1000"] for r in rows[:500])
    assert rows[-1]["occupation_primary"] is None
    assert rows[-1]["scope_reason"] == "occupation_unresolved"
    assert all(r["location_places"] == ["HA_NOI", "HO_CHI_MINH"] for r in rows)
    assert "location_clean" not in rows[0]
    assert "location" not in rows[0]
    assert (
        not {
            "location_places_2025",
            "location_labels_2025",
            "location_status_2025",
            "location_crosswalk",
            "boundary_version",
        }
        & rows[0].keys()
    )
    quality = json.loads((tmp_path / "one/quality_report.json").read_text())
    assert quality["scope"]["500"]["records"] == 500
    assert quality["duplicate_candidate_sensitivity"]["extra_candidate_records"] == 498
    assert (core.read_bytes(), manifest.read_bytes()) == before
    assert a["semantic_validation"] == "pending_independent_review"
    for name, info in a["artifacts"].items():
        assert file_sha256(tmp_path / "one" / name) == info["sha256"]


def test_empty_has_typed_parquet_and_complete_zero_grain(tmp_path):
    core, manifest = prepare(tmp_path, [])
    result = run_enrichment(core, manifest, tmp_path / "empty", allow_unpinned_fixture=True)
    assert result["partition"]["enrichment"] == 0
    assert pq.read_schema(tmp_path / "empty/enrichment.parquet").equals(enrichment_schema())


def test_cli_rejects_unpinned_input_and_repo_destination(tmp_path, capsys):
    core, manifest = prepare(tmp_path, ["Developer"])
    assert (
        main(
            [
                "silver",
                "enrich",
                "--core",
                str(core),
                "--core-manifest",
                str(manifest),
                "--output-dir",
                str(tmp_path / "no"),
            ]
        )
        == 2
    )
    assert "pinned historical core" in capsys.readouterr().err
    assert not (tmp_path / "no").exists()
    checkout = tmp_path / "checkout"
    (checkout / "src/job_warehouse").mkdir(parents=True)
    (checkout / "pyproject.toml").touch()
    with pytest.raises(ValueError, match="outside the repository"):
        run_enrichment(core, manifest, checkout / "data/run", allow_unpinned_fixture=True)


@pytest.mark.parametrize(
    "problem",
    ["wrong_sha", "wrong_count", "wrong_key", "duplicate_key", "wrong_schema", "wrong_assets"],
)
def test_bad_core_is_not_published(tmp_path, problem):
    core, manifest = prepare(tmp_path, ["Developer", "Kế toán"])
    info = json.loads(manifest.read_text())
    if problem == "wrong_sha":
        info["artifacts"]["core.parquet"]["sha256"] = "b" * 64
    elif problem == "wrong_count":
        info["partition"]["core"] = 3
    elif problem == "wrong_assets":
        info["asset_hashes"] = {}
    else:
        table = pq.read_table(core)
        rows = table.to_pylist()
        if problem == "wrong_key":
            rows[0]["record_key"] = "b" * 64
        if problem == "duplicate_key":
            rows[1] = rows[0]
        table = pa.Table.from_pylist(rows, schema=core_schema())
        if problem == "wrong_schema":
            table = table.drop(["requirements"])
        pq.write_table(table, core)
        info["artifacts"]["core.parquet"]["sha256"] = file_sha256(core)
    manifest.write_text(json.dumps(info))
    with pytest.raises(ValueError):
        run_enrichment(core, manifest, tmp_path / "failed", allow_unpinned_fixture=True)
    assert not (tmp_path / "failed").exists()
    assert not list(tmp_path.glob(".silver-enrichment-*"))


def test_rerun_cannot_replace_completed_output(tmp_path):
    core, manifest = prepare(tmp_path, ["Developer"])
    run_enrichment(core, manifest, tmp_path / "done", allow_unpinned_fixture=True)
    with pytest.raises(ValueError, match="already exists"):
        run_enrichment(core, manifest, tmp_path / "done", allow_unpinned_fixture=True)


@pytest.mark.parametrize("contents", ["{}", "[]", "null", "{invalid json"])
def test_invalid_manifest_is_a_cli_error_without_a_traceback(tmp_path, capsys, contents):
    core, manifest = prepare(tmp_path, ["Developer"])
    manifest.write_text(contents)
    assert (
        main(
            [
                "silver",
                "enrich",
                "--core",
                str(core),
                "--core-manifest",
                str(manifest),
                "--output-dir",
                str(tmp_path / "no"),
            ]
        )
        == 2
    )
    assert "Invalid S2 core manifest" in capsys.readouterr().err
    assert not (tmp_path / "no").exists()


def test_changed_assets_abort_atomic_publication(tmp_path, monkeypatch):
    core, manifest = prepare(tmp_path, ["Developer"])
    original = runner.configuration_hashes
    calls = 0

    def changed():
        nonlocal calls
        calls += 1
        result = original()
        if calls > 1:
            result["occupations.py"] = "changed-during-run"
        return result

    monkeypatch.setattr(runner, "configuration_hashes", changed)
    with pytest.raises(ValueError, match="changed during enrichment"):
        run_enrichment(core, manifest, tmp_path / "no", allow_unpinned_fixture=True)
    assert not (tmp_path / "no").exists()
    assert not list(tmp_path.glob(".silver-enrichment-*"))
