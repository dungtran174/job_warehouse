from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(slots=True)
class FetcherState:
    requested: str
    active: str
    fallback_used: bool = False
    headless: bool | None = None
    challenge_detected: bool = False


@dataclass(frozen=True, slots=True)
class FetchResponse:
    url: str
    text: str
    status_code: int
    headers: dict[str, str]
    attempt: int
    duration_seconds: float
    fetcher: str
    page_title: str | None = None
    screenshot_path: str | None = None


class FetchError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        url: str,
        attempt: int,
        status_code: int | None = None,
        retryable: bool = False,
        blocked: bool = False,
        terminal: bool = False,
        challenge_type: str | None = None,
        artifact_paths: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.url = url
        self.attempt = attempt
        self.status_code = status_code
        self.retryable = retryable
        self.blocked = blocked
        self.terminal = terminal
        self.challenge_type = challenge_type
        self.artifact_paths = artifact_paths


class Fetcher(Protocol):
    state: FetcherState

    def configure_run(self, batch_root: Path, batch_id: str) -> None: ...

    def get(self, url: str) -> FetchResponse: ...

    def fallback(self, reason: str) -> bool: ...

    def close(self) -> None: ...

    def __enter__(self) -> Fetcher: ...

    def __exit__(self, *_args: object) -> None: ...
