from __future__ import annotations

import json
import os
from pathlib import Path

from job_crawler.models import RunManifest


class ManifestWriter:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, manifest: RunManifest) -> None:
        temporary = self.path.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(manifest.model_dump(mode="json"), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)

    def read(self) -> RunManifest:
        return RunManifest.model_validate_json(self.path.read_text(encoding="utf-8"))
