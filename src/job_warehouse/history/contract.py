"""Versioned contract for historical input, without inferred website identity."""

CONTRACT_VERSION = "history-input-v1"
DATASET_NAME = "tinixai/vietnamese-job-descriptions"
REVISION = "679c3a17347ff6ce769d9bf510c122a087493cf6"
SOURCE_URL = f"https://huggingface.co/datasets/{DATASET_NAME}"
ARTIFACT_URL = f"{SOURCE_URL}/resolve/{REVISION}/data.parquet"
LICENSE_ID = "CC-BY-NC-4.0"
ATTRIBUTION = "TiniX AI (Tinixai), Vietnamese Job Descriptions"
EXPECTED_SHA256 = "4d5e11b58490edc40900386986de71e844cd9f0f3a5fc714418747f66462f834"
EXPECTED_ROWS = 606_878
YEARS = frozenset(range(2022, 2027))
DEFAULT_MIN_INDUSTRY_RECORDS = 500

COLUMNS = (
    "id",
    "job_title",
    "company_name",
    "salary",
    "location",
    "job_type",
    "job_industry",
    "experience_level",
    "education_level",
    "job_position",
    "job_description",
    "benefits",
    "requirements",
    "year",
)
CONTENT_COLUMNS = tuple(column for column in COLUMNS if column != "id")
LONG_TEXT_COLUMNS = frozenset({"job_description", "benefits", "requirements"})
VALUE_COUNT_COLUMNS = (
    "salary",
    "job_type",
    "job_industry",
    "experience_level",
    "education_level",
    "job_position",
    "year",
)
# Count these literals; never replace them or equate them with physical nulls.
SENTINELS = frozenset(
    value.casefold()
    for value in (
        "Không",
        "Chưa xác định",
        "Chưa cập nhật",
        "Đang cập nhật",
        "Khác",
        "Nghề nghiệp khác",
    )
)


class HistoryProfileError(ValueError):
    """Input or report publication failed; no completed report is published."""
