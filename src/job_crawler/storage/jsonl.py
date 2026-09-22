from __future__ import annotations

import gzip
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from job_crawler.models import CrawlError, JobRecord, RunManifest
from job_crawler.storage.checkpoint import Checkpoint
from job_crawler.storage.manifest import ManifestWriter


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BatchPaths:
    root: Path
    jobs: Path
    errors: Path
    manifest: Path
    checkpoint: Path
    html: Path
    screenshots: Path


def make_batch_id(now: datetime) -> str:
    return f"{now:%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"


def batch_paths(output_dir: Path, source: str, snapshot_date: str, batch_id: str) -> BatchPaths:
    root = output_dir / source / f"snapshot_date={snapshot_date}" / f"batch_id={batch_id}"
    return BatchPaths(
        root=root,
        jobs=root / "jobs.jsonl",
        errors=root / "errors.jsonl",
        manifest=root / "manifest.json",
        checkpoint=root / "checkpoint.sqlite3",
        html=root / "html",
        screenshots=root / "screenshots",
    )


def find_latest_resumable(output_dir: Path, source: str) -> Path | None:
    roots = sorted(output_dir.glob(f"{source}/snapshot_date=*/batch_id=*"), reverse=True)
    for root in roots:
        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            status = json.loads(manifest_path.read_text(encoding="utf-8")).get("status")
        except (OSError, json.JSONDecodeError):
            continue
        if status in {"running", "stopped", "failed", "completed_with_errors"}:
            return root
    return None


class BatchStorage:
    def __init__(self, paths: BatchPaths, *, create: bool) -> None:
        self.paths = paths
        if create:
            paths.root.mkdir(parents=True, exist_ok=False)
            paths.jobs.touch()
            paths.errors.touch()
        elif not paths.root.is_dir():
            raise StorageError(f"Resume batch does not exist: {paths.root}")
        self.checkpoint = Checkpoint(paths.checkpoint)
        self.manifest_writer = ManifestWriter(paths.manifest)
        self.existing_job_ids = self._read_existing_job_ids()
        self.checkpoint.sync_completed(self.existing_job_ids)

    @classmethod
    def resume(cls, root: Path) -> BatchStorage:
        paths = BatchPaths(
            root=root,
            jobs=root / "jobs.jsonl",
            errors=root / "errors.jsonl",
            manifest=root / "manifest.json",
            checkpoint=root / "checkpoint.sqlite3",
            html=root / "html",
            screenshots=root / "screenshots",
        )
        return cls(paths, create=False)

    def close(self) -> None:
        self.checkpoint.close()

    def _read_existing_job_ids(self) -> set[str]:
        result: set[str] = set()
        if not self.paths.jobs.exists():
            return result
        with self.paths.jobs.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    job_id = json.loads(line)["source_job_id"]
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    raise StorageError(
                        f"Invalid jobs.jsonl line {line_number}; refusing unsafe resume"
                    ) from exc
                result.add(str(job_id))
        return result

    @staticmethod
    def _append(path: Path, line: str) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    def append_job(self, record: JobRecord) -> bool:
        if record.source_job_id in self.existing_job_ids:
            return False
        self._append(self.paths.jobs, record.model_dump_json())
        self.existing_job_ids.add(record.source_job_id)
        return True

    def append_error(self, error: CrawlError) -> None:
        self._append(self.paths.errors, error.model_dump_json())

    def save_html(self, source_job_id: str, html: str) -> str:
        return self.save_page_html(source_job_id, html)

    def save_page_html(self, name: str, html: str) -> str:
        self.paths.html.mkdir(parents=True, exist_ok=True)
        destination = self.paths.html / f"{name}.html.gz"
        temporary = self.paths.html / f".{name}.html.gz.tmp"
        with gzip.open(temporary, "wt", encoding="utf-8") as handle:
            handle.write(html)
        os.replace(temporary, destination)
        return str(destination.relative_to(self.paths.root))

    def write_manifest(self, manifest: RunManifest) -> None:
        self.manifest_writer.write(manifest)

    def read_manifest(self) -> RunManifest:
        return self.manifest_writer.read()
