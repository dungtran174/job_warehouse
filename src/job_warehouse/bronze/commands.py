"""CLI orchestration and per-attempt local reports, excluding database secrets."""

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
import pyarrow as pa

from job_warehouse.bronze.database import connect_registry
from job_warehouse.bronze.registry import migrate_registry, register_artifact
from job_warehouse.bronze.validation import validate_artifact
from job_warehouse.history.contract import CONTRACT_VERSION, HistoryProfileError


def write_run_report(directory: Path, report: dict[str, object]) -> None:
    temporary = directory / ".run.json.tmp"
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, directory / "run.json")


def run_bronze(args: argparse.Namespace) -> int:
    directory: Path = args.report_dir.absolute()
    try:
        directory.mkdir(parents=True, exist_ok=False)
    except OSError:
        print(
            "Cannot create new report directory; choose a new writable directory", file=sys.stderr
        )
        return 2
    report: dict[str, object] = {
        "report_version": "bronze-run-v1",
        "run_id": str(uuid4()),
        "command": args.bronze_command,
        "started_at": datetime.now(UTC).isoformat(),
        "status": "running",
        "validation_version": CONTRACT_VERSION,
    }
    try:
        write_run_report(directory, report)
        if args.bronze_command == "migrate":
            with connect_registry() as conn:
                applied = migrate_registry(conn)
            report.update(status="succeeded", migration_applied=applied)
        else:
            report.update(
                input_root=str(args.input_root.absolute()), relative_path=args.relative_path
            )
            artifact = validate_artifact(
                args.input_root, args.relative_path, batch_size=args.batch_size
            )
            report.update(
                sha256=artifact.sha256,
                row_count=artifact.row_count,
                byte_size=artifact.byte_size,
                pinned_artifact_verified=True,
            )
            with connect_registry() as conn:
                result = register_artifact(conn, artifact)
            registration = asdict(result)
            registration["ingested_at"] = result.ingested_at.isoformat()
            report.update(status="succeeded", registration=registration)
    except (HistoryProfileError, OSError, psycopg.Error, pa.ArrowException) as exc:
        # libpq errors can contain connection parameters; do not print them or a traceback.
        if isinstance(exc, HistoryProfileError):
            error = str(exc)
        elif isinstance(exc, psycopg.Error):
            error = (
                f"PostgreSQL operation failed ({type(exc).__name__}); check service/configuration"
            )
        elif isinstance(exc, pa.ArrowException):
            error = f"Parquet decoding failed ({type(exc).__name__}); input was not registered"
        else:
            error = "Local file/report operation failed; check paths and permissions"
        report.update(status="failed", error=error)
        print(error, file=sys.stderr)
    report["finished_at"] = datetime.now(UTC).isoformat()
    try:
        write_run_report(directory, report)
    except OSError:
        print(
            "Cannot publish final report; registry may already be committed. "
            "Inspect registry or repeat safely with a new report directory.",
            file=sys.stderr,
        )
        return 2
    print(f"Bronze {args.bronze_command}: {report['status']}; report={directory / 'run.json'}")
    return 0 if report["status"] == "succeeded" else 2
