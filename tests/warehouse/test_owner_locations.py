"""Owner workbook joins every repeated address without changing raw/grain."""

import json
import zipfile
from xml.sax.saxutils import escape

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from job_warehouse.history.identity import file_sha256
from job_warehouse.silver.enrichment.owner_locations import apply_owner_mapping, read_mapping


def workbook(path, mapped, unknown):
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    names = '<sheets><sheet name="Toàn bộ 13614"/><sheet name="Chưa xác định 197"/></sheets>'
    header = ["record_count", "example_source_dataset_id", "location_raw", "tinh_thanh_pho"]
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", f"<workbook {ns}>{names}</workbook>")
        for i, rows in enumerate([mapped, unknown], 1):
            content = ""
            for index, values in enumerate([header, *rows], 1):
                cells = "".join(
                    f'<c r="{col}{index}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>'
                    for col, v in zip("ABCD", values, strict=True)
                )
                content += f"<row>{cells}</row>"
            z.writestr(
                f"xl/worksheets/sheet{i}.xml",
                f"<worksheet {ns}><sheetData>{content}</sheetData></worksheet>",
            )


def fixture_run(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    source = [
        {"record_key": str(i), "source_dataset_id": i, "location": raw}
        for i, raw in enumerate(["specific street", "specific street", "0107782409", "Hà Nội"], 1)
    ]
    core = tmp_path / "core.parquet"
    pq.write_table(pa.Table.from_pylist(source), core)
    rows = [
        {
            "record_key": s["record_key"],
            "occupation_primary": "SALES",
            "year_value": 2022,
            "location_places": ["HA_NOI"] if s["location"] == "Hà Nội" else [],
            "location_status": "mapped_single" if s["location"] == "Hà Nội" else "unmapped",
            "location_group": "Hà Nội" if s["location"] == "Hà Nội" else "Chưa xác định",
            "location_flags": [],
            "location_version": "fixture",
            "enrichment_version": "fixture",
        }
        for s in source
    ]
    table = pa.Table.from_pylist(rows)
    table = table.set_column(
        table.schema.get_field_index("location_flags"),
        "location_flags",
        pa.array([r["location_flags"] for r in rows], type=pa.list_(pa.string())),
    )
    pq.write_table(table, base / "enrichment.parquet")
    manifest = {
        "input": {"path": str(core), "sha256": file_sha256(core)},
        "artifacts": {"enrichment.parquet": {"sha256": file_sha256(base / "enrichment.parquet")}},
        "partition": {"enrichment": 4},
        "source": {"revision": "fixture"},
        "location_version": "fixture",
        "taxonomy_version": "fixture",
    }
    (base / "manifest.json").write_text(json.dumps(manifest))
    return base, core, rows


def test_exact_owner_join_all_repeats_and_unknown_provenance(tmp_path):
    base, core, old = fixture_run(tmp_path)
    xlsx = tmp_path / "input.xlsx"
    missing = [1, 3, "0107782409", "0107782409"]
    workbook(xlsx, [[2, 1, "specific street", "Bình Dương"], missing], [missing])
    hashes = [file_sha256(p) for p in [xlsx, core, base / "enrichment.parquet"]]
    report = apply_owner_mapping(base, xlsx, tmp_path / "out")
    assert report["matched_records"] == 3
    assert report["unresolved_strings"] == report["unresolved_records"] == 1
    actual = pq.read_table(tmp_path / "out/enrichment.parquet").to_pylist()
    assert [r["location"] for r in actual] == [
        "Bình Dương",
        "Bình Dương",
        "Chưa xác định",
        "Hà Nội",
    ]
    assert [r["record_key"] for r in actual] == [r["record_key"] for r in old]
    assert all(r["occupation_primary"] == "SALES" and r["year_value"] == 2022 for r in actual)
    assert actual[0]["location_mapping_row"] == actual[1]["location_mapping_row"] == 2
    assert actual[2]["location_places"] == [] and actual[2]["location_status"] == "unknown"
    assert actual[3]["location_mapping_method"] == "source_extractor"
    assert [file_sha256(p) for p in [xlsx, core, base / "enrichment.parquet"]] == hashes
    assert file_sha256(tmp_path / "out/owner_locations.xlsx") == hashes[0]


@pytest.mark.parametrize("problem", ["count", "missing", "extra", "example"])
def test_population_mismatch_aborts_publication(tmp_path, problem):
    base, _, _ = fixture_run(tmp_path)
    xlsx = tmp_path / "input.xlsx"
    missing = [1, 3, "0107782409", "0107782409"]
    row = [2, 1, "specific street", "Hồ Chí Minh"]
    if problem == "count":
        row[0] = 1
    if problem == "example":
        row[1] = 999
    mapped = [row, missing] if problem != "missing" else [row]
    if problem == "extra":
        mapped.append([1, 999, "absent address", "Hà Nội"])
    workbook(xlsx, mapped, [missing] if problem != "missing" else [])
    with pytest.raises(ValueError):
        apply_owner_mapping(base, xlsx, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("problem", ["duplicate", "invalid_label", "unknown_sheet_mismatch"])
def test_mapping_validation(tmp_path, problem):
    row = [1, 1, "address", "Hà Nội"]
    mapped, unknown = [row], []
    if problem == "duplicate":
        mapped.append(row)
    if problem == "invalid_label":
        row[3] = "not a province"
    if problem == "unknown_sheet_mismatch":
        unknown = [[2, 1, "address", "Hà Nội"]]
    workbook(tmp_path / "input.xlsx", mapped, unknown)
    with pytest.raises(ValueError):
        read_mapping(tmp_path / "input.xlsx")
