from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DEFAULT_TOPCV_START_URL = "https://www.topcv.vn/tim-viec-lam-moi-nhat?type_keyword=1&sba=1"
DEFAULT_CAREERVIET_START_URL = "https://careerviet.vn/viec-lam/tat-ca-viec-lam-vi.html"
DEFAULT_START_URLS = {
    "topcv": DEFAULT_TOPCV_START_URL,
    "careerviet": DEFAULT_CAREERVIET_START_URL,
    "careerlink": "https://www.careerlink.vn/vieclam/tim-kiem-viec-lam",
    "vieclam24h": "https://vieclam24h.vn/tim-kiem-viec-lam-nhanh",
    "timviec365": "https://timviec365.vn/viec-lam",
    "vietnamworks": "https://www.vietnamworks.com/tim-viec-lam/tim-tat-ca-viec-lam",
}
SAMPLE_MAX_PAGES = 2
SAMPLE_MAX_DETAILS = 20
MEDIUM_MAX_PAGES = 5
MEDIUM_MAX_DETAILS = 50
PILOT_MAX_PAGES = 5
PILOT_MAX_DETAILS = 250
PAGE6_CHECK_MAX_PAGES = 6
PAGE6_CHECK_MAX_DETAILS = 300
CAREERLINK_MAX_PAGES = 8
CAREERLINK_MAX_ATTEMPTS = 330
CAREERLINK_MAX_RECORDS = 300


class ConfigError(ValueError):
    """Raised before any request when crawler configuration is unsafe or invalid."""


@dataclass(frozen=True, slots=True)
class CrawlConfig:
    source: str = "topcv"
    mode: Literal["sample", "medium", "pilot", "page6-check", "bounded", "full-snapshot"] = "sample"
    start_url: str = DEFAULT_TOPCV_START_URL
    output_dir: Path = Path("data/raw")
    timeout_seconds: float = 20.0
    delay_min_seconds: float = 1.5
    delay_max_seconds: float = 3.0
    max_retries: int = 3
    max_pages: int | None = SAMPLE_MAX_PAGES
    max_details: int | None = SAMPLE_MAX_DETAILS
    target_records: int | None = None
    user_agent: str = "job-warehouse-crawler/0.1 (+public-research; contact=configure-me)"
    timezone: str = "Asia/Ho_Chi_Minh"
    save_html: bool = False
    log_level: str = "INFO"
    authorization_reference: str | None = None
    project_owner_public_test: bool = False
    confirm_full: bool = False
    resume: bool = False
    resume_batch_id: str | None = None
    fetcher: Literal["auto", "http", "playwright"] = "auto"
    headed: bool = False
    save_screenshot_on_error: bool = False
    browser_wait_ms: int = 1500
    browser_executable_path: str | None = None
    require_complete_content: bool = False

    @classmethod
    def from_environment(cls, **overrides: object) -> CrawlConfig:
        values: dict[str, object] = {
            "output_dir": Path(os.getenv("JOB_CRAWLER_OUTPUT_DIR", "data/raw")),
            "timeout_seconds": float(os.getenv("JOB_CRAWLER_TIMEOUT_SECONDS", "20")),
            "delay_min_seconds": float(os.getenv("JOB_CRAWLER_DELAY_MIN_SECONDS", "1.5")),
            "delay_max_seconds": float(os.getenv("JOB_CRAWLER_DELAY_MAX_SECONDS", "3.0")),
            "max_retries": int(os.getenv("JOB_CRAWLER_MAX_RETRIES", "3")),
            "user_agent": os.getenv(
                "JOB_CRAWLER_USER_AGENT",
                "job-warehouse-crawler/0.1 (+public-research; contact=configure-me)",
            ),
            "log_level": os.getenv("JOB_CRAWLER_LOG_LEVEL", "INFO"),
            "fetcher": os.getenv("JOB_CRAWLER_FETCHER", "auto"),
            "browser_wait_ms": int(os.getenv("JOB_CRAWLER_BROWSER_WAIT_MS", "1500")),
            "browser_executable_path": os.getenv("JOB_CRAWLER_BROWSER_EXECUTABLE_PATH"),
        }
        values.update(overrides)
        return cls(**values)  # type: ignore[arg-type]

    def validate(self) -> None:
        if self.source not in DEFAULT_START_URLS:
            raise ConfigError(f"Unsupported source: {self.source}")
        if self.project_owner_public_test and self.authorization_reference is not None:
            raise ConfigError(
                "Choose one access basis: project-owner public test or source authorization."
            )
        if not self.project_owner_public_test and (
            not self.authorization_reference or not self.authorization_reference.strip()
        ):
            raise ConfigError(
                "Choose an access basis: a genuine source --authorization-reference or "
                "--project-owner-public-test for a bounded public sample."
            )
        if self.source == "timviec365":
            if self.mode not in {"sample", "bounded"} or (
                self.mode == "sample"
                and (self.max_pages != 1 or not self.max_details or self.max_details > 3)
            ):
                raise ConfigError(
                    "Timviec365 supports a 1/3 sample or explicitly bounded collection."
                )
            if self.fetcher != "http" or not self.save_html or not self.require_complete_content:
                raise ConfigError("Timviec365 requires HTTP, saved HTML and complete content.")
            if self.delay_min_seconds < 10 or self.max_retries != 0:
                raise ConfigError("Timviec365 requires delay >= 10 seconds and no automatic retry.")
        if self.source == "careerlink":
            if self.fetcher != "http" or not self.save_html or not self.require_complete_content:
                raise ConfigError("CareerLink requires HTTP, saved HTML and complete content.")
            if self.delay_min_seconds < 3 or self.max_retries != 0:
                raise ConfigError("CareerLink requires delay >= 3 seconds and no automatic retry.")
            if self.mode not in {"sample", "bounded"}:
                raise ConfigError("CareerLink supports sample or explicitly bounded batches only.")
        if self.source == "vieclam24h":
            if self.mode != "bounded" or not self.project_owner_public_test:
                raise ConfigError("Việc Làm 24h supports explicitly owner-bounded batches only.")
            if self.fetcher != "playwright" or not self.headed:
                raise ConfigError("Việc Làm 24h uses an ordinary headed browser chosen upfront.")
            if not self.save_html or not self.require_complete_content:
                raise ConfigError("Việc Làm 24h requires saved HTML and complete detail content.")
            if self.delay_min_seconds < 10 or self.max_retries != 0:
                raise ConfigError("Việc Làm 24h requires delay >= 10 seconds and no retries.")
        if self.source == "vietnamworks" and self.fetcher == "playwright":
            if not self.headed or not self.save_html or not self.require_complete_content:
                raise ConfigError("VietnamWorks browser requires headed, saved HTML, full content.")
            if self.delay_min_seconds < 10 or self.max_retries != 0:
                raise ConfigError("VietnamWorks browser requires delay >= 10 and no retries.")
        if self.mode == "bounded":
            if (
                self.source not in {"careerlink", "timviec365", "vieclam24h", "vietnamworks"}
                or not self.project_owner_public_test
            ):
                raise ConfigError(
                    "Bounded mode is owner-directed "
                    "CareerLink/Timviec365/Việc Làm 24h/VietnamWorks."
                )
            if self.source == "vietnamworks" and self.fetcher != "playwright":
                raise ConfigError(
                    "VietnamWorks bounded collection uses the tested ordinary browser."
                )
            page_limit = {
                "careerlink": CAREERLINK_MAX_PAGES,
                "timviec365": 13,
                "vieclam24h": 12,
                "vietnamworks": 8,
            }[self.source]
            if self.max_pages is None or not 1 <= self.max_pages <= page_limit:
                raise ConfigError(f"Bounded --max-pages must be between 1 and {page_limit}.")
            detail_limit = CAREERLINK_MAX_ATTEMPTS if self.source == "careerlink" else 300
            if self.max_details is None or not 1 <= self.max_details <= detail_limit:
                raise ConfigError(f"Bounded --max-details must be between 1 and {detail_limit}.")
            if (
                self.source == "careerlink"
                and self.max_details > 300
                and self.target_records is None
            ):
                raise ConfigError("CareerLink attempts above 300 require --target-records.")
            if (
                self.source == "careerlink"
                and (self.max_pages > 6 or self.max_details > 300)
                and self.delay_min_seconds < 10
            ):
                raise ConfigError("Extended CareerLink budgets require delay >= 10 seconds.")
        elif self.mode == "sample":
            if self.max_pages is None or not 1 <= self.max_pages <= SAMPLE_MAX_PAGES:
                raise ConfigError("Sample --max-pages must be between 1 and 2.")
            if self.max_details is None or not 1 <= self.max_details <= SAMPLE_MAX_DETAILS:
                raise ConfigError("Sample --max-details must be between 1 and 20.")
            if (
                self.project_owner_public_test
                and self.source not in {"vietnamworks", "careerlink"}
                and (self.max_pages != 1 or self.max_details > 3)
            ):
                raise ConfigError(
                    "Project-owner public test is limited to one listing and three details."
                )
        elif self.project_owner_public_test:
            raise ConfigError("Project-owner public test is available only in sample mode.")
        elif self.mode == "medium":
            if self.max_pages is None or not 1 <= self.max_pages <= MEDIUM_MAX_PAGES:
                raise ConfigError("Medium --max-pages must be between 1 and 5.")
            if self.max_details is None or not 1 <= self.max_details <= MEDIUM_MAX_DETAILS:
                raise ConfigError("Medium --max-details must be between 1 and 50.")
        elif self.mode == "pilot":
            if self.max_pages is None or not 1 <= self.max_pages <= PILOT_MAX_PAGES:
                raise ConfigError("Pilot --max-pages must be between 1 and 5.")
            if self.max_details is None or not 1 <= self.max_details <= PILOT_MAX_DETAILS:
                raise ConfigError("Pilot --max-details must be between 1 and 250.")
        elif self.mode == "page6-check":
            if self.source != "careerviet" or not self.resume or not self.resume_batch_id:
                raise ConfigError(
                    "Page 6 check requires CareerViet and an explicit resume batch ID."
                )
            if (
                self.max_pages != PAGE6_CHECK_MAX_PAGES
                or self.max_details != PAGE6_CHECK_MAX_DETAILS
            ):
                raise ConfigError(
                    "Page 6 check requires exactly 6 cumulative pages and 300 details."
                )
            if self.fetcher != "http" or not self.save_html or not self.require_complete_content:
                raise ConfigError("Page 6 check requires HTTP, saved HTML, and complete content.")
        elif not self.confirm_full:
            raise ConfigError("Full snapshot requires --confirm-full.")
        if self.target_records is not None:
            if self.source != "careerlink" or self.mode != "bounded":
                raise ConfigError("--target-records is supported only for CareerLink bounded mode.")
            if not 1 <= self.target_records <= CAREERLINK_MAX_RECORDS:
                raise ConfigError("CareerLink --target-records must be between 1 and 300.")
        if self.max_pages is not None and self.max_pages < 1:
            raise ConfigError("--max-pages must be positive.")
        if self.max_details is not None and self.max_details < 1:
            raise ConfigError("--max-details must be positive.")
        if self.timeout_seconds <= 0:
            raise ConfigError("Timeout must be positive.")
        if self.delay_min_seconds < 0 or self.delay_max_seconds < self.delay_min_seconds:
            raise ConfigError("Delay range is invalid.")
        if self.max_retries < 0:
            raise ConfigError("Retry count cannot be negative.")
        if self.fetcher not in {"auto", "http", "playwright"}:
            raise ConfigError("--fetcher must be auto, http, or playwright.")
        if (
            self.project_owner_public_test
            and self.fetcher == "playwright"
            and self.source not in {"vieclam24h", "vietnamworks"}
        ):
            raise ConfigError("Project-owner public test must start with HTTP or auto.")
        if self.browser_wait_ms < 0 or self.browser_wait_ms > 10_000:
            raise ConfigError("Browser wait must be between 0 and 10000 milliseconds.")
        if self.fetcher != "playwright" and (
            "configure-me" in self.user_agent or "YOUR_EMAIL" in self.user_agent
        ):
            raise ConfigError("Configure a transparent User-Agent with a real contact address.")
        if self.resume_batch_id is not None:
            if not self.resume:
                raise ConfigError("--resume-batch-id requires --resume.")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", self.resume_batch_id):
                raise ConfigError("--resume-batch-id contains unsafe characters.")
