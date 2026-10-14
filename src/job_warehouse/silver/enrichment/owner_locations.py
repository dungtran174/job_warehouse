"""Apply owner-supplied XLSX locations to a verified S3 run, outside Git.

The workbook is data only. Formulas are rejected and external links/macros are
never evaluated. Exact raw addresses are keys; example IDs are not join keys.
"""

import csv
import json
import os
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import zip_longest
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from job_warehouse.history.identity import file_sha256
from job_warehouse.silver.enrichment.assets import configuration_hashes
from job_warehouse.silver.enrichment.locations import places

VERSION = "owner-location-map-v1"
PIPELINE_VERSION = "silver-enrichment-v20"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
HEADERS = ["record_count", "example_source_dataset_id", "location_raw", "tinh_thanh_pho"]


@dataclass(frozen=True)
class Assignment:
    count: int
    example_id: int
    label: str
    code: str | None
    excel_row: int


def _sheet(z: zipfile.ZipFile, path: str, shared: list[str]) -> list[list[str]]:
    if z.getinfo(path).file_size > 50_000_000:
        raise ValueError("Worksheet too large")
    result = []
    for row in ET.fromstring(z.read(path)).findall("s:sheetData/s:row", NS):
        values = dict.fromkeys("ABCD", "")
        for cell in row.findall("s:c", NS):
            if cell.find("s:f", NS) is not None:
                raise ValueError("Mapping formulas are not supported")
            column = re.sub(r"\d+$", "", cell.attrib["r"])
            v = cell.find("s:v", NS)
            value = v.text or "" if v is not None else ""
            if cell.get("t") == "inlineStr":
                value = "".join(t.text or "" for t in cell.findall(".//s:t", NS))
            elif cell.get("t") == "s":
                value = shared[int(value)]
            if column not in values:
                if value:
                    raise ValueError("Unexpected mapping column")
            else:
                values[column] = value
        result.append(list(values.values()))
    if not result or result[0] != HEADERS:
        raise ValueError("Unexpected mapping headers")
    return result[1:]


def read_mapping(path: Path) -> dict[str, Assignment]:
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            shared = [
                "".join(t.text or "" for t in item.findall(".//s:t", NS))
                for item in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("s:si", NS)
            ]
        names = [
            e.attrib["name"]
            for e in ET.fromstring(z.read("xl/workbook.xml")).findall("s:sheets/s:sheet", NS)
        ]
        if names != ["Toàn bộ 13614", "Chưa xác định 197"]:
            raise ValueError("Expected the complete mapping and unresolved worksheets")
        all_rows = _sheet(z, "xl/worksheets/sheet1.xml", shared)
        unknown_rows = _sheet(z, "xl/worksheets/sheet2.xml", shared)
    unresolved = {row[2]: row for row in unknown_rows}
    if len(unresolved) != len(unknown_rows):
        raise ValueError("Duplicate unresolved raw address")
    labels = {label: code for code, label in places().items()}
    result = {}
    for row_index, row in enumerate(all_rows, 2):
        count, example, raw, label = row
        if not raw or raw in result or not count.isdecimal() or int(count) <= 0:
            raise ValueError("Duplicate/empty raw address or invalid record count")
        if not example.isdecimal():
            raise ValueError("Invalid example dataset ID")
        if raw in unresolved:
            if row != unresolved[raw]:
                raise ValueError("Unresolved sheet differs from complete mapping")
            code, display = None, "Chưa xác định"
        else:
            if label not in labels:
                raise ValueError(f"Unknown province label: {label}")
            code, display = labels[label], label
        result[raw] = Assignment(int(count), int(example), display, code, row_index)
    if not set(unresolved) <= set(result):
        raise ValueError("Unresolved address absent from complete mapping")
    return result


def _rows(path: Path, columns: list[str] | None = None) -> Any:
    for batch in pq.ParquetFile(path).iter_batches(batch_size=4096, columns=columns):
        yield from batch.to_pylist()


def apply_owner_mapping(base_run: Path, workbook: Path, output_dir: Path) -> dict[str, Any]:
    destination = output_dir.resolve()
    if destination.exists():
        raise ValueError("Choose a new output directory")
    if any((p / "src/job_warehouse").is_dir() for p in (destination, *destination.parents)):
        raise ValueError("Output must be outside the repository")
    manifest_path = base_run / "manifest.json"
    base = json.loads(manifest_path.read_text())
    core = Path(base["input"]["path"])
    base_parquet = base_run / "enrichment.parquet"
    hashes = {p: file_sha256(p) for p in [manifest_path, core, base_parquet, workbook]}
    if hashes[core] != base["input"]["sha256"]:
        raise ValueError("Core SHA differs from base manifest")
    if hashes[base_parquet] != base["artifacts"]["enrichment.parquet"]["sha256"]:
        raise ValueError("Base enrichment SHA mismatch")
    mapping = read_mapping(workbook)
    schema = pq.read_schema(base_parquet)
    if "location" in schema.names:
        raise ValueError("Base run already has a location display column")
    schema = schema.append(pa.field("location", pa.string(), nullable=False))
    schema = schema.append(pa.field("location_mapping_method", pa.string(), nullable=False))
    schema = schema.append(pa.field("location_mapping_row", pa.int32()))
    counts: Counter[str] = Counter()
    matched: Counter[str] = Counter()
    examples: dict[str, set[int]] = {}
    seen: set[str] = set()
    labels = places()
    assets = configuration_hashes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".owner-locations-", dir=destination.parent) as tmp:
        stage = Path(tmp)
        with pq.ParquetWriter(stage / "enrichment.parquet", schema) as writer:
            pending = []
            for old, source in zip_longest(
                _rows(base_parquet), _rows(core, ["record_key", "source_dataset_id", "location"])
            ):
                if old is None or source is None or old["record_key"] != source["record_key"]:
                    raise ValueError("Base/core order or row count mismatch")
                if old["record_key"] in seen:
                    raise ValueError("Duplicate record key")
                seen.add(old["record_key"])
                raw = source["location"]
                assignment = mapping.get(raw)
                old["location_mapping_row"] = None
                old["location_mapping_method"] = "source_extractor"
                if assignment is not None:
                    if old["location_status"] != "unmapped":
                        raise ValueError("Owner mapping would replace an already resolved record")
                    matched[raw] += 1
                    examples.setdefault(raw, set()).add(source["source_dataset_id"])
                    old["location_places"] = [assignment.code] if assignment.code else []
                    old["location_status"] = "mapped_single" if assignment.code else "unknown"
                    old["location_group"] = assignment.label
                    old["location_flags"] = sorted(
                        set(old["location_flags"]) | {"owner_excel_mapping"}
                    )
                    old["location_mapping_row"] = assignment.excel_row
                    old["location_mapping_method"] = "owner_excel"
                elif old["location_status"] == "unmapped":
                    raise ValueError("Workbook does not cover every base unmapped record")
                old["location"] = (
                    "; ".join(labels[c] for c in old["location_places"])
                    if old["location_places"]
                    else old["location_group"]
                )
                old["enrichment_version"] = PIPELINE_VERSION
                old["location_version"] = base["location_version"] + "+" + VERSION
                counts[old["location_status"]] += 1
                pending.append(old)
                if len(pending) == 4096:
                    writer.write_table(pa.Table.from_pylist(pending, schema=schema))
                    pending.clear()
            if pending:
                writer.write_table(pa.Table.from_pylist(pending, schema=schema))
        if set(matched) != set(mapping) or any(
            matched[raw] != item.count or item.example_id not in examples[raw]
            for raw, item in mapping.items()
        ):
            raise ValueError(
                "Workbook raw addresses/counts/example IDs differ from base population"
            )
        if len(seen) != base["partition"]["enrichment"]:
            raise ValueError("Base manifest row count mismatch")
        if (
            any(file_sha256(p) != sha for p, sha in hashes.items())
            or assets != configuration_hashes()
        ):
            raise ValueError("Input or code changed during mapping")
        shutil.copyfile(workbook, stage / "owner_locations.xlsx")
        with (stage / "mapping_import.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["location_raw", "location", "record_count", "excel_row"])
            w.writerows(
                (raw, item.label, item.count, item.excel_row) for raw, item in mapping.items()
            )
        report = {
            "rows": len(seen),
            "mapped_raw_strings": len(mapping),
            "matched_records": sum(matched.values()),
            "unresolved_strings": sum(item.code is None for item in mapping.values()),
            "unresolved_records": sum(item.count for item in mapping.values() if item.code is None),
            "status_counts": dict(counts),
            "other_fields_policy": "occupation/year/identity unchanged",
            "mapping_validation": "Owner supplied labels; reconciliation, "
            "not independent geographic validation",
        }
        (stage / "quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        result = {
            "status": "owner_mapping_applied_not_db_published",
            "created_at": datetime.now(UTC).isoformat(),
            "enrichment_version": PIPELINE_VERSION,
            "location_version": base["location_version"] + "+" + VERSION,
            "taxonomy_version": base["taxonomy_version"],
            "base_manifest": str(manifest_path.resolve()),
            "input_hashes": {str(p.resolve()): sha for p, sha in hashes.items()},
            "source": base["source"],
            "partition": base["partition"],
            "asset_hashes": assets,
            "semantic_validation": "owner_supplied_mapping_not_independent_AI_gate",
            "artifacts": {
                p.name: {"sha256": file_sha256(p), "bytes": p.stat().st_size}
                for p in stage.iterdir()
            },
        }
        (stage / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        if destination.exists():
            raise ValueError("Output appeared during processing")
        os.rename(stage, destination)
    return report
